"""Complete local preview/send API, legacy history and rendering contracts."""

import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from vision.ai_provider import ProviderResult
from vision.app import create_app
from vision.config import Settings
from vision.store import MIGRATIONS, SCHEMA_VERSION, Store


class Provider:
    def __init__(self):
        self.calls = []

    async def send(self, body, key):
        self.calls.append(body)
        return ProviderResult(
            text=json.dumps(
                {
                    "summary": "Only retained evidence",
                    "diagnoses": [],
                    "unknowns": ["No physical check"],
                    "requested_sections": [],
                }
            ),
            input_tokens=5,
            output_tokens=9,
        )


def test_real_http_preview_send_followup_and_old_history(tmp_path):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    settings = Settings(
        ai_enabled=True,
        anthropic_model="synthetic",
        anthropic_api_key=SecretStr("synthetic-provider-key"),
        anthropic_input_usd_per_million=1,
        anthropic_output_usd_per_million=2,
    )
    app = create_app(runtime, settings, connect=False)
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        client.headers["x-vision-request"] = "1"
        provider = Provider()
        app.state.ai.providers["anthropic"] = provider
        app.state.monitor.observe_state(
            {"entity_id": "sensor.private_fixture", "state": "unavailable", "attributes": {}}
        )
        # A caller cannot bypass preview using the previous manual endpoint contract.
        assert client.post("/api/intelligence", json={"kind": "audit"}).status_code == 422
        invalid = client.post(
            "/api/intelligence/preview", json={"profile": "diagnostic", "diagnostic_consent": True}
        )
        assert invalid.status_code == 400
        assert (
            client.get("/api/intelligence/preview?kind=incident&target=missing").status_code == 400
        )
        prepared = client.post(
            "/api/intelligence/preview",
            json={"kind": "availability", "target": "availability:sensor.private_fixture"},
        )
        assert prepared.status_code == 200
        prepared = prepared.json()
        assert "sensor.private_fixture" not in json.dumps(prepared["preview"])
        assert (
            "synthetic-provider-key"
            not in prepared["preview"]["requests"]["anthropic"]["body_utf8"]
        )
        token = {"request_id": prepared["request_id"], "digest": prepared["digest"]}
        assert (
            client.post("/api/intelligence", json={**token, "profile": "diagnostic"}).status_code
            == 422
        )
        response = client.post("/api/intelligence", json=token)
        assert response.status_code == 202
        for _ in range(100):
            state = client.get(
                "/api/intelligence/requests/" + prepared["request_id"] + "/status"
            ).json()
            if state["status"] != "sending":
                break
            time.sleep(0.01)
        assert state["status"] == "completed"
        assert (
            len(provider.calls) == 1
            and provider.calls[0] == prepared["preview"]["requests"]["anthropic"]["body_utf8"]
        )
        assert client.post("/api/intelligence", json=token).status_code == 409
        retained = client.get("/api/intelligence/requests/" + prepared["request_id"]).json()
        assert retained["preview"] == prepared["preview"] and retained["status"] == "completed"
        assert "synthetic-provider-key" not in json.dumps(retained)
        conversation = client.get(
            "/api/intelligence/conversations/" + prepared["conversation_id"]
        ).json()
        assert len(conversation["rounds"]) == 1
        follow = client.post(
            "/api/intelligence/preview",
            json={
                "kind": "availability",
                "target": "availability:sensor.private_fixture",
                "conversation_id": prepared["conversation_id"],
                "followup_focus": "validation",
            },
        )
        assert follow.status_code == 200 and follow.json()["preview"]["round"] == 2
        assert client.post(
            "/api/intelligence/requests/" + follow.json()["request_id"] + "/revoke"
        ).json() == {"revoked": True}
        # Search reaches retained legacy analyses beyond Intelligence's recent-50 window.
        old_result = {
            "summary": "legacy needle",
            "diagnoses": [
                {
                    "finding": "Historical",
                    "evidence": ["E1"],
                    "severity": "info",
                    "confidence": "low",
                    "uncertainty": "Historical unknown",
                    "next_step": "Manual check",
                    "validation": "Observe",
                }
            ],
        }
        for index in range(55):
            app.state.store.execute(
                "INSERT INTO analyses VALUES (NULL,?,'audit',NULL,'openai','legacy',?,?)",
                (
                    time.time(),
                    json.dumps(old_result if index == 0 else {"summary": "Other", "diagnoses": []}),
                    json.dumps({"mapping": {"E1": "legacy local object"}}),
                ),
            )
        assert len(client.get("/api/intelligence").json()["analyses"]) == 50
        history = client.get("/api/history/page?kind=analyses&q=legacy%20needle").json()
        assert (
            len(history["items"]) == 1
            and json.loads(history["items"][0]["result"])["summary"] == "legacy needle"
        )
        assert app.state.store.rows("SELECT count(*) n FROM usage")[0]["n"] == 1


