"""Real local API admission, preserved legacy rows and bounded dashboard work."""

import hashlib
import sqlite3
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.store import MIGRATIONS, SCHEMA_VERSION, Store


def seed_monitor(monitor, count=3, now=None):
    now = time.time() - 100 if now is None else now
    monitor.devices = [{"id": f"device-{i}", "name": f"<Device {i}>"} for i in range(count)]
    for index in range(count):
        entity = f"light.synthetic_{index}"
        monitor.registry[entity] = {"device_id": f"device-{index}", "platform": "synthetic"}
        monitor.observe_state(
            {"entity_id": entity, "state": "unavailable"}, now, track_device=False
        )
    monitor.reliability.refresh(now)
    monitor.reliability.refresh(now + 100)


@pytest.fixture
def api(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), Settings(), connect=False
    )
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        seed_monitor(app.state.monitor)
        yield client, app


def test_local_device_workflow_guard_validation_and_no_provider_or_ha_action(api):
    client, app = api
    store = app.state.store
    source = store.rows("SELECT * FROM availability ORDER BY id")
    url = "/api/reliability/devices/device-0"
    assert client.get(url).json()["state"] == "offline"
    assert client.post(url + "/checks", json={"kind": "power"}).status_code == 403
    headers = {"x-vision-request": "1"}
    assert (
        client.post(
            url + "/checks", json={"kind": "execute", "command": "ping"}, headers=headers
        ).status_code
        == 422
    )
    result = client.post(
        url + "/checks",
        json={
            "kind": "power",
            "note": '<script>alert("not markup")</script> {"token":"private-canary"}',
        },
        headers=headers,
    )
    assert result.status_code == 200
    marker = result.json()["checks"][0]
    assert marker["validation"] == "unknown" and "private-canary" not in marker["note"]
    saved = client.post(
        url + "/policy",
        json={"attention": "expected", "power": "battery", "note": "Explicit local declaration"},
        headers=headers,
    )
    assert saved.status_code == 200 and saved.json()["attention"] == "expected"
    assert store.rows("SELECT * FROM availability ORDER BY id") == source
    assert not store.rows("SELECT * FROM usage") and not store.rows("SELECT * FROM ai_requests")
    assert not app.state.tasks  # No monitor/provider/research network task exists in this test.
    assert client.get("/api/reliability?window=60d").status_code == 422
    assert client.get("/api/reliability/devices?state=healthy").status_code == 400
    assert client.get("/api/reliability/devices?limit=101").status_code == 422
    assert client.get("/api/reliability/devices/missing").status_code == 404


def test_device_pagination_and_integration_drilldown_are_real_bounded_queries(api):
    client, _ = api
    first = client.get("/api/reliability/devices?platform=synthetic&state=offline&limit=2").json()
    second = client.get(
        "/api/reliability/devices?platform=synthetic&state=offline&limit=2&page=2"
    ).json()
    assert first["total"] == 3 and first["has_more"] and len(second["items"]) == 1
    assert not {r["device_id"] for r in first["items"]} & {r["device_id"] for r in second["items"]}
    assert client.get("/api/reliability/devices?platform=unknown").json()["total"] == 0
    overview = client.get("/api/overview").json()["reliability"]
    assert overview["priorities"][0]["device_count"] == 3
    assert overview["integrations"]["items"][0]["devices"] == 3


