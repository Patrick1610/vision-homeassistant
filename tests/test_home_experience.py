"""Real local journey: independent preference semantics, provenance and preserved source rows."""

import asyncio
import hashlib
import json
import sqlite3
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.evidence import dependency_graph, structure
from vision.ha import EVENTS, HAError, validate_read
from vision.home import problem_id
from vision.store import MIGRATIONS, SCHEMA_VERSION, Store

HEADERS = {"x-vision-request": "1"}


def seed(monitor, states=("unavailable", "unavailable", "on"), *, now=None):
    now = time.time() - 300 if now is None else now
    monitor.devices = [{"id": f"d{i}", "name": f"Friendly lamp {i}"} for i in range(len(states))]
    monitor.local_areas = {"room": "Living room <local-only>"}
    monitor.local_device_locations = {f"d{i}": {"area_id": "room"} for i in range(len(states))}
    for i, state in enumerate(states):
        entity = f"light.local_{i}"
        monitor.registry[entity] = {"device_id": f"d{i}", "platform": "synthetic"}
        monitor.observe_state(
            {"entity_id": entity, "state": state, "attributes": {"friendly_name": f"Function {i}"}},
            now,
            track_device=False,
        )
    monitor.reliability.refresh(now)
    monitor.reliability.refresh(now + 100)
    monitor.connected = True
    monitor.home.refresh()
    monitor.entities["automation.evening"] = {
        "name": "Evening lighting",
        "entity_id": "automation.evening",
        "availability": "available",
    }
    monitor.store.replace_graph(
        dependency_graph(
            monitor.entities,
            monitor.registry,
            monitor.devices,
            {
                "automation.evening": structure(
                    {
                        "actions": [
                            {"action": "light.turn_on", "target": {"entity_id": "light.local_0"}}
                        ]
                    }
                )
            },
        )
    )
    return now


@pytest.fixture
def home(tmp_path):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    app = create_app(runtime, Settings(), connect=False)
    with TestClient(app, client=("127.0.0.1", 1)) as client:
        seed(app.state.monitor)
        yield client, app


def post(client, path, value):
    return client.post("/api/" + path, json=value, headers=HEADERS)


def test_today_bootstrap_is_not_correlated_outage_and_dossier_is_useful(home):
    client, app = home
    today = client.get("/api/today").json()
    assert today["status"] == "attention" and len(today["priorities"]) == 2
    assert all(p["kind"] == "device" and not p["changed"] for p in today["priorities"])
    assert today["priorities"][0]["room"] == "Living room <local-only>"
    key = problem_id("device", "d0")
    detail = client.get("/api/problems/" + key).json()
    assert detail["device"]["state"] == "offline"
    assert detail["members"][0]["name"] == "Function 0"
    impact = detail["dependencies"]["affected_automations"][0]
    assert impact["display_name"] == "Evening lighting"
    assert impact["href"] == "#automations/automation.evening"
    assert detail["problem"]["selection"] == {"kind": "device", "device_id": "d0"}
    assert app.state.tasks == [] and not app.state.store.rows("SELECT * FROM usage")
    assert client.get("/api/problems?limit=101").status_code == 422
    assert client.get("/api/problems?mode=everything").status_code == 422


def test_actual_covered_transitions_group_with_healthy_contrary_evidence(home):
    client, app = home
    m = app.state.monitor
    at = time.time() - 200
    seed(m, ("on", "on", "on"), now=at)
    for i in range(2):
        m.observe_state(
            {"entity_id": f"light.local_{i}", "state": "unavailable"}, at + 150, track_device=False
        )
    m.reliability.refresh(at + 150)
    m.home.refresh()
    values = client.get("/api/today").json()["priorities"]
    assert len(values) == 1 and values[0]["kind"] == "group"
    assert values[0]["member_count"] == 2 and not values[0]["declared_shared_upstream"]
    assert values[0]["selection"]["kind"] == "device_group"
    detail = client.get("/api/problems/" + values[0]["problem_id"]).json()
    assert len(detail["members"]) == 2
    assert detail["healthy_counterevidence"][0]["device_id"] == "d2"
    identity = values[0]["problem_id"]
    m.home.refresh()
    assert client.get("/api/today").json()["priorities"][0]["problem_id"] == identity
    m.reliability.gap(at + 160)
    m.home.refresh()
    assert client.get("/api/today").json()["status"] == "limited"
    assert client.get("/api/today").json()["priorities"][0]["stale"]
    assert client.get("/api/today").json()["priorities"][0]["state"] == "unknown"


