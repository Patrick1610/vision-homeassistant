"""Independent small arithmetic facts and synthetic local-only device workflows."""

from types import SimpleNamespace

import pytest

from vision.config import Settings
from vision.monitor import Monitor
from vision.reliability import classify_device, entity_role, summarize_window, union_intervals
from vision.security import Redactor
from vision.store import Store


def row(device, start, end, state="offline", **extra):
    return {
        "device_id": device,
        "started": start,
        "ended": end,
        "state": state,
        "cohort": "stable",
        "attention": "review",
        "episode_kind": "transition",
        "episode_started": start,
        **extra,
    }


def test_device_union_is_not_entity_sum_and_wall_time_is_not_device_hours():
    result = summarize_window(
        [row("a", 0, 3600), row("a", 1200, 2400), row("b", 2400, 3600)], [(0, 3600)], 0, 3600, 12
    )
    assert result["device_hours"] == pytest.approx(4800 / 3600)
    assert result["simultaneous_outage_hours"] == 1
    assert result["peak_offline_devices"] == 2
    assert union_intervals([(0, 10), (10, 20), (8, 15)], 5, 18) == [(5, 18)]


def test_short_outage_between_bucket_points_still_contributes_hours():
    result = summarize_window([row("a", 10, 20)], [(0, 100)], 0, 100, 2)
    assert all(p["new"] == 0 for p in result["points"])
    assert result["device_hours"] == pytest.approx(10 / 3600)


def test_gap_and_unknown_do_not_become_healthy_denominators():
    result = summarize_window(
        [row("a", 0, 100), row("b", 0, 100, "unknown")], [(0, 25), (75, 100)], 0, 100, 4
    )
    assert result["device_hours"] == pytest.approx(50 / 3600)
    assert result["known_device_hours"] == pytest.approx(50 / 3600)
    assert result["unknown_device_hours"] == pytest.approx(50 / 3600)
    assert result["offline_share"] == 1
    assert result["points"][1]["new"] is None
    assert result["burden"]["direction"] == "unknown"
    assert not result["trend"]["comparable_devices"]


def test_half_window_burden_comparison_differs_from_endpoint_status():
    result = summarize_window(
        [
            row("a", 0, 10, "online"),
            row("a", 10, 40),
            row("a", 40, 100, "online"),
            row("b", 0, 100, "unknown"),
        ],
        [(0, 100)],
        0,
        100,
        10,
    )
    assert result["trend"]["unchanged"] == 1
    assert result["burden"]["direction"] == "decreased"
    assert result["burden"]["comparable_devices"] == 1
    assert result["burden"]["before_device_hours"] == pytest.approx(30 / 3600)
    assert result["burden"]["after_device_hours"] == 0
    assert result["burden"]["denominator_device_hours_per_half"] == pytest.approx(50 / 3600)
    assert result["offline_share"] == pytest.approx(0.3)


def test_replaced_cohort_and_unknown_period_block_burden_claim():
    result = summarize_window(
        [row("a", 0, 50), row("a", 50, 100, "online", cohort="changed")], [(0, 100)], 0, 100
    )
    assert result["burden"]["direction"] == "unknown"
    assert not result["burden"]["comparable_devices"]


def test_new_expected_and_persistent_disjoint_and_baseline_not_a_new_outage():
    result = summarize_window(
        [
            row("old", -50, None),
            row("baseline", 10, None, episode_kind="baseline"),
            row("new", 20, None),
            row("expected", 0, None, attention="expected"),
        ],
        [(0, 100)],
        0,
        100,
        1,
    )
    point = result["points"][0]
    assert (point["persistent"], point["new"], point["expected"]) == (2, 1, 1)