def test_additive_five_to_six_and_restart_preserve_legacy_and_uncertain_usage(tmp_path):
    path = tmp_path / "vision.db"
    with sqlite3.connect(path) as source:
        for version in range(1, 6):
            for statement in MIGRATIONS[version]:
                source.execute(statement)
        source.execute("PRAGMA user_version=5")
        source.execute("INSERT INTO meta VALUES ('legacy',?)", (json.dumps("retained"),))
        source.execute(
            "INSERT INTO analyses VALUES (1,?,'audit',NULL,'openai','legacy',?,?)",
            (
                time.time(),
                json.dumps({"summary": "Legacy", "diagnoses": []}),
                json.dumps({"mapping": {"E1": "local"}}),
            ),
        )
        source.execute(
            "INSERT INTO usage VALUES (1,?,'openai','legacy',NULL,NULL,.4,'reserved')",
            (time.time(),),
        )
    options = tmp_path / "options.json"
    options.write_text('{"ai_enabled":false,"daily_audit":false,"poll_seconds":75}')
    before = options.read_bytes()
    store = Store(path)
    assert store.get_meta("legacy") == "retained"
    assert store.rows("PRAGMA user_version")[0]["user_version"] == SCHEMA_VERSION
    assert store.rows("SELECT cost_usd,status FROM usage") == [
        {"cost_usd": 0.4, "status": "uncertain"}
    ]
    assert json.loads(store.rows("SELECT evidence FROM analyses")[0]["evidence"])["mapping"] == {
        "E1": "local"
    }
    with sqlite3.connect(tmp_path / "vision.db.v5.bak") as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 5
        assert backup.execute("SELECT count(*) FROM analyses").fetchone()[0] == 1
    store.close()
    store = Store(path)
    assert len(store.rows("SELECT * FROM analyses")) == 1
    assert options.read_bytes() == before and Settings.load(options).ai_privacy == "compact"
    store.close()


def test_frontend_legacy_rendering_task_preselection_run_binding_and_escaping():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for frontend contract")
    source = (Path(__file__).parents[1] / "vision/static/app.js").read_text()
    helpers = source[source.index("const plain =") : source.index("const issueLink")]
    script = (
        """const esc = (v) => String(v??'').replace(/[&<>"']/g,
        c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
        const parse=v=>typeof v==='string'?JSON.parse(v):v;
        const date=()=>''; const badge=esc; const empty=esc;
        const list=a=>a.map(esc).join(''); """
        + helpers
        + """; console.log(JSON.stringify({
        legacy:findings({result:{summary:'<img src=x>',diagnoses:[
        {finding:'Historical',evidence:['E1'],next_step:'check',validation:'observe'}]}}),
        task:suggestedTask({case:{source:'automation_step',detail:{}},
        run:{evidence:{errors:[{kind:'template_error'}]}}}),
        serviceTimeout:suggestedTask({case:{source:'automation_step',detail:{}},
        run:{evidence:{errors:[{kind:'timeout',path:'action/0'}]}}}),
        link:investigationLink('automation','automation.example','failed/run','success/run')}));"""
    )
    result = json.loads(subprocess.check_output([node, "-e", script]))
    assert (
        "Historical" in result["legacy"]
        and "E1" in result["legacy"]
        and "<img" not in result["legacy"]
    )
    assert result["task"] == "template_error"
    assert result["serviceTimeout"] == "incident"
    assert "run_id=failed%2Frun" in result["link"] and "compare=success%2Frun" in result["link"]
    assert "data-analyze" not in source and 'api("intelligence/preview",' in source


def test_known_storage_startup_reasons_are_safe_and_source_failure_closes(tmp_path, monkeypatch):
    from vision.store import STORAGE_FAILURES, StorageStartupError

    path = tmp_path / "vision.db"
    store = Store(path)
    connect = sqlite3.connect

    def rejected(path, *args, **kwargs):
        if kwargs.get("uri"):
            raise sqlite3.OperationalError("synthetic-private-source-path")
        return connect(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", rejected)
    with pytest.raises(StorageStartupError) as error:
        store.write_snapshot(tmp_path / "synthetic.backup")
    assert error.value.code == "snapshot_source"
    assert "synthetic-private-source-path" not in str(error.value)
    assert "competing Vision processes" in STORAGE_FAILURES["storage_busy"]
    store.close()


def test_restart_marks_transmitted_requests_uncertain_and_keeps_exact_payload(tmp_path):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    app = create_app(runtime, Settings(), connect=False)
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        value = client.post(
            "/api/intelligence/preview", json={}, headers={"x-vision-request": "1"}
        ).json()
        request_id = value["request_id"]
        original = app.state.store.rows("SELECT payload,digest,local_evidence FROM ai_requests")[0]
        app.state.store.execute("UPDATE ai_requests SET status='sending'")
        usage_id = app.state.store.execute(
            "INSERT INTO usage VALUES (NULL,?,'openai','synthetic',NULL,NULL,.4,'reserved')",
            (time.time(),),
        )
        app.state.store.execute(
            "INSERT INTO ai_attempts VALUES (?,?, 'openai',1)", (usage_id, request_id)
        )
    store = Store(tmp_path / "vision.db")
    restored = store.rows("SELECT payload,digest,local_evidence,status FROM ai_requests")[0]
    assert restored.pop("status") == "uncertain" and restored == original
    assert store.rows("SELECT status,cost_usd FROM usage") == [
        {"status": "uncertain", "cost_usd": 0.4}
    ]
    assert len(store.rows("SELECT * FROM ai_attempts")) == 1
    store.close()


def test_busy_startup_uses_allowlisted_reason_and_closes_connection(tmp_path, monkeypatch):
    from vision.store import StorageStartupError

    connect = sqlite3.connect
    closed = []

    class Busy(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "BEGIN IMMEDIATE":
                error = sqlite3.OperationalError("synthetic-private-lock-details")
                error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise error
            return super().execute(sql, *args, **kwargs)

        def close(self):
            closed.append(True)
            return super().close()

    def factory(*args, **kwargs):
        return connect(*args, **kwargs, factory=Busy)

    monkeypatch.setattr(sqlite3, "connect", factory)
    with pytest.raises(StorageStartupError) as error:
        Store(tmp_path / "vision.db")
    assert error.value.code == "storage_busy" and "synthetic-private" not in str(error.value)
    assert closed == [True]
