import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from aiohttp import web

from vision.config import Settings
from vision.ha import HAClient, HAError, validate_read
from vision.monitor import Monitor, structure, trace_outcome
from vision.security import Redactor
from vision.store import Store


@pytest.fixture
def monitor(tmp_path):
    store = Store(tmp_path / "vision.db")
    value = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor(["private-secret"]))
    yield value
    store.close()


@pytest.mark.parametrize(
    "command,params",
    [
        ("call_service", {"domain": "light", "service": "turn_on"}),
        ("repairs/ignore_issue", {}),
        ("config/entity_registry/update", {}),
        ("trace/debug/continue", {}),
        ("get_states", {"path": "/api/services"}),
        ("subscribe_events", {"event_type": "*"}),
        ("trace/get", {"domain": "automation", "item_id": "../x", "run_id": "a"}),
        ("trace/get", {"domain": "script", "item_id": "x", "run_id": "a"}),
    ],
)
def test_write_policy_denies(command, params):
    with pytest.raises(HAError, match="read_policy_denied"):
        validate_read(command, params)


@pytest.mark.parametrize(
    "trace,outcome",
    [
        ({"script_execution": "finished"}, "succeeded"),
        ({"script_execution": "failed_conditions"}, "condition_stopped"),
        ({"script_execution": "aborted", "last_step": "condition/0"}, "condition_stopped"),
        ({"script_execution": "aborted", "last_step": "action/3"}, "stopped"),
        ({"script_execution": "cancelled"}, "stopped"),
        ({"script_execution": "error"}, "failed"),
        ({"error": "an error"}, "failed"),
        ({"state": "running"}, "running"),
        ({"state": "stopped"}, "unknown"),
    ],
)
def test_outcome_semantics(trace, outcome):
    assert trace_outcome(trace) == outcome


def state(value, updated="2026-10-01T00:00:00Z"):
    return {
        "entity_id": "sensor.example",
        "state": value,
        "last_updated": updated,
        "attributes": {"friendly_name": "Example", "password": "private-secret"},
    }


def test_availability_duration_recurring_expected_and_gap(monitor):
    monitor.observe_state(state("unavailable"), now=100)
    monitor.observe_state(state("unavailable"), now=110)
    assert len(monitor.store.rows("SELECT * FROM availability")) == 1
    monitor.observe_state(state("20"), now=120)
    monitor.observe_state(state("unknown"), now=130)
    assert monitor.inventory()[0]["outages"]["episodes"] == 2
    assert monitor.store.rows("SELECT occurrences FROM issues")[0]["occurrences"] == 2
    monitor.store.execute("INSERT INTO exceptions VALUES ('sensor.example','sleeping',NULL)")
    monitor.observe_state(state("unknown"), now=140)
    assert monitor.inventory()[0]["expected_offline"]
    assert monitor.store.rows("SELECT active FROM issues")[0]["active"] == 0
    monitor.gap()
    intervals = monitor.store.rows("SELECT * FROM availability ORDER BY id")
    assert intervals[-1]["ended"] == 140
    assert intervals[-1]["uncertain"] == 1
    assert "private-secret" not in json.dumps(intervals)


def test_trigger_and_trace_deduplicate(monitor):
    monitor.event(
        {
            "event_type": "automation_triggered",
            "data": {"entity_id": "automation.test"},
            "context": {"id": "ctx"},
        }
    )
    rows = monitor.store.rows("SELECT * FROM runs")
    assert rows[0]["outcome"] == "unknown" and rows[0]["triggered"] == 1
    trace = {"run_id": "run", "context": {"id": "ctx"}, "script_execution": "finished"}
    monitor.save_trace("automation.test", trace)
    monitor.save_trace("automation.test", trace)
    rows = monitor.store.rows("SELECT * FROM runs")
    assert len(rows) == 1 and rows[0]["triggered"] == 1 and rows[0]["outcome"] == "succeeded"


def test_structural_configuration_does_not_copy_values():
    value = structure(
        {
            "triggers": [{"trigger": "state", "entity_id": "sensor.example"}],
            "actions": [{"action": "notify.phone", "data": {"message": "private-secret"}}],
        }
    )
    assert value["referenced_entities"] == ["sensor.example"]
    assert "private-secret" not in json.dumps(value)
    assert value["triggers"] == 1 and value["actions"] == 1


