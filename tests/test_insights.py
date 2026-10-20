import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.evidence import dependency_graph
from vision.insights import Insights
from vision.monitor import Monitor
from vision.security import Redactor
from vision.store import Store


@pytest.fixture
def local(tmp_path):
    store = Store(tmp_path / "vision.db")
    monitor = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor(["synthetic-secret"]))
    service = monitor.insights
    yield monitor, service
    store.close()


def poll_cases(service, **kwargs):
    # Simulate the monitor's completed ingestion cycle before testing its read model.
    service.refresh()
    return service.cases(**kwargs)


def state(monitor, entity="sensor.example", value="unavailable"):
    monitor.observe_state({"entity_id": entity, "state": value, "attributes": {}})


def run(monitor, run_id, config=None, outcome="finished", error=None, started=None):
    monitor.save_trace(
        "automation.example",
        {
            "run_id": run_id,
            "script_execution": outcome,
            **({"timestamp": {"start": started}} if started else {}),
            **({"config": config} if config is not None else {}),
            "trace": {
                "action/0": [{"result": {"done": True}, **({"error": error} if error else {})}]
            },
        },
    )
    monitor.insights.refresh()


def test_critical_repair_and_automation_errors_survive_1200_offline_cases(local):
    monitor, service = local
    with monitor.store.transaction():
        for index in range(1200):
            state(monitor, f"sensor.example_{index}")
        monitor.store.issue("repair:example", "repair", "critical", "Critical repair", {})
        monitor.store.issue(
            "automation:automation.example",
            "automation",
            "error",
            "Execution failed",
            {"entity_id": "automation.example"},
        )
    overview = service.overview()
    assert [item["key"] for item in overview["cases"]["items"][:2]] == [
        "repair:example",
        "automation:automation.example",
    ]
    assert overview["availability_count"] == 1200
    assert overview["cases"]["total"] == 1202
    assert len(poll_cases(service, source="availability", limit=20)["items"]) == 20


@pytest.mark.parametrize("status", ["known", "expected", "snoozed"])
def test_attention_overlays_preserve_source_facts_and_episode_history(local, status):
    monitor, service = local
    state(monitor)
    before = monitor.store.rows("SELECT * FROM issues")[0]
    dossier = service.annotate(before["key"], status, "synthetic-secret note")
    assert dossier["case"]["source_active"] and dossier["case"]["status"] == status
    assert "synthetic-secret" not in dossier["case"]["note"]
    assert not poll_cases(service)["items"]
    after = monitor.store.rows("SELECT * FROM issues")[0]
    assert after == before
    state(monitor)
    assert monitor.store.rows("SELECT occurrences FROM issues")[0]["occurrences"] == 1
    service.annotate(before["key"], "review", "")
    assert poll_cases(service)["items"][0]["source_active"]


def test_snooze_survives_restart_and_expires_without_source_update(local, tmp_path):
    monitor, service = local
    state(monitor)
    service.annotate("availability:sensor.example", "snoozed", "Temporary", 1)
    other = Store(tmp_path / "vision.db")
    try:
        restarted = Insights(Monitor(other, Settings(), SimpleNamespace(token=""), Redactor()))
        assert restarted.dossier("availability:sensor.example")["case"]["status"] == "snoozed"
        other.execute("UPDATE case_annotations SET expires=?", (time.time() - 1,))
        assert poll_cases(restarted)["items"][0]["status"] == "review"
    finally:
        other.close()


def test_expected_offline_legacy_exception_does_not_erase_current_source_fact(local):
    monitor, service = local
    monitor.store.execute("INSERT INTO exceptions VALUES ('sensor.example','Expected',NULL)")
    state(monitor)
    case = service.dossier("availability:sensor.example")["case"]
    assert case["source_active"] and case["status"] == "expected"
    monitor.store.execute("DELETE FROM exceptions")
    assert poll_cases(service)["items"][0]["status"] == "review"