def test_schema_nine_is_additive_and_keeps_old_rows_backups_options_and_accounting(tmp_path):
    path = tmp_path / "vision.db"
    with sqlite3.connect(path) as db:
        for version in range(1, 9):
            for statement in MIGRATIONS[version]:
                db.execute(statement)
        db.execute("PRAGMA user_version=8")
        db.execute("INSERT INTO availability VALUES (1,'light.old','unavailable',1,2,0)")
        db.execute("INSERT INTO meta VALUES ('operator-local','{\"kept\":true}')")
        db.execute("INSERT INTO meta VALUES ('run_evidence_bytes','0')")
        old = {
            table: db.execute('SELECT * FROM "' + table + '" ORDER BY rowid').fetchall()
            for (table,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    options = tmp_path / "options.json"
    options.write_bytes(b'{"ai_enabled":false,"private":"unchanged"}')
    store = Store(path)
    assert store.db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 11
    for table, rows in old.items():
        assert [
            tuple(r) for r in store.db.execute('SELECT * FROM "' + table + '" ORDER BY rowid')
        ] == rows
    assert store.rows("PRAGMA foreign_key_check") == []
    assert store.rows("PRAGMA quick_check")[0]["quick_check"] == "ok"
    backup = tmp_path / "vision.db.v8.bak"
    backup_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
    store.close()
    reopened = Store(path)
    reopened.close()
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == backup_hash
    assert options.read_bytes() == b'{"ai_enabled":false,"private":"unchanged"}'
    with sqlite3.connect(backup) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 8
        assert db.execute("SELECT state FROM availability").fetchone()[0] == "unavailable"


def test_real_landing_with_5686_entities_and_100003_legacy_segments_is_read_only_bounded(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), Settings(), connect=False
    )
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        monitor, store = app.state.monitor, app.state.store
        now = time.time()
        with store.transaction():
            store.db.executemany(
                "INSERT INTO availability(entity_id,state,started,ended) VALUES (?,?,?,?)",
                (
                    (
                        f"sensor.historical_{i % 5686}",
                        "unavailable",
                        now - 200000 - i,
                        now - 190000 - i,
                    )
                    for i in range(100003)
                ),
            )
            monitor.devices = [{"id": f"device-{i}"} for i in range(1422)]
            for index in range(5686):
                entity = f"light.synthetic_{index}"
                monitor.registry[entity] = {
                    "device_id": f"device-{index // 4}",
                    "platform": "synthetic",
                }
                # Availability only: unrelated source issues are outside this metric fixture.
                monitor.entities[entity] = {
                    "entity_id": entity,
                    "name": entity,
                    "availability": "available",
                    "updated": now,
                }
            monitor.reliability.refresh(now)
            monitor.reliability.refresh(now + 100)
        before, queries = store.db.total_changes, []
        store.db.set_trace_callback(queries.append)
        try:
            for route in (
                "/api/overview",
                "/api/reliability?window=7d",
                "/api/reliability?window=30d",
            ):
                queries.clear()
                response = client.get(route)
                assert response.status_code == 200
                assert len(response.content) < 160000
                assert len(queries) <= 16, queries
                assert not any(
                    "FROM availability" in q or "FROM device_observations" in q for q in queries
                )
                assert not any(
                    q.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries
                )
                metric = response.json().get("reliability", response.json())
                assert metric["counts"]["online"] == 1422
                assert (
                    metric["burden"]["direction"] == "unknown"
                )  # No invented pre-baseline history.
            assert store.db.total_changes == before
        finally:
            store.db.set_trace_callback(None)
        assert store.rows("SELECT count(*) n FROM availability")[0]["n"] == 100003
        assert not store.rows("SELECT * FROM usage")


def test_new_and_persistent_clusters_have_distinct_copy_and_exact_affected_device_route(api):
    from urllib.parse import parse_qs, urlsplit

    client, app = api
    monitor, service = app.state.monitor, app.state.monitor.reliability
    now = service.as_of + 1000
    for index in range(3):
        device_id, entity_id = f"new-{index}", f"light.new_{index}"
        monitor.devices.append({"id": device_id, "name": f"New lamp {index}"})
        monitor.registry[entity_id] = {"device_id": device_id, "platform": "synthetic"}
        monitor.observe_state({"entity_id": entity_id, "state": "on"}, now, track_device=False)
    service.refresh(now)
    for index in range(3):
        monitor.observe_state(
            {"entity_id": f"light.new_{index}", "state": "unavailable"}, now + 100
        )
    service.refresh(now + 200)
    cards = client.get("/api/reliability").json()["priorities"]
    assert len(cards) == 2
    new, old = cards
    assert new["kind"] == "new_device" and old["kind"] == "device_backlog"
    assert new["title"].startswith("New observations") and old["title"].startswith(
        "Persistent backlog"
    )
    assert new["device_count"] == old["device_count"] == 3
    assert new["new_device_count"] == 3 and old["new_device_count"] == 0
    assert "3 changed / 3 affected" in new["title"]
    assert new["evidence_since"] > old["evidence_since"]
    assert new["href"] != old["href"]
    for card in cards:
        selection = parse_qs(urlsplit(card["href"][1:]).query)
        assert set(selection) == {"device"}
        chosen = selection["device"][0]
        assert chosen == card["device_id"]
        detail = client.get("/api/reliability/devices/" + chosen)
        assert detail.status_code == 200 and detail.json()["device_id"] == chosen
        assert detail.json()["state"] == "offline"
        assert all(
            r["device_id"].startswith("new-") == chosen.startswith("new-")
            for r in card["related_devices"]
        )
        assert len(card["impact"]) < 100 and "Cause unknown" in card["impact"]
        assert "correlation" in card["scope_note"]


def test_explicit_worsening_acknowledgment_uses_guarded_api_and_note_save_does_not_rebase(
    api, monkeypatch
):
    client, app = api
    monitor, service = app.state.monitor, app.state.monitor.reliability
    now = time.time()
    monitor.registry["light.additional"] = {"device_id": "device-0", "platform": "synthetic"}
    monitor.observe_state({"entity_id": "light.additional", "state": "on"}, now + 10)
    service.refresh(now + 10)
    url = "/api/reliability/devices/device-0/policy"
    headers = {"x-vision-request": "1"}
    monkeypatch.setattr("vision.reliability.time.time", lambda: now + 20)
    assert client.post(url, json={"attention": "known"}, headers=headers).status_code == 200
    monitor.observe_state({"entity_id": "light.additional", "state": "unavailable"}, now + 30)
    assert service.policies["device-0"]["worsened_at"] == now + 30
    monkeypatch.setattr("vision.reliability.time.time", lambda: now + 40)
    saved = client.post(url, json={"attention": "known", "note": "Only a note"}, headers=headers)
    assert saved.json()["policy"]["baseline_state"] == "partial"
    assert saved.json()["policy"]["worsened_at"] == now + 30
    acknowledged = client.post(
        url, json={"attention": "known", "acknowledge_worsening": True}, headers=headers
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["policy"]["baseline_state"] == "offline"
    assert acknowledged.json()["policy"]["worsened_at"] is None
    monitor.observe_state({"entity_id": "light.additional", "state": "unknown"}, now + 50)
    assert (
        client.post(
            url, json={"attention": "known", "acknowledge_worsening": True}, headers=headers
        ).status_code
        == 400
    )


def test_device_evidence_timestamp_is_real_detail_recording_not_poll_time(api):
    client, app = api
    service = app.state.monitor.reliability
    original = app.state.store.rows(
        "SELECT payload FROM device_current WHERE device_id='device-0'"
    )[0]
    import json

    evidence_at = json.loads(original["payload"])["evidence_at"]
    service.refresh(evidence_at + 500)
    value = client.get("/api/reliability/devices/device-0").json()
    assert value["evidence_at"] == evidence_at
    assert value["evidence_at"] != service.as_of
    listed = client.get("/api/reliability/devices").json()["items"]
    assert (
        next(item for item in listed if item["device_id"] == "device-0")["evidence_at"]
        == evidence_at
    )


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), True, "100", {}])
def test_missing_or_invalid_evidence_timestamp_is_nullable_without_fallback(api, invalid):
    client, app = api
    value = app.state.monitor.reliability.current["device-0"]
    value["evidence_at"] = invalid
    assert value["started"] is not None  # A valid interval start is deliberately not a fallback.
    assert client.get("/api/reliability/devices/device-0").json()["evidence_at"] is None