def test_upstream_ha_golden_trace_semantics():
    fixture = json.loads((Path(__file__).parent / "fixtures/ha_trace_semantics.json").read_text())
    assert fixture["source_tag"] == "2026.10.2"
    assert len(fixture["cases"]) >= 5
    for case in fixture["cases"]:
        assert trace_outcome(case["trace"]) == case["outcome"], case["name"]


@pytest.mark.parametrize(
    "execution", ["failed_single", "failed_max_runs", "disallowed_recursion_detected"]
)
def test_mode_blocked_is_not_success(execution):
    assert trace_outcome({"script_execution": execution}) == "blocked"


def test_registry_only_entities_remain_in_inventory(monitor):
    monitor.registry = {
        "sensor.disabled": {"disabled_by": "user", "device_id": "device-1"},
        "automation.disabled": {"disabled_by": "user", "device_id": None},
    }
    inventory = monitor.inventory()
    assert len(inventory) == 2
    assert all(e["availability"] == "disabled" for e in inventory)
    detail = monitor.automation_detail("automation.disabled")
    assert detail["enabled"] is None and not detail["possibly_unused"]
    assert not monitor.store.rows("SELECT * FROM issues")


def test_log_grouping_and_counts_across_ha_buffer_reset(monitor):
    record = {
        "name": "synthetic.integration",
        "source": ["synthetic/source.py", 10],
        "level": "ERROR",
        "message": ["Attempt 1 timed out"],
        "count": 2,
        "first_occurred": 100,
    }
    key = monitor.log_issue(record)
    assert monitor.log_issue(record) == key
    assert monitor.store.rows("SELECT occurrences FROM issues")[0]["occurrences"] == 2
    record.update(message=["Attempt 2 timed out"], count=3)
    assert monitor.log_issue(record) == key
    record.update(count=1, first_occurred=200)
    monitor.log_issue(record)
    assert monitor.store.rows("SELECT occurrences FROM issues")[0]["occurrences"] == 4


def test_concurrent_log_markers_do_not_double_count(monitor):
    record = {
        "name": "synthetic.integration",
        "source": ["synthetic/source.py", 10],
        "level": "ERROR",
        "message": ["Synthetic"],
        "count": 2,
        "first_occurred": 100,
    }
    other = {**record, "count": 3, "first_occurred": 200}
    for _ in range(3):
        assert monitor.log_issue(record) == monitor.log_issue(other)
    monitor.log_issue({**record, "count": 1})  # An older snapshot must not reset the counter.
    monitor.log_issue(record)
    assert monitor.store.rows("SELECT occurrences FROM issues")[0]["occurrences"] == 5


async def test_real_websocket_handshake_read_and_event(unused_tcp_port):
    sent = []
    received = []

    async def handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_json({"type": "auth_required"})
        auth = await ws.receive_json()
        assert auth == {"type": "auth", "access_token": "test-only"}
        await ws.send_json({"type": "auth_ok"})
        async for frame in ws:
            data = json.loads(frame.data)
            received.append(data)
            await ws.send_json({"id": data["id"], "type": "result", "success": True, "result": []})
            await ws.send_json({"type": "event", "event": {"event_type": "state_changed"}})
        return ws

    app = web.Application()
    app.router.add_get("/api/websocket", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    try:
        async with HAClient(f"http://127.0.0.1:{unused_tcp_port}", "test-only", sent.append) as ha:
            assert await ha.read("get_states") == []
            with pytest.raises(HAError):
                await ha.read("call_service")
            await asyncio.sleep(0.01)
        assert received[0]["type"] == "get_states" and len(received) == 1
        assert sent[0]["event_type"] == "state_changed"
    finally:
        await runner.cleanup()


async def test_config_negative_cache_and_aggregate_coverage(monitor):
    class MixedConfigHA:
        def __init__(self):
            self.calls = []

        async def read(self, command, **params):
            if command == "get_states":
                return [
                    {"entity_id": f"automation.{name}", "state": "on", "attributes": {"id": name}}
                    for name in ("ui", "yaml")
                ]
            return {"issues": []} if command == "repairs/list_issues" else []

        async def automation_config(self, automation_id):
            self.calls.append(automation_id)
            if automation_id == "yaml":
                raise HAError("config_unavailable")
            return {"triggers": [], "actions": []}

    ha = MixedConfigHA()
    await monitor.sync(ha)
    await monitor.sync(ha)
    assert ha.calls == ["ui", "yaml"]
    assert monitor.capabilities["automation_config"].startswith("1/2")
    monitor.config_attempts = {}
    await monitor.sync(ha)
    assert ha.calls == ["ui", "yaml", "ui", "yaml"]