def test_disabled_update_diagnostic_unknown_and_partial_stay_distinct():
    assert entity_role("update.firmware") == "ancillary"
    assert entity_role("sensor.battery", device_class="battery") == "ancillary"
    assert entity_role("sensor.temperature", device_class="temperature") == "primary"
    assert entity_role("sensor.hidden", category="diagnostic") == "ancillary"
    assert entity_role("light.main", disabled=True) == "disabled"
    assert classify_device([{"role": "primary", "availability": "unknown"}])["state"] == "unknown"
    assert (
        classify_device([{"role": "ancillary", "availability": "unavailable"}])["state"]
        == "unknown"
    )
    assert (
        classify_device(
            [
                {"role": "primary", "availability": "unavailable"},
                {"role": "primary", "availability": "available"},
            ]
        )["state"]
        == "partial"
    )
    assert (
        classify_device(
            [{"role": "primary", "availability": "unavailable"}], registry_complete=False
        )["state"]
        == "unknown"
    )


@pytest.fixture
def observed(tmp_path):
    store = Store(tmp_path / "vision.db")
    monitor = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor())
    monitor.devices = [{"id": "synthetic-device", "name": "Synthetic lamp"}]
    monitor.registry = {
        "light.main": {"device_id": "synthetic-device", "platform": "synthetic"},
        "update.firmware": {
            "device_id": "synthetic-device",
            "platform": "synthetic",
            "entity_category": "diagnostic",
        },
    }
    monitor.observe_state(
        {"entity_id": "light.main", "state": "unavailable"}, 100, track_device=False
    )
    monitor.observe_state(
        {"entity_id": "update.firmware", "state": "unknown"}, 100, track_device=False
    )
    monitor.reliability.refresh(100)
    yield monitor, store
    store.close()


def test_device_cohort_starts_now_and_unchanged_polls_do_not_append_rows(observed):
    monitor, store = observed
    service = monitor.reliability
    service.refresh(200)
    assert len(store.rows("SELECT * FROM device_observations")) == 1
    assert service.snapshot()["counts"]["offline"] == 1
    assert service.cache["24h"]["device_hours"] == pytest.approx(100 / 3600)
    assert service.cache["30d"]["coverage_start"] == 100
    assert service.cache["30d"]["points"][0]["new"] is None
    assert service.current["synthetic-device"]["episode_kind"] == "baseline"


def test_registry_deletion_and_loss_are_unknown_not_recovery(observed):
    monitor, store = observed
    service = monitor.reliability
    monitor.devices = []
    service.refresh(200)
    assert service.current["synthetic-device"]["state"] == "unknown"
    assert service.cache["24h"]["burden"]["direction"] == "unknown"
    service.refresh(300, registry_complete=False)
    assert not service.snapshot()["reliable_now"]
    assert service.snapshot()["counts"]["unknown"] == 1
    assert store.rows("SELECT count(*) n FROM device_current")[0]["n"] == 1


def test_local_policy_does_not_extend_coverage_or_alter_source_history(observed, monkeypatch):
    monitor, store = observed
    service = monitor.reliability
    before = store.rows("SELECT * FROM availability")
    monkeypatch.setattr("vision.reliability.time.time", lambda: 200)
    service.policy("synthetic-device", "known", "battery", "Local expectation")
    assert store.rows("SELECT observed_until FROM device_coverage")[0]["observed_until"] == 100
    assert store.rows("SELECT * FROM availability") == before
    assert service.snapshot()["known_offline"] == 1
    assert not service.priorities()
    assert service.device("synthetic-device")["policy"]["attention"] == "known"


@pytest.mark.parametrize(
    "broken",
    [
        [row("a", float("nan"), 100)],
        [row("a", True, 100)],
        [row("a", 100, 0)],
        [None],
        [row("a", 0, 100), row("a", 40, 60, "online")],
    ],
)
def test_corrupt_or_conflicting_intervals_are_limited_not_healthy_zero(broken):
    value = summarize_window(broken, [(0, 100)], 0, 100)
    assert value["limited"]
    assert value["device_hours"] is None and value["offline_share"] is None
    assert value["burden"]["direction"] == "unknown"
    assert all(p["new"] is None for p in value["points"])


def test_unwatermarked_coverage_is_unknown_and_touching_devices_peak_one():
    missing = summarize_window([row("a", 0, None)], [(0, None)], 0, 100)
    assert missing["limited"] and missing["covered_hours"] == 0
    valid = summarize_window([row("a", 0, 50), row("b", 50, 100)], [(0, 100)], 0, 100)
    assert valid["peak_offline_devices"] == 1
    zero = summarize_window([row("a", 0, 0)], [(0, 100)], 0, 100)
    assert not zero["limited"] and zero["device_hours"] == 0


