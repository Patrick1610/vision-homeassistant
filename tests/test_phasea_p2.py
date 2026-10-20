import hashlib
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from vision.config import Settings
from vision.evidence import fingerprint, structure, trace_summary
from vision.ha import HAError
from vision.monitor import Monitor, decisive_condition_stop, trace_outcome
from vision.security import Redactor
from vision.store import MIGRATIONS, SCHEMA_VERSION, Store


@pytest.fixture
def monitor(tmp_path):
    store = Store(tmp_path / "vision.db")
    value = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor())
    yield value
    store.close()


def trace(run_id, execution="finished", continued_error=False):
    element = {"result": {"done": True}}
    if continued_error:
        element["error"] = "Synthetic continued error"
    return {
        "run_id": run_id,
        "script_execution": execution,
        "timestamp": {"start": "2026-10-20T00:00:00Z"},
        "trace": {"action/0": [element]},
    }


def legacy_run(monitor, execution="succeeded", source=None):
    monitor.store.execute(
        "INSERT INTO runs VALUES ('automation.example','legacy',NULL,2000000000,?,0,'{}')",
        (execution,),
    )
    if source:
        monitor.store.execute(
            "INSERT INTO run_timing VALUES ('automation.example','legacy',2000000000,?)",
            (source,),
        )


@pytest.mark.parametrize("source", [None, "unknown"])
def test_legacy_nonnull_success_cannot_clear_proven_failure(monitor, source):
    monitor.save_trace("automation.example", trace("proven", "error"))
    assert (
        monitor.store.rows("SELECT active FROM issues WHERE source='automation'")[0]["active"] == 1
    )
    legacy_run(monitor, source=source)
    monitor.save_trace("automation.example", {"run_id": "legacy", "script_execution": "finished"})
    issue = monitor.store.rows("SELECT active,detail FROM issues WHERE source='automation'")[0]
    assert issue["active"] == 1 and json.loads(issue["detail"])["run_id"] == "proven"


@pytest.mark.parametrize("source", [None, "unknown"])
def test_legacy_nonnull_success_cannot_suppress_new_proven_failure(monitor, source):
    legacy_run(monitor, source=source)
    monitor.save_trace("automation.example", trace("proven", "error"))
    issue = monitor.store.rows("SELECT active,detail FROM issues WHERE source='automation'")
    assert issue and issue[0]["active"] == 1
    assert json.loads(issue[0]["detail"])["run_id"] == "proven"


def test_legacy_nonnull_error_free_stub_cannot_clear_proven_step_error(monitor):
    monitor.save_trace("automation.example", trace("proven", continued_error=True))
    legacy_run(monitor)
    monitor.save_trace(
        "automation.example",
        {
            "run_id": "legacy",
            "script_execution": "finished",
            "trace": {"action/0": [{"result": {"done": True}}]},
        },
    )
    issue = monitor.store.rows("SELECT active,detail FROM issues WHERE source='automation_step'")[0]
    assert issue["active"] == 1 and json.loads(issue["detail"])["run_id"] == "proven"


def test_proven_success_does_not_claim_resolution_of_unordered_legacy_failure(monitor):
    legacy_run(monitor, "failed")
    monitor.store.execute("UPDATE runs SET started=1 WHERE run_id='legacy'")
    monitor.store.issue(
        "automation:automation.example", "automation", "error", "Synthetic", {"run_id": "legacy"}
    )
    monitor.save_trace("automation.example", trace("proven_success"))
    assert (
        monitor.store.rows("SELECT active FROM issues WHERE source='automation'")[0]["active"] == 1
    )


