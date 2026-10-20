import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from vision.config import Settings
from vision.evidence import (
    MAX_NODES,
    MAX_STEPS,
    dependency_graph,
    fingerprint,
    structure,
    trace_summary,
)
from vision.ha import HAError
from vision.monitor import Monitor, trace_outcome
from vision.security import Redactor
from vision.store import MIGRATIONS, SCHEMA_VERSION, Store


def legacy_database(path):
    db = sqlite3.connect(path)
    db.executescript((Path(__file__).parent / "fixtures/vision_v1_schema.sql").read_text())
    db.execute("PRAGMA user_version=1")
    db.execute("INSERT INTO meta VALUES ('settings','{\"retention_days\":90}')")
    db.execute("INSERT INTO availability VALUES (1,'sensor.example','unknown',1,2,1)")
    db.execute("INSERT INTO issues VALUES ('log:example','log','error','Example','{}',1,2,3,1)")
    db.execute("INSERT INTO runs VALUES ('automation.example','run','ctx',1,'failed',1,'{}')")
    db.execute("INSERT INTO exceptions VALUES ('sensor.example','Expected sleep',NULL)")
    db.execute("INSERT INTO analyses VALUES (1,1,'audit',NULL,'openai','model','{}','{}')")
    db.execute("INSERT INTO usage VALUES (1,1,'openai','model',NULL,NULL,.25,'reserved')")
    db.commit()
    db.close()


def test_versioned_migration_preserves_all_legacy_records_and_reservation(tmp_path):
    path = tmp_path / "vision.db"
    legacy_database(path)
    for _ in range(2):
        store = Store(path)
        assert store.rows("PRAGMA user_version")[0]["user_version"] == SCHEMA_VERSION
        assert store.get_meta("settings") == {"retention_days": 90}
        assert store.rows("SELECT * FROM availability")[0]["uncertain"] == 1
        assert store.rows("SELECT * FROM issues")[0]["occurrences"] == 3
        assert store.rows("SELECT * FROM runs")[0]["context_id"] == "ctx"
        assert store.exceptions()[0]["reason"] == "Expected sleep"
        assert store.rows("SELECT * FROM analyses")[0]["result"] == "{}"
        assert store.rows("SELECT * FROM usage")[0]["status"] == "uncertain"
        assert store.rows("SELECT * FROM usage")[0]["cost_usd"] == 0.25
        store.close()


def test_migration_failure_rolls_back_schema_and_user_data(tmp_path, monkeypatch):
    path = tmp_path / "vision.db"
    legacy_database(path)
    monkeypatch.setitem(MIGRATIONS, 2, MIGRATIONS[2] + ("INVALID MIGRATION",))
    with pytest.raises(sqlite3.OperationalError):
        Store(path)
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    assert db.execute("SELECT status FROM usage").fetchone()[0] == "reserved"
    assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
    assert not db.execute(
        "SELECT name FROM sqlite_master WHERE name='automation_structures'"
    ).fetchall()
    db.close()


def sample_config():
    return {
        "alias": "Private household name",
        "description": "Never retained",
        "triggers": [{"trigger": "state", "entity_id": "sensor.example", "to": "private-state"}],
        "conditions": [{"condition": "template", "value_template": "{{ private_secret }}"}],
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "state",
                                "entity_id": "binary_sensor.ready",
                                "state": "on",
                            }
                        ],
                        "sequence": [
                            {
                                "action": "light.turn_on",
                                "target": {"device_id": "device_1", "area_id": "area_1"},
                                "data": {"brightness": 123, "password": "private-password"},
                            }
                        ],
                    }
                ],
                "default": [
                    {
                        "repeat": {
                            "count": 3,
                            "sequence": [
                                {
                                    "wait_for_trigger": [
                                        {"trigger": "state", "entity_id": "sensor.example"}
                                    ],
                                    "timeout": "00:00:10",
                                    "continue_on_timeout": False,
                                }
                            ],
                        }
                    },
                    {
                        "action": "notify.phone",
                        "continue_on_error": True,
                        "data": {"message": "private-message"},
                    },
                ],
            }
        ],
        "mode": "queued",
        "max": 4,
    }


