"""Preserving limits, durable attention and off-loop snapshot qualification."""

import asyncio
import json
import threading
import time

import pytest
from test_reliability import add_primary, row
from test_reliability import observed as observed

from vision import reliability
from vision.reliability import DeviceReliability, classify_device, entity_role, summarize_window


def count(store):
    return store.rows("SELECT count(*) n FROM device_observations")[0]["n"]


def test_role_policy_handles_initial_event_image_unknown_without_hiding_unknown_primary():
    for entity in ("event.button", "image.latest", "update.firmware"):
        assert entity_role(entity) == "ancillary"
    for domain in ("camera", "text", "date", "time"):
        assert entity_role(domain + ".native") == "primary"
    for dc in ("enum", "date", "timestamp"):
        assert entity_role("sensor.native", device_class=dc) == "primary"
    assert entity_role("sensor.native", category="diagnostic", device_class="enum") == "ancillary"
    mixed = [
        {"role": "primary", "availability": "unavailable"},
        {"role": "primary", "availability": "unknown"},
        {"role": "ancillary", "availability": "unknown"},
    ]
    assert classify_device(mixed)["state"] == "unknown"
    assert classify_device(mixed[2:])["state"] == "unknown"


def test_member_flaps_update_current_evidence_not_history_boundaries(observed):
    monitor, store = observed
    service = monitor.reliability
    add_primary(monitor, now=105)
    monitor.observe_state({"entity_id": "light.second", "state": "on"}, 106)
    service.refresh(110)
    before = count(store)
    # Three members ensure the device remains partial as one member changes.
    monitor.registry["light.third"] = dict(monitor.registry["light.second"])
    monitor.observe_state({"entity_id": "light.third", "state": "on"}, 111)
    service.refresh(112)
    before = count(store)
    for index in range(40):
        monitor.observe_state(
            {"entity_id": "light.second", "state": "on" if index % 2 else "unavailable"},
            120 + index,
        )
    assert service.current["synthetic-device"]["state"] == "partial"
    assert count(store) == before
    value = store.rows("SELECT payload FROM device_current")[0]["payload"]
    assert json.loads(value)["evidence_at"] == 159
    assert len(value.encode()) <= reliability.MAX_CURRENT_PAYLOAD_BYTES
    statements = []
    store.db.set_trace_callback(statements.append)
    service.observe("light.second", 170)
    store.db.set_trace_callback(None)
    assert not any(sql.startswith(("BEGIN", "INSERT", "UPDATE")) for sql in statements)


def test_durable_worsening_survives_unknown_note_power_restart_and_explicit_ack(
    observed, monkeypatch
):
    monitor, store = observed
    service = monitor.reliability
    add_primary(monitor, now=105)
    monitor.observe_state({"entity_id": "light.second", "state": "on"}, 110)
    service.refresh(115)
    monkeypatch.setattr(reliability.time, "time", lambda: 120)
    service.policy("synthetic-device", "known", "unknown", "Partial baseline")
    monitor.observe_state({"entity_id": "light.second", "state": "unavailable"}, 130)
    baseline = service.policies["synthetic-device"]["baseline_state"]
    assert service.priorities()[0]["kind"] == "worsened_device"
    monitor.observe_state({"entity_id": "light.second", "state": "unknown"}, 140)
    service.policy("synthetic-device", "known", "battery", "A note is not acknowledgement")
    assert service.policies["synthetic-device"]["baseline_state"] == baseline == "partial"
    assert service.priorities()[0]["kind"] == "worsened_device"
    monitor.observe_state({"entity_id": "light.second", "state": "unavailable"}, 150)
    restarted = DeviceReliability(monitor)
    monitor.reliability = restarted
    restarted.refresh(160)
    assert restarted.priorities()[0]["kind"] == "worsened_device"
    result = restarted.policy(
        "synthetic-device",
        "known",
        "battery",
        "Explicitly accepted current evidence",
        acknowledge_worsening=True,
    )
    assert result["policy"]["baseline_state"] == "offline"
    assert result["policy"]["worsened_at"] is None
    assert not restarted.priorities()