def test_independent_preferences_cancel_reads_and_rerun_preserve_policy_and_source(home):
    client, app = home
    m, db = app.state.monitor, app.state.store
    m.reliability.policy("d0", "known", "battery", "Already known")
    m.home.refresh()
    before = {
        t: db.rows(f"SELECT * FROM {t}")
        for t in (
            "device_policies",
            "device_observations",
            "device_checks",
            "availability",
            "usage",
        )
    }
    unchanged = db.db.total_changes
    assert client.get("/api/home/preferences").json()["intake"] == "new"
    client.get("/api/home/devices")
    assert db.db.total_changes == unchanged  # Merely opening/cancelling intake cannot mutate.
    value = {
        "locale": "nl",
        "intake": "draft",
        "devices": [
            {"device_id": "d0", "importance": "high", "known_issue": True, "usual_behavior": True}
        ],
    }
    assert post(client, "home/preferences", value).status_code == 200
    assert (
        post(
            client,
            "home/preferences",
            {"intake": "complete", "devices": [{"device_id": "d0", "importance": "low"}]},
        ).status_code
        == 200
    )
    entry = client.get("/api/home/devices?q=Friendly lamp 0").json()["items"][0]
    assert entry["preference"]["known_issue"] and entry["preference"]["usual_behavior"]
    assert entry["preference"]["importance"] == "low"
    assert client.get("/api/home/preferences").json()["locale"] == "nl"
    for table, rows in before.items():
        assert db.rows(f"SELECT * FROM {table}") == rows
    assert (
        post(
            client, "home/preferences", {"devices": [{"device_id": "d0", "known_issue": "false"}]}
        ).status_code
        == 422
    )
    saved = db.rows("SELECT * FROM home_preferences")
    assert (
        post(
            client,
            "home/preferences",
            {"locale": "en", "devices": [{"device_id": "not-registered"}]},
        ).status_code
        == 400
    )
    assert db.rows("SELECT * FROM home_preferences") == saved


def test_local_known_partial_to_offline_worsening_survives_unknown_and_importance_edit(home):
    client, app = home
    m = app.state.monitor
    now = time.time() - 200
    seed(m, ("on", "on", "on"), now=now)
    # Two primary members create an actual partial state on d0.
    m.registry["switch.second"] = {"device_id": "d0", "platform": "synthetic"}
    m.observe_state(
        {"entity_id": "switch.second", "state": "unavailable"}, now + 110, track_device=False
    )
    m.reliability.refresh(now + 110)
    m.home.refresh()
    assert m.reliability.current["d0"]["state"] == "partial"
    assert (
        post(
            client, "home/preferences", {"devices": [{"device_id": "d0", "known_issue": True}]}
        ).status_code
        == 200
    )
    m.observe_state(
        {"entity_id": "light.local_0", "state": "unavailable"}, now + 120, track_device=False
    )
    m.reliability.refresh(now + 120)
    m.home.refresh()
    assert m.home.preference(m.reliability.current["d0"])["worsened"]
    baseline = m.store.rows("SELECT * FROM home_device_preferences WHERE device_id='d0'")[0]
    m.observe_state(
        {"entity_id": "light.local_0", "state": "unknown"}, now + 130, track_device=False
    )
    m.reliability.refresh(now + 130)
    m.home.refresh()
    m.observe_state(
        {"entity_id": "light.local_0", "state": "unavailable"}, now + 140, track_device=False
    )
    m.reliability.refresh(now + 140)
    m.home.refresh()
    assert (
        post(
            client,
            "home/preferences",
            {
                "intake": "complete",
                "devices": [{"device_id": "d0", "importance": "high", "usual_behavior": True}],
            },
        ).status_code
        == 200
    )
    after = m.store.rows("SELECT * FROM home_device_preferences WHERE device_id='d0'")[0]
    for field in ("baseline_state", "baseline_cohort", "worsened_at", "worsened_cohort"):
        assert after[field] == baseline[field]
    assert client.get("/api/today").json()["priorities"][0]["preference"]["worsened"]
    assert (
        post(
            client,
            "home/preferences",
            {"devices": [{"device_id": "d0", "acknowledge_worsening": True}]},
        ).status_code
        == 200
    )
    assert not m.home.preference(m.reliability.current["d0"])["worsened"]