def test_safe_ast_preserves_control_flow_targets_and_uncertainty():
    result = structure(sample_config())
    encoded = json.dumps(result)
    for private in ("private", "Never retained", "household", "brightness", "value_template"):
        assert private not in encoded
    assert result["mode"] == "queued" and result["max_runs"] == 4
    assert not result["coverage"]["truncated"] and result["coverage"]["dynamic_references"]
    assert result["referenced_entities"] == ["binary_sensor.ready", "sensor.example"]
    assert any(
        n["path"] == "action/0/default/0/repeat/sequence/0" and n["timeout"]["seconds"] == 10
        for n in result["nodes"]
    )
    assert any(r["kind"] == "area" and r["id"] == "area_1" for r in result["references"])
    assert any(
        r["role"] == "condition" and r["id"] == "binary_sensor.ready" for r in result["references"]
    )


def test_ast_fingerprint_is_stable_across_process_hash_seeds():
    code = (
        "import json,sys; from vision.evidence import structure,fingerprint; "
        "print(fingerprint(structure(json.load(sys.stdin))))"
    )
    digests = {
        subprocess.check_output(
            [sys.executable, "-c", code],
            input=json.dumps(sample_config()).encode(),
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        )
        .decode()
        .strip()
        for seed in (1, 23, 987)
    }
    assert digests == {fingerprint(structure(sample_config()))}


def test_structure_bounds_do_not_claim_complete_static_references():
    result = structure(
        {
            "actions": [
                {"action": "light.turn_on", "target": {"entity_id": f"light.example_{n}"}}
                for n in range(MAX_NODES + 5)
            ]
        }
    )
    assert len(result["nodes"]) == MAX_NODES
    assert result["coverage"]["truncated"]
    result = structure(
        {
            "actions": [
                {
                    "action": "{{ unknown_service }}",
                    "target": {"entity_id": "{{ arbitrary_template() }}"},
                }
            ]
        }
    )
    assert not result["references"] and result["coverage"]["dynamic_references"]
    assert "arbitrary_template" not in json.dumps(result)


def test_predicates_retain_only_safe_typed_operands_and_mark_omissions():
    result = structure(
        {
            "conditions": [
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.example",
                    "above": 12.5,
                    "below": "{{ private_value }}",
                    "attribute": "private_attribute",
                },
                {
                    "condition": "state",
                    "entity_id": "binary_sensor.ready",
                    "state": "on",
                    "for": {"minutes": 2},
                },
            ],
            "triggers": [{"trigger": "time", "at": "08:30"}],
        }
    )
    assert result["nodes"][0]["predicate"] == {"at": "08:30"}
    numeric, state = result["nodes"][1:]
    assert numeric["predicate"] == {"above": 12.5} and numeric["predicate_coverage"] == "partial"
    assert state["predicate"] == {"state": "on", "for_seconds": 120}
    assert "private" not in json.dumps(result)


def test_structural_history_is_persistent_and_retained_trace_cannot_replace_current(tmp_path):
    path = tmp_path / "vision.db"
    store = Store(path)
    initial = structure({"actions": [{"action": "light.turn_on"}]})
    changed = structure({"actions": [{"action": "light.turn_off"}]})
    store.save_structure("automation.example", initial, "retained_trace", 1)
    store.save_structure("automation.example", changed, "current_config", 2)
    store.save_structure("automation.example", initial, "retained_trace", 3)
    assert store.structures()["automation.example"] == changed
    assert [r["kind"] for r in store.rows("SELECT * FROM configuration_changes")] == [
        "baseline",
        "current_baseline",
    ]
    store.save_structure("automation.example", initial, "current_config", 4)
    store.save_structure("automation.example", changed, "current_config", 5)
    store.save_structure("automation.example", changed, "current_config", 6)
    assert len(store.rows("SELECT * FROM automation_structures")) == 2
    assert len(store.rows("SELECT * FROM configuration_changes WHERE kind='changed'")) == 2
    store.close()
    store = Store(path)
    assert store.structures()["automation.example"] == changed
    store.close()