def test_gap_starts_new_baseline_and_does_not_continue_proven_episode(observed):
    monitor, _ = observed
    service = monitor.reliability
    monitor.observe_state({"entity_id": "light.main", "state": "on"}, 120)
    service.refresh(125)
    monitor.observe_state({"entity_id": "light.main", "state": "unavailable"}, 130)
    service.refresh(140)
    assert service.current["synthetic-device"]["episode_kind"] == "transition"
    service.gap(200)
    service.refresh(400)
    current = service.current["synthetic-device"]
    assert current["episode_kind"] == "baseline" and current["episode_started"] == 400


def test_window_admission_includes_whole_devices_independently(observed, monkeypatch):
    monitor, store = observed
    now = 30 * 86400
    store.execute("DELETE FROM device_current")
    store.execute("DELETE FROM device_observations")
    for index in range(5):
        store.execute(
            "INSERT INTO device_observations(device_id,state,started,ended,episode_kind,cohort,"
            "attention,platforms,evidence,reason) VALUES ('a','online',?,?,'none','stable',"
            "'review','[]','{}','synthetic')",
            (index * 86400, (index + 1) * 86400),
        )
    store.execute(
        "INSERT INTO device_observations(device_id,state,started,episode_kind,cohort,attention,"
        "platforms,evidence,reason) VALUES ('b','offline',?,'baseline','stable',"
        "'review','[]','{}','test')",
        (now - 100,),
    )
    monkeypatch.setattr(reliability, "MAX_INTERVALS", 3)
    monitor.reliability.build_cache(now)
    small, long = (monitor.reliability.cache[w] for w in ("24h", "30d"))
    assert not small["limited"] and small["selection"]["included_devices"] == 1
    assert long["limited"] and long["selection"] == {
        "included_devices": 1,
        "excluded_devices": 1,
        "total_devices": 2,
        "rows": 1,
        "encoded_bytes": store.rows(
            "SELECT encoded_bytes FROM device_observations WHERE device_id='b'"
        )[0]["encoded_bytes"],
        "reason": "whole-device window selection limit",
    }
    assert long["burden"]["excluded_devices"] >= 1
    assert {r["device_id"] for r in monitor.reliability.inputs["30d"]["rows"]} == {"b"}


@pytest.mark.parametrize("bound", ["rows", "bytes"])
def test_history_admission_keeps_old_rows_and_current_evidence_with_unknown_gap(
    observed, monkeypatch, bound
):
    monitor, store = observed
    service = monitor.reliability
    service.refresh(110)
    before = store.rows("SELECT * FROM device_observations")
    usage = service.storage()
    monkeypatch.setattr(
        reliability, "MAX_HISTORY_ROWS", usage["records"] if bound == "rows" else 250000
    )
    monkeypatch.setattr(
        reliability, "MAX_HISTORY_BYTES", usage["bytes"] if bound == "bytes" else 128 * 1024 * 1024
    )
    monitor.observe_state({"entity_id": "light.main", "state": "on"}, 120)
    assert service.storage()["blocked"]
    assert count(store) == len(before)
    assert store.rows("SELECT ended FROM device_observations")[0]["ended"] == 110
    assert store.rows("SELECT observation_id FROM device_current")[0]["observation_id"] is None
    assert service.current["synthetic-device"]["state"] == "online"
    assert service.current["synthetic-device"]["interval_ended"] is not None
    service.refresh(130)
    assert service.cache["24h"]["covered_hours"] == pytest.approx(10 / 3600)
    # Configured retention, not admission eviction, can eventually free closed history.
    monkeypatch.setattr(reliability.time, "time", lambda: 100 * 86400)
    store.prune(90)
    assert count(store) == 0
    monkeypatch.setattr(reliability, "MAX_HISTORY_ROWS", 250000)
    monkeypatch.setattr(reliability, "MAX_HISTORY_BYTES", 128 * 1024 * 1024)
    service.refresh(100 * 86400)
    assert not service.storage()["blocked"] and count(store) == 1


