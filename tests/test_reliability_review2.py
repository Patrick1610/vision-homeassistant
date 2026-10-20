"""Cold failure, efficient gap masking and unpublished-schema safety regressions."""

import asyncio
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_reliability import observed as observed

from vision import reliability
from vision.app import create_app
from vision.config import Settings
from vision.reliability import DeviceReliability, classify_device, entity_role, summarize_window
from vision.store import MIGRATIONS, STORAGE_FAILURES, StorageStartupError, Store


def test_cold_init_retains_measurement_start_and_all_chart_aggregates_are_unknown(observed):
    monitor, _ = observed
    service = DeviceReliability(monitor)
    snapshot = service.snapshot()
    assert snapshot["cache_state"] == "init" and snapshot["cache_as_of"] is None
    assert snapshot["coverage_start"] == 100
    assert snapshot["limited"] and snapshot["evidence_limited"]
    for key in (
        "device_hours",
        "covered_hours",
        "coverage_fraction",
        "known_device_hours",
        "unknown_device_hours",
        "expected_device_hours",
        "offline_share",
        "simultaneous_outage_hours",
        "peak_offline_devices",
    ):
        assert snapshot[key] is None, key
    assert all(p["coverage"] is None and p["observed"] is None for p in snapshot["points"])


def test_actual_first_readonly_capture_failure_through_startup_asgi_is_unknown_then_retries(
    observed, monkeypatch
):
    _, store = observed
    capture = reliability.read_cache_input

    def fail_capture(path, end, current):
        # A genuine mode=ro open failure; the main storage remains healthy.
        return capture(path.with_name("not-present.db"), end, current)

    monkeypatch.setattr(reliability, "read_cache_input", fail_capture)
    app = create_app(
        SimpleNamespace(supervised=False, data=store.path.parent, token=""),
        Settings(),
        connect=False,
    )
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        value = client.get("/api/reliability").json()
        assert value["cache_state"] == "failed" and value["cache_as_of"] is None
        assert value["cache_error_stage"] == "capture" and value["cache_failure_count"] == 1
        assert value["coverage_start"] == 100
        assert value["device_hours"] is value["covered_hours"] is value["coverage_fraction"] is None
        assert client.get("/api/health").status_code == 200
        monkeypatch.setattr(reliability, "read_cache_input", capture)

        async def retry():
            service = app.state.monitor.reliability
            service.request_cache(200)
            await service.wait_cache()

        client.portal.call(retry)
        recovered = client.get("/api/reliability").json()
        assert recovered["cache_state"] == "ready" and recovered["cache_as_of"] == 200
        assert recovered["cache_error"] is None and recovered["cache_failure_count"] == 0


def test_eight_gaps_do_not_amplify_600_unchanged_online_devices_and_coverage_still_masks_them(
    observed, monkeypatch
):
    monitor, store = observed
    service = monitor.reliability
    monitor.devices = []
    monitor.registry = {}
    monitor.entities = {}
    service.current.clear()
    store.execute("DELETE FROM device_current")
    store.execute("DELETE FROM device_observations")
    store.execute("DELETE FROM device_coverage")
    for index in range(601):
        device, entity = f"device-{index}", f"light.synthetic_{index}"
        monitor.devices.append({"id": device})
        monitor.registry[entity] = {"device_id": device, "platform": "synthetic"}
        monitor.observe_state(
            {"entity_id": entity, "state": "unavailable" if index == 600 else "on"},
            100,
            track_device=False,
        )
    monkeypatch.setattr(reliability.time, "time", lambda: 100)

    async def run():
        service.refresh(100)
        service.check("device-600", "power", "Before coverage interruptions")
        for index in range(8):
            service.refresh(110 + 30 * index)
            service.gap(120 + 30 * index)
            service.refresh(130 + 30 * index)
        service.refresh(350)
        await service.wait_cache()

    asyncio.run(run())
    assert store.rows("SELECT count(*) n FROM device_observations")[0]["n"] == 601 + 8
    assert (
        store.rows("SELECT count(*) n FROM device_observations WHERE state='online'")[0]["n"] == 600
    )
    summary = service.snapshot()
    assert summary["covered_hours"] == pytest.approx(90 / 3600)
    assert summary["known_device_hours"] == pytest.approx(601 * 90 / 3600)
    assert summary["device_hours"] == pytest.approx(90 / 3600)
    assert summary["burden"]["direction"] == "unknown"
    assert service.current["device-600"]["episode_kind"] == "baseline"
    assert service.current["device-600"]["episode_started"] == 340
    assert service.device("device-600")["checks"][0]["validation"] == "unknown"


