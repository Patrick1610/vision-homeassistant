"""Small transactional local history; never a Recorder replica."""

import asyncio
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS availability (
 id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, state TEXT NOT NULL,
 started REAL NOT NULL, ended REAL, uncertain INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS availability_entity ON availability(entity_id, started);
CREATE UNIQUE INDEX IF NOT EXISTS availability_open ON availability(entity_id) WHERE ended IS NULL;
CREATE TABLE IF NOT EXISTS issues (
 key TEXT PRIMARY KEY, source TEXT NOT NULL, severity TEXT NOT NULL,
 title TEXT NOT NULL, detail TEXT NOT NULL, first_seen REAL NOT NULL,
 last_seen REAL NOT NULL, occurrences INTEGER NOT NULL, active INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
 entity_id TEXT NOT NULL, run_id TEXT NOT NULL, context_id TEXT,
 started REAL NOT NULL, outcome TEXT NOT NULL, triggered INTEGER NOT NULL DEFAULT 0,
 detail TEXT NOT NULL, PRIMARY KEY(entity_id, run_id));
CREATE INDEX IF NOT EXISTS runs_context ON runs(entity_id, context_id);
CREATE TABLE IF NOT EXISTS exceptions (
 entity_id TEXT PRIMARY KEY, reason TEXT NOT NULL, expires REAL);
CREATE TABLE IF NOT EXISTS analyses (
 id INTEGER PRIMARY KEY, created REAL NOT NULL, kind TEXT NOT NULL,
 target TEXT, provider TEXT NOT NULL, model TEXT NOT NULL, result TEXT NOT NULL,
 evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage (
 id INTEGER PRIMARY KEY, created REAL NOT NULL, provider TEXT NOT NULL,
 model TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
 cost_usd REAL NOT NULL, status TEXT NOT NULL);

"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Create privately before SQLite can create the main or WAL files.
        descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
        self.lock = threading.RLock()
        self.depth = 0
        self.owner = None
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=5)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            self.db.close()
            raise RuntimeError("Database belongs to a newer Vision version")
        if version == 0:
            self.db.executescript(SCHEMA)
            self.db.execute("PRAGMA user_version=1")
        # A crash/request cancellation cannot prove that a provider did not bill.
        self.db.execute("UPDATE usage SET status='uncertain' WHERE status='reserved'")
        self.db.commit()

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
                "SELECT 1 FROM exceptions WHERE entity_id=? AND (expires IS NULL OR expires>?)",
                (entity_id, now),
            )
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

    def prune(self, days):
        before = time.time() - days * 86400
        # Billing ledger is retained for 400 days so retention cannot reset budgets.
        with self.transaction():
            self.db.execute("DELETE FROM availability WHERE ended<?", (before,))
            self.db.execute("DELETE FROM runs WHERE started<?", (before,))
            self.db.execute("DELETE FROM issues WHERE active=0 AND last_seen<?", (before,))
            self.db.execute("DELETE FROM analyses WHERE created<?", (before,))
            self.db.execute("DELETE FROM usage WHERE created<?", (time.time() - 400 * 86400,))
