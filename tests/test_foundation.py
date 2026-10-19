import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import SecretStr

from vision.app import create_app
from vision.config import Runtime, Settings
from vision.security import Redactor
from vision.store import Store


def test_persistence_and_billing_recovery(tmp_path):
    path = tmp_path / "vision.db"
    store = Store(path)
    store.set_meta("audit", {"id": 3})
    store.execute("INSERT INTO usage VALUES (1,1,'openai','model',NULL,NULL,.1,'reserved')")
    store.close()
    store = Store(path)
    assert store.get_meta("audit") == {"id": 3}
    assert store.rows("SELECT status FROM usage")[0]["status"] == "uncertain"
    assert path.stat().st_mode & 0o777 == 0o600
    store.close()


def test_ingress_and_secrets(tmp_path):
    runtime = SimpleNamespace(supervised=True, data=tmp_path, token="private-ha-token")
    settings = Settings(
        openai_api_key=SecretStr("private-provider-key"), allowed_user_ids=["tester"]
    )
    with TestClient(create_app(runtime, settings, connect=False), client=("172.30.32.2", 123)) as c:
        c.headers["x-remote-user-id"] = "tester"
        assert c.get("/").status_code == 200
        assert c.get("/static/app.js").status_code == 200
        response = c.get("/api/settings")
        assert "private" not in response.text
        assert response.json()["openai_key_configured"] is True
        assert c.post("/api/anything").status_code == 403
        assert "Content-Security-Policy" in response.headers
        c.headers["x-remote-user-id"] = "unlisted-user"
        assert c.get("/api/settings").status_code == 403
    with TestClient(create_app(runtime, settings, connect=False), client=("172.30.33.4", 123)) as c:
        assert c.get("/", headers={"x-forwarded-for": "172.30.32.2"}).status_code == 403
        assert "Content-Security-Policy" in c.get("/").headers


def test_redaction():
    redactor = Redactor(["a-private-value"])
    data = redactor.clean(
        {
            "api_key": "abc",
            "message": "a-private-value Bearer abcdef https://private.local/path 192.168.1.1",
        }
    )
    assert "a-private-value" not in json.dumps(data)
    assert "abcdef" not in json.dumps(data)
    assert "private.local" not in json.dumps(data)
    assert data["api_key"] == "[REDACTED]"


def test_supervisor_and_direct_websocket_paths(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "synthetic-token")
    runtime = Runtime()
    assert runtime.websocket_url == "http://supervisor/core/websocket"
    assert runtime.ha_url == "http://supervisor/core"
    monkeypatch.delenv("SUPERVISOR_TOKEN")
    monkeypatch.setenv("HA_URL", "http://example.invalid:8123")
    assert Runtime().websocket_url == "http://example.invalid:8123/api/websocket"