def test_feedback_is_subjective_idempotent_redacted_and_does_not_resolve(home):
    client, app = home
    db = app.state.store
    key = problem_id("device", "d0")
    detail = client.get("/api/problems/" + key).json()
    before = db.rows("SELECT * FROM device_observations")
    feedback = {
        "request_id": "feedback_request_123456",
        "episode": detail["problem"]["episode"],
        "kind": "seems_recovered",
        "note": '{"token":"synthetic-secret-canary"}<script>x</script>',
    }
    for _ in range(2):
        response = post(client, f"problems/{key}/feedback", feedback)
        assert response.status_code == 200
    assert len(response.json()["feedback"]) == 1
    assert "synthetic-secret-canary" not in response.text
    assert response.json()["device"]["state"] == "offline"
    assert db.rows("SELECT * FROM device_observations") == before
    feedback.update(request_id="feedback_checked_123456", kind="checked")
    assert post(client, f"problems/{key}/feedback", feedback).status_code == 200
    assert len(db.rows("SELECT * FROM device_checks")) == 1
    assert not db.rows("SELECT * FROM usage")
    feedback["episode"] = "0" * 32
    assert post(client, f"problems/{key}/feedback", feedback).status_code == 409


def test_source_admission_has_no_device_topthree_starvation_and_episode_identity(home):
    client, app = home
    m, db = app.state.monitor, app.state.store
    now = time.time()
    m.entities["automation.test"] = {"name": "Friendly automation"}
    db.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
        ("automation.test", "run1", None, now, "failed", 1, "{}"),
    )
    db.execute(
        "INSERT INTO run_timing VALUES (?,?,?,?)", ("automation.test", "run1", now, "ha_trace")
    )
    db.issue(
        "automation:automation.test",
        "automation",
        "error",
        "Failed",
        {"entity_id": "automation.test", "run_id": "run1"},
        now,
    )
    db.issue(
        "automation_step:automation.test",
        "automation_step",
        "warning",
        "Same run contains step errors",
        {"entity_id": "automation.test", "run_id": "run1"},
        now,
    )
    db.issue("repair:critical", "repair", "critical", "Severe source health", {}, now)
    m.home.refresh()
    items = client.get("/api/problems?mode=attention").json()["items"]
    run = next(r for r in items if r.get("selection", {}).get("kind") == "automation_run")
    assert sum(r.get("selection", {}).get("kind") == "automation_run" for r in items) == 1
    assert run["state"] == "source_failure"
    assert (
        run["selection"]["entity_id"] == "automation.test" and run["selection"]["run_id"] == "run1"
    )
    assert run["name"] == "Friendly automation"
    assert client.get("/api/today").json()["priorities"][0]["target"] == "repair:critical"
    old = next(r for r in items if r["target"] == "repair:critical")
    app.state.insights.annotate("repair:critical", "known", "Quiet", 24)
    m.home.refresh()
    assert all(
        r["target"] != "repair:critical" for r in client.get("/api/today").json()["priorities"]
    )
    db.execute("DELETE FROM issues WHERE key='repair:critical'")
    db.issue("repair:critical", "repair", "critical", "New episode", {}, now + 1)
    m.home.refresh()
    new = client.get("/api/today").json()["priorities"][0]
    assert new["problem_id"] != old["problem_id"]