def completed_trace():
    return {
        "run_id": "example_run",
        "script_execution": "finished",
        "last_step": "action/2",
        "timestamp": {"start": "2026-10-01T12:00:00Z", "finish": "2026-10-01T12:00:12Z"},
        "trace": {
            "action/0": [
                {
                    "timestamp": "2026-10-01T12:00:01Z",
                    "error": "TemplateError: private-secret",
                    "changed_variables": {"password": "never-store"},
                }
            ],
            "action/1": [{"result": {"wait": {"remaining": 0, "completed": False}}}],
            "action/2": [{"result": {"done": True}}],
        },
    }


def test_completed_run_with_earlier_errors_remains_completed_and_errors_are_visible():
    trace = completed_trace()
    assert trace_outcome(trace) == "succeeded"
    summary = trace_summary(trace, Redactor(["private-secret"]), "succeeded")
    assert summary["completed_with_errors"] and summary["error_count"] == 1
    assert summary["errors"][0]["kind"] == "template_error"
    assert summary["steps"][0]["offset_seconds"] == 1
    assert summary["steps"][1]["wait_timed_out"]
    assert summary["duration_seconds"] == 12
    assert "private-secret" not in json.dumps(summary) and "never-store" not in json.dumps(summary)
    assert "changed_variables" not in json.dumps(summary)


def test_trace_errors_and_timeout_stop_have_different_whole_run_semantics():
    trace = {
        "script_execution": "aborted",
        "last_step": "action/0",
        "trace": {
            "action/0": [
                {
                    "error": "TimeoutError",
                    "result": {"timeout": True, "wait": {"remaining": 0, "completed": False}},
                }
            ]
        },
    }
    assert trace_outcome(trace) == "stopped"
    summary = trace_summary(trace, Redactor(), "stopped")
    assert summary["errors"][0]["kind"] == "timeout"
    assert not summary["completed_with_errors"]
    assert (
        trace_outcome(
            {
                "script_execution": "finished",
                "last_step": "action/1",
                "trace": {"action/0/choose/0/conditions/0": [{"result": {"result": False}}]},
            }
        )
        == "succeeded"
    )


def test_trace_truncation_and_summary_only_coverage_are_explicit():
    trace = {"trace": {f"action/{n}": [{"result": {"done": True}}] for n in range(MAX_STEPS + 5)}}
    summary = trace_summary(trace, Redactor(), "succeeded")
    assert len(summary["steps"]) == MAX_STEPS and summary["step_count"] == MAX_STEPS + 5
    assert summary["coverage"]["truncated"] and summary["coverage"]["error_count_is_lower_bound"]
    assert not trace_summary({}, Redactor(), "succeeded")["coverage"]["full_trace_available"]
    assert trace_summary({}, Redactor(), "succeeded")["coverage"]["error_count_is_lower_bound"]


def test_trace_error_text_has_a_total_storage_bound():
    trace = {"trace": {f"action/{n}": [{"error": "x" * 10000}] for n in range(MAX_STEPS)}}
    summary = trace_summary(trace, Redactor(), "succeeded")
    assert len(json.dumps(summary).encode()) < 150000
    assert summary["error_count"] == MAX_STEPS
    assert summary["coverage"]["errors_truncated"]


def test_redaction_bounds_work_without_exposing_partial_secrets():
    redactor = Redactor(["configured-private-secret"])
    assert "configured-private-secret" not in redactor.text("configured-private-secret " * 1000, 80)
    assert "private" not in redactor.text("prefix " + "private" * 10000, 80)
    assert "xxx" not in redactor.text("prefix Bearer " + "x" * 10000, 80)
    assert len(redactor.text("x" * 10000, 80)) <= 80