def test_storage_counters_utf8_rollback_and_no_body_scan(observed):
    _, store = observed
    original = store.rows("SELECT * FROM device_storage ORDER BY kind")
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.execute("UPDATE device_current SET payload=payload||'é🙂'")
            store.execute("UPDATE device_observations SET reason=reason||'é🙂'")
            assert (
                store.rows("SELECT bytes FROM device_storage WHERE kind='history'")[0]["bytes"]
                == original[1]["bytes"] + 6
            )
            raise RuntimeError("rollback")
    assert store.rows("SELECT * FROM device_storage ORDER BY kind") == original
    # Every variable persisted history column contributes to exact UTF-8 accounting.
    actual = store.rows(
        "SELECT sum(encoded_bytes) bytes,count(*) records FROM device_observations"
    )[0]
    assert (
        reliability.history_bytes(store.rows("SELECT * FROM device_observations")[0])
        == actual["bytes"]
    )
    statements = []
    store.db.set_trace_callback(statements.append)
    usage = store.rows("SELECT * FROM device_storage WHERE kind='history'")[0]
    store.db.set_trace_callback(None)
    assert usage["bytes"] == actual["bytes"]
    assert not any("sum(" in sql.lower() or "payload" in sql.lower() for sql in statements)


@pytest.mark.parametrize("new_observation", [300, 100 * 86400])
def test_removed_pointer_yields_to_active_registry_without_losing_policy_checks(
    observed, monkeypatch, new_observation
):
    monitor, store = observed
    service = monitor.reliability
    monkeypatch.setattr(reliability, "MAX_DEVICES", 1)
    service.policy("synthetic-device", "known", "mains", "Retain me")
    service.check("synthetic-device", "power", "Historical local check")
    monitor.devices = []
    service.refresh(200)
    monitor.devices = [{"id": "replacement"}]
    monitor.registry = {"light.replacement": {"device_id": "replacement", "platform": "test"}}
    monitor.observe_state(
        {"entity_id": "light.replacement", "state": "on"}, 300, track_device=False
    )
    service.refresh(new_observation)
    assert list(service.current) == ["replacement"]
    assert service.current["replacement"]["state"] == "online"
    assert store.rows("SELECT * FROM device_policies")[0]["device_id"] == "synthetic-device"
    assert store.rows("SELECT * FROM device_checks")[0]["device_id"] == "synthetic-device"
    assert count(store) >= 3  # No history eviction to admit the replacement.


def test_membership_limit_degrades_only_affected_devices(observed, monkeypatch):
    monitor, _ = observed
    monitor.devices.append({"id": "b"})
    monitor.registry = {
        "light.a": {"device_id": "synthetic-device", "platform": "test"},
        "light.b": {"device_id": "b", "platform": "test"},
        "light.c": {"device_id": "b", "platform": "test"},
    }
    for entity in monitor.registry:
        monitor.observe_state(
            {"entity_id": entity, "state": "unavailable"}, 200, track_device=False
        )
    monkeypatch.setattr(reliability, "MAX_ENTITIES", 2)
    monitor.reliability.refresh(200)
    assert monitor.reliability.current["synthetic-device"]["state"] == "offline"
    assert monitor.reliability.current["b"]["state"] == "unknown"
    assert monitor.reliability.inventory_coverage["incomplete_devices"] == 1


def test_empty_membership_and_online_membership_are_distinct_and_corrupt_state_is_unknown(observed):
    empty = summarize_window([], [(0, 100)], 0, 100, 1)
    online = summarize_window([row("a", 0, 100, "online")], [(0, 100)], 0, 100, 1)
    assert empty["points"][0]["observed"] == 0
    assert online["points"][0]["observed"] == online["points"][0]["online"] == 1
    monitor, store = observed
    store.execute("UPDATE device_current SET payload=json_set(payload,'$.state','corrupt')")
    restarted = DeviceReliability(monitor)
    assert restarted.device_summary(restarted.current["synthetic-device"])["state"] == "unknown"
    assert restarted.snapshot()["counts"]["unknown"] == 1