def test_migration_ten_is_additive_and_restart_preserves_v9_history(tmp_path):
    path = tmp_path / "vision.db"
    with sqlite3.connect(path) as db:
        for version in range(1, 10):
            for sql in MIGRATIONS[version]:
                db.execute(sql)
        db.execute("PRAGMA user_version=9")
        db.execute("INSERT INTO meta VALUES ('run_evidence_bytes','0')")
        db.execute("INSERT INTO availability VALUES (1,'light.retained','unavailable',1,2,1)")
        db.execute("INSERT INTO analyses VALUES (1,1,'audit',NULL,'mock','mock','{}','{}')")
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        old = {t: db.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}
    store = Store(path)
    assert SCHEMA_VERSION == store.rows("PRAGMA user_version")[0]["user_version"] == 11
    for table, rows in old.items():
        assert [
            tuple(r.values()) for r in store.rows(f'SELECT * FROM "{table}" ORDER BY rowid')
        ] == rows
    backup = path.with_name("vision.db.v9.bak")
    before = hashlib.sha256(backup.read_bytes()).hexdigest()
    store.close()
    store = Store(path)
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == before
    assert store.rows("PRAGMA foreign_key_check") == []
    store.close()


def test_area_read_is_exact_closed_local_presentation_only(home):
    client, app = home
    validate_read("config/area_registry/list", {})
    with pytest.raises(HAError):
        validate_read("config/area_registry/list", {"area_id": "room"})
    with pytest.raises(HAError):
        validate_read("config/area_registry/update", {})
    assert EVENTS == {"state_changed", "automation_triggered"}
    assert client.post("/api/home/preferences", json={"locale": "nl"}).status_code == 403
    assert "Living room <local-only>" not in json.dumps(app.state.monitor.registry)
    from vision.ai import evidence_bundle

    assert "Living room <local-only>" not in json.dumps(evidence_bundle(app.state.monitor))


def test_capacity_refusal_never_offers_dead_links_or_a_false_quiet_day(home, monkeypatch):
    client, app = home
    m = app.state.monitor
    m.store.execute("DELETE FROM home_problems")
    monkeypatch.setattr("vision.home.MAX_PROBLEMS", 0)
    m.home.refresh()
    today = client.get("/api/today").json()
    assert today["status"] == "limited" and today["limited"]
    assert today["actionable_total"] is None and not today["priorities"]
    assert not any(d["problem_available"] for d in client.get("/api/home/devices").json()["items"])
    assert client.get("/api/problems").json()["items"] == []


def test_sync_pending_and_all_unknown_are_insufficient_visibility_not_quiet(home):
    client, app = home
    m = app.state.monitor
    m.home.syncing = m.home.pending = True
    m.home.refresh()
    value = client.get("/api/today").json()
    assert value["status"] == "attention" and value["pending"] and value["priorities"]
    assert client.get("/api/problems").json()["items"]
    m.home.syncing = False
    seed(m, ("unknown", "unknown"))
    assert client.get("/api/today").json()["status"] == "limited"


def test_retained_episode_accepts_later_report_without_backdating_or_claiming_repair(home):
    client, app = home
    m = app.state.monitor
    key = problem_id("device", "d0")
    original = client.get("/api/problems/" + key).json()
    now = time.time()
    m.observe_state({"entity_id": "light.local_0", "state": "on"}, now, track_device=False)
    m.reliability.refresh(now)
    m.home.refresh()
    retained = client.get("/api/problems/" + key).json()
    assert not retained["current"] and retained["device"]["state"] == "online"
    before = time.time()
    result = post(
        client,
        f"problems/{key}/feedback",
        {
            "request_id": "retrospective_checked_12345",
            "episode": original["problem"]["episode"],
            "kind": "checked",
        },
    )
    assert result.status_code == 200
    check = result.json()["device"]["checks"][0]
    assert check["created"] >= before and check["validation"] == "unknown"