def test_restart_closes_at_watermark_and_keeps_policy_without_acknowledgment(observed, monkeypatch):
    monitor, store = observed
    monkeypatch.setattr("vision.reliability.time.time", lambda: 150)
    monitor.reliability.policy("synthetic-device", "known", "unknown", "Known backlog")
    monkeypatch.setattr("vision.reliability.time.time", lambda: 1000)
    restarted = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor())
    service = restarted.reliability
    assert not service.snapshot()["reliable_now"]
    assert service.snapshot()["counts"]["offline"] == 0
    assert service.snapshot()["counts"]["unknown"] == 1
    assert service.list_devices(state="offline")["total"] == 0
    assert store.rows("SELECT observed_until,ended FROM device_coverage")[0] == {
        "observed_until": 100,
        "ended": 100,
    }
    assert service.cache_state == "init"
    service.build_cache(1000)  # Explicit CLI readiness; startup uses await wait_cache().
    assert service.cache["24h"]["device_hours"] == 0
    restarted.registry, restarted.devices, restarted.entities = (
        monitor.registry,
        monitor.devices,
        monitor.entities,
    )
    service.refresh(1000)
    assert service.current["synthetic-device"]["attention"] == "known"
    assert service.priorities() == []


def add_primary(monitor, entity="light.second", state="on", now=100):
    monitor.registry[entity] = {"device_id": "synthetic-device", "platform": "synthetic"}
    monitor.observe_state({"entity_id": entity, "state": state}, now, track_device=False)


def test_known_partial_to_offline_is_observed_worsening_not_daily_baseline(observed, monkeypatch):
    monitor, store = observed
    service = monitor.reliability
    add_primary(monitor)
    service.refresh(110)
    assert service.current["synthetic-device"]["state"] == "partial"
    monkeypatch.setattr("vision.reliability.time.time", lambda: 120)
    service.policy("synthetic-device", "known", "unknown", "Partial baseline")
    service.refresh(130)
    assert not service.priorities()
    monitor.observe_state({"entity_id": "light.second", "state": "unavailable"}, 140)
    service.refresh(150)
    assert service.priorities()[0]["kind"] == "worsened_device"
    assert (
        store.rows("SELECT baseline_state FROM device_policies")[0]["baseline_state"] == "partial"
    )
    service.refresh(500)
    assert service.priorities()[0]["kind"] == "worsened_device"


def test_gap_before_known_partial_to_offline_does_not_prove_worsening(observed, monkeypatch):
    monitor, _ = observed
    service = monitor.reliability
    add_primary(monitor)
    service.refresh(110)
    monkeypatch.setattr("vision.reliability.time.time", lambda: 120)
    service.policy("synthetic-device", "known", "unknown", "Partial baseline")
    service.gap(130)
    monitor.observe_state({"entity_id": "light.second", "state": "unavailable"}, 140)
    service.refresh(150)
    assert not service.priorities()


@pytest.mark.parametrize("interruption", ["none", "unknown", "mapping", "gap"])
def test_manual_check_requires_later_continuous_known_same_cohort(
    observed, monkeypatch, interruption
):
    monitor, store = observed
    service = monitor.reliability
    monkeypatch.setattr("vision.reliability.time.time", lambda: 120)
    marker = service.check(
        "synthetic-device", "power", 'Checked manually {"token":"secret-canary"}'
    )
    assert marker["checks"][0]["validation"] == "unknown"
    assert "secret-canary" not in store.rows("SELECT note FROM device_checks")[0]["note"]
    if interruption == "unknown":
        monitor.observe_state({"entity_id": "light.main", "state": "unknown"}, 130)
    elif interruption == "mapping":
        add_primary(monitor, now=130)
        service.refresh(130)
        monitor.registry.pop("light.second")
    elif interruption == "gap":
        service.gap(130)
    monitor.observe_state({"entity_id": "light.main", "state": "on"}, 150)
    service.refresh(200)
    expected = "observed_recovery" if interruption == "none" else "unknown"
    assert service.device("synthetic-device")["checks"][0]["validation"] == expected
    assert not store.rows("SELECT * FROM usage")