def test_blocked_storage_exposes_counter_headroom_and_cached_retention_eligibility(
    observed, monkeypatch
):
    monitor, store = observed
    service = monitor.reliability
    service.refresh(110)
    monkeypatch.setattr(reliability, "MAX_HISTORY_ROWS", 1)
    monitor.observe_state({"entity_id": "light.main", "state": "on"}, 120)
    service.build_cache(130)
    queries = []
    store.db.set_trace_callback(queries.append)
    value = service.snapshot()["storage"]
    store.db.set_trace_callback(None)
    assert value["blocked"] and value["records"] == value["row_limit"] == 1
    assert value["remaining_rows"] == 0 and value["remaining_encoded_bytes"] > 0
    assert value["earliest_retention_eligible_at"] == 110 + Settings().retention_days * 86400
    assert value["retention_estimate_as_of"] == 130
    assert not any("device_observations" in sql for sql in queries)


@pytest.mark.parametrize("readonly_failure", [False, True])
def test_experimental_schema9_is_rejected_before_db_or_backup_mutation(
    tmp_path, monkeypatch, readonly_failure
):
    path = tmp_path / "vision.db"
    backup = tmp_path / "vision.db.v8.bak"
    with sqlite3.connect(path) as db:
        for version in range(1, 9):
            for statement in MIGRATIONS[version]:
                db.execute(statement)
        db.execute("PRAGMA user_version=8")
        db.execute("INSERT INTO availability VALUES (1,'light.synthetic','unavailable',10,20,0)")
        db.execute("INSERT INTO meta VALUES ('unchanged','true')")
        db.execute("INSERT INTO usage VALUES (1,10,'mock','synthetic',NULL,NULL,0.25,'reserved')")
        db.commit()
        with sqlite3.connect(backup) as copy:
            db.backup(copy)
        db.executescript((Path(__file__).parent / "fixtures/schema9-experimental.sql").read_text())
        db.execute("PRAGMA user_version=9")
        db.execute(
            "INSERT INTO device_observations VALUES (1,'old','Retained','[]','offline',10,NULL,10,"
            "'baseline','cohort','known','unknown','{}','observed')"
        )
        db.execute("INSERT INTO device_current VALUES ('old',1)")
    os.chmod(path, 0o640)
    original, previous_backup = path.read_bytes(), backup.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    connect = sqlite3.connect
    uri = path.resolve().as_uri() + "?mode=ro"

    def unavailable_readonly(database, *args, **kwargs):
        if readonly_failure and database == uri:
            raise sqlite3.OperationalError("Synthetic read-only access failure")
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", unavailable_readonly)
    with pytest.raises(StorageStartupError) as failure:
        Store(path)
    assert failure.value.code == "unsupported_preview_schema"
    assert str(failure.value) == STORAGE_FAILURES["unsupported_preview_schema"]
    assert "Do not delete history or tables" in str(failure.value)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
    assert path.read_bytes() == original and backup.read_bytes() == previous_backup
    assert path.stat().st_mode & 0o777 == 0o640
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 9
        assert db.execute("SELECT * FROM device_current").fetchall() == [("old", 1)]
        assert db.execute("SELECT cost_usd,status FROM usage").fetchall() == [(0.25, "reserved")]
        assert db.execute("SELECT * FROM availability").fetchall() == [
            (1, "light.synthetic", "unavailable", 10, 20, 0)
        ]


@pytest.mark.parametrize("other", ["available", "unknown", "not_loaded", None])
def test_unknown_or_available_unclassified_member_still_blocks_whole_device_offline(other):
    evidence = classify_device(
        [
            {"role": "primary", "availability": "unavailable"},
            {"role": "unclassified", "availability": other},
        ]
    )
    assert evidence["state"] == "unknown" and evidence["blocking_unclassified"] == 1


def test_explicitly_unavailable_unclassified_member_does_not_veto_unanimous_primary():
    missing = {"role": "unclassified", "availability": "unavailable"}
    assert classify_device([missing])["state"] == "unknown"
    observed = classify_device([missing, {"role": "primary", "availability": "unavailable"}])
    assert observed["state"] == "offline" and observed["unclassified_unavailable"] == 1
    assert observed["unassessed_members"] == 0
    assert (
        classify_device([missing, {"role": "primary", "availability": "unknown"}])["state"]
        == "unknown"
    )


@pytest.mark.parametrize(
    "domain,state",
    [
        ("sensor", "3"),
        ("binary_sensor", "off"),
        ("alarm_control_panel", "triggered"),
        ("lawn_mower", "error"),
        ("device_tracker", "not_home"),
    ],
)
def test_closed_functional_roles_use_ha_availability_not_native_value_meaning(
    observed, domain, state
):
    monitor, _ = observed
    entity = domain + ".functional"
    monitor.devices = [{"id": "test"}]
    monitor.registry = {entity: {"device_id": "test", "platform": "synthetic"}}
    monitor.observe_state({"entity_id": entity, "state": state}, 200, track_device=False)
    monitor.reliability.refresh(200)
    assert entity_role(entity) == "primary"
    assert monitor.reliability.current["test"]["state"] == "online"
    monitor.observe_state({"entity_id": entity, "state": "unknown"}, 210)
    assert monitor.reliability.current["test"]["state"] == "unknown"
    monitor.observe_state({"entity_id": entity, "state": "unavailable"}, 220)
    assert monitor.reliability.current["test"]["state"] == "offline"