def test_intake_cannot_acknowledge_worsening_and_defaults_do_not_clear_choices(home):
    client, app = home
    before = app.state.store.rows("SELECT * FROM device_policies")
    assert (
        post(
            client,
            "home/preferences",
            {"intake": "complete", "devices": [{"device_id": "d0", "acknowledge_worsening": True}]},
        ).status_code
        == 400
    )
    assert app.state.store.rows("SELECT * FROM device_policies") == before
    assert client.get("/api/home/preferences").json()["intake"] == "new"


def test_condition_mode_and_old_poll_refreshed_failures_stay_outside_daily_queue(home):
    client, app = home
    m, db = app.state.monitor, app.state.store
    seed(m, ("on", "on", "on"))
    for index, outcome in enumerate(("condition_stopped", "blocked", "failed")):
        entity = f"automation.noise_{index}"
        started = time.time() - (172800 if outcome == "failed" else 60)
        db.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
            (entity, "old", None, started, outcome, 1, "{}"),
        )
        db.execute("INSERT INTO run_timing VALUES (?,?,?,?)", (entity, "old", started, "ha_trace"))
        db.issue(
            "automation:" + entity,
            "automation",
            "error",
            "Retained",
            {"entity_id": entity, "run_id": "old"},
            time.time(),
        )
    m.home.refresh()
    assert client.get("/api/today").json()["status"] == "quiet"
    assert client.get("/api/problems").json()["items"] == []
    assert len(db.rows("SELECT * FROM runs")) == 3


def test_home_gets_are_read_only_and_do_not_read_history_or_automation_payloads(home):
    client, app = home
    statements = []
    db = app.state.store.db
    before = db.total_changes
    db.set_trace_callback(statements.append)
    for _ in range(3):
        assert client.get("/api/today").status_code == 200
        assert client.get("/api/problems").status_code == 200
    db.set_trace_callback(None)
    assert db.total_changes == before
    assert not any(
        " FROM device_observations " in s or "automation_structures" in s for s in statements
    )


@pytest.mark.asyncio
async def test_area_projection_bounds_and_failure_do_not_change_device_coverage(home):
    client, app = home
    from vision.ha import HAError

    m = app.state.monitor
    before = (m.reliability.reliable, m.reliability.as_of, m.reliability.current.copy())

    class Areas:
        async def read(self, command):
            assert command == "config/area_registry/list"
            return [{"area_id": "room", "name": "Friendly room", "picture": "not-retained"}] * 513

    await m.refresh_local_areas(Areas())
    assert m.local_areas == {"room": "Friendly room"} and m.local_area_status["limited"]

    class Missing:
        async def read(self, command):
            raise HAError("capability_unavailable")

    await m.refresh_local_areas(Missing())
    assert m.local_areas == {} and not m.local_area_status["available"]
    assert (m.reliability.reliable, m.reliability.as_of, m.reliability.current) == before


@pytest.mark.asyncio
async def test_live_event_cadence_retains_coherent_priorities_and_coalesces(home, monkeypatch):
    client, app = home
    m = app.state.monitor
    before = client.get("/api/today").json()
    calls = []
    refresh = m.home.refresh

    def counted():
        calls.append(time.monotonic())
        refresh()

    monkeypatch.setattr(m.home, "refresh", counted)
    m.home.last_refresh = time.monotonic()
    for i in range(10):
        m.observe_state(
            {"entity_id": "light.local_0", "state": "on" if i % 2 == 0 else "unavailable"},
            time.time(),
        )
        value = client.get("/api/today").json()
        assert value["pending"] and value["status"] == "attention"
        assert value["priorities"] == before["priorities"]
        assert value["as_of"] == before["as_of"]
        assert client.get("/api/problems").json()["items"]
        await asyncio.sleep(0.1)
    assert not calls
    await asyncio.sleep(1.15)
    assert len(calls) == 1 and not m.home.pending