async def test_missing_full_trace_is_retried_when_capability_recovers(tmp_path):
    class RecoveringHA:
        def __init__(self):
            self.calls = 0

        async def read(self, command, **params):
            if command == "get_states":
                return [
                    {
                        "entity_id": "automation.example",
                        "state": "on",
                        "attributes": {"id": "example"},
                    }
                ]
            if command == "repairs/list_issues":
                return {"issues": []}
            if command == "trace/list":
                return [
                    {"item_id": "example", "run_id": "example_run", "script_execution": "finished"}
                ]
            if command == "trace/get":
                self.calls += 1
                if self.calls == 1:
                    raise HAError("read_unavailable")
                return completed_trace()
            return []

        async def automation_config(self, automation_id):
            return {}

    store = Store(tmp_path / "vision.db")
    monitor = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor())
    ha = RecoveringHA()
    await monitor.sync(ha)
    first = json.loads(store.rows("SELECT summary FROM run_evidence")[0]["summary"])
    assert not first["coverage"]["full_trace_available"]
    assert store.rows("SELECT started FROM runs")[0]["started"] is None
    store.set_meta("trace_fetch_circuit", {"failures": 1, "next_probe": 0})
    store.execute("UPDATE trace_fetches SET next_attempt=0")
    await monitor.sync(ha)
    second = json.loads(store.rows("SELECT summary FROM run_evidence")[0]["summary"])
    assert ha.calls == 2 and second["completed_with_errors"]
    assert store.rows("SELECT started FROM runs")[0]["started"] == 1790856000
    store.close()


def test_run_step_evidence_persists_without_clearing_newer_failure(tmp_path):
    path = tmp_path / "vision.db"
    store = Store(path)
    monitor = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor(["private-secret"]))
    monitor.save_trace(
        "automation.example", {**completed_trace(), "run_id": "newer", "error": "failure"}
    )
    older = {
        **completed_trace(),
        "timestamp": {"start": "2026-09-01T12:00:00Z", "finish": "2026-09-01T12:00:12Z"},
    }
    monitor.save_trace("automation.example", older)
    assert (
        store.rows("SELECT active FROM issues WHERE key='automation:automation.example'")[0][
            "active"
        ]
        == 1
    )
    assert len(store.rows("SELECT * FROM run_evidence")) == 2
    store.close()
    store = Store(path)
    assert json.loads(
        store.rows("SELECT summary FROM run_evidence WHERE run_id='example_run'")[0]["summary"]
    )["completed_with_errors"]
    store.execute("DELETE FROM runs WHERE run_id='example_run'")
    assert len(store.rows("SELECT * FROM run_evidence")) == 1
    store.close()


def test_dependency_graph_retains_types_and_unexpanded_area_targets(tmp_path):
    graph = dependency_graph(
        {"automation.example": {}, "light.example": {}},
        {"light.example": {"platform": "synthetic", "device_id": "device_1"}},
        [{"id": "device_1"}],
        {"automation.example": structure(sample_config())},
    )
    assert {n["kind"] for n in graph["nodes"]} == {
        "integration",
        "device",
        "entity",
        "automation",
        "target",
    }
    assert any(
        e["source"] == "integration:synthetic" and e["target"] == "device:device_1"
        for e in graph["edges"]
    )
    assert any(e["target"] == "target:area:area_1" for e in graph["edges"])
    store = Store(tmp_path / "vision.db")
    store.replace_graph(graph, 10)
    assert store.get_meta("dependencies_observed_at") == 10
    assert len(store.rows("SELECT * FROM dependency_edges")) == len(graph["edges"])
    store.replace_graph({"nodes": [], "edges": []}, 20)
    assert not store.rows("SELECT * FROM dependency_edges")
    store.close()