def test_disabled_registry_entity_is_not_a_missing_reference(local):
    monitor, service = local
    monitor.registry = {"sensor.disabled": {"disabled_by": "user"}}
    monitor.capabilities["config/entity_registry/list"] = "available"
    monitor.record_structure(
        "automation.example",
        {
            "actions": [
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": ["sensor.disabled", "light.absent"]},
                }
            ]
        },
        "current_config",
    )
    cases = poll_cases(service, source="static")["items"]
    assert len(cases) == 1 and cases[0]["detail"]["target"] == "entity:light.absent"
    assert cases[0]["detail"]["path"] == "action/0"


def test_dynamic_area_label_and_trace_only_refs_are_explicitly_unknown(local):
    monitor, service = local
    monitor.capabilities["config/entity_registry/list"] = "available"
    config = {
        "actions": [
            {
                "action": "light.turn_on",
                "target": {
                    "entity_id": "{{ unknown }}",
                    "area_id": "unknown_area",
                    "label_id": "unknown_label",
                },
            }
        ]
    }
    monitor.record_structure("automation.example", config, "current_config")
    assert not poll_cases(service, source="static")["items"]
    assert monitor.structures["automation.example"]["coverage"]["dynamic_references"]
    monitor.record_structure(
        "automation.historical",
        {"actions": [{"action": "light.turn_on", "target": {"entity_id": "light.absent"}}]},
        "retained_trace",
    )
    assert not poll_cases(service, source="static")["items"]
    state(monitor, "automation.historical", "on")
    assert not service.automation("automation.historical")["structure_coverage"][
        "current_configuration_available"
    ]


def test_missing_reference_cannot_be_cleared_by_registry_permission_loss(local):
    monitor, service = local
    monitor.capabilities["config/entity_registry/list"] = "available"
    monitor.record_structure(
        "automation.example",
        {"actions": [{"action": "light.turn_on", "target": {"entity_id": "light.absent"}}]},
        "current_config",
    )
    key = poll_cases(service, source="static")["items"][0]["key"]
    monitor.capabilities["config/entity_registry/list"] = "unavailable"
    service.refresh()
    assert service.dossier(key)["case"]["source_active"]


def test_unchanged_static_rule_observation_does_not_inflate_recurrence_or_write(local):
    monitor, service = local
    monitor.record_structure(
        "automation.example", {"actions": [{"wait_template": "{{ unknown }}"}]}, "current_config"
    )
    first = poll_cases(service, source="static")["items"][0]
    changes = monitor.store.db.total_changes
    for _ in range(5):
        assert poll_cases(service, source="static")["items"][0]["first_seen"] == first["first_seen"]
    assert monitor.store.db.total_changes == changes


def test_comparison_requires_same_configuration_digest(local):
    monitor, service = local
    a = {"actions": [{"action": "light.turn_on"}]}
    b = {"actions": [{"action": "light.turn_off"}]}
    run(monitor, "a", a, error="TimeoutError")
    run(monitor, "same", a)
    run(monitor, "changed", b)
    run(monitor, "unknown")
    assert service.comparison("automation.example", "a", "same")["comparable"]
    assert service.comparison("automation.example", "a", "same")["differences"]
    for right in ("changed", "unknown"):
        result = service.comparison("automation.example", "a", right)
        assert not result["comparable"] and not result["differences"]
        assert result["left"]["evidence"]["errors"][0]["kind"] == "timeout"


def test_dossier_preserves_unknown_start_gap_redacted_messages_and_log_recurrence(local):
    monitor, service = local
    run(monitor, "unknown", outcome="error", error="Timeout synthetic-secret")
    dossier = service.dossier("automation:automation.example")
    assert dossier["last_observation_gap"]
    assert any("start time" in text for text in dossier["unknowns"])
    assert dossier["run"]["started"] is None
    assert "synthetic-secret" not in json.dumps(dossier)
    monitor.log_issue(
        {"name": "example", "message": ["Warning example"], "count": 3, "level": "ERROR"}
    )
    key = monitor.store.rows("SELECT key FROM issues WHERE source='log'")[0]["key"]
    for _ in range(3):
        monitor.log_issue(
            {"name": "example", "message": ["Warning example"], "count": 3, "level": "ERROR"}
        )
    assert service.dossier(key)["recurrence"]["reported"] == 3