def test_unknown_device_class_is_not_mislabelled_as_missing_class(observed):
    monitor, _ = observed
    monitor.observe_state(
        {
            "entity_id": "sensor.unrecognized",
            "state": "unavailable",
            "attributes": {"device_class": "not-a-known-class"},
        },
        200,
    )
    assert monitor.availability_metadata["sensor.unrecognized"]["device_class"] == "unrecognized"
    assert entity_role("sensor.unrecognized", device_class="unrecognized") == "unclassified"


def test_retained_episode_defaults_and_nonfinite_times_do_not_crash_priorities(observed):
    monitor, store = observed
    payload = json.loads(store.rows("SELECT payload FROM device_current")[0]["payload"])
    payload.pop("episode_kind")
    payload["episode_started"] = float("nan")
    store.execute("UPDATE device_current SET payload=?", (json.dumps(payload),))
    service = DeviceReliability(monitor)
    service.reliable, service.as_of = True, 200
    assert service.priorities()[0]["kind"] == "device_backlog"
    assert service.current["synthetic-device"]["episode_started"] is None


def test_readonly_capture_explicitly_closes_connection_with_bounded_timeout(observed, monkeypatch):
    monitor, store = observed
    connect = reliability.sqlite3.connect
    closed, timeouts = [], []
    expected_uri = store.path.as_uri() + "?mode=ro"

    class TrackedConnection(sqlite3.Connection):
        def close(self):
            closed.append(True)
            return super().close()

    def tracked(*args, **kwargs):
        if not args or args[0] != expected_uri or not kwargs.get("uri"):
            return connect(*args, **kwargs)
        timeouts.append(kwargs.get("timeout"))
        return connect(*args, **kwargs, factory=TrackedConnection)

    monkeypatch.setattr(reliability.sqlite3, "connect", tracked)
    unrelated = sqlite3.connect(":memory:")
    unrelated.close()
    monitor.reliability.build_cache(200)
    assert closed == [True] and timeouts == [3]


def test_oldest_removed_pointer_yields_capacity_before_newer_alphabetical_tombstone(
    observed, monkeypatch
):
    monitor, store = observed
    service = monitor.reliability
    monitor.devices.append({"id": "aaa-newer"})
    monitor.registry["light.newer"] = {"device_id": "aaa-newer", "platform": "synthetic"}
    monitor.observe_state({"entity_id": "light.newer", "state": "on"}, 150, track_device=False)
    service.refresh(150)
    monitor.devices = []
    service.refresh(200)
    for device, at in [("synthetic-device", 100), ("aaa-newer", 150)]:
        service.current[device]["removed_at"] = at
        store.execute("UPDATE device_current SET removed_at=? WHERE device_id=?", (at, device))
    monkeypatch.setattr(reliability, "MAX_DEVICES", 2)
    monitor.devices = [{"id": "replacement"}]
    monitor.registry = {"light.replacement": {"device_id": "replacement", "platform": "synthetic"}}
    monitor.observe_state(
        {"entity_id": "light.replacement", "state": "on"}, 300, track_device=False
    )
    service.refresh(300)
    assert set(service.current) == {"aaa-newer", "replacement"}
    assert (
        store.rows("SELECT count(*) n FROM device_observations WHERE device_id='synthetic-device'")[
            0
        ]["n"]
        >= 1
    )


def test_populated_classification_change_keeps_old_cohort_and_validation_unknown(
    observed, monkeypatch
):
    monitor, store = observed
    service = monitor.reliability
    monitor.registry["sensor.functional"] = {
        "device_id": "synthetic-device",
        "platform": "synthetic",
        "entity_category": "diagnostic",
    }
    monitor.observe_state({"entity_id": "sensor.functional", "state": "1"}, 110, track_device=False)
    service.refresh(110)
    monkeypatch.setattr(reliability.time, "time", lambda: 115)
    service.policy("synthetic-device", "known", "unknown", "Retained baseline")
    service.check("synthetic-device", "integration", "Before classification changed")
    baseline = service.current["synthetic-device"]["cohort"]
    monitor.registry["sensor.functional"].pop("entity_category")
    service.refresh(120)
    assert service.current["synthetic-device"]["state"] == "partial"
    assert service.current["synthetic-device"]["cohort"] != baseline
    monitor.observe_state({"entity_id": "light.main", "state": "on"}, 130)
    service.refresh(140)
    rows = store.rows("SELECT * FROM device_observations")
    assert baseline in {row["cohort"] for row in rows}
    summary = summarize_window(rows, [(100, 140)], 100, 140, 4)
    assert summary["coverage_fraction"] == 1 and summary["device_hours"] > 0
    assert summary["burden"]["direction"] == "unknown"
    assert summary["burden"]["comparable_devices"] == 0
    assert summary["trend"]["comparable_devices"] == 0
    assert service.device("synthetic-device")["checks"][0]["validation"] == "unknown"
    assert store.rows("SELECT baseline_cohort FROM device_policies")[0]["baseline_cohort"] == (
        baseline
    )
