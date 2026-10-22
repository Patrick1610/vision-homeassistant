"""Small transactional local history; never a Recorder replica."""

import asyncio
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

from .evidence import fingerprint

SCHEMA_VERSION = 11
AI_MAX_REQUESTS = 512
AI_MAX_STORAGE_BYTES = 64 * 1024 * 1024
AI_RESULT_RESERVE_BYTES = 1024 * 1024
CASE_NOTES_PER_CASE = 50
DETAIL_BYTES_PER_ENTITY = 256 * 1024
DETAIL_BYTES_TOTAL = 8 * 1024 * 1024
DETAILED_RUNS_PER_ENTITY = 8
MAX_SNAPSHOTS_PER_VERSION = 3
MAX_SNAPSHOT_BYTES = 1024 * 1024 * 1024
SNAPSHOT_FREE_RESERVE = 16 * 1024 * 1024
STORAGE_FAILURES = {
    "unsupported_preview_schema": (
        "Unsupported unpublished device schema; preserve the private data volume and backups. "
        "With Vision stopped, use a compatible preview or restore a compatible backup copy. "
        "Do not delete history or tables"
    ),
    "snapshot_space": "Insufficient space for migration snapshot; free private volume space",
    "snapshot_budget": "Migration snapshot budget reached; review backups with Vision stopped",
    "snapshot_invalid": "Migration snapshot validation failed; preserve the private data volume",
    "snapshot_pending": (
        "Unfinished migration snapshot: stop Vision, preserve /data, inspect "
        "vision.db.backup-* and their -journal/-wal/-shm sidecars before restarting"
    ),
    "snapshot_too_large": (
        "Database exceeds migration snapshot size limit; preserve /data and review storage policy"
    ),
    "storage_busy": "Storage startup lock timed out; stop competing Vision processes and retry",
    "snapshot_source": (
        "Migration snapshot source could not be opened read-only; preserve /data and check access"
    ),
}


class StorageStartupError(RuntimeError):
    """Only these fixed safe categories may cross the app's startup-error boundary."""

    def __init__(self, code):
        self.code = code
        super().__init__(STORAGE_FAILURES[code])