def test_same_integration_cluster_does_not_fill_three_cards_or_assert_a_cause(observed):
    monitor, _ = observed
    for index in range(3):
        device_id, entity_id = f"cluster-{index}", f"light.cluster_{index}"
        monitor.devices.append({"id": device_id})
        monitor.registry[entity_id] = {"device_id": device_id, "platform": "synthetic"}
        monitor.observe_state(
            {"entity_id": entity_id, "state": "unavailable"}, 100, track_device=False
        )
    monitor.reliability.refresh(110)
    queue = monitor.reliability.priorities()
    assert len(queue) == 1 and queue[0]["device_count"] == 4
    assert "correlation" in queue[0]["scope_note"] and "not a proven" in queue[0]["scope_note"]
    assert queue[0]["href"] == "#devices/reliability?device=" + queue[0]["device_id"]
    assert len(queue[0]["related_devices"]) == 4


@pytest.mark.parametrize("status", ["known", "expected", "snoozed"])
def test_health_and_run_queue_respects_episode_bound_attention(observed, monkeypatch, status):
    monitor, store = observed
    service = monitor.reliability
    now = 1000
    monkeypatch.setattr("vision.reliability.time.time", lambda: now)
    store.issue("repair:synthetic", "repair", "critical", "Critical observation", {}, now=now)
    store.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
        ("automation.test", "r1", None, now, "failed", 0, "{}"),
    )
    store.execute(
        "INSERT INTO run_timing VALUES (?,?,?,?)", ("automation.test", "r1", now, "ha_trace")
    )
    store.issue(
        "automation:automation.test",
        "automation",
        "error",
        "Failed",
        {"entity_id": "automation.test", "run_id": "r1"},
        now=now,
    )
    for key in ("repair:synthetic", "automation:automation.test"):
        monitor.insights.annotate(key, status, "Local attention", hours=1)
    service.as_of = now
    assert all(r["kind"] not in {"health", "recent_failure"} for r in service.priorities())
    # Exact expiry resumes review; a stale episode must never suppress a new generation.
    store.execute("UPDATE case_annotations SET expires=?", (now,))
    assert {"health", "recent_failure"} <= {r["kind"] for r in service.priorities()}
    store.execute("UPDATE case_annotations SET expires=NULL,case_first_seen=0")
    assert {"health", "recent_failure"} <= {r["kind"] for r in service.priorities()}


def test_old_polled_log_normal_mode_and_recovered_run_do_not_create_fresh_actions(
    observed, monkeypatch
):
    monitor, store = observed
    now = 1_000_000
    monkeypatch.setattr("vision.reliability.time.time", lambda: now)
    service = monitor.reliability
    service.as_of = now
    for run_id, started, outcome in (
        ("old", 1, "failed"),
        ("failed", now - 10, "failed"),
        ("later", now, "succeeded"),
        ("mode", now, "blocked"),
        ("condition", now, "condition_stopped"),
    ):
        store.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
            ("automation.test", run_id, None, started, outcome, 0, "{}"),
        )
        store.execute(
            "INSERT INTO run_timing VALUES (?,?,?,?)",
            ("automation.test", run_id, started, "ha_trace"),
        )
    store.issue(
        "automation:automation.test",
        "automation",
        "error",
        "Old failure",
        {"entity_id": "automation.test", "run_id": "failed"},
        now=1,
    )
    store.issue("log:old", "log", "error", "Old log", {"message": "Retained"}, now=1)
    store.issue("log:old", "log", "error", "Old log", {"message": "Retained"}, now=now)
    assert not any(r["kind"] == "recent_failure" for r in service.priorities())
    assert store.rows("SELECT last_seen FROM issues WHERE key='log:old'")[0]["last_seen"] == now


