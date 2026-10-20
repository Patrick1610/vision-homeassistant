"""A migration rollback point must cover exactly the writer-locked source."""

import hashlib
import os
import sqlite3
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.store import (
    MAX_SNAPSHOTS_PER_VERSION,
    MIGRATIONS,
    SCHEMA_VERSION,
    StorageStartupError,
    Store,
)


def schema_four(path):
    source = sqlite3.connect(path)
    for version in range(1, 5):
        for statement in MIGRATIONS[version]:
            source.execute(statement)
    source.execute("PRAGMA user_version=4")
    source.commit()
    source.execute("PRAGMA journal_mode=WAL")
    source.execute("PRAGMA wal_autocheckpoint=0")
    source.execute("INSERT INTO meta VALUES ('synthetic','A')")
    source.commit()
    source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    for suffix in ("", "-wal", "-shm"):
        path.with_name(path.name + suffix).chmod(0o600)
    return source


def snapshot_marker(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True) as saved:
        assert saved.execute("PRAGMA user_version").fetchone()[0] == 4
        return saved.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()[0]


def copy_inodes(tmp_path):
    return {(path.stat().st_dev, path.stat().st_ino) for path in tmp_path.glob("vision.db*.bak")}


@pytest.mark.parametrize("fail", [False, True])
def test_writer_reservation_covers_backup_and_first_ddl_then_releases(tmp_path, monkeypatch, fail):
    path = tmp_path / "vision.db"
    source = schema_four(path)
    original = Store.migration_backup
    probes = []

    def probe_writer():
        with sqlite3.connect(path, timeout=0.03) as other:
            try:
                other.execute("UPDATE meta SET value='B' WHERE key='synthetic'")
                other.commit()
            except sqlite3.OperationalError as error:
                probes.append("locked" in str(error).lower())
            else:
                probes.append(False)

    def backup(self, path):
        original(self, path)
        probe_writer()  # Exactly the old backup→BEGIN IMMEDIATE gap.

        def before_ddl(statement):
            if statement == MIGRATIONS[5][0]:
                probe_writer()

        self.db.set_trace_callback(before_ddl)

    monkeypatch.setattr(Store, "migration_backup", backup)
    if fail:
        monkeypatch.setitem(MIGRATIONS, 5, MIGRATIONS[5] + ("INTENTIONAL INVALID DDL",))
    try:
        if fail:
            with pytest.raises(sqlite3.OperationalError):
                Store(path)
        else:
            store = Store(path)
            store.close()
        assert probes == [True, True]
        assert snapshot_marker(tmp_path / "vision.db.v4.bak") == "A"
        assert source.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()[0] == "A"
        assert source.execute("PRAGMA user_version").fetchone()[0] == (
            4 if fail else SCHEMA_VERSION
        )
        source.execute("UPDATE meta SET value='C' WHERE key='synthetic'")
        source.commit()  # Both success and failure release the writer reservation.
        if fail:
            with pytest.raises(sqlite3.OperationalError):
                Store(path)
            assert {snapshot_marker(file) for file in tmp_path.glob("vision.db.v4*.bak")} == {
                "A",
                "C",
            }
    finally:
        source.close()


@pytest.mark.parametrize("first_fails", [False, True])
def test_two_coordinated_startups_wait_and_reread_locked_version(
    tmp_path, monkeypatch, first_fails
):
    path = tmp_path / "vision.db"
    source = schema_four(path)
    entered, release, second_started, second_done = (threading.Event() for _ in range(4))
    original = Store.migration_backup
    backups, results = [], {}

    def gated_backup(self, path):
        original(self, path)
        backups.append(threading.current_thread().name)
        if threading.current_thread().name == "first":
            entered.set()
            if not release.wait(2):
                raise RuntimeError("Synthetic coordination timed out")
            if first_fails:
                raise RuntimeError("Synthetic first startup failure")

    def start(name):
        if name == "second":
            second_started.set()
        try:
            store = Store(path)
            results[name] = store.rows("PRAGMA user_version")[0]["user_version"]
            store.close()
        except Exception as error:
            results[name] = type(error).__name__
        finally:
            if name == "second":
                second_done.set()

    monkeypatch.setattr(Store, "migration_backup", gated_backup)
    first = threading.Thread(target=start, args=("first",), name="first", daemon=True)
    second = threading.Thread(target=start, args=("second",), name="second", daemon=True)
    try:
        first.start()
        assert entered.wait(2), results
        second.start()
        assert second_started.wait(1)
        assert not second_done.wait(0.1), "The second startup bypassed the first writer reservation"
        release.set()
        first.join(3)
        second.join(3)
        assert not first.is_alive() and not second.is_alive(), "Startup/backup deadlock"
        assert results == {
            "first": "RuntimeError" if first_fails else SCHEMA_VERSION,
            "second": SCHEMA_VERSION,
        }
        assert backups == (["first", "second"] if first_fails else ["first"])
        assert len(copy_inodes(tmp_path)) == 1
        assert snapshot_marker(tmp_path / "vision.db.pre-migration.bak") == "A"
    finally:
        release.set()
        if first.ident:
            first.join(3)
        if second.ident:
            second.join(3)
        source.close()