@pytest.mark.asyncio
async def test_sync_failure_releases_flag_and_stale_empty_cache_never_claims_quiet(home):
    client, app = home
    m = app.state.monitor

    class Broken:
        async def read(self, command):
            raise RuntimeError("synthetic sync failure")

    with pytest.raises(RuntimeError):
        await m.sync(Broken())
    assert not m.home.syncing and m.home.pending
    assert client.get("/api/today").json()["priorities"]
    m.connected = False
    disconnected = client.get("/api/today").json()
    assert disconnected["status"] == "limited"
    assert all(p["state"] == "unknown" and p["stale"] for p in disconnected["priorities"])
    seed(m, ("on", "on", "on"))
    assert client.get("/api/today").json()["status"] == "quiet"
    for i in range(10):
        m.observe_state({"entity_id": "light.local_0", "state": str(i)}, time.time())
        assert client.get("/api/today").json()["status"] == "quiet"
        assert not m.home.pending
    m.observe_state({"entity_id": "light.local_0", "state": "unavailable"}, time.time())
    value = client.get("/api/today").json()
    assert value["pending"] and value["status"] == "limited"
    assert not value["priorities"] and value["actionable_total"] is None
    m.home.refresh()
    assert client.get("/api/today").json()["status"] == "attention"


@pytest.mark.parametrize(
    "field,attention", [("known_issue", "known"), ("usual_behavior", "expected")]
)
def test_explicit_null_restores_legacy_inheritance_but_absent_preserves_false(
    home, field, attention
):
    client, app = home
    m = app.state.monitor
    m.reliability.policy("d0", attention, "unknown", "Legacy choice")
    m.home.refresh()
    assert (
        post(
            client, "home/preferences", {"devices": [{"device_id": "d0", field: False}]}
        ).status_code
        == 200
    )
    post(client, "home/preferences", {"devices": [{"device_id": "d0", "importance": "high"}]})
    assert m.home.personal["d0"][field] == 0
    assert not m.home.preference(m.reliability.current["d0"])[field]
    post(client, "home/preferences", {"devices": [{"device_id": "d0", field: None}]})
    assert m.home.personal["d0"][field] is None
    assert m.home.preference(m.reliability.current["d0"])[field]


def test_group_identity_is_cohort_stable_and_old_feedback_is_not_current(home):
    client, app = home
    m = app.state.monitor
    at = time.time() - 250
    seed(m, ("on", "on", "on"), now=at)
    identities, episodes = set(), set()
    first = None
    for i in range(10):
        for state in ("on", "unavailable"):
            now = at + 105 + i * 10 + (state == "unavailable")
            for entity in (
                ["light.local_1"] if state == "on" else ["light.local_0", "light.local_1"]
            ):
                m.observe_state({"entity_id": entity, "state": state}, now, track_device=False)
            m.reliability.refresh(now)
            m.home.refresh()
        group = next(
            p for p in client.get("/api/today").json()["priorities"] if p["kind"] == "group"
        )
        identities.add(group["problem_id"])
        episodes.add(group["episode"])
        if first is None:
            first = group
            payload = {
                "request_id": "first_group_report_12345",
                "episode": group["episode"],
                "kind": "no_change",
                "note": "Earlier group episode",
            }
            assert (
                post(client, f"problems/{group['problem_id']}/feedback", payload).status_code == 200
            )
    assert len(identities) == 1 and len(episodes) == 10
    assert (
        app.state.store.rows("SELECT count(*) n FROM home_problems WHERE kind='group'")[0]["n"] == 1
    )
    detail = client.get("/api/problems/" + first["problem_id"]).json()
    assert not detail["feedback"] and len(detail["earlier_feedback"]) == 1
    assert post(client, f"problems/{first['problem_id']}/feedback", payload).status_code == 200
    payload["check_kind"] = "power"
    assert post(client, f"problems/{first['problem_id']}/feedback", payload).status_code == 409
    for i in range(2):
        m.observe_state(
            {"entity_id": f"light.local_{i}", "state": "on"}, at + 220, track_device=False
        )
    m.reliability.refresh(at + 220)
    m.home.refresh()
    retired = client.get("/api/problems/" + first["problem_id"]).json()
    assert not retired["current"] and len(retired["members"]) == 2
    assert all(
        member["state"] == "unknown" and member["retained_only"] for member in retired["members"]
    )