def test_offloop_coalescing_rebuild_and_nonblocking_policy_post(observed, monkeypatch):
    monitor, _ = observed
    service = monitor.reliability
    original = reliability.compile_cache
    entered, release = threading.Event(), threading.Event()
    compiles = []

    def delayed(data):
        compiles.append(data["as_of"])
        entered.set()
        assert release.wait(3)
        return original(data)

    monkeypatch.setattr(reliability, "compile_cache", delayed)

    async def run():
        service.request_cache(200)
        deadline = time.monotonic() + 2
        while not entered.is_set():
            assert time.monotonic() < deadline
            await asyncio.sleep(0.001)
        heartbeat = 0
        for _ in range(12):
            assert service.snapshot()["cache_pending"]
            heartbeat += 1
            await asyncio.sleep(0.002)
        assert heartbeat == 12  # Worker remains gated while loop and snapshot/JSON reads progress.
        before = len(compiles)
        for at in range(201, 211):
            service.request_cache(at)
        service.policy("synthetic-device", "known", "battery", "Immediate local acknowledgement")
        assert not service.snapshot()["priorities"]
        service.check("synthetic-device", "power", "No compile in this POST")
        assert len(compiles) == before
        with pytest.raises(RuntimeError, match="background"):
            service.build_cache(220)
        release.set()
        await service.wait_cache()
        assert len(compiles) == 2 and service.cache_state == "ready"
        assert not service.snapshot()["cache_pending"]
        await service.close()

    asyncio.run(run())


def test_worker_failure_retains_last_snapshot_with_explicit_failed_state(observed, monkeypatch):
    service = observed[0].reliability
    previous = service.cache_as_of

    def broken(_):
        raise ValueError("Private path must not be returned")

    monkeypatch.setattr(reliability, "compile_cache", broken)

    async def run():
        service.request_cache(200)
        await service.wait_cache()
        value = service.snapshot()
        assert value["cache_state"] == "failed" and value["cache_as_of"] == previous
        assert value["cache_error"] == "Device chart snapshot unavailable"
        await service.close()

    asyncio.run(run())


@pytest.mark.parametrize("invalid", [None, {}, [], 123])
def test_nonstring_retained_states_fail_to_unknown_instead_of_crashing(observed, invalid):
    monitor, store = observed
    payload = json.loads(store.rows("SELECT payload FROM device_current")[0]["payload"])
    payload["state"] = invalid
    store.execute("UPDATE device_current SET payload=?", (json.dumps(payload),))
    service = DeviceReliability(monitor)
    assert service.snapshot()["counts"]["unknown"] == 1
    assert service.device("synthetic-device")["state"] == "unknown"
    summary = summarize_window([row("a", 0, 100, invalid)], [(0, 100)], 0, 100)
    assert summary["limited"] and summary["device_hours"] is None


def test_different_categories_cannot_double_count_one_device_at_bucket_end():
    result = summarize_window(
        [row("a", 0, 100, episode_kind="baseline"), row("a", 20, 80)], [(0, 100)], 0, 100, 10
    )
    assert result["conflicting_intervals"] and result["limited"]
    assert all(point["observed"] is None for point in result["points"])


def test_changed_membership_does_not_prove_worsening_against_different_baseline(observed):
    monitor, _ = observed
    service = monitor.reliability
    add_primary(monitor, now=105)
    service.refresh(110)
    assert service.current["synthetic-device"]["state"] == "partial"
    service.policy("synthetic-device", "known", "unknown", "Old cohort")
    add_primary(monitor, entity="light.replacement", now=120)
    service.refresh(125)
    monitor.observe_state({"entity_id": "light.second", "state": "unavailable"}, 130)
    monitor.observe_state({"entity_id": "light.replacement", "state": "unavailable"}, 135)
    service.refresh(140)
    assert service.current["synthetic-device"]["state"] == "offline"
    assert service.policies["synthetic-device"]["worsened_at"] is None
    assert not service.priorities()


def test_first_instant_has_no_comparable_device_and_counts_exclusion(observed):
    service = observed[0].reliability
    value = service.snapshot()
    assert value["burden"]["total_devices"] == 1
    assert value["burden"]["comparable_devices"] == 0
    assert value["burden"]["excluded_devices"] == 1


def test_entity_removal_releases_availability_metadata(observed):
    monitor, _ = observed
    monitor.availability_metadata["light.main"] = {"device_class": "enum"}
    monitor.event(
        {"event_type": "state_changed", "data": {"entity_id": "light.main", "new_state": None}}
    )
    assert "light.main" not in monitor.availability_metadata
    assert "light.main" not in monitor.entities
