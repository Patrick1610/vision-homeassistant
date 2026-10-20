import asyncio
import hashlib
import json
import re
import shutil
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from vision.config import Settings
from vision.evidence import HA_ACTION_PATH_LIMIT, dependency_graph, structure, trace_summary
from vision.ha import HAError
from vision.monitor import TRACE_FETCHES_PER_SYNC, Monitor, trace_outcome
from vision.security import MAX_REDACTION_INPUT, RedactingFormatter, Redactor
from vision.store import (
    DETAIL_BYTES_PER_ENTITY,
    DETAIL_BYTES_TOTAL,
    MIGRATIONS,
    SCHEMA_VERSION,
    Store,
)


def old_database(path):
    db = sqlite3.connect(path)
    db.executescript((Path(__file__).parent / "fixtures/vision_v1_schema.sql").read_text())
    db.execute("PRAGMA user_version=1")
    db.execute("INSERT INTO runs VALUES ('automation.example','old','context',1,'failed',1,'{}')")
    db.execute("INSERT INTO usage VALUES (1,1,'openai','test',NULL,NULL,.25,'reserved')")
    db.commit()
    return db


def make_monitor(path):
    store = Store(path)
    return Monitor(store, Settings(), SimpleNamespace(token=""), Redactor())


def known_trace(run_id, start, outcome="finished", **extra):
    return {
        "run_id": run_id,
        "script_execution": outcome,
        "timestamp": {"start": start},
        "trace": {"action/0": [{"result": {"done": True}}]},
        **extra,
    }


def test_migration_backup_is_private_consistent_original_and_restorable(tmp_path):
    path = tmp_path / "vision.db"
    old = old_database(path)
    # Keep a connection open so committed changes remain in the WAL during backup.
    old.execute("INSERT INTO meta VALUES ('wal_only','{\"preserved\":true}')")
    old.commit()
    store = Store(path)
    backup = tmp_path / "vision.db.pre-migration.bak"
    assert backup.stat().st_mode & 0o777 == 0o600
    original_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
    store.close()
    old.close()
    restored = tmp_path / "restored.db"
    shutil.copyfile(backup, restored)
    db = sqlite3.connect(restored)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    assert json.loads(db.execute("SELECT value FROM meta WHERE key='wal_only'").fetchone()[0])[
        "preserved"
    ]
    assert db.execute("SELECT status FROM usage").fetchone()[0] == "reserved"
    assert db.execute("SELECT run_id FROM runs").fetchone()[0] == "old"
    db.close()
    store = Store(path)
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == original_hash
    store.close()


def test_backup_failure_prevents_any_migration(tmp_path, monkeypatch):
    path = tmp_path / "vision.db"
    old_database(path).close()

    def unavailable(self, path):
        raise OSError("Synthetic backup failure")

    monkeypatch.setattr(Store, "migration_backup", unavailable)
    with pytest.raises(OSError):
        Store(path)
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    assert db.execute("SELECT status FROM usage").fetchone()[0] == "reserved"
    assert not db.execute(
        "SELECT name FROM sqlite_master WHERE name='automation_structures'"
    ).fetchall()
    db.close()


