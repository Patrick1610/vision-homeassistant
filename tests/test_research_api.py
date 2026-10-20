"""Real ASGI research lifecycle and immutable request audit; localhost mocks only."""

import asyncio
import copy
import json
import threading
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_public_research import PublicMock, device_request

from vision.app import create_app
from vision.config import Settings
from vision.research_sources import canonical, digest


def test_202_public_job_light_status_server_bound_attach_and_old_v2_audit(tmp_path):
    settings = Settings(
        ai_enabled=True,
        anthropic_model="synthetic",
        anthropic_api_key=SecretStr("synthetic-provider-secret"),
        anthropic_input_usd_per_million=1,
        anthropic_output_usd_per_million=2,
    )
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), settings, connect=False
    )
    entered = threading.Event()
    mock = PublicMock()
    with TestClient(app, client=("127.0.0.1", 123), headers={"x-vision-request": "1"}) as client:

        async def setup():
            gate = asyncio.Event()
            request = device_request(app.state.ai)

            async def handler(call):
                response = await mock(call)
                if not entered.is_set():
                    entered.set()
                    await gate.wait()
                return response

            await app.state.ai.research.client.aclose()
            app.state.ai.research.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            return gate, request

        gate, request = client.portal.call(setup)
        base = client.post("/api/intelligence/preview", json=request.model_dump()).json()
        original = client.get("/api/intelligence/requests/" + base["request_id"]).json()
        serialized = app.state.store.rows(
            "SELECT payload,digest FROM ai_requests WHERE id=?", (base["request_id"],)
        )[0]
        planned = client.post(
            "/api/intelligence/research/plan",
            json={"request_id": base["request_id"], "digest": base["digest"]},
        )
        assert planned.status_code == 200 and not mock.calls
        plan = planned.json()
        assert "private-device-canary" not in json.dumps(plan)
        started = client.post(
            "/api/intelligence/research",
            json={"plan_id": plan["plan_id"], "plan_digest": plan["plan_digest"]},
        )
        assert started.status_code == 202 and entered.wait(1)
        job = started.json()
        status = client.get("/" + job["status_url"]).json()
        assert status["status"] == "running" and len(json.dumps(status)) < 1000
        assert set(status) == {
            "research_id",
            "status",
            "phase",
            "attempts",
            "source_count",
            "error",
            "created",
        }
        assert (
            client.post(
                "/api/intelligence/research",
                json={"plan_id": plan["plan_id"], "plan_digest": plan["plan_digest"]},
            ).status_code
            == 400
        )
        client.portal.call(gate.set)

        async def finish():
            await app.state.ai.research.task

        client.portal.call(finish)
        detail = client.get("/api/intelligence/research/" + job["research_id"]).json()
        assert detail["status"] == "completed" and detail["source_count"] == 5
        assert (
            client.post(
                "/api/intelligence/research/" + job["research_id"] + "/preview",
                json={"research_digest": detail["research_digest"], "target": "smuggled"},
            ).status_code
            == 422
        )
        attached = client.post(
            "/api/intelligence/research/" + job["research_id"] + "/preview",
            json={"research_digest": detail["research_digest"], "diagnostic_consent": False},
        )
        assert attached.status_code == 200
        value = attached.json()
        assert (
            value["preview"]["target_type"] == "device"
            and value["preview"]["schema_version"] == "vision-diagnosis-3"
        )
        assert value["local_selection"]["target"] == request.target
        assert client.get("/api/intelligence/requests/" + base["request_id"]).json() == original
        assert (
            app.state.store.rows(
                "SELECT payload,digest FROM ai_requests WHERE id=?", (base["request_id"],)
            )[0]
            == serialized
        )
        assert len(mock.calls) == 6 and not app.state.store.rows("SELECT * FROM usage")

        # Corrupt projection data must refuse locally with a fixed 400, before admission/payment.
        job_row = app.state.ai.research.jobs[job["research_id"]]
        intact = copy.deepcopy(job_row["snapshot"])
        job_row["snapshot"]["sources"][0]["excerpts"][0]["text"] += " changed"
        job_row["research_digest"] = digest(job_row["snapshot"])
        invalid = client.post(
            "/api/intelligence/research/" + job["research_id"] + "/preview",
            json={"research_digest": job_row["research_digest"]},
        )
        assert invalid.status_code == 400
        assert invalid.json()["detail"] == "Public source integrity validation failed"
        job_row["snapshot"], job_row["research_digest"] = intact, digest(intact)
        payload = json.loads(serialized["payload"])
        payload["question"] = "synthetic-reconstruction-canary" * 40
        changed_digest = digest(payload)
        app.state.store.execute(
            "UPDATE ai_requests SET payload=?,digest=? WHERE id=?",
            (canonical(payload), changed_digest, base["request_id"]),
        )
        job_row["base"]["digest"] = changed_digest
        invalid = client.post(
            "/api/intelligence/research/" + job["research_id"] + "/preview",
            json={"research_digest": job_row["research_digest"]},
        )
        assert invalid.status_code == 400
        assert (
            invalid.json()["detail"]
            == "Public research unavailable: stored preview reconstruction failed"
        )
        assert not app.state.store.rows("SELECT * FROM usage")