def test_presentation_retention_reclaims_only_expired_unreferenced_rows_and_never_loads_bodies(
    home, monkeypatch
):
    client, app = home
    m, db = app.state.monitor, app.state.store
    db.execute("DELETE FROM home_problems")
    monkeypatch.setattr("vision.home.MAX_PROBLEMS", 8)
    old = time.time() - 365 * 86400
    with db.transaction():
        for i in range(8):
            db.execute(
                "INSERT INTO home_problems VALUES (?,?,?,?,?,?,?,0)",
                (
                    f"old{i}",
                    "device",
                    f"old{i}",
                    "e" * 32,
                    "{}",
                    old,
                    time.time() if i == 7 else old,
                ),
            )
        db.execute(
            "INSERT INTO home_feedback VALUES (1,?,?,?,?,?,?,?,NULL)",
            (
                "retained_owner_report",
                "old6",
                "e" * 32,
                old,
                "no_change",
                "Preserve owner report",
                "{}",
            ),
        )
        db.execute("UPDATE home_problems SET present=1 WHERE problem_id='old5'")
    preserved = db.rows("SELECT * FROM home_feedback")
    m.home.last_retention = 0
    statements = []
    db.db.set_trace_callback(statements.append)
    m.home.refresh()
    db.db.set_trace_callback(None)
    assert db.rows("SELECT * FROM home_feedback") == preserved
    assert {r["problem_id"] for r in db.rows("SELECT * FROM home_problems")} == {
        "old6",
        "old7",
        "old5",
        problem_id("device", "d0"),
        problem_id("device", "d1"),
    }
    retired = db.rows("SELECT updated,present FROM home_problems WHERE problem_id='old5'")[0]
    assert retired["present"] == 0 and retired["updated"] > time.time() - 10
    m.home.last_retention = 0
    m.home.refresh()
    assert db.rows("SELECT 1 FROM home_problems WHERE problem_id='old5'")
    assert client.get("/api/today").json()["status"] == "attention"
    assert not any(
        "SELECT problem_id,snapshot,present FROM home_problems LIMIT" in s for s in statements
    )
    for p in client.get("/api/today").json()["priorities"]:
        assert client.get("/api/problems/" + p["problem_id"]).status_code == 200


@pytest.mark.parametrize("reason", ["device_not_retained", "check_capacity"])
def test_checked_report_survives_unavailable_optional_marker(home, monkeypatch, reason):
    client, app = home
    m, db = app.state.monitor, app.state.store
    key = problem_id("device", "d0")
    detail = client.get("/api/problems/" + key).json()
    if reason == "device_not_retained":
        m.reliability.current.pop("d0")
    else:
        monkeypatch.setattr("vision.reliability.MAX_CHECKS", 0)
    before = db.rows("SELECT * FROM device_checks")
    payload = {
        "request_id": "optional_marker_123456",
        "episode": detail["problem"]["episode"],
        "kind": "checked",
        "check_kind": "power",
    }
    answer = post(client, f"problems/{key}/feedback", payload)
    assert answer.status_code == 200
    assert answer.json()["feedback"][0]["check_unavailable"] == reason
    assert answer.json()["feedback"][0]["check_id"] is None
    assert db.rows("SELECT * FROM device_checks") == before
    assert len(db.rows("SELECT * FROM home_feedback")) == 1 and not db.rows("SELECT * FROM usage")
    assert post(client, f"problems/{key}/feedback", payload).status_code == 200
    payload["check_kind"] = "connection"
    conflict = post(client, f"problems/{key}/feedback", payload)
    assert conflict.status_code == 409 and "identifier" in conflict.json()["detail"]
    payload["request_id"] = "new_conflicting_episode"
    payload["episode"] = "0" * 32
    assert "episode" in post(client, f"problems/{key}/feedback", payload).json()["detail"]