def test_compacted_running_error_updates_on_finished_stub_and_survives_restart(monitor):
    monitor.save_trace(
        "automation.example", {**trace("running", "started", True), "state": "running"}
    )
    row = monitor.store.rows("SELECT * FROM run_evidence")[0]
    with monitor.store.transaction():
        monitor.store.compact_evidence_row(row, move_to_run=True)
    assert not monitor.store.rows("SELECT * FROM run_evidence")
    before = json.loads(monitor.store.rows("SELECT detail FROM runs")[0]["detail"])[
        "_vision_evidence"
    ]
    assert not before["completed_with_errors"] and before["error_count"] == 1
    monitor.save_trace("automation.example", {"run_id": "running", "script_execution": "finished"})
    run = monitor.store.rows("SELECT * FROM runs")[0]
    summary = json.loads(run["detail"])["_vision_evidence"]
    assert run["outcome"] == "succeeded" and summary["completed_with_errors"]
    assert summary["error_count"] == 1 and summary["coverage"]["details_compacted"]
    issue = json.loads(
        monitor.store.rows("SELECT detail FROM issues WHERE source='automation_step'")[0]["detail"]
    )
    assert issue["completed_with_errors"]
    assert not monitor.store.rows("SELECT * FROM run_evidence")
    assert monitor.store.get_meta("run_evidence_bytes") == 0
    db_path = monitor.store.db.execute("PRAGMA database_list").fetchone()[2]
    independent = Store(Path(db_path))
    try:
        retained = json.loads(independent.rows("SELECT detail FROM runs")[0]["detail"])[
            "_vision_evidence"
        ]
        assert retained["completed_with_errors"] and retained["error_count"] == 1
    finally:
        independent.close()


def test_standalone_action_condition_stop_uses_latest_false_result_without_path_name():
    value = {
        "script_execution": "aborted",
        "last_step": "action/2",
        "trace": {
            "action/2": [{"timestamp": "2026-10-20T00:00:00Z", "result": {"result": False}}],
        },
    }
    assert trace_outcome(value) == "condition_stopped"
    assert trace_outcome({"script_execution": "failed_conditions"}) == "condition_stopped"


@pytest.mark.parametrize("malformed", [None, [], "malformed"])
def test_terminal_error_veto_is_unconditional_for_malformed_results(malformed):
    tree = {
        "action/1": [{"timestamp": "2026-10-20T00:00:00Z", "result": {"result": False}}],
        "action/2": [
            {"timestamp": "2026-10-20T00:00:00Z", "error": "Synthetic error", "result": malformed}
        ],
    }
    assert not decisive_condition_stop(tree)
    assert trace_outcome({"script_execution": "aborted", "trace": tree}) == "stopped"


def test_parallel_timeout_is_not_masked_by_a_later_started_false_branch():
    last_step = "action/0/parallel/1/sequence/1/choose/0/conditions/0"
    value = {
        "script_execution": "aborted",
        "last_step": last_step,
        "trace": {
            "action/0": [{"timestamp": "2026-10-20T00:00:00Z", "error": "TimeoutError"}],
            "action/0/parallel/0/sequence/0": [
                {
                    "timestamp": "2026-10-20T00:00:00Z",
                    "error": "TimeoutError",
                    "result": {"timeout": True},
                }
            ],
            last_step: [{"timestamp": "2026-10-20T00:00:01Z", "result": {"result": False}}],
        },
    }
    assert trace_outcome(value) == "stopped"
    summary = trace_summary(value, Redactor(), trace_outcome(value))
    assert any(error["kind"] == "timeout" for error in summary["errors"])
    assert summary["coverage"]["step_timestamp_semantics"] == "step_start"
    assert summary["coverage"]["abort_reason_unknown"]


def test_parallel_abort_without_error_does_not_make_a_false_branch_the_stop_reason():
    last_step = "action/0/parallel/1/sequence/1/choose/0/conditions/0"
    value = {
        "script_execution": "aborted",
        "last_step": last_step,
        "trace": {
            "action/0/parallel/0/sequence/0": [
                {
                    "timestamp": "2026-10-20T00:00:00Z",
                    "result": {"wait": {"completed": False, "remaining": 10}},
                }
            ],
            last_step: [{"timestamp": "2026-10-20T00:00:01Z", "result": {"result": False}}],
        },
    }
    assert trace_outcome(value) == "stopped"
    summary = trace_summary(value, Redactor(), trace_outcome(value))
    assert not summary["errors"] and summary["error_count"] == 0
    assert summary["coverage"]["step_timestamp_semantics"] == "step_start"
    assert summary["coverage"]["abort_reason_unknown"]


