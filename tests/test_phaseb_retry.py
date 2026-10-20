"""Bounded migration retries and constant-load case pages; no external data."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.store import (
    MAX_SNAPSHOTS_PER_VERSION,
    MIGRATIONS,
    SNAPSHOT_FREE_RESERVE,
    STORAGE_FAILURES,
    StorageStartupError,
    Store,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def legacy(path):
    db = sqlite3.connect(path)
    db.executescript((Path(__file__).parent / "fixtures/vision_v1_schema.sql").read_text())
    db.execute("PRAGMA user_version=1")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA wal_autocheckpoint=0")
    db.execute("INSERT INTO meta VALUES ('synthetic','A')")
    db.execute("INSERT INTO usage VALUES (1,1,'anthropic','model',NULL,NULL,.4,'reserved')")
    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return db


def fail_migration(monkeypatch):
    monkeypatch.setitem(MIGRATIONS, 2, MIGRATIONS[2] + ("INTENTIONAL INVALID MIGRATION",))


def full_copies(tmp_path):
    files = list(tmp_path.glob("vision.db*.bak"))
    return {(file.stat().st_dev, file.stat().st_ino): file.stat().st_size for file in files}


def read_marker(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        return db.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()[0]


def test_failed_migration_restarts_reuse_identical_consistent_snapshot_and_see_wal(
    tmp_path, monkeypatch
):
    path = tmp_path / "vision.db"
    source = legacy(path)
    fail_migration(monkeypatch)
    try:
        initial_main = digest(path)
        snapshots = []
        for _ in range(10):
            with pytest.raises(sqlite3.OperationalError):
                Store(path)
            snapshots.append(full_copies(tmp_path))
            assert not list(tmp_path.glob("*.backup-*"))
            assert source.execute("PRAGMA user_version").fetchone()[0] == 1
            assert source.execute("SELECT cost_usd,status FROM usage").fetchone() == (
                0.4,
                "reserved",
            )
        assert len(snapshots[0]) == 1 and all(value == snapshots[0] for value in snapshots)
        original = tmp_path / "vision.db.pre-migration.bak"
        original_hash = digest(original)
        assert read_marker(original) == "A"
        source.execute("UPDATE meta SET value='B' WHERE key='synthetic'")
        source.commit()  # The committed change remains WAL-only while this connection stays open.
        assert digest(path) == initial_main
        with pytest.raises(sqlite3.OperationalError):
            Store(path)
        assert len(full_copies(tmp_path)) == 2
        assert {read_marker(file) for file in tmp_path.glob("vision.db.v1*.bak")} == {"A", "B"}
        assert digest(original) == original_hash
        before = full_copies(tmp_path)
        with pytest.raises(sqlite3.OperationalError):
            Store(path)
        assert full_copies(tmp_path) == before
        assert not list(tmp_path.glob("*.backup-*"))
    finally:
        source.close()


def test_changed_source_at_retained_snapshot_limit_fails_without_stale_reuse(tmp_path, monkeypatch):
    path = tmp_path / "vision.db"
    source = legacy(path)
    fail_migration(monkeypatch)
    try:
        for index in range(MAX_SNAPSHOTS_PER_VERSION):
            source.execute("UPDATE meta SET value=? WHERE key='synthetic'", (str(index),))
            source.commit()
            with pytest.raises(sqlite3.OperationalError):
                Store(path)
        assert len(full_copies(tmp_path)) == MAX_SNAPSHOTS_PER_VERSION
        before = full_copies(tmp_path)
        # At the limit, identical sources still reuse their snapshot.
        with pytest.raises(sqlite3.OperationalError):
            Store(path)
        assert full_copies(tmp_path) == before
        source.execute("UPDATE meta SET value='newer' WHERE key='synthetic'")
        source.commit()
        with pytest.raises(StorageStartupError) as error:
            Store(path)
        assert error.value.code == "snapshot_budget"
        assert full_copies(tmp_path) == before
        assert not list(tmp_path.glob("*.backup-*"))
        assert (
            source.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()[0] == "newer"
        )
        assert source.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        source.close()


@pytest.mark.parametrize("valid_sqlite", [False, True])
def test_exact_operator_collision_is_never_overwritten_chmodded_or_used_stale(
    tmp_path, valid_sqlite
):
    path = tmp_path / "vision.db"
    source = legacy(path)
    collision = tmp_path / "vision.db.v1.bak"
    try:
        if valid_sqlite:
            with sqlite3.connect(collision) as backup:
                source.backup(backup)
        else:
            collision.write_bytes(b"Operator-owned file")
        collision.chmod(0o644)
        before = collision.read_bytes(), collision.stat().st_mode
        source.execute("UPDATE meta SET value='current' WHERE key='synthetic'")
        source.commit()
        store = Store(path)
        store.close()
        assert (collision.read_bytes(), collision.stat().st_mode) == before
        fresh = [file for file in tmp_path.glob("vision.db.v1-*.bak")]
        assert len(fresh) == 1 and read_marker(fresh[0]) == "current"
        assert fresh[0].stat().st_mode & 0o777 == 0o600
        assert read_marker(tmp_path / "vision.db.pre-migration.bak") == "current"
    finally:
        source.close()


@pytest.mark.parametrize("reason", ["space", "bytes"])
def test_snapshot_capacity_gate_precedes_copy_and_schema_change(tmp_path, monkeypatch, reason):
    path = tmp_path / "vision.db"
    source = legacy(path)
    before = digest(path)
    estimate = (
        source.execute("PRAGMA page_count").fetchone()[0]
        * source.execute("PRAGMA page_size").fetchone()[0]
    )
    if reason == "space":
        monkeypatch.setattr(
            "vision.store.shutil.disk_usage",
            lambda _: SimpleNamespace(
                free=estimate + SNAPSHOT_FREE_RESERVE - 1,
            ),
        )
    else:
        monkeypatch.setattr("vision.store.MAX_SNAPSHOT_BYTES", estimate - 1)

    def forbidden_copy(*args):
        pytest.fail("Capacity must be checked before copying")

    monkeypatch.setattr(Store, "write_snapshot", forbidden_copy)
    try:
        with pytest.raises(StorageStartupError) as error:
            Store(path)
        assert error.value.code == ("snapshot_space" if reason == "space" else "snapshot_too_large")
        assert not full_copies(tmp_path) and not list(tmp_path.glob("*.backup-*"))
        assert digest(path) == before
        assert source.execute("PRAGMA user_version").fetchone()[0] == 1
        assert source.execute("SELECT cost_usd,status FROM usage").fetchone() == (0.4, "reserved")
    finally:
        source.close()


def test_partial_snapshot_is_cleaned_and_never_published(tmp_path, monkeypatch):
    path = tmp_path / "vision.db"
    source = legacy(path)

    def partial_copy(self, temporary):
        temporary.write_bytes(b"Partial synthetic data")
        raise OSError("Synthetic private-path secret must never reach app logs")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Store, "write_snapshot", partial_copy)
            with pytest.raises(OSError):
                Store(path)
        assert not full_copies(tmp_path) and not list(tmp_path.glob("*.backup-*"))
        assert source.execute("PRAGMA user_version").fetchone()[0] == 1
        store = Store(path)
        store.close()
        assert len(full_copies(tmp_path)) == 1
    finally:
        source.close()


def test_uncertain_crash_snapshot_stops_before_another_copy_without_touching_file(
    tmp_path, monkeypatch
):
    path = tmp_path / "vision.db"
    source = legacy(path)
    leftover = tmp_path / "vision.db.backup-uncertain"
    leftover.write_bytes(b"Uncertain crash or operator bytes")
    leftover.chmod(0o644)
    before = leftover.read_bytes(), leftover.stat().st_mode

    def forbidden_copy(*args):
        pytest.fail("Uncertain temporary copies must block another allocation")

    monkeypatch.setattr(Store, "write_snapshot", forbidden_copy)
    try:
        with pytest.raises(StorageStartupError) as error:
            Store(path)
        assert error.value.code == "snapshot_pending"
        assert (leftover.read_bytes(), leftover.stat().st_mode) == before
        assert not full_copies(tmp_path)
        assert source.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        source.close()


def test_app_startup_exposes_only_allowlisted_capacity_reason(tmp_path, monkeypatch):
    source = legacy(tmp_path / "vision.db")
    monkeypatch.setattr("vision.store.shutil.disk_usage", lambda _: SimpleNamespace(free=0))
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="synthetic-private-token")
    app = create_app(runtime, Settings(), connect=False)
    try:
        with pytest.raises(RuntimeError) as error, TestClient(app):
            pass
        assert str(error.value) == STORAGE_FAILURES["snapshot_space"]
        assert str(tmp_path) not in str(error.value) and "synthetic-private-token" not in str(
            error.value
        )
        assert error.value.__cause__ is None
    finally:
        source.close()


def test_legacy_large_coverage_map_becomes_bounded_summary_with_targeted_details(tmp_path):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    app = create_app(runtime, Settings(), connect=False)
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        store = app.state.store
        store.save_structure(
            "automation.example_2999",
            {
                "nodes": [],
                "references": [],
                "coverage": {},
            },
            "current_config",
        )
        app.state.insights.refresh_rules()
        store.set_meta(
            "local_rules_coverage",
            {
                "observed": 120000,
                "retained": 500,
                "omitted": 119500,
                "truncated": True,
                "automations_limited": {
                    f"automation.example_{index}": {
                        "observed": 40,
                        "retained": 0,
                        "omitted": 40,
                    }
                    for index in range(3000)
                },
            },
        )
        app.state.insights.refresh_rules()  # Monitor write boundary, never a GET conversion.
        summary = store.get_meta("local_rules_coverage")
        assert "automations_limited" not in summary and summary["automations_limited_count"] == 3000
        before = store.db.total_changes
        for route in ("/api/cases", "/api/overview"):
            response = client.get(route)
            assert response.status_code == 200
            value = response.json()
            coverage = (
                value["rule_coverage"]
                if route == "/api/cases"
                else value["local"]["cases"]["rule_coverage"]
            )
            assert len(json.dumps(coverage).encode()) < 1024
            assert coverage["observed"] == 120000 and coverage["omitted"] == 119500
            assert coverage["retained"] == 500 and coverage["automations_limited_count"] == 3000
        assert store.db.total_changes == before
        app.state.monitor.observe_state(
            {"entity_id": "automation.example_2999", "state": "on", "attributes": {}}
        )
        detail = client.get("/api/investigation/automation.example_2999").json()
        assert detail["structure_coverage"]["local_rule_selection"]["omitted"] == 40


@pytest.mark.parametrize("missing_only", [False, True])
def test_hundred_run_linked_cards_batch_present_duplicate_missing_and_malformed_runs(
    tmp_path, missing_only
):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    app = create_app(runtime, Settings(), connect=False)
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        store = app.state.store
        with store.transaction():
            for index in range(60):
                store.execute(
                    "INSERT INTO runs VALUES ('automation.example',?,NULL,?,'failed',0,'{}')",
                    (f"r{index}", time.time()),
                )
                store.execute(
                    "INSERT INTO run_timing VALUES ('automation.example',?,?,'ha_trace')",
                    (f"r{index}", time.time()),
                )
            raw = json.dumps({"errors": [None], "error_count": 1})
            store.execute(
                "INSERT INTO run_evidence VALUES ('automation.example','r0',?,?,0)",
                (raw, len(raw.encode())),
            )
            for index in range(100):
                run_id = f"r{index % 60}" if index < 80 and not missing_only else f"missing{index}"
                store.issue(
                    f"example:{index:03}",
                    "automation",
                    "error",
                    "Synthetic failed run",
                    {
                        "entity_id": "automation.example",
                        "run_id": run_id,
                    },
                )
        before = store.db.total_changes
        queries = []
        store.db.set_trace_callback(queries.append)
        try:
            for route, budget in (("/api/cases?limit=100", 5), ("/api/overview", 14)):
                queries.clear()
                response = client.get(route)
                assert response.status_code == 200
                assert len(queries) <= budget, queries
                assert sum("FROM wanted JOIN runs" in query for query in queries) == 1
                assert not any(
                    "projection" in query or "row_number()" in query for query in queries
                )
                if route.startswith("/api/cases"):
                    rows = response.json()["items"]
                    assert len(rows) == 100
                    assert sum(
                        "linked run no longer retained" in row["summary"] for row in rows
                    ) == (100 if missing_only else 20)
                    if not missing_only:
                        assert (
                            "unknown"
                            in next(row for row in rows if row["key"] == "example:000")[
                                "summary"
                            ].lower()
                        )
            assert store.db.total_changes == before
            with sqlite3.connect(tmp_path / "vision.db", timeout=0.1) as writer:
                writer.execute("BEGIN IMMEDIATE")
                assert client.get("/api/cases?limit=100").status_code == 200
                writer.rollback()
        finally:
            store.db.set_trace_callback(None)