def test_parent_area_inheritance_is_one_verified_main_device_hop(home):
    _, app = home
    m = app.state.monitor
    m.local_areas.update(parent_room="Parent room", own_room="Own room")
    m.local_device_locations = {
        "child": {"parent_device_id": "parent", "area_id": None},
        "parent": {"area_id": "parent_room"},
    }
    assert m.home.room("child") == "Parent room"
    m.local_device_locations["child"]["area_id"] = "own_room"
    assert m.home.room("child") == "Own room"
    m.local_device_locations["child"]["area_id"] = "dangling"
    assert m.home.room("child") is None

    m.local_device_locations["child"] = {"via_device_id": "parent"}
    assert m.home.room("child") is None
    m.local_device_locations["child"] = {"parent_device_id": "parent"}
    m.local_device_locations["parent"]["parent_device_id"] = "child"
    assert m.home.room("child") is None


def test_successful_checked_retry_after_new_episode_returns_prior_report_without_second_check(home):
    client, app = home
    m, db = app.state.monitor, app.state.store
    key = problem_id("device", "d0")
    payload = {
        "request_id": "successful_check_retry_1234",
        "kind": "checked",
        "check_kind": "power",
        "episode": client.get("/api/problems/" + key).json()["problem"]["episode"],
    }
    assert post(client, f"problems/{key}/feedback", payload).status_code == 200
    checks = db.rows("SELECT * FROM device_checks")
    at = time.time()
    for delta, state in ((1, "on"), (2, "unavailable")):
        m.observe_state(
            {"entity_id": "light.local_0", "state": state}, at + delta, track_device=False
        )
        m.reliability.refresh(at + delta)
        m.home.refresh()
    response = post(client, f"problems/{key}/feedback", payload)
    assert response.status_code == 200
    assert not response.json()["feedback"] and len(response.json()["earlier_feedback"]) == 1
    assert not response.json()["device"]["checks"]
    assert len(response.json()["device"]["earlier_checks"]) == 1
    assert db.rows("SELECT * FROM device_checks") == checks
    payload["check_kind"] = "connection"
    assert post(client, f"problems/{key}/feedback", payload).status_code == 409


def test_native_check_capacity_message_is_fixed_and_unexpected_check_errors_are_not_success(
    home, monkeypatch
):
    client, app = home
    m, db = app.state.monitor, app.state.store
    monkeypatch.setattr("vision.reliability.MAX_CHECKS", 0)
    before = db.rows("SELECT * FROM device_checks")
    with pytest.raises(ValueError) as failure:
        m.reliability.check("d0", "power", "Contract only")
    assert type(failure.value) is ValueError
    assert (
        str(failure.value) == "Local check history capacity reached; existing records are retained"
    )
    assert db.rows("SELECT * FROM device_checks") == before
    key = problem_id("device", "d0")
    payload = {
        "request_id": "unexpected_check_failure_1234",
        "kind": "checked",
        "episode": client.get("/api/problems/" + key).json()["problem"]["episode"],
    }

    monkeypatch.setattr("vision.reliability.MAX_CHECKS", 10_000)
    native_check = m.reliability.check

    def unexpected(*args):
        native_check(*args)
        assert len(db.rows("SELECT * FROM device_checks")) == len(before) + 1
        raise ValueError("Synthetic private check error canary")

    monkeypatch.setattr(m.reliability, "check", unexpected)
    safe_client = TestClient(app, client=("127.0.0.1", 1), raise_server_exceptions=False)
    try:
        answer = post(safe_client, f"problems/{key}/feedback", payload)
    finally:
        safe_client.close()
    assert answer.status_code == 500
    assert answer.json() == {"detail": "Internal error; no HA action was performed"}
    assert "canary" not in answer.text
    assert not db.rows("SELECT * FROM home_feedback")
    assert db.rows("SELECT * FROM device_checks") == before