async def test_identical_list_stubs_do_not_rewrite_runs_during_backoff(monitor):
    class UnavailableHA:
        calls = 0

        async def read(self, command, **params):
            self.calls += 1
            raise HAError("capability_unavailable")

    ha = UnavailableHA()
    traces = []
    for index in range(100):
        entity_id = f"automation.example_{index}"
        monitor.entities[entity_id] = {"entity_id": entity_id, "automation_id": str(index)}
        traces.append({"item_id": str(index), "run_id": "run", "script_execution": "finished"})
    await monitor.sync_traces(ha, traces)
    previous = monitor.store.rows("SELECT * FROM runs ORDER BY entity_id")
    timings = monitor.store.rows("SELECT * FROM run_timing ORDER BY entity_id")
    changes = monitor.store.db.total_changes
    await monitor.sync_traces(ha, traces)
    assert ha.calls == 1 and monitor.store.db.total_changes - changes <= 4
    assert monitor.store.rows("SELECT * FROM runs ORDER BY entity_id") == previous
    assert monitor.store.rows("SELECT * FROM run_timing ORDER BY entity_id") == timings
    traces[0]["script_execution"] = "error"
    await monitor.sync_traces(ha, traces)
    assert (
        monitor.store.rows("SELECT outcome FROM runs WHERE entity_id='automation.example_0'")[0][
            "outcome"
        ]
        == "failed"
    )
    assert ha.calls == 1


def test_trace_configuration_is_projected_once(monitor, monkeypatch):
    calls = []

    def project(value):
        calls.append(value)
        return structure(value)

    monkeypatch.setattr("vision.monitor.structure", project)
    config = {"actions": [{"action": "light.turn_on"}]}
    monitor.save_trace("automation.example", {**trace("configured"), "config": config})
    assert calls == [config]
    summary = json.loads(monitor.store.rows("SELECT summary FROM run_evidence")[0]["summary"])
    assert summary["configuration_digest"] == fingerprint(structure(config))


async def test_registry_redaction_only_repeats_for_changed_entries(monitor, monkeypatch):
    registry = [
        {
            "entity_id": f"sensor.example_{index}",
            "device_id": f"device_{index}",
            "platform": "synthetic",
        }
        for index in range(100)
    ]

    class HA:
        async def read(self, command, **params):
            if command == "config/entity_registry/list":
                return registry
            if command == "repairs/list_issues":
                return {"issues": []}
            return []

    cleaned = []
    original = monitor.redactor.clean

    def clean(value, depth=0):
        if isinstance(value, dict) and set(value) == {"device_id", "disabled_by", "platform"}:
            cleaned.append(value)
        return original(value, depth)

    monkeypatch.setattr(monitor.redactor, "clean", clean)
    ha = HA()
    await monitor.sync(ha)
    assert len(cleaned) == 100
    await monitor.sync(ha)
    assert len(cleaned) == 100
    registry[0]["device_id"] = "changed_device"
    await monitor.sync(ha)
    assert len(cleaned) == 101


def test_rich_detail_replaces_stale_moved_metadata(monitor):
    monitor.save_trace("automation.example", trace("run", "started", True))
    row = monitor.store.rows("SELECT * FROM run_evidence")[0]
    with monitor.store.transaction():
        monitor.store.compact_evidence_row(row, move_to_run=True)
    monitor.save_trace("automation.example", trace("run", "finished", True))
    retained = json.loads(monitor.store.rows("SELECT detail FROM runs")[0]["detail"])
    assert "_vision_evidence" not in retained
    summary = json.loads(monitor.store.rows("SELECT summary FROM run_evidence")[0]["summary"])
    assert summary["steps"] and summary["error_count"] == 1 and summary["completed_with_errors"]


def test_unknown_time_blocker_is_visible_without_changing_incident_history(monitor):
    monitor.save_trace(
        "automation.example",
        {
            "run_id": "unknown",
            "script_execution": "error",
            "trace": {"action/0": [{"error": "Synthetic error"}]},
        },
    )
    before = {row["key"]: row for row in monitor.store.rows("SELECT * FROM issues")}
    monitor.save_trace("automation.example", trace("proven_success"))
    for issue in monitor.store.rows("SELECT * FROM issues"):
        detail = json.loads(issue["detail"])
        assert detail["blocked_by_unknown_time_run"] and detail["blocking_run_id"] == "unknown"
        assert detail["blocking_start_source"] == "unknown"
        for field in ("first_seen", "last_seen", "occurrences"):
            assert issue[field] == before[issue["key"]][field]
    # Real timestamp recovery removes the uncertainty; the next success resolves it.
    monitor.save_trace(
        "automation.example",
        {**trace("unknown", "error", True), "timestamp": {"start": "2026-10-19T00:00:00Z"}},
    )
    monitor.save_trace(
        "automation.example",
        {**trace("next_success"), "timestamp": {"start": "2026-10-20T01:00:00Z"}},
    )
    for issue in monitor.store.rows("SELECT * FROM issues"):
        assert not issue["active"]
        assert "blocked_by_unknown_time_run" not in json.loads(issue["detail"])