MIGRATIONS = {
    # Frozen migrations are never edited after publication. Add another version.
    1: (
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS availability (id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, "
        "state TEXT NOT NULL, started REAL NOT NULL, ended REAL, "
        "uncertain INTEGER NOT NULL DEFAULT 0)",
        "CREATE INDEX IF NOT EXISTS availability_entity ON availability(entity_id, started)",
        "CREATE UNIQUE INDEX IF NOT EXISTS availability_open "
        "ON availability(entity_id) WHERE ended IS NULL",
        "CREATE TABLE IF NOT EXISTS issues (key TEXT PRIMARY KEY, source TEXT NOT NULL, "
        "severity TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL, "
        "first_seen REAL NOT NULL, "
        "last_seen REAL NOT NULL, occurrences INTEGER NOT NULL, active INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS runs (entity_id TEXT NOT NULL, run_id TEXT NOT NULL, "
        "context_id TEXT, started REAL NOT NULL, outcome TEXT NOT NULL, triggered INTEGER NOT NULL "
        "DEFAULT 0, detail TEXT NOT NULL, PRIMARY KEY(entity_id,run_id))",
        "CREATE INDEX IF NOT EXISTS runs_context ON runs(entity_id,context_id)",
        "CREATE TABLE IF NOT EXISTS exceptions (entity_id TEXT PRIMARY KEY, "
        "reason TEXT NOT NULL, expires REAL)",
        "CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY, created REAL NOT NULL, "
        "kind TEXT NOT NULL, target TEXT, provider TEXT NOT NULL, model TEXT NOT NULL, "
        "result TEXT NOT NULL, evidence TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY, created REAL NOT NULL, "
        "provider TEXT NOT NULL, model TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER, "
        "cost_usd REAL NOT NULL, status TEXT NOT NULL)",
    ),
    2: (
        "CREATE TABLE automation_structures (id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, "
        "digest TEXT NOT NULL, projection TEXT NOT NULL, first_seen REAL NOT NULL, "
        "last_seen REAL NOT NULL, UNIQUE(entity_id,digest))",
        "CREATE TABLE automation_current (entity_id TEXT PRIMARY KEY, structure_id INTEGER "
        "NOT NULL REFERENCES automation_structures(id), observed_at REAL NOT NULL, source TEXT "
        "NOT NULL CHECK(source IN ('current_config','retained_trace')))",
        "CREATE TABLE configuration_changes (id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, "
        "observed_at REAL NOT NULL, before_id INTEGER REFERENCES automation_structures(id), "
        "after_id INTEGER NOT NULL REFERENCES automation_structures(id), source TEXT NOT NULL, "
        "kind TEXT NOT NULL CHECK(kind IN ('baseline','changed','current_baseline')))",
        "CREATE INDEX changes_entity ON configuration_changes(entity_id,observed_at)",
        "CREATE TABLE run_evidence (entity_id TEXT NOT NULL, run_id TEXT NOT NULL, "
        "summary TEXT NOT NULL, PRIMARY KEY(entity_id,run_id), FOREIGN KEY(entity_id,run_id) "
        "REFERENCES runs(entity_id,run_id) ON DELETE CASCADE)",
        "CREATE TABLE dependency_nodes (key TEXT PRIMARY KEY, kind TEXT NOT NULL, "
        "identifier TEXT NOT NULL)",
        "CREATE TABLE dependency_edges (source TEXT NOT NULL REFERENCES dependency_nodes(key) "
        "ON DELETE CASCADE, target TEXT NOT NULL REFERENCES dependency_nodes(key) ON DELETE "
        "CASCADE, relation TEXT NOT NULL, path TEXT NOT NULL, "
        "PRIMARY KEY(source,target,relation,path))",
        "CREATE INDEX dependencies_target ON dependency_edges(target)",
        "CREATE INDEX runs_started ON runs(started)",
    ),
    3: (
        "CREATE TABLE run_evidence_saved AS SELECT * FROM run_evidence",
        "DROP TABLE run_evidence",
        "CREATE TABLE runs_new (entity_id TEXT NOT NULL, run_id TEXT NOT NULL, context_id TEXT, "
        "started REAL, outcome TEXT NOT NULL, triggered INTEGER NOT NULL DEFAULT 0, "
        "detail TEXT NOT NULL, PRIMARY KEY(entity_id,run_id))",
        "INSERT INTO runs_new(rowid,entity_id,run_id,context_id,started,outcome,triggered,detail) "
        "SELECT rowid,entity_id,run_id,context_id,started,outcome,triggered,detail FROM runs",
        "DROP TABLE runs",
        "ALTER TABLE runs_new RENAME TO runs",
        "CREATE INDEX runs_context ON runs(entity_id,context_id)",
        "CREATE INDEX runs_started ON runs(started)",
        "CREATE TABLE run_evidence (entity_id TEXT NOT NULL, run_id TEXT NOT NULL, "
        "summary TEXT NOT NULL, stored_bytes INTEGER NOT NULL, "
        "compacted INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY(entity_id,run_id), FOREIGN KEY(entity_id,run_id) "
        "REFERENCES runs(entity_id,run_id) ON DELETE CASCADE)",
        "INSERT INTO run_evidence SELECT entity_id,run_id,summary,length(cast(summary AS BLOB)),0 "
        "FROM run_evidence_saved",
        "DROP TABLE run_evidence_saved",
        "CREATE TABLE run_timing (entity_id TEXT NOT NULL, run_id TEXT NOT NULL, observed_at REAL "
        "NOT NULL, start_source TEXT NOT NULL, PRIMARY KEY(entity_id,run_id), "
        "FOREIGN KEY(entity_id,run_id) REFERENCES runs(entity_id,run_id) ON DELETE CASCADE)",
        "CREATE TABLE trace_fetches (entity_id TEXT NOT NULL, run_id TEXT NOT NULL, "
        "attempts INTEGER NOT NULL, last_attempt REAL NOT NULL, next_attempt REAL NOT NULL, "
        "PRIMARY KEY(entity_id,run_id), FOREIGN KEY(entity_id,run_id) "
        "REFERENCES runs(entity_id,run_id) ON DELETE CASCADE)",
        "CREATE TABLE run_structures (entity_id TEXT NOT NULL, run_id TEXT NOT NULL, "
        "structure_id INTEGER NOT NULL REFERENCES automation_structures(id), "
        "PRIMARY KEY(entity_id,run_id), FOREIGN KEY(entity_id,run_id) "
        "REFERENCES runs(entity_id,run_id) ON DELETE CASCADE)",
    ),
    4: (
        "CREATE TABLE case_annotations (key TEXT PRIMARY KEY, status TEXT NOT NULL "
        "CHECK(status IN ('known','expected','snoozed')), note TEXT NOT NULL, "
        "updated REAL NOT NULL, expires REAL)",
        "CREATE TABLE case_notes (id INTEGER PRIMARY KEY, key TEXT NOT NULL, created REAL "
        "NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL, expires REAL)",
        "CREATE INDEX case_notes_key ON case_notes(key,created,id)",
        "CREATE INDEX issues_attention ON issues(active,source,severity,last_seen,key)",
        "CREATE INDEX runs_entity_time ON runs(entity_id,started)",
    ),
    5: (
        "ALTER TABLE case_annotations ADD COLUMN case_first_seen REAL",
        "UPDATE case_annotations SET case_first_seen="
        "(SELECT first_seen FROM issues WHERE issues.key=case_annotations.key)",
        "ALTER TABLE case_notes ADD COLUMN case_first_seen REAL",
        "UPDATE case_notes SET case_first_seen="
        "(SELECT first_seen FROM issues WHERE issues.key=case_notes.key)",
        "CREATE INDEX case_notes_episode ON case_notes(key,case_first_seen,created,id)",
        *(
            "CREATE TRIGGER runs_insights_"
            + operation.lower()
            + " AFTER "
            + operation
            + " ON runs BEGIN INSERT INTO meta VALUES ('runs_revision','1') "
            "ON CONFLICT(key) DO UPDATE SET value=cast(meta.value AS INTEGER)+1; END"
            for operation in ("INSERT", "UPDATE", "DELETE")
        ),
    ),
    6: (
        "CREATE TABLE ai_requests (id TEXT PRIMARY KEY,created REAL NOT NULL,expires REAL NOT NULL,"
        "status TEXT NOT NULL,conversation_id TEXT NOT NULL,round INTEGER NOT NULL,"
        "kind TEXT NOT NULL,"
        "target TEXT,profile TEXT NOT NULL,run_id TEXT,compare_id TEXT,"
        "config_binding TEXT NOT NULL,"
        "digest TEXT NOT NULL,payload TEXT NOT NULL,local_evidence TEXT NOT NULL,"
        "analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL,error TEXT)",
        "CREATE INDEX ai_requests_conversation ON ai_requests(conversation_id,round,created)",
        "CREATE INDEX ai_requests_expiry ON ai_requests(status,expires)",
        "CREATE TABLE ai_attempts (usage_id INTEGER PRIMARY KEY REFERENCES usage(id) "
        "ON DELETE CASCADE,request_id TEXT NOT NULL REFERENCES ai_requests(id) ON DELETE CASCADE,"
        "provider TEXT NOT NULL,attempt INTEGER NOT NULL)",
    ),
    7: (
        "CREATE INDEX ai_requests_analysis ON ai_requests(analysis_id)",
        "CREATE TABLE ai_billing_receipts (usage_id INTEGER PRIMARY KEY REFERENCES usage(id) "
        "ON DELETE CASCADE,created REAL NOT NULL,request_id TEXT NOT NULL,"
        "conversation_id TEXT NOT NULL,round INTEGER NOT NULL,digest TEXT NOT NULL,"
        "provider TEXT NOT NULL,attempt INTEGER NOT NULL,revoked INTEGER NOT NULL DEFAULT 0)",
        "CREATE INDEX ai_billing_receipts_request ON ai_billing_receipts(request_id)",
        "INSERT INTO ai_billing_receipts "
        "SELECT a.usage_id,u.created,r.id,r.conversation_id,r.round,r.digest,"
        "a.provider,a.attempt,r.status='revoked' FROM ai_attempts a "
        "JOIN usage u ON u.id=a.usage_id JOIN ai_requests r ON r.id=a.request_id",
    ),
    8: (
        "CREATE TABLE ai_storage_sizes (kind TEXT NOT NULL CHECK(kind IN ('request','analysis')),"
        "record_id TEXT NOT NULL,stored_bytes INTEGER NOT NULL CHECK(stored_bytes>=0),"
        "PRIMARY KEY(kind,record_id))",
        *(
            "INSERT INTO ai_storage_sizes SELECT '" + kind + "',cast(id AS TEXT),"
            "length(cast(" + first + " AS BLOB))+length(cast(" + second + " AS BLOB)) FROM " + table
            for kind, table, first, second in (
                ("request", "ai_requests", "payload", "local_evidence"),
                ("analysis", "analyses", "result", "evidence"),
            )
        ),
        *(
            "CREATE TRIGGER "
            + table
            + "_storage_"
            + operation.lower()
            + " AFTER "
            + operation
            + (" OF id," + first + "," + second if operation == "UPDATE" else "")
            + " ON "
            + table
            + " BEGIN "
            + (
                "DELETE FROM ai_storage_sizes WHERE kind='"
                + kind
                + "' AND record_id=cast(OLD.id AS TEXT); "
                if operation != "INSERT"
                else ""
            )
            + (
                "INSERT INTO ai_storage_sizes VALUES ('"
                + kind
                + "',cast(NEW.id AS TEXT),length(cast(NEW."
                + first
                + " AS BLOB))"
                "+length(cast(NEW." + second + " AS BLOB))); "
                if operation != "DELETE"
                else ""
            )
            + "END"
            for kind, table, first, second in (
                ("request", "ai_requests", "payload", "local_evidence"),
                ("analysis", "analyses", "result", "evidence"),
            )
            for operation in ("INSERT", "UPDATE", "DELETE")
        ),
    ),
    9: (
        "CREATE TABLE device_observations (id INTEGER PRIMARY KEY,device_id TEXT NOT NULL,"
        "state TEXT NOT NULL CHECK(state IN ('online','offline','partial','unknown','excluded')),"
        "started REAL NOT NULL,ended REAL,episode_started REAL,episode_kind TEXT NOT NULL,"
        "cohort TEXT NOT NULL,attention TEXT NOT NULL,platforms TEXT NOT NULL,"
        "evidence TEXT NOT NULL,reason TEXT NOT NULL,encoded_bytes INTEGER GENERATED ALWAYS AS ("
        "length(cast(device_id AS BLOB))+length(cast(state AS BLOB))+length(cast(episode_kind "
        "AS BLOB))+length(cast(cohort AS BLOB))+length(cast(attention AS "
        "BLOB))+length(cast(platforms AS BLOB))+length(cast(evidence AS "
        "BLOB))+length(cast(reason AS BLOB))+64) STORED)",
        "CREATE UNIQUE INDEX device_observations_open ON device_observations(device_id) WHERE "
        "ended IS NULL",
        "CREATE INDEX device_observations_device ON device_observations(device_id,started,id)",
        "CREATE INDEX device_observations_end ON device_observations(ended,started)",
        "CREATE INDEX device_observations_start ON device_observations(started,id)",
        "CREATE TABLE device_current (device_id TEXT PRIMARY KEY,observation_id INTEGER "
        "REFERENCES device_observations(id),payload TEXT NOT NULL,registry_present INTEGER NOT "
        "NULL,removed_at REAL)",
        "CREATE TABLE device_storage (kind TEXT PRIMARY KEY,records INTEGER NOT NULL,bytes "
        "INTEGER NOT NULL)",
        "INSERT INTO device_storage VALUES ('history',0,0),('current',0,0)",
        *(
            "CREATE TRIGGER device_"
            + kind
            + "_size_"
            + operation.lower()
            + " AFTER "
            + operation
            + (" OF " + ",".join(columns) if operation == "UPDATE" else "")
            + " ON "
            + table
            + " BEGIN "
            + (
                "UPDATE device_storage SET records=records-1,bytes=bytes-("
                + "+".join("length(cast(OLD." + column + " AS BLOB))" for column in columns)
                + "+"
                + str(overhead)
                + ") WHERE kind='"
                + kind
                + "'; "
                if operation != "INSERT"
                else ""
            )
            + (
                "UPDATE device_storage SET records=records+1,bytes=bytes+("
                + "+".join("length(cast(NEW." + column + " AS BLOB))" for column in columns)
                + "+"
                + str(overhead)
                + ") WHERE kind='"
                + kind
                + "'; "
                if operation != "DELETE"
                else ""
            )
            + "END"
            for kind, table, columns, overhead in (
                (
                    "history",
                    "device_observations",
                    (
                        "device_id",
                        "state",
                        "episode_kind",
                        "cohort",
                        "attention",
                        "platforms",
                        "evidence",
                        "reason",
                    ),
                    64,
                ),
                ("current", "device_current", ("device_id", "payload"), 32),
            )
            for operation in ("INSERT", "UPDATE", "DELETE")
        ),
        "CREATE TABLE device_coverage (id INTEGER PRIMARY KEY,started REAL NOT "
        "NULL,observed_until REAL NOT NULL,ended REAL,reason TEXT NOT NULL)",
        "CREATE UNIQUE INDEX device_coverage_open ON device_coverage((1)) WHERE ended IS NULL",
        "CREATE TABLE device_policies (device_id TEXT PRIMARY KEY,attention TEXT NOT NULL "
        "CHECK(attention IN ('review','known','expected')),power TEXT NOT NULL "
        "CHECK(power IN ('unknown','battery','mains')),note TEXT NOT NULL,updated REAL NOT NULL,"
        "baseline_state TEXT NOT NULL,baseline_cohort TEXT NOT NULL,baseline_at "
        "REAL,worsened_at REAL,worsened_cohort TEXT)",
        "CREATE TABLE device_checks (id INTEGER PRIMARY KEY,device_id TEXT NOT NULL,created "
        "REAL NOT NULL,kind TEXT NOT NULL,note TEXT NOT NULL,before_state TEXT NOT NULL,cohort "
        "TEXT NOT NULL)",
        "CREATE INDEX device_checks_device ON device_checks(device_id,created,id)",
    ),
}


MIGRATIONS[10] = (
    "CREATE TABLE home_preferences (id INTEGER PRIMARY KEY CHECK(id=1),locale TEXT NOT NULL "
    "CHECK(locale IN ('auto','nl','en')),intake TEXT NOT NULL "
    "CHECK(intake IN ('new','draft','complete','skipped')),updated REAL NOT NULL)",
    "INSERT INTO home_preferences VALUES (1,'auto','new',0)",
    "CREATE TABLE home_device_preferences (device_id TEXT PRIMARY KEY,importance TEXT NOT NULL "
    "CHECK(importance IN ('low','normal','high')),known_issue INTEGER "
    "CHECK(known_issue IN (0,1)),usual_behavior INTEGER CHECK(usual_behavior IN (0,1)),"
    "baseline_state TEXT NOT NULL,"
    "baseline_cohort TEXT NOT NULL,acknowledged_at REAL,worsened_at REAL,"
    "worsened_cohort TEXT,updated REAL NOT NULL)",
    "CREATE TABLE home_problems (problem_id TEXT PRIMARY KEY,kind TEXT NOT NULL,target TEXT NOT "
    "NULL,episode TEXT NOT NULL,snapshot TEXT NOT NULL,first_observed REAL NOT NULL,"
    "updated REAL NOT NULL,present INTEGER NOT NULL)",
    "CREATE INDEX home_problems_present ON home_problems(present,updated,problem_id)",
    "CREATE TABLE home_feedback (id INTEGER PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,"
    "problem_id TEXT NOT NULL REFERENCES home_problems(problem_id),episode TEXT NOT NULL,"
    "created REAL NOT NULL,kind TEXT NOT NULL,note TEXT NOT NULL,basis TEXT NOT NULL "
    "CHECK(length(cast(basis AS BLOB))<=4096),check_id INTEGER "
    "REFERENCES device_checks(id))",
    "CREATE INDEX home_feedback_problem ON home_feedback(problem_id,created,id)",
)


MIGRATIONS[11] = (
    "CREATE TABLE home_ai_consent (id INTEGER PRIMARY KEY CHECK(id=1),version TEXT NOT NULL,"
    "enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),generation INTEGER NOT NULL,"
    "updated REAL NOT NULL)",
    "CREATE TABLE home_investigations (id TEXT PRIMARY KEY,problem_id TEXT NOT NULL,"
    "episode TEXT NOT NULL,revision TEXT NOT NULL,language TEXT NOT NULL "
    "CHECK(language IN ('nl','en')),input_digest TEXT NOT NULL,config_binding TEXT NOT NULL,"
    "consent_generation INTEGER NOT NULL,start_slot INTEGER NOT NULL,created REAL NOT NULL,"
    "updated REAL NOT NULL,"
    "status TEXT NOT NULL,in_flight INTEGER NOT NULL CHECK(in_flight IN (0,1)),error TEXT,"
    "scope TEXT NOT NULL CHECK(length(CAST(scope AS BLOB))<=8192),"
    "base_request_id TEXT REFERENCES ai_requests(id) ON DELETE SET NULL,"
    "final_request_id TEXT REFERENCES ai_requests(id) ON DELETE SET NULL,"
    "research_id TEXT,plan TEXT CHECK(length(CAST(plan AS BLOB))<=12288),"
    "analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL)",
    "CREATE INDEX home_investigations_problem ON home_investigations(problem_id,created)",
)


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # A preliminary RO check preserves unsupported-preview bytes and permissions.
        # If SQLite needs recovery, the writer-reserved check below is authoritative.
        if path.exists() and path.stat().st_size:
            try:
                with closing(
                    sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
                ) as source:
                    self.validate_device_schema(source)
            except sqlite3.Error:
                # A hot journal/RO-sidecar failure may require writable recovery.
                # Affirmative StorageStartupError still propagates; RW rechecks below.
                pass
        # Create privately before SQLite can create the main or WAL files.
        descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
        self.path = path.resolve()
        self.lock = threading.RLock()
        self.depth = 0
        self.owner = None
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=5)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.row_factory = sqlite3.Row
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError("Database belongs to a newer Vision version")
            # A backup and its migration share one writer reservation. Re-read the
            # version under the lock: another startup may have migrated while we waited.
            self.db.execute("BEGIN IMMEDIATE")
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError("Database belongs to a newer Vision version")
            self.validate_device_schema(self.db)
            os.chmod(path, 0o600)
            for suffix in ("-wal", "-shm", "-journal"):
                sidecar = path.with_name(path.name + suffix)
                if sidecar.is_file() and not sidecar.is_symlink():
                    os.chmod(sidecar, 0o600)
            if (
                version < SCHEMA_VERSION
                and self.db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1"
                ).fetchone()
            ):
                self.migration_backup(path)
            for target in range(version + 1, SCHEMA_VERSION + 1):
                for statement in MIGRATIONS[target]:
                    self.db.execute(statement)
                self.db.execute(f"PRAGMA user_version={target}")
            # A crash/request cancellation cannot prove that a provider did not bill.
            self.db.execute("UPDATE usage SET status='uncertain' WHERE status='reserved'")
            self.db.execute("UPDATE ai_requests SET status='uncertain' WHERE status='sending'")
            self.db.commit()
            journal = self.db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if journal.lower() != "wal":
                raise RuntimeError("Vision storage requires WAL journal mode")
            self.journal_mode = journal.lower()
            with self.transaction():
                # A prior interrupted writer may have left a NULL-start record.
                # Record only its first recovered observation, never a run start.
                self.db.execute(
                    "INSERT OR IGNORE INTO run_timing SELECT r.entity_id,r.run_id,?,'unknown' "
                    "FROM runs r WHERE r.started IS NULL AND NOT EXISTS "
                    "(SELECT 1 FROM run_timing t WHERE t.entity_id=r.entity_id "
                    "AND t.run_id=r.run_id)",
                    (time.time(),),
                )
                self.recount_evidence_bytes()
                self.prune_case_history()
                for row in self.rows(
                    "SELECT entity_id FROM run_evidence GROUP BY entity_id "
                    "HAVING sum(stored_bytes)>? OR sum(compacted=0)>?",
                    (DETAIL_BYTES_PER_ENTITY, DETAILED_RUNS_PER_ENTITY),
                ):
                    self.enforce_evidence_budget(row["entity_id"])
                self.enforce_evidence_budget()
        except BaseException as error:
            try:
                self.db.rollback()
            finally:
                self.db.close()
            if isinstance(error, sqlite3.Error) and (
                getattr(error, "sqlite_errorcode", 0) & 255
            ) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise StorageStartupError("storage_busy") from None
            raise

    @staticmethod
    def validate_device_schema(db):
        if db.execute("PRAGMA user_version").fetchone()[0] != 9:
            return
        required = {
            "device_current": {
                "device_id",
                "observation_id",
                "payload",
                "registry_present",
                "removed_at",
            },
            "device_observations": {"device_id", "state", "started", "ended", "encoded_bytes"},
            "device_storage": {"kind", "records", "bytes"},
            "device_policies": {"baseline_state", "worsened_at", "worsened_cohort"},
        }
        for table, columns in required.items():
            retained = {row[1] for row in db.execute("PRAGMA table_xinfo(" + table + ")")}
            if not columns <= retained:
                raise StorageStartupError("unsupported_preview_schema")

    def migration_backup(self, path):
        """Reuse identical consistent snapshots; bound retained and temporary copies."""
        # The caller holds BEGIN IMMEDIATE until migration commit/rollback.
        # A read snapshot alone would allow another WAL writer to change the source.
        if not self.db.in_transaction:
            raise RuntimeError("Migration snapshot requires the startup writer reservation")
        self._migration_backup(path)

    def _migration_backup(self, path):
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        live_inodes = set()
        for suffix in ("", "-wal", "-shm"):
            live = path.with_name(path.name + suffix)
            if live.exists():
                stat = live.stat()
                live_inodes.add((stat.st_dev, stat.st_ino))
        original = path.with_name(path.name + ".pre-migration.bak")
        if original.exists() or original.is_symlink():
            self.reject_live_alias(original, live_inodes)
            self.validate_snapshot(original)
        pattern = re.compile(re.escape(path.name) + r"\.v(\d+)(?:-[a-f0-9]{32,64})?\.bak$")
        candidates, inodes = [], {}
        for item in path.parent.iterdir():
            if item.name.startswith(path.name + ".backup-"):
                # A crash or operator file has uncertain ownership/completeness.
                # Never ignore its disk use or remove it automatically.
                raise StorageStartupError("snapshot_pending")
            match = pattern.fullmatch(item.name)
            if match and not item.is_symlink() and item.is_file():
                self.reject_live_alias(item, live_inodes)
                stat = item.stat()
                inodes[(stat.st_dev, stat.st_ino)] = stat.st_size
                if int(match[1]) == version:
                    candidates.append(item)
        if original.exists():
            stat = original.stat()
            inodes[(stat.st_dev, stat.st_ino)] = stat.st_size
        # At the retained limit a single temporary copy may still prove reuse.
        # No fourth retained source revision may be published, and no files are rotated.
        if len(candidates) > MAX_SNAPSHOTS_PER_VERSION:
            raise StorageStartupError("snapshot_budget")
        estimate = (
            self.db.execute("PRAGMA page_count").fetchone()[0]
            * self.db.execute("PRAGMA page_size").fetchone()[0]
        )
        if estimate > MAX_SNAPSHOT_BYTES:
            raise StorageStartupError("snapshot_too_large")
        if sum(inodes.values()) + estimate > MAX_SNAPSHOT_BYTES:
            raise StorageStartupError("snapshot_budget")
        if shutil.disk_usage(path.parent).free < estimate + SNAPSHOT_FREE_RESERVE:
            raise StorageStartupError("snapshot_space")
        temporary = path.with_name(path.name + ".backup-" + uuid.uuid4().hex)
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            self.write_snapshot(temporary)
            self.validate_snapshot(temporary, version)
            with temporary.open("rb") as saved:
                os.fsync(saved.fileno())
            digest = self.snapshot_digest(temporary)
            backup = None
            for candidate in candidates:
                # Never chmod or otherwise modify an existing operator file.
                if (
                    candidate.stat().st_mode & 0o077
                    or candidate.stat().st_size != temporary.stat().st_size
                ):
                    continue
                try:
                    self.validate_snapshot(candidate, version)
                except StorageStartupError:
                    continue
                if self.snapshot_digest(candidate) == digest:
                    backup = candidate
                    break
            if backup is None:
                if len(candidates) >= MAX_SNAPSHOTS_PER_VERSION:
                    raise StorageStartupError("snapshot_budget")
                backup = path.with_name(path.name + f".v{version}.bak")
                try:
                    os.link(temporary, backup)
                except FileExistsError:
                    backup = path.with_name(path.name + f".v{version}-" + digest + ".bak")
                    try:
                        os.link(temporary, backup)
                    except FileExistsError:
                        # A colliding, unverified file is preserved, including its permissions.
                        backup = path.with_name(
                            path.name + f".v{version}-" + uuid.uuid4().hex + ".bak"
                        )
                        os.link(temporary, backup)
            if not original.exists():
                os.link(backup, original)
        finally:
            for suffix in ("", "-journal", "-wal", "-shm"):
                # Only this invocation's exclusive temporary filename is owned here.
                temporary.with_name(temporary.name + suffix).unlink(missing_ok=True)

    @staticmethod
    def reject_live_alias(path, live_inodes):
        if path.is_symlink():
            raise StorageStartupError("snapshot_invalid")
        stat = path.stat()
        if (stat.st_dev, stat.st_ino) in live_inodes:
            raise StorageStartupError("snapshot_invalid")

    def write_snapshot(self, temporary):
        # Backing up the connection's own write transaction would deadlock.
        # A separate read-only connection sees the stable committed source while
        # our startup connection prevents other writers from changing it.
        try:
            source = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            raise StorageStartupError("snapshot_source") from None
        try:
            target = sqlite3.connect(temporary)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()

    @staticmethod
    def validate_snapshot(path, version=None):
        if path.is_symlink():
            raise StorageStartupError("snapshot_invalid")
        try:
            saved = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
            try:
                if saved.execute("PRAGMA quick_check").fetchone()[0] != "ok" or (
                    version is not None
                    and saved.execute("PRAGMA user_version").fetchone()[0] != version
                ):
                    raise StorageStartupError("snapshot_invalid")
            finally:
                saved.close()
        except sqlite3.Error:
            raise StorageStartupError("snapshot_invalid") from None

    @staticmethod
    def snapshot_digest(path):
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(65536), b""):
                digest.update(chunk)
        return digest.digest().hex()

    @contextmanager
    def transaction(self):
        """Synchronous atomic region. Never hold this context across an await."""
        with self.lock:
            owner = self.execution_owner()
            if self.depth and self.owner != owner:
                raise RuntimeError(
                    "Cross-task transaction nesting denied; never await in a transaction"
                )
            outer = self.depth == 0
            if outer:
                self.db.execute("BEGIN IMMEDIATE")
                self.owner = owner
            self.depth += 1
            try:
                yield self.db
            except BaseException:
                if outer:
                    self.db.rollback()
                raise
            else:
                if outer:
                    self.db.commit()
            finally:
                self.depth -= 1
                if outer:
                    self.owner = None

    @staticmethod
    def execution_owner():
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        return threading.get_ident(), task

    def check_owner(self):
        if self.depth and self.owner != self.execution_owner():
            raise RuntimeError("Cross-task transaction access denied")

    def rows(self, sql, args=()):
        with self.lock:
            self.check_owner()
            return [dict(row) for row in self.db.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.transaction():
            return self.db.execute(sql, args).lastrowid

    def get_meta(self, key, default=None):
        with self.lock:
            self.check_owner()
            row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        self.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))

    def exceptions(self):
        return self.rows("SELECT * FROM exceptions ORDER BY entity_id")

    def expected(self, entity_id, now=None):
        now = time.time() if now is None else now
        return bool(
            self.rows(
                "SELECT 1 FROM exceptions WHERE entity_id=? AND (expires IS NULL OR expires>?) "
                "UNION ALL SELECT 1 FROM case_annotations a JOIN issues i ON i.key=a.key "
                "AND i.first_seen=a.case_first_seen WHERE a.key=? AND a.status='expected' "
                "AND (a.expires IS NULL OR a.expires>?) LIMIT 1",
                (entity_id, now, "availability:" + entity_id, now),
            )
        )

    def expected_entities(self, now=None):
        now = time.time() if now is None else now
        return {
            row["entity_id"]
            for row in self.rows(
                "SELECT entity_id FROM exceptions WHERE expires IS NULL OR expires>? "
                "UNION SELECT substr(a.key,14) entity_id FROM case_annotations a JOIN issues i "
                "ON i.key=a.key AND i.first_seen=a.case_first_seen WHERE a.status='expected' "
                "AND a.key LIKE 'availability:%' AND (a.expires IS NULL OR a.expires>?)",
                (now, now),
            )
        }

    def structures(self):
        return {
            row["entity_id"]: json.loads(row["projection"])
            for row in self.rows(
                "SELECT c.entity_id,s.projection FROM automation_current c "
                "JOIN automation_structures s ON s.id=c.structure_id"
            )
        }

    def save_structure(self, entity_id, projection, source, now=None):
        """A retained run's config cannot replace a current configuration observation."""
        if source not in {"current_config", "retained_trace"}:
            raise ValueError("Unknown structural evidence source")
        now = time.time() if now is None else now
        digest = fingerprint(projection)
        with self.transaction():
            self.execute(
                "INSERT INTO automation_structures"
                "(entity_id,digest,projection,first_seen,last_seen) "
                "VALUES (?,?,?,?,?) ON CONFLICT(entity_id,digest) DO UPDATE SET "
                "last_seen=excluded.last_seen",
                (entity_id, digest, json.dumps(projection), now, now),
            )
            version_id = self.rows(
                "SELECT id FROM automation_structures WHERE entity_id=? AND digest=?",
                (entity_id, digest),
            )[0]["id"]
            previous = self.rows("SELECT * FROM automation_current WHERE entity_id=?", (entity_id,))
            current = previous[0] if previous else None
            if source == "retained_trace" and current:
                return version_id
            before = current["structure_id"] if current else None
            if before != version_id or (current and current["source"] != source):
                kind = (
                    "baseline"
                    if not current
                    else ("current_baseline" if current["source"] != source else "changed")
                )
                self.execute(
                    "INSERT INTO configuration_changes(entity_id,observed_at,before_id,after_id,"
                    "source,kind) VALUES (?,?,?,?,?,?)",
                    (entity_id, now, before, version_id, source, kind),
                )
            self.execute(
                "INSERT INTO automation_current VALUES (?,?,?,?) ON CONFLICT(entity_id) "
                "DO UPDATE SET structure_id=excluded.structure_id,observed_at=excluded.observed_at,"
                "source=excluded.source",
                (entity_id, version_id, now, source),
            )
            return version_id

    def replace_graph(self, graph, now=None):
        with self.transaction():
            digest = fingerprint(graph)
            self.set_meta("dependencies_observed_at", time.time() if now is None else now)
            if self.get_meta("dependencies_digest") == digest:
                return False
            self.db.execute("DELETE FROM dependency_edges")
            self.db.execute("DELETE FROM dependency_nodes")
            self.db.executemany(
                "INSERT INTO dependency_nodes VALUES (?,?,?)",
                ((n["key"], n["kind"], n["identifier"]) for n in graph["nodes"]),
            )
            self.db.executemany(
                "INSERT INTO dependency_edges VALUES (?,?,?,?)",
                ((e["source"], e["target"], e["relation"], e["path"]) for e in graph["edges"]),
            )
            self.set_meta("dependencies_digest", digest)
            return True

    def recount_evidence_bytes(self):
        total = self.db.execute(
            "SELECT coalesce(sum(stored_bytes),0) FROM run_evidence"
        ).fetchone()[0]
        self.set_meta("run_evidence_bytes", total)
        return total

    @staticmethod
    def compact_summary(summary):
        compact = {
            key: summary.get(key)
            for key in (
                "schema_version",
                "step_count",
                "error_count",
                "duration_seconds",
                "completed_with_errors",
                "configuration_digest",
                "configuration_source",
            )
        }
        compact.update(
            steps=[],
            errors=[],
            coverage={
                **summary["coverage"],
                "details_compacted": True,
                "compaction_reason": "storage budget",
            },
        )
        return compact

    def save_run_evidence(self, entity_id, run_id, summary, outcome):
        with self.transaction():
            old = self.rows(
                "SELECT * FROM run_evidence WHERE entity_id=? AND run_id=?", (entity_id, run_id)
            )
            previous = json.loads(old[0]["summary"]) if old else None
            if not old:
                detail = self.rows(
                    "SELECT detail FROM runs WHERE entity_id=? AND run_id=?", (entity_id, run_id)
                )
                previous = (
                    json.loads(detail[0]["detail"]).get("_vision_evidence") if detail else None
                )
                if previous and not summary["coverage"]["full_trace_available"]:
                    # The detail was compacted, but whole-run state still advances.
                    previous["completed_with_errors"] = (
                        outcome == "succeeded" and previous["error_count"] > 0
                    )
                    retained_detail = json.loads(detail[0]["detail"])
                    retained_detail["_vision_evidence"] = previous
                    encoded_detail = json.dumps(retained_detail)
                    if encoded_detail != detail[0]["detail"]:
                        self.db.execute(
                            "UPDATE runs SET detail=? WHERE entity_id=? AND run_id=?",
                            (encoded_detail, entity_id, run_id),
                        )
                    return previous
            if (
                previous
                and "configuration_digest" in previous
                and "configuration_digest" not in summary
            ):
                summary["configuration_digest"] = previous["configuration_digest"]
                summary["configuration_source"] = previous["configuration_source"]
            if previous and previous["coverage"].get("full_trace_available"):
                if not summary["coverage"]["full_trace_available"]:
                    summary = previous
                elif previous["error_count"] > summary["error_count"]:
                    # HA may already have evicted an earlier loop iteration.
                    summary["errors"] = (previous.get("errors", []) + summary["errors"])[:100]
                    summary["error_count"] = previous["error_count"]
                    summary["coverage"]["previous_errors_preserved"] = True
                    summary["coverage"]["error_count_is_lower_bound"] = True
            summary["completed_with_errors"] = outcome == "succeeded" and summary["error_count"] > 0
            encoded = json.dumps(summary)
            size = len(encoded.encode())
            if summary["coverage"]["full_trace_available"]:
                row = self.rows(
                    "SELECT detail FROM runs WHERE entity_id=? AND run_id=?",
                    (entity_id, run_id),
                )[0]
                retained_detail = json.loads(row["detail"])
                if "_vision_evidence" in retained_detail:
                    retained_detail.pop("_vision_evidence")
                    self.db.execute(
                        "UPDATE runs SET detail=? WHERE entity_id=? AND run_id=?",
                        (json.dumps(retained_detail), entity_id, run_id),
                    )
            if not old or old[0]["summary"] != encoded:
                self.db.execute(
                    "INSERT INTO run_evidence(entity_id,run_id,summary,stored_bytes,compacted) "
                    "VALUES (?,?,?,?,?) ON CONFLICT(entity_id,run_id) DO UPDATE SET "
                    "summary=excluded.summary,stored_bytes=excluded.stored_bytes,"
                    "compacted=excluded.compacted",
                    (
                        entity_id,
                        run_id,
                        encoded,
                        size,
                        int(summary["coverage"].get("details_compacted", False)),
                    ),
                )
                total = (
                    self.get_meta("run_evidence_bytes", 0)
                    + size
                    - (old[0]["stored_bytes"] if old else 0)
                )
                self.set_meta("run_evidence_bytes", total)
                self.enforce_evidence_budget(entity_id)
            return summary

    def enforce_evidence_budget(self, entity_id=None):
        """Compact added step details; preserve every run and its observed counts."""
        if entity_id is not None:
            rows = self.rows(
                "SELECT e.*,r.started FROM run_evidence e JOIN runs r USING(entity_id,run_id) "
                "WHERE entity_id=? ORDER BY r.started DESC,e.rowid DESC",
                (entity_id,),
            )
            used = 0
            for index, row in enumerate(rows):
                used += row["stored_bytes"]
                if not row["compacted"] and (
                    index >= DETAILED_RUNS_PER_ENTITY or used > DETAIL_BYTES_PER_ENTITY
                ):
                    self.compact_evidence_row(row)
        while self.get_meta("run_evidence_bytes", 0) > DETAIL_BYTES_TOTAL:
            self.recount_evidence_bytes()
            for row in self.rows(
                "SELECT e.* FROM run_evidence e JOIN runs r USING(entity_id,run_id) "
                "ORDER BY e.compacted ASC,r.started ASC,e.rowid ASC LIMIT 128"
            ):
                if self.get_meta("run_evidence_bytes", 0) <= DETAIL_BYTES_TOTAL:
                    break
                self.compact_evidence_row(row, move_to_run=bool(row["compacted"]))

    def compact_evidence_row(self, row, move_to_run=False):
        summary = self.compact_summary(json.loads(row["summary"]))
        encoded = json.dumps(summary)
        if move_to_run:
            detail = json.loads(
                self.rows(
                    "SELECT detail FROM runs WHERE entity_id=? AND run_id=?",
                    (row["entity_id"], row["run_id"]),
                )[0]["detail"]
            )
            detail["_vision_evidence"] = summary
            self.db.execute(
                "UPDATE runs SET detail=? WHERE entity_id=? AND run_id=?",
                (json.dumps(detail), row["entity_id"], row["run_id"]),
            )
            self.db.execute(
                "DELETE FROM run_evidence WHERE entity_id=? AND run_id=?",
                (row["entity_id"], row["run_id"]),
            )
            size = 0
        else:
            size = len(encoded.encode())
            self.db.execute(
                "UPDATE run_evidence SET summary=?,stored_bytes=?,compacted=1 "
                "WHERE entity_id=? AND run_id=?",
                (encoded, size, row["entity_id"], row["run_id"]),
            )
        self.set_meta(
            "run_evidence_bytes",
            self.get_meta("run_evidence_bytes", 0) + size - row["stored_bytes"],
        )

    def issue(self, key, source, severity, title, detail, now=None, occurrences=None):
        """Availability counts reopen episodes; explicit log counts come from HA."""
        with self.transaction():
            return self._issue(key, source, severity, title, detail, now, occurrences)

    def _issue(self, key, source, severity, title, detail, now=None, occurrences=None):
        now = time.time() if now is None else now
        old = self.rows("SELECT * FROM issues WHERE key=?", (key,))
        count = (
            occurrences
            if occurrences is not None
            else (old[0]["occurrences"] + (not old[0]["active"]) if old else 1)
        )
        self.execute(
            "INSERT INTO issues VALUES (?,?,?,?,?,?,?,?,1) ON CONFLICT(key) DO UPDATE SET "
            "severity=excluded.severity,title=excluded.title,detail=excluded.detail,"
            "last_seen=excluded.last_seen,occurrences=max(issues.occurrences,excluded.occurrences),"
            "active=1",
            (
                key,
                source,
                severity,
                title,
                json.dumps(detail),
                old[0]["first_seen"] if old else now,
                now,
                count,
            ),
        )

    def close(self):
        with self.lock:
            self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.db.close()

    def prune_case_history(self, before=None):
        """Annotations belong to one retained case generation; notes have a hard cap."""
        with self.transaction():
            for table in ("case_annotations", "case_notes"):
                self.db.execute(
                    f"DELETE FROM {table} WHERE NOT EXISTS "
                    f"(SELECT 1 FROM issues i WHERE i.key={table}.key "
                    f"AND i.first_seen={table}.case_first_seen)"
                )
            if before is not None:
                self.db.execute("DELETE FROM case_notes WHERE created<?", (before,))
            self.db.execute(
                "DELETE FROM case_notes WHERE id IN (SELECT id FROM ("
                "SELECT id,row_number() OVER(PARTITION BY key,case_first_seen "
                "ORDER BY created DESC,id DESC) n FROM case_notes) WHERE n>?)",
                (CASE_NOTES_PER_CASE,),
            )

    def cleanup_ai_previews(self, now=None):
        """Discard expired unused bodies; a transmitted attempt is historical evidence."""
        self.db.execute(
            "DELETE FROM ai_requests WHERE status='preview' AND expires<? AND NOT EXISTS "
            "(SELECT 1 FROM ai_attempts a WHERE a.request_id=ai_requests.id) AND NOT EXISTS "
            "(SELECT 1 FROM home_investigations o WHERE (o.in_flight=1 OR o.status IN "
            "('admitted','preparing','researching','freezing','sending')) AND "
            "ai_requests.id IN (o.base_request_id,o.final_request_id))",
            (time.time() if now is None else now,),
        )

    def ai_storage(self):
        sizes = self.rows(
            "SELECT coalesce(sum(kind='request'),0) request_count,"
            "coalesce(sum(stored_bytes),0) stored_bytes FROM ai_storage_sizes"
        )[0]
        promises = self.rows(
            "SELECT "
            "coalesce(sum(status IN ('preview','sending') OR EXISTS "
            "(SELECT 1 FROM ai_attempts a JOIN usage u ON u.id=a.usage_id "
            "WHERE a.request_id=ai_requests.id AND u.status='reserved')),0) promises "
            "FROM ai_requests"
        )[0]
        stored = sizes["stored_bytes"]
        promised = promises["promises"] * AI_RESULT_RESERVE_BYTES
        return {
            "request_count": sizes["request_count"],
            "stored_bytes": stored,
            "promised_result_bytes": promised,
            "available_request_slots": max(0, AI_MAX_REQUESTS - sizes["request_count"]),
            "available_payload_bytes": max(0, AI_MAX_STORAGE_BYTES - stored - promised),
            "max_requests": AI_MAX_REQUESTS,
            "max_storage_bytes": AI_MAX_STORAGE_BYTES,
            "result_reserve_bytes": AI_RESULT_RESERVE_BYTES,
        }

    def prune(self, days):
        before = time.time() - days * 86400
        # Billing ledger is retained for 400 days so retention cannot reset budgets.
        with self.transaction():
            self.db.execute("DELETE FROM availability WHERE ended<?", (before,))
            self.db.execute("DELETE FROM runs WHERE started<?", (before,))
            self.db.execute(
                "DELETE FROM runs WHERE started IS NULL AND EXISTS "
                "(SELECT 1 FROM run_timing t WHERE t.entity_id=runs.entity_id "
                "AND t.run_id=runs.run_id AND t.observed_at<?)",
                (before,),
            )
            self.db.execute("DELETE FROM issues WHERE active=0 AND last_seen<?", (before,))
            self.prune_case_history(before)
            self.cleanup_ai_previews()
            self.db.execute(
                "DELETE FROM ai_requests WHERE created<? AND NOT EXISTS "
                "(SELECT 1 FROM home_investigations o WHERE (o.in_flight=1 OR o.status IN "
                "('admitted','preparing','researching','freezing','sending')) AND "
                "ai_requests.id IN (o.base_request_id,o.final_request_id))",
                (before,),
            )
            self.db.execute("DELETE FROM analyses WHERE created<?", (before,))
            self.db.execute("DELETE FROM usage WHERE created<?", (time.time() - 400 * 86400,))
            self.db.execute("DELETE FROM configuration_changes WHERE observed_at<?", (before,))
            self.db.execute(
                "DELETE FROM device_observations WHERE ended<? AND NOT EXISTS "
                "(SELECT 1 FROM device_current WHERE observation_id=device_observations.id)",
                (before,),
            )
            self.db.execute("DELETE FROM device_coverage WHERE ended<?", (before,))
            self.db.execute(
                "DELETE FROM automation_structures WHERE last_seen<? AND id NOT IN "
                "(SELECT structure_id FROM automation_current) AND id NOT IN "
                "(SELECT structure_id FROM run_structures) AND id NOT IN "
                "(SELECT after_id FROM configuration_changes UNION SELECT before_id "
                "FROM configuration_changes WHERE before_id IS NOT NULL)",
                (before,),
            )
            self.recount_evidence_bytes()
