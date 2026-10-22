"""Source-bound synthetic ASGI data for the shipped daily-journey DOM tests."""

import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from tests.test_home_experience import seed  # noqa: E402
from vision.app import create_app  # noqa: E402
from vision.config import Settings  # noqa: E402

with TemporaryDirectory() as directory:
    app = create_app(
        SimpleNamespace(supervised=False, data=Path(directory), token=""),
        Settings(),
        connect=False,
    )
    with TestClient(app, client=("127.0.0.1", 1)) as client:
        initial = client.get("/api/today").json()
        seed(app.state.monitor)
        paths = [
            "health",
            "settings",
            "exceptions",
            "devices",
            "overview",
            "automations",
            "history/page?kind=runs",
            "today?window=24h",
            "home/preferences",
            "home/devices?page=1&q=",
            "problems?mode=attention&page=1",
        ]
        values = {path: client.get("/api/" + path).json() for path in paths}
        values["qa/initial-limited"] = initial
        for item in values["problems?mode=attention&page=1"]["items"]:
            path = "problems/" + item["problem_id"]
            values[path] = client.get("/api/" + path).json()
        for device in values["home/devices?page=1&q="]["items"]:
            path = "reliability/devices/" + device["device_id"]
            values[path] = client.get("/api/" + path).json()
        m = app.state.monitor
        key = values["problems?mode=attention&page=1"]["items"][0]["problem_id"]
        path = "problems/" + key
        p = values[path]["problem"]
        headers = {"x-vision-request": "1"}
        response = client.post(
            "/api/" + path + "/feedback",
            headers=headers,
            json={
                "request_id": "earlier_episode_check_1234",
                "episode": p["episode"],
                "kind": "checked",
                "note": "First episode report only",
            },
        )
        assert response.status_code == 200
        at = time.time()
        for offset, state in ((1, "on"), (2, "unavailable")):
            m.observe_state(
                {"entity_id": "light.local_0", "state": state}, at + offset, track_device=False
            )
            m.reliability.refresh(at + offset)
            m.home.refresh()
        values["qa/earlier-episode"] = client.get("/api/" + path).json()
        m.reliability.current.pop(p["target"])
        answer = client.post(
            "/api/" + path + "/feedback",
            headers=headers,
            json={
                "request_id": "unavailable_marker_1234",
                "episode": values["qa/earlier-episode"]["problem"]["episode"],
                "kind": "checked",
                "note": "Subjective report retained",
            },
        )
        assert answer.status_code == 200
        values["qa/check-unavailable"] = answer.json()
        print(json.dumps(values))
