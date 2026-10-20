"""Pin the actual bounded ASGI queries used by the action-oriented dashboard."""

import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.evidence import structure


def test_overview_supporting_availability_query_is_bounded_attention_shape(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), Settings(), connect=False
    )
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        monitor, store = app.state.monitor, app.state.store
        for number in range(37):
            monitor.observe_state(
                {
                    "entity_id": f"sensor.synthetic_{number}",
                    "state": "unavailable",
                    "attributes": {},
                }
            )
        query = "/api/cases?source=availability&status=attention&limit=1"
        result = client.get(query)
        assert result.status_code == 200
        value = result.json()
        assert value["total"] == 37 and value["limit"] == 1 and len(value["items"]) == 1
        case = value["items"][0]
        assert case["source"] == "availability" and case["status"] == "review"
        assert case["priority"] == 6 and case["manual_check"]
        monitor.insights.annotate(case["key"], "expected", "Synthetic expected sleep")
        assert client.get(query).json()["total"] == 36
        assert store.rows("SELECT active FROM issues WHERE key=?", (case["key"],))[0]["active"] == 1
        assert not store.rows("SELECT * FROM usage")


def test_overview_supporting_change_query_returns_only_bounded_changed_projections(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), Settings(), connect=False
    )
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        store, now = app.state.store, time.time()
        for number in range(6):
            store.save_structure(
                "automation.synthetic",
                structure({"actions": [{"delay": number}]}),
                "current_config",
                now=now - 60 + number,
            )
        result = client.get("/api/history/page?kind=changes&outcome=changed&limit=3")
        assert result.status_code == 200
        rows = result.json()["items"]
        assert len(rows) == 3
        assert all(
            row["entity_id"] == "automation.synthetic" and row["kind"] == "changed" for row in rows
        )
        assert all(isinstance(row["observed_at"], (int, float)) and row["delta"] for row in rows)
        assert rows == sorted(rows, key=lambda row: (row["observed_at"], row["id"]), reverse=True)
        assert not store.rows("SELECT * FROM usage")