def test_backup_under_startup_writer_reservation_has_process_timeout(tmp_path):
    path = tmp_path / "vision.db"
    source = schema_four(path)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; from vision.store import Store; "
                "import sys; store=Store(Path(sys.argv[1])); store.close()",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert snapshot_marker(tmp_path / "vision.db.v4.bak") == "A"
    finally:
        source.close()


@pytest.mark.parametrize("kind", ["candidate", "original"])
@pytest.mark.parametrize("suffix", ["", "-wal", "-shm"])
def test_live_main_wal_shm_hardlink_never_becomes_snapshot(tmp_path, monkeypatch, kind, suffix):
    path = tmp_path / "vision.db"
    source = schema_four(path)
    live = path.with_name(path.name + suffix)
    alias = tmp_path / (
        "vision.db.v4.bak" if kind == "candidate" else "vision.db.pre-migration.bak"
    )
    os.link(live, alias)
    before = alias.stat().st_ino, alias.stat().st_mode

    def forbidden_copy(*args):
        pytest.fail("Live inode aliases must be rejected before copying")

    monkeypatch.setattr(Store, "write_snapshot", forbidden_copy)
    try:
        with pytest.raises(StorageStartupError) as error:
            Store(path)
        assert error.value.code == "snapshot_invalid"
        assert (alias.stat().st_ino, alias.stat().st_mode) == before
        assert source.execute("PRAGMA user_version").fetchone()[0] == 4
        assert source.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()[0] == "A"
        assert not list(tmp_path.glob("vision.db.backup-*"))
        if not suffix:
            assert snapshot_marker(alias) == "A"
        if kind == "candidate":
            assert not (tmp_path / "vision.db.pre-migration.bak").exists()
    finally:
        source.close()


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_uncertain_snapshot_sidecars_fail_with_safe_actionable_pattern(tmp_path, suffix):
    path = tmp_path / "vision.db"
    source = schema_four(path)
    leftover = tmp_path / ("vision.db.backup-user_sensitive_filename" + suffix)
    leftover.write_bytes(b"Operator or crash bytes")
    before = leftover.read_bytes(), leftover.stat().st_mode
    try:
        with pytest.raises(StorageStartupError) as error:
            Store(path)
        assert error.value.code == "snapshot_pending"
        assert "vision.db.backup-*" in str(error.value) and "/data" in str(error.value)
        assert all(word in str(error.value) for word in ("stop Vision", "-journal", "-wal", "-shm"))
        assert "user_sensitive_filename" not in str(error.value)
        assert (leftover.read_bytes(), leftover.stat().st_mode) == before
        assert source.execute("PRAGMA user_version").fetchone()[0] == 4
    finally:
        source.close()


@pytest.mark.parametrize("kind", ["candidate", "original"])
def test_restored_checkpointed_source_rejects_byte_identical_live_hardlink(tmp_path, kind):
    seed = schema_four(tmp_path / "seed.db")
    path = tmp_path / "vision.db"
    try:
        with sqlite3.connect(path) as restored:
            seed.backup(restored)
    finally:
        seed.close()
    path.chmod(0o600)
    # A backup-restored main can exactly match a fresh API copy, reproducing adoption.
    proof = tmp_path / "proof.db"
    with sqlite3.connect(path) as source, sqlite3.connect(proof) as saved:
        source.backup(saved)
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(proof.read_bytes()).digest()
    proof.unlink()
    alias = tmp_path / (
        "vision.db.v4.bak" if kind == "candidate" else "vision.db.pre-migration.bak"
    )
    os.link(path, alias)
    original_bytes = alias.read_bytes()
    with pytest.raises(StorageStartupError) as error:
        Store(path)
    assert error.value.code == "snapshot_invalid"
    assert alias.read_bytes() == original_bytes and snapshot_marker(alias) == "A"
    with sqlite3.connect(path) as source:
        assert source.execute("PRAGMA user_version").fetchone()[0] == 4
    if kind == "candidate":
        assert not (tmp_path / "vision.db.pre-migration.bak").exists()