def test_fresh_and_frozen_v1_upgrade_have_identical_schema(tmp_path):
    fresh_path, upgraded_path = tmp_path / "fresh.db", tmp_path / "upgrade.db"
    old_database(upgraded_path).close()
    fresh, upgraded = Store(fresh_path), Store(upgraded_path)

    def schema(store):
        return [
            (row["type"], row["name"], re.sub(r"\s+", "", row["sql"] or "").lower())
            for row in store.rows(
                "SELECT type,name,sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            )
        ]

    assert schema(fresh) == schema(upgraded)
    assert upgraded.rows("PRAGMA user_version")[0]["user_version"] == SCHEMA_VERSION
    assert upgraded.rows("SELECT * FROM runs")[0]["run_id"] == "old"
    assert not fresh_path.with_name("fresh.db.pre-migration.bak").exists()
    fresh.close()
    upgraded.close()


def test_unpublished_schema2_run_details_survive_schema3_upgrade(tmp_path):
    path = tmp_path / "vision.db"
    db = old_database(path)
    for statement in MIGRATIONS[2]:
        db.execute(statement)
    db.execute("PRAGMA user_version=2")
    summary = trace_summary(
        {"trace": {"action/0": [{"error": "Synthetic error"}]}}, Redactor(), "failed"
    )
    db.execute(
        "INSERT INTO run_evidence VALUES ('automation.example','old',?)", (json.dumps(summary),)
    )
    db.commit()
    db.close()
    store = Store(path)
    assert (
        json.loads(store.rows("SELECT summary FROM run_evidence")[0]["summary"])["error_count"] == 1
    )
    assert store.rows("SELECT run_id FROM runs")[0]["run_id"] == "old"
    store.close()


def test_unknown_start_cannot_clear_or_suppress_genuine_latest_failure(tmp_path):
    monitor = make_monitor(tmp_path / "vision.db")
    monitor.save_trace("automation.example", {"run_id": "stub", "script_execution": "finished"})
    assert monitor.store.rows("SELECT started FROM runs")[0]["started"] is None
    monitor.save_trace(
        "automation.example",
        known_trace("new_failure", "2026-10-20T00:00:00Z", "error", error="Synthetic failure"),
    )
    monitor.save_trace("automation.example", {"run_id": "stub", "script_execution": "finished"})
    assert (
        monitor.store.rows("SELECT active FROM issues WHERE source='automation'")[0]["active"] == 1
    )
    monitor.save_trace("automation.example", known_trace("stub", "2026-10-01T00:00:00Z"))
    runs = monitor.store.rows("SELECT started FROM runs WHERE run_id='stub'")
    assert runs[0]["started"] == 1790812800
    assert (
        monitor.store.rows("SELECT active FROM issues WHERE source='automation'")[0]["active"] == 1
    )
    assert (
        monitor.store.rows("SELECT start_source FROM run_timing WHERE run_id='stub'")[0][
            "start_source"
        ]
        == "ha_trace"
    )
    monitor.store.close()


def test_stub_after_full_retains_steps_errors_and_context(tmp_path):
    monitor = make_monitor(tmp_path / "vision.db")
    trace = known_trace(
        "run", "2026-10-20T00:00:00Z", "started", state="running", context={"id": "context"}
    )
    trace["trace"]["action/0"][0]["error"] = "Synthetic continued error"
    monitor.save_trace("automation.example", trace)
    monitor.save_trace("automation.example", {"run_id": "run", "script_execution": "finished"})
    evidence = json.loads(monitor.store.rows("SELECT summary FROM run_evidence")[0]["summary"])
    assert evidence["coverage"]["full_trace_available"] and evidence["error_count"] == 1
    assert evidence["completed_with_errors"] and evidence["steps"]
    assert monitor.store.rows("SELECT context_id FROM runs")[0]["context_id"] == "context"
    monitor.store.close()


def test_unknown_error_run_never_replaces_proven_newer_error_link(tmp_path):
    monitor = make_monitor(tmp_path / "vision.db")
    newer = known_trace("proven", "2026-10-20T00:00:00Z")
    newer["trace"]["action/0"][0]["error"] = "Synthetic continued error"
    monitor.save_trace("automation.example", newer)
    monitor.save_trace(
        "automation.example",
        {
            "run_id": "unknown",
            "script_execution": "finished",
            "trace": {"action/0": [{"error": "Unknown-time continued error"}]},
        },
    )
    issue = monitor.store.rows("SELECT detail FROM issues WHERE source='automation_step'")[0]
    assert json.loads(issue["detail"])["run_id"] == "proven"
    monitor.save_trace("automation.example", known_trace("next", "2026-10-20T01:00:00Z"))
    assert (
        monitor.store.rows("SELECT active FROM issues WHERE source='automation_step'")[0]["active"]
        == 1
    )
    monitor.store.close()


def test_loop_abort_uses_chronological_evidence_not_last_inserted_false_branch():
    trace = {
        "script_execution": "aborted",
        "last_step": "action/0/repeat/sequence/1/choose/0/conditions/0",
        "trace": {
            "action/0/repeat/sequence/0": [
                {"timestamp": "2026-10-20T00:00:01Z", "result": {"wait": {"completed": True}}},
                {
                    "timestamp": "2026-10-20T00:00:03Z",
                    "error": "TimeoutError",
                    "result": {"timeout": True},
                },
            ],
            "action/0/repeat/sequence/1/choose/0/conditions/0": [
                {"timestamp": "2026-10-20T00:00:02Z", "result": {"result": False}}
            ],
        },
    }
    assert trace_outcome(trace) == "stopped"
    assert trace_summary(trace, Redactor(), "stopped")["errors"][0]["kind"] == "timeout"
    # With no chronological evidence the false branch still cannot establish a stop cause.
    for elements in trace["trace"].values():
        for element in elements:
            element.pop("timestamp")
    assert trace_outcome(trace) == "stopped"


def test_upstream_path_cap_is_unknown_and_cannot_resolve_prior_step_error(tmp_path):
    monitor = make_monitor(tmp_path / "vision.db")
    failed = known_trace("first", "2026-10-19T00:00:00Z")
    failed["trace"]["action/0"][0]["error"] = "Synthetic continued error"
    monitor.save_trace("automation.example", failed)
    capped = known_trace("second", "2026-10-20T00:00:00Z")
    capped["trace"]["action/0/repeat/sequence/0"] = [
        {"result": {"done": True}}
    ] * HA_ACTION_PATH_LIMIT
    summary = trace_summary(capped, Redactor(), "succeeded")
    assert summary["coverage"]["source_path_limit_reached"]
    assert summary["coverage"]["error_count_is_lower_bound"]
    monitor.save_trace("automation.example", capped)
    assert (
        monitor.store.rows("SELECT active FROM issues WHERE source='automation_step'")[0]["active"]
        == 1
    )
    monitor.store.close()


def test_path_shapes_error_counts_and_nested_reference_coverage():
    trace = {
        "trace": {
            "action/0/wait_for_trigger/0": [
                {"error": "error", "template_errors": ["template"] * 10}
            ],
            "action/1/parallel/0/sequence/0": [{"result": {"done": True}}],
            "unknown/private_a": [{}],
            "unknown/private_b": [{}],
        }
    }
    summary = trace_summary(trace, Redactor(), "failed")
    assert summary["steps"][0]["path"] == "action/0/wait_for_trigger/0"
    assert summary["steps"][0]["errors_observed"] == 11
    assert summary["steps"][0]["errors_retained"] == 10
    assert (
        summary["coverage"]["errors_truncated"] and summary["coverage"]["unrecognized_paths"] == 2
    )
    assert summary["steps"][2]["path"] != summary["steps"][3]["path"]
    assert "private_" not in json.dumps(summary)
    projection = structure(
        {
            "actions": [
                {
                    "action": "light.turn_on",
                    "data": {"nested": [{"nested": [{"entity_id": "light.example"}]}]},
                }
            ]
        }
    )
    assert projection["referenced_entities"] == ["light.example"]
    assert "bounded" in projection["coverage"]["reference_scan"]


def test_unlimited_logging_redaction_is_bounded_fast_and_has_intact_marker():
    import logging

    formatter = RedactingFormatter(logging.Formatter("%(message)s"), Redactor(["private-secret"]))
    started = time.monotonic()
    record = logging.LogRecord(
        "synthetic", logging.ERROR, "", 1, "prefix " + "x" * 1000000 + " private-secret", (), None
    )
    result = formatter.format(record)
    assert time.monotonic() - started < 1
    assert len(result) <= MAX_REDACTION_INPUT
    assert result.endswith("[TRUNCATED]") and "private-secret" not in result
    assert Redactor().text("x" * 10000, 80) == "[TRUNCATED]"
    expanded = Redactor().text("http://a " * 100, 80)
    assert len(expanded) <= 80 and expanded.endswith("[TRUNCATED]")


def test_unchanged_large_graph_only_refreshes_one_meta_row(tmp_path):
    store = Store(tmp_path / "vision.db")
    entities = {f"sensor.example_{index}": {} for index in range(5000)}
    registry = {
        key: {"platform": "synthetic", "device_id": f"device_{index // 10}"}
        for index, key in enumerate(entities)
    }
    graph = dependency_graph(entities, registry, [], {})
    assert store.replace_graph(graph, 1)
    before = store.db.total_changes
    rows = store.rows("SELECT rowid,key FROM dependency_nodes ORDER BY key")
    assert not store.replace_graph(graph, 2)
    assert store.db.total_changes - before <= 2
    assert store.rows("SELECT rowid,key FROM dependency_nodes ORDER BY key") == rows
    assert store.get_meta("dependencies_observed_at") == 2
    store.close()


class TraceHA:
    def __init__(self, failure=False, slow=False):
        self.calls = []
        self.failure, self.slow = failure, slow

    async def read(self, command, **params):
        self.calls.append(params["item_id"])
        if self.slow:
            await asyncio.sleep(1)
        if self.failure:
            raise HAError("capability_unavailable")
        return {"run_id": params["run_id"], "script_execution": "finished", "trace": {}}


def trace_inventory(monitor, count):
    traces = []
    for index in range(count):
        automation_id = f"example_{index:03}"
        monitor.entities["automation." + automation_id] = {
            "entity_id": "automation." + automation_id,
            "automation_id": automation_id,
        }
        traces.append({"item_id": automation_id, "run_id": "run", "script_execution": "finished"})
    return traces


async def test_detail_reads_are_bounded_and_round_robin_is_fair(tmp_path):
    monitor = make_monitor(tmp_path / "vision.db")
    traces = trace_inventory(monitor, 30)
    ha = TraceHA()
    for cycle in range(3):
        # Busy early automation adds new runs every cycle; later entries must progress.
        traces[0]["run_id"] = f"busy_{cycle}"
        before = len(ha.calls)
        await monitor.sync_traces(ha, traces)
        assert len(ha.calls) - before <= TRACE_FETCHES_PER_SYNC
    assert "example_029" in ha.calls
    assert monitor.store.get_meta("trace_fetch_status")["pending"] < 5
    monitor.store.close()


async def test_unavailable_capability_has_one_backed_off_probe_and_recovers_after_restart(
    tmp_path, monkeypatch
):
    path = tmp_path / "vision.db"
    monitor = make_monitor(path)
    traces = trace_inventory(monitor, 30)
    clock = [1800000000.0]
    monkeypatch.setattr("vision.monitor.time.time", lambda: clock[0])
    ha = TraceHA(failure=True)
    await monitor.sync_traces(ha, traces)
    await monitor.sync_traces(ha, traces)
    assert len(ha.calls) == 1
    monitor.store.close()
    monitor = make_monitor(path)
    trace_inventory(monitor, 30)
    await monitor.sync_traces(ha, traces)
    assert len(ha.calls) == 1
    for _ in range(29):
        clock[0] += 4000
        await monitor.sync_traces(ha, traces)
    assert len(set(ha.calls)) == 30  # Fair even while every capability probe fails.
    ha.failure = False
    for _ in range(3):
        clock[0] += 4000
        await monitor.sync_traces(ha, traces)
    assert monitor.store.get_meta("trace_fetch_status")["pending"] == 0
    monitor.store.close()


async def test_slow_trace_read_cannot_fan_out_or_stall_poll(tmp_path, monkeypatch):
    monitor = make_monitor(tmp_path / "vision.db")
    traces = trace_inventory(monitor, 30)
    monkeypatch.setattr("vision.monitor.TRACE_FETCH_TIMEOUT", 0.01)
    ha = TraceHA(slow=True)
    started = time.monotonic()
    await monitor.sync_traces(ha, traces)
    assert time.monotonic() - started < 0.5
    assert len(ha.calls) == 1
    monitor.store.close()


async def test_one_expired_trace_does_not_poison_other_automation_reads(tmp_path):
    class MixedHA(TraceHA):
        async def read(self, command, **params):
            if params["item_id"] == "example_000":
                self.calls.append(params["item_id"])
                raise HAError("read_not_found")
            return await super().read(command, **params)

    monitor = make_monitor(tmp_path / "vision.db")
    traces = trace_inventory(monitor, 30)
    ha = MixedHA()
    for _ in range(3):
        await monitor.sync_traces(ha, traces)
    assert "example_029" in ha.calls
    assert monitor.store.get_meta("trace_fetch_status")["pending"] == 1
    assert monitor.store.get_meta("trace_fetch_circuit")["next_probe"] == 0
    monitor.store.close()


def test_aggregate_detail_budget_preserves_all_runs_and_compacted_counts(tmp_path):
    path = tmp_path / "vision.db"
    monitor = make_monitor(path)
    # More than 32 MiB of candidate detail across 200 automations; no raw HA fixtures.
    errors = [{"error": "Synthetic error " + "x" * 780} for _ in range(20)]
    for entity in range(200):
        for run in range(10):
            trace = known_trace(f"run_{run}", f"2026-10-20T00:{run:02}:00Z")
            trace["trace"] = {"action/0": errors}
            monitor.save_trace(f"automation.example_{entity}", trace)
    store = monitor.store
    assert store.rows("SELECT count(*) count FROM runs")[0]["count"] == 2000
    assert (
        store.rows("SELECT sum(stored_bytes) size FROM run_evidence")[0]["size"]
        <= DETAIL_BYTES_TOTAL
    )
    assert (
        store.rows(
            "SELECT max(size) size FROM (SELECT sum(stored_bytes) size "
            "FROM run_evidence GROUP BY entity_id)"
        )[0]["size"]
        <= DETAIL_BYTES_PER_ENTITY
    )
    assert store.rows("SELECT count(*) count FROM run_evidence WHERE compacted=1")[0]["count"] > 0
    sample = json.loads(
        store.rows("SELECT summary FROM run_evidence WHERE compacted=1 LIMIT 1")[0]["summary"]
    )
    assert sample["error_count"] == 20 and sample["coverage"]["details_compacted"]
    store.close()
    assert path.stat().st_size < 16 * 1024 * 1024


def test_run_config_association_survives_historical_structure_and_pruning(tmp_path):
    monitor = make_monitor(tmp_path / "vision.db")
    monitor.record_structure(
        "automation.example", {"actions": [{"action": "light.turn_off"}]}, "current_config"
    )
    trace = known_trace(
        "old_config", "2026-10-20T00:00:00Z", config={"actions": [{"action": "light.turn_on"}]}
    )
    monitor.save_trace("automation.example", trace)
    assert monitor.structures["automation.example"]["nodes"][0]["service"] == "light.turn_off"
    linked = monitor.store.rows(
        "SELECT s.projection FROM run_structures r "
        "JOIN automation_structures s ON s.id=r.structure_id"
    )
    assert json.loads(linked[0]["projection"])["nodes"][0]["service"] == "light.turn_on"
    monitor.store.execute("UPDATE automation_structures SET last_seen=0")
    monitor.store.prune(730)
    assert monitor.store.rows("SELECT * FROM run_structures")
    monitor.store.close()


def test_compact_metadata_overflow_preserves_run_counts_and_resists_stubs(tmp_path, monkeypatch):
    monkeypatch.setattr("vision.store.DETAIL_BYTES_TOTAL", 4096)
    monitor = make_monitor(tmp_path / "vision.db")
    for index in range(30):
        trace = known_trace(f"run_{index}", f"2026-10-20T00:{index:02}:00Z")
        trace["trace"]["action/0"][0]["error"] = "Synthetic continued error"
        monitor.save_trace("automation.example", trace)
    rows = monitor.store.rows(
        "SELECT run_id,detail FROM runs WHERE detail LIKE '%_vision_evidence%'"
    )
    assert rows and len(monitor.store.rows("SELECT * FROM runs")) == 30
    row = rows[0]
    compacted = json.loads(row["detail"])["_vision_evidence"]
    assert compacted["error_count"] == 1 and compacted["coverage"]["details_compacted"]
    monitor.save_trace(
        "automation.example", {"run_id": row["run_id"], "script_execution": "finished"}
    )
    detail = json.loads(
        monitor.store.rows("SELECT detail FROM runs WHERE run_id=?", (row["run_id"],))[0]["detail"]
    )
    assert detail["_vision_evidence"]["error_count"] == 1
    assert monitor.store.rows("SELECT sum(stored_bytes) size FROM run_evidence")[0]["size"] <= 4096
    monitor.store.close()