def test_event_run_and_timing_roll_back_together_on_storage_failure(monitor, monkeypatch):
    original = monitor.store.execute

    def execute(sql, args=()):
        if sql.startswith("INSERT OR IGNORE INTO run_timing"):
            raise RuntimeError("Synthetic timing write failure")
        return original(sql, args)

    monkeypatch.setattr(monitor.store, "execute", execute)
    with pytest.raises(RuntimeError, match="timing write"):
        monitor.event(
            {
                "event_type": "automation_triggered",
                "data": {"entity_id": "automation.example"},
                "context": {"id": "context"},
            }
        )
    assert not monitor.store.rows("SELECT * FROM runs")
    assert not monitor.store.rows("SELECT * FROM run_timing")


def test_recovered_null_start_orphan_has_bounded_observation_retention(tmp_path):
    path = tmp_path / "vision.db"
    store = Store(path)
    store.execute(
        "INSERT INTO runs VALUES ('automation.example','orphan',NULL,NULL,'unknown',0,'{}')"
    )
    store.save_run_evidence(
        "automation.example", "orphan", trace_summary({}, Redactor(), "unknown"), "unknown"
    )
    store.execute("INSERT INTO trace_fetches VALUES ('automation.example','orphan',1,0,0)")
    snapshot = store.save_structure("automation.example", structure({}), "retained_trace")
    store.execute(
        "INSERT INTO run_structures VALUES ('automation.example','orphan',?)", (snapshot,)
    )
    store.close()
    store = Store(path)
    timing = store.rows("SELECT * FROM run_timing")[0]
    assert timing["start_source"] == "unknown" and timing["observed_at"] > 0
    assert store.rows("SELECT started FROM runs")[0]["started"] is None
    store.execute("UPDATE run_timing SET observed_at=?", (time.time() - 8 * 86400,))
    store.prune(7)
    for table in ("runs", "run_timing", "run_evidence", "trace_fetches", "run_structures"):
        assert not store.rows(f"SELECT * FROM {table}")
    assert not store.rows("PRAGMA foreign_key_check")
    store.close()


def test_future_migration_keeps_original_and_new_source_version_backup(tmp_path, monkeypatch):
    path = tmp_path / "vision.db"
    legacy = sqlite3.connect(path)
    legacy.executescript((Path(__file__).parent / "fixtures/vision_v1_schema.sql").read_text())
    legacy.execute("PRAGMA user_version=1")
    legacy.commit()
    legacy.close()
    store = Store(path)
    store.set_meta("after_upgrade", "Synthetic 0.2 observation")
    store.close()
    original = tmp_path / "vision.db.pre-migration.bak"
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    monkeypatch.setattr("vision.store.SCHEMA_VERSION", SCHEMA_VERSION + 1)
    monkeypatch.setitem(
        MIGRATIONS, SCHEMA_VERSION + 1, ("CREATE TABLE synthetic_future (id INTEGER)",)
    )
    upgraded = Store(path)
    backup = tmp_path / f"vision.db.v{SCHEMA_VERSION}.bak"
    assert backup.exists() and backup.stat().st_mode & 0o777 == 0o600
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
    assert (tmp_path / "vision.db.v1.bak").exists()
    saved = sqlite3.connect(backup)
    assert saved.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert (
        json.loads(saved.execute("SELECT value FROM meta WHERE key='after_upgrade'").fetchone()[0])
        == "Synthetic 0.2 observation"
    )
    saved.close()
    assert upgraded.rows("PRAGMA user_version")[0]["user_version"] == SCHEMA_VERSION + 1
    upgraded.close()