def test_nondeterministic_valid_snapshot_bytes_hit_fixed_retained_limit(tmp_path, monkeypatch):
    path = tmp_path / "vision.db"
    source = schema_four(path)
    original, count = Store.write_snapshot, 0

    def varying_header(self, temporary):
        nonlocal count
        original(self, temporary)
        count += 1
        # Only the valid application-id header differs; schema/data/user_version do not.
        with temporary.open("r+b") as saved:
            saved.seek(68)
            saved.write((100 + count).to_bytes(4, "big"))

    monkeypatch.setattr(Store, "write_snapshot", varying_header)
    monkeypatch.setitem(MIGRATIONS, 5, MIGRATIONS[5] + ("INTENTIONAL INVALID DDL",))
    try:
        for _ in range(MAX_SNAPSHOTS_PER_VERSION):
            with pytest.raises(sqlite3.OperationalError):
                Store(path)
        assert len(copy_inodes(tmp_path)) == MAX_SNAPSHOTS_PER_VERSION
        with pytest.raises(StorageStartupError) as error:
            Store(path)
        assert error.value.code == "snapshot_budget"
        assert len(copy_inodes(tmp_path)) == MAX_SNAPSHOTS_PER_VERSION
        assert not list(tmp_path.glob("vision.db.backup-*"))
        assert source.execute("PRAGMA user_version").fetchone()[0] == 4
        assert {snapshot_marker(file) for file in tmp_path.glob("vision.db.v4*.bak")} == {"A"}
    finally:
        source.close()


def test_hundred_distinct_entities_and_numeric_run_ids_use_one_batch(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), Settings(), connect=False
    )
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        store = app.state.store
        with store.transaction():
            for index in range(100):
                entity = f"automation.example_{index:03}"
                store.execute(
                    "INSERT INTO runs VALUES (?,?,NULL,1,'failed',0,'{}')", (entity, str(index))
                )
                store.issue(
                    "case:" + entity,
                    "automation",
                    "error",
                    "Synthetic failure",
                    {
                        "entity_id": entity,
                        "run_id": index,
                    },
                )
        queries = []
        before = store.db.total_changes
        store.db.set_trace_callback(queries.append)
        try:
            response = client.get("/api/cases?limit=100")
            assert response.status_code == 200
            rows = response.json()["items"]
            assert len(rows) == 100 and all(row["run_outcome"] == "failed" for row in rows)
            assert all("linked run no longer retained" not in row["summary"] for row in rows)
            assert len(queries) <= 5
            assert sum("FROM wanted JOIN runs" in query for query in queries) == 1
            assert not any("projection" in query for query in queries)
            assert store.db.total_changes == before
        finally:
            store.db.set_trace_callback(None)


def test_ephemeral_rule_metadata_cleanup_preserves_retained_evidence(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), Settings(), connect=False
    )
    with TestClient(app, client=("127.0.0.1", 123)):
        monitor, store = app.state.monitor, app.state.store
        monitor.record_structure(
            "automation.example",
            {"actions": [{"wait_template": "{{ omitted }}"}]},
            "current_config",
        )
        monitor.insights.refresh()
        key = "local_rule_coverage:automation.example"
        assert store.get_meta(key)["observed"] == 1
        issues = store.rows("SELECT * FROM issues")
        structures = store.rows("SELECT * FROM automation_structures")
        store.set_meta("counter:unrelated", {"count": 3})
        store.execute("DELETE FROM automation_current WHERE entity_id='automation.example'")
        monitor.insights.refresh()
        assert store.get_meta(key) is None
        assert store.rows("SELECT * FROM issues") == issues
        assert store.rows("SELECT * FROM automation_structures") == structures
        assert store.get_meta("counter:unrelated") == {"count": 3}