def test_history_keyset_has_stable_ties_nulls_and_bounds(local):
    monitor, service = local
    for index in range(17):
        run(monitor, f"run_{index}", started="2026-10-20T00:00:00Z" if index % 3 else None)
    seen, cursor = [], None
    while True:
        page = service.history("runs", limit=4, cursor=cursor)
        assert len(page["items"]) <= 4
        seen.extend(item["run_id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 17
    assert service.history("runs", q="' OR 1=1--")["items"] == []
    with pytest.raises(ValueError):
        service.history("sqlite_master")
    with pytest.raises(ValueError):
        service.history("runs", limit=101)
    with pytest.raises(ValueError):
        service.history("runs", cursor="invalid")


def test_configuration_change_history_is_observed_not_edit_time(local):
    monitor, service = local
    state(monitor, "automation.example", "on")
    monitor.record_structure("automation.example", {"actions": []}, "current_config")
    monitor.record_structure("automation.example", {"actions": [{"delay": 1}]}, "current_config")
    detail = service.automation("automation.example")
    assert [row["kind"] for row in detail["configuration_changes"]] == ["changed", "baseline"]
    assert "not a Home Assistant edit time" in detail["configuration_limit"]
    assert "Observed structural baseline" in detail["configuration_changes"][1]["delta"]["summary"]
    assert detail["configuration_changes"][0]["delta"]["items"][0]["after"].startswith("delay")
    today = time.strftime("%Y-%m-%d", time.gmtime())
    assert len(service.history("changes", day=today)["items"]) == 2


def test_typed_impact_does_not_claim_causality(local):
    monitor, service = local
    monitor.record_structure(
        "automation.example",
        {"actions": [{"action": "light.turn_on", "target": {"entity_id": "light.example"}}]},
        "current_config",
    )
    monitor.store.replace_graph(dependency_graph({}, {}, [], monitor.structures))
    result = service.impact("automation.example")
    assert result["relations"] and "causation are unknown" in result["coverage"]


def test_local_api_dossier_status_history_and_investigation_without_ai(tmp_path):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    app = create_app(runtime, Settings(), connect=False)
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        state(app.state.monitor)
        state(app.state.monitor, "automation.example", "on")
        run(app.state.monitor, "failure", outcome="error", error="TimeoutError")
        assert client.get("/api/cases").status_code == 200
        assert client.get("/api/cases/availability:sensor.example").json()["case"]["active"] == 1
        saved = client.post(
            "/api/cases/availability:sensor.example/status",
            json={"status": "expected", "note": "Sleep"},
            headers={"x-vision-request": "1"},
        )
        assert saved.status_code == 200 and saved.json()["case"]["source_active"]
        assert (
            client.post(
                "/api/exceptions",
                json={"entity_id": "sensor.example", "reason": "Sleep"},
                headers={"x-vision-request": "1"},
            ).status_code
            == 200
        )
        assert app.state.store.rows("SELECT active FROM issues WHERE source='availability'")[0][
            "active"
        ]
        detail = client.get("/api/investigation/automation.example?run_id=failure")
        assert detail.status_code == 200 and detail.json()["run"]["evidence"]["error_count"] == 1
        assert client.get("/api/history/page?kind=runs&limit=1").status_code == 200
        assert client.get("/api/history/page?kind=sqlite_master").status_code == 422
        assert client.get("/api/cases?source=invalid").status_code == 422
        assert client.get("/api/intelligence").json()["enabled"] is False
        assert app.state.store.rows("SELECT count(*) n FROM usage")[0]["n"] == 0


def test_trigger_event_at_same_proven_time_cannot_suppress_failed_trace(local):
    monitor, service = local
    monitor.event(
        {
            "event_type": "automation_triggered",
            "time_fired": "2026-10-20T00:00:00Z",
            "context": {"id": "z_other_context"},
            "data": {"entity_id": "automation.example"},
        }
    )
    run(monitor, "A_failed_trace", outcome="error", started="2026-10-20T00:00:00Z")
    assert service.dossier("automation:automation.example")["case"]["source_active"]


def test_backup_upgrade_preserves_operator_files_matching_version_pattern(tmp_path):
    import sqlite3
    from pathlib import Path

    path = tmp_path / "vision.db"
    old = sqlite3.connect(path)
    old.executescript((Path(__file__).parent / "fixtures/vision_v1_schema.sql").read_text())
    old.execute("PRAGMA user_version=1")
    old.commit()
    old.close()
    operator_file = tmp_path / "vision.db.v777.bak"
    operator_file.write_bytes(b"Operator-created synthetic snapshot")
    before = operator_file.read_bytes()
    store = Store(path)
    try:
        assert operator_file.read_bytes() == before
        assert (tmp_path / "vision.db.pre-migration.bak").exists()
    finally:
        store.close()


def test_identical_rich_evidence_removes_stale_duplicate_metadata(local):
    monitor, service = local
    run(monitor, "same", error="Synthetic error")
    evidence = service.run("automation.example", "same")["evidence"]
    monitor.store.execute(
        "UPDATE runs SET detail=? WHERE run_id='same'",
        (json.dumps({"_vision_evidence": evidence}),),
    )
    monitor.store.save_run_evidence("automation.example", "same", evidence, "succeeded")
    detail = json.loads(monitor.store.rows("SELECT detail FROM runs")[0]["detail"])
    assert "_vision_evidence" not in detail
    assert service.run("automation.example", "same")["evidence"] == evidence


def test_refused_start_is_supported_mode_finding_but_cancellation_is_not(local):
    monitor, service = local
    monitor.save_trace(
        "automation.example",
        {
            "run_id": "blocked",
            "script_execution": "failed_single",
            "timestamp": {"start": "2026-10-20T00:00:00Z"},
        },
    )
    cases = poll_cases(service)["items"]
    assert cases[0]["detail"]["rule"] == "mode_conflict"
    assert cases[0]["detail"]["run_id"] == "blocked"
    monitor.save_trace(
        "automation.example",
        {
            "run_id": "cancelled",
            "script_execution": "cancelled",
            "timestamp": {"start": "2026-10-20T01:00:00Z"},
        },
    )
    assert not poll_cases(service)["items"]


def test_refused_start_case_uses_observation_time_not_historical_run_start(local):
    monitor, service = local
    before = time.time()
    monitor.save_trace(
        "automation.example",
        {
            "run_id": "blocked",
            "script_execution": "failed_single",
            "timestamp": {"start": "2020-01-01T00:00:00Z"},
        },
    )
    case = poll_cases(service)["items"][0]
    assert case["first_seen"] >= before and case["last_seen"] >= before
    run(monitor, "unrelated", started="2026-10-20T00:00:00Z")
    poll_cases(service)
    assert service.dossier(case["key"])["case"]["first_seen"] == case["first_seen"]


def test_incoming_automation_target_impact_uses_both_graph_representations(local):
    monitor, service = local
    monitor.record_structure(
        "automation.example",
        {
            "actions": [
                {"action": "automation.trigger", "target": {"entity_id": "automation.target"}}
            ]
        },
        "current_config",
    )
    monitor.store.replace_graph(dependency_graph({}, {}, [], monitor.structures))
    incoming = service.impact("automation.target")["relations"]
    assert any(
        row["source"] == "automation:automation.example"
        and row["target"] == "entity:automation.target"
        for row in incoming
    )


def test_overview_groups_same_run_sources_and_exposes_concrete_failure_first(local):
    monitor, service = local
    run(monitor, "failed", outcome="error", error="TimeoutError", started="2026-10-20T00:00:00Z")
    monitor.store.issue(
        "automation_step:automation.other", "automation_step", "warning", "Step errors", {}
    )
    items = service.overview()["cases"]["items"]
    assert items[0]["source"] == "automation"
    assert items[0]["run_outcome"] == "failed"
    assert "action/0" in items[0]["summary"] and "TimeoutError" in items[0]["summary"]
    assert items[0]["manual_check"]
    assert items[0]["related_case_keys"] == ["automation_step:automation.example"]


def test_automation_index_bulk_load_excludes_thousands_of_runs_and_structures(local, monkeypatch):
    monitor, _ = local
    with monitor.store.transaction():
        for index in range(200):
            entity_id = f"automation.example_{index}"
            monitor.entities[entity_id] = {
                "entity_id": entity_id,
                "name": entity_id,
                "availability": "available",
                "enabled": True,
                "last_triggered": None,
            }
            monitor.structures[entity_id] = {
                "nodes": [{"path": f"action/{n}"} for n in range(1000)]
            }
            for run_index in range(20):
                monitor.store.execute(
                    "INSERT INTO runs VALUES (?,?,NULL,1,?,1,?)",
                    (entity_id, str(run_index), "succeeded", json.dumps({"retained": "x" * 512})),
                )
    queries = []
    original = monitor.store.rows

    def rows(sql, args=()):
        queries.append(sql)
        return original(sql, args)

    monkeypatch.setattr(monitor.store, "rows", rows)
    index = monitor.automation_index()
    assert len(index) == 200 and len(queries) == 1
    assert all("runs" not in item and "structure" not in item for item in index)
    assert all(item["stats"][0]["count"] == 20 for item in index)
    assert len(json.dumps(index).encode()) < 150_000


def test_device_membership_impact_follows_declared_automation_refs(local):
    monitor, service = local
    monitor.registry = {"light.example": {"device_id": "example_device", "platform": "example"}}
    monitor.record_structure(
        "automation.example",
        {"actions": [{"action": "light.turn_on", "target": {"entity_id": "light.example"}}]},
        "current_config",
    )
    monitor.store.replace_graph(
        dependency_graph({}, monitor.registry, [{"id": "example_device"}], monitor.structures)
    )
    result = service.impact("example_device", "device")
    assert result["affected_automations"][0]["source"] == "automation:automation.example"
    assert not result["members_truncated"]


def test_local_expected_annotation_updates_inventory_without_hiding_source(local):
    monitor, service = local
    state(monitor)
    service.annotate("availability:sensor.example", "expected", "Sleep")
    assert monitor.inventory()[0]["expected_offline"]
    assert monitor.store.rows("SELECT active FROM issues")[0]["active"] == 1
    state(monitor, value="on")
    case = service.dossier("availability:sensor.example")["case"]
    assert not case["source_active"] and case["status"] == "resolved"
    assert case["local_status"] == "expected"


def test_paginated_analysis_history_keeps_old_results_accessible_without_provider(local):
    monitor, service = local
    monitor.store.execute(
        "INSERT INTO analyses VALUES (1,1,?,?,?,?,?,?)",
        ("audit", None, "openai", "synthetic", json.dumps({"summary": "Old result"}), "{}"),
    )
    page = service.history("analyses", q="audit")
    assert json.loads(page["items"][0]["result"])["summary"] == "Old result"


def test_static_case_identity_is_bound_to_configuration_revision(local):
    monitor, service = local
    monitor.record_structure(
        "automation.example",
        {"actions": [{"action": "light.turn_on", "continue_on_error": True}]},
        "current_config",
    )
    first = poll_cases(service, source="static")["items"][0]
    monitor.record_structure(
        "automation.example",
        {"actions": [{"action": "light.turn_off", "continue_on_error": True}]},
        "current_config",
    )
    second = poll_cases(service, source="static")["items"][0]
    assert first["key"] != second["key"]
    assert not service.dossier(first["key"])["case"]["source_active"]
    assert second["detail"]["configuration_digest"] != first["detail"]["configuration_digest"]


def test_unknown_time_refusal_remains_visible_until_authoritative_time_recovery(local):
    monitor, service = local
    monitor.save_trace(
        "automation.example", {"run_id": "blocked", "script_execution": "failed_single"}
    )
    assert poll_cases(service)["items"][0]["detail"]["rule"] == "mode_conflict"
    run(monitor, "success", started="2026-10-20T00:00:00Z")
    assert "chronology is unknown" in poll_cases(service)["items"][0]["summary"]
    monitor.save_trace(
        "automation.example",
        {
            "run_id": "blocked",
            "script_execution": "failed_single",
            "timestamp": {"start": "2020-01-01T00:00:00Z"},
        },
    )
    assert not poll_cases(service)["items"]