def test_retained_cohort_and_interval_caps_are_explicit_not_silent_eviction(observed, monkeypatch):
    monitor, store = observed
    service = monitor.reliability
    monkeypatch.setattr("vision.reliability.MAX_DEVICES", 1)
    monitor.devices.append({"id": "replacement"})
    monitor.registry = {
        **monitor.registry,
        "light.replacement": {"device_id": "replacement", "platform": "synthetic"},
    }
    monitor.observe_state(
        {"entity_id": "light.replacement", "state": "on"}, 200, track_device=False
    )
    service.refresh(200)
    assert service.inventory_coverage["omitted_devices"] == 1
    assert service.inventory_coverage["limited"]
    assert list(service.current) == ["synthetic-device"]
    assert service.current["synthetic-device"]["state"] == "offline"
    monitor.observe_state({"entity_id": "light.main", "state": "on"}, 205)
    monkeypatch.setattr("vision.reliability.MAX_INTERVALS", 1)
    service.build_cache(210)
    value = service.snapshot()
    assert value["limited"] and value["device_hours"] is None
    assert value["burden"]["before_device_hours"] is None
    assert store.rows("SELECT count(*) n FROM device_observations")[0]["n"] == 2


def test_retention_keeps_manual_checks_policy_and_current_tombstone(observed, monkeypatch):
    monitor, store = observed
    service = monitor.reliability
    monkeypatch.setattr("vision.reliability.time.time", lambda: 120)
    service.policy("synthetic-device", "expected", "unknown", "Persistent local expectation")
    service.check("synthetic-device", "integration", "Manual check history")
    monitor.devices = []
    service.refresh(130)
    service.gap(140)
    monkeypatch.setattr("vision.reliability.time.time", lambda: 200 * 86400)
    store.prune(90)
    assert len(store.rows("SELECT * FROM device_observations")) == 1
    assert store.rows("SELECT state FROM device_observations")[0]["state"] == "unknown"
    assert (
        len(store.rows("SELECT * FROM device_policies"))
        == len(store.rows("SELECT * FROM device_checks"))
        == 1
    )
    assert not store.rows("SELECT * FROM device_coverage")
    assert store.rows("PRAGMA foreign_key_check") == []


def test_failed_local_policy_rolls_back_all_rows_and_recovery_does_not_bridge_gap(
    observed, monkeypatch
):
    import sqlite3

    monitor, store = observed
    service = monitor.reliability
    previous = store.rows("SELECT * FROM device_observations")
    store.execute(
        "CREATE TEMP TRIGGER fail_observation BEFORE INSERT ON device_observations "
        "BEGIN SELECT RAISE(ABORT,'synthetic write failure'); END"
    )
    monkeypatch.setattr("vision.reliability.time.time", lambda: 150)
    with pytest.raises(sqlite3.IntegrityError):
        service.policy("synthetic-device", "expected", "battery", "Must roll back")
    assert store.rows("SELECT * FROM device_policies") == []
    assert store.rows("SELECT * FROM device_observations") == previous
    assert not service.snapshot()["reliable_now"]
    store.execute("DROP TRIGGER fail_observation")
    service.refresh(200)
    service.refresh(210)
    assert service.current["synthetic-device"]["attention"] == "review"
    assert service.cache["24h"]["device_hours"] == pytest.approx(10 / 3600)
    assert service.device("synthetic-device")["coverage_gaps"] == [{"started": 100, "ended": 200}]


def test_conflicting_retained_observations_cannot_validate_a_manual_recovery(observed, monkeypatch):
    monitor, store = observed
    service = monitor.reliability
    monkeypatch.setattr("vision.reliability.time.time", lambda: 120)
    service.check("synthetic-device", "power", "Manual observation")
    old = service.current["synthetic-device"]
    store.execute(
        "INSERT INTO device_observations(device_id,platforms,state,started,ended,"
        "episode_kind,cohort,attention,evidence,reason) "
        "VALUES (?,?,'online',100,150,'none',?,'review','{}','synthetic conflict')",
        (old["device_id"], "[]", old["cohort"]),
    )
    monitor.observe_state({"entity_id": "light.main", "state": "on"}, 170)
    service.refresh(200)
    assert service.snapshot()["limited"]
    assert service.device("synthetic-device")["checks"][0]["validation"] == "unknown"
