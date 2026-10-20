"""Server-owned AI lifetime, storage admission and retained billing provenance."""

import asyncio
import json
import sqlite3
import time
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from test_ai_pipeline import SyntheticProvider, consent, diagnosis
from test_ai_pipeline import ai as ai

from vision.ai import AIError, Intelligence
from vision.ai_contract import AnalysisInput
from vision.ai_provider import HTTPProvider
from vision.app import create_app
from vision.config import Settings
from vision.monitor import Monitor
from vision.security import Redactor
from vision.store import AI_RESULT_RESERVE_BYTES, MIGRATIONS, Store


def configured():
    return Settings(
        ai_enabled=True,
        anthropic_model="synthetic",
        anthropic_api_key=SecretStr("synthetic-key"),
        anthropic_input_usd_per_million=1,
        anthropic_output_usd_per_million=2,
    )


async def test_http_202_job_survives_client_close_and_light_status_never_reloads_bodies(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), configured(), connect=False
    )
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def provider(request):
        calls.append(request.content)
        entered.set()
        await release.wait()
        prompt = json.loads(json.loads(request.content)["messages"][0]["content"])
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(diagnosis(next(iter(prompt["bundle"]["evidence"])))),
                    }
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 5, "output_tokens": 9},
            },
        )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as native:
            app.state.ai.providers["anthropic"] = HTTPProvider("anthropic", native)
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
            async with httpx.AsyncClient(
                transport=transport, base_url="http://vision", headers={"x-vision-request": "1"}
            ) as client:
                preview = (await client.post("/api/intelligence/preview", json={})).json()
                token = {key: preview[key] for key in ("request_id", "digest")}
                started = time.monotonic()
                response = await client.post("/api/intelligence", json=token)
                assert response.status_code == 202 and time.monotonic() - started < 0.5
                await asyncio.wait_for(entered.wait(), 1)
                assert (await client.post("/api/intelligence", json=token)).status_code == 409
                queries = []
                app.state.store.db.set_trace_callback(queries.append)
                status = await client.get("/" + response.json()["status_url"])
                app.state.store.db.set_trace_callback(None)
                assert status.json()["status"] == "sending" and status.json()["in_flight"]
                assert len(status.content) < 1024 and "preview" not in status.json()
                assert all(
                    "payload" not in query and "local_evidence" not in query for query in queries
                )
            # Closing the initiating HTTP client is not a cancellation of Vision's job.
            assert not app.state.ai.job_task.done()
            release.set()
            await asyncio.wait_for(app.state.ai.job_task, 1)
            async with httpx.AsyncClient(transport=transport, base_url="http://vision") as observer:
                status = (await observer.get("/" + response.json()["status_url"])).json()
                assert status["status"] == "completed" and not status["in_flight"]
                detail = (
                    await observer.get("/api/intelligence/analyses/" + str(status["analysis_id"]))
                ).json()
                assert json.loads(detail["result"])["diagnoses"]
                thin = (await observer.get("/api/intelligence")).json()["analyses"][0]
                assert "result" not in thin and "evidence" not in thin and thin["summary"]
                assert json.loads(detail["evidence"])["mapping"]
            assert calls == [preview["preview"]["requests"]["anthropic"]["body_utf8"].encode()]
            assert len(app.state.store.rows("SELECT * FROM usage")) == 1


async def test_absolute_deadline_releases_job_lock_and_keeps_uncertain_billing(ai, monkeypatch):
    monkeypatch.setattr("vision.ai.MAX_JOB_SECONDS", 0.01)

    async def never(body, key):
        ai.providers["anthropic"].calls.append((body, key))
        await asyncio.sleep(60)

    ai.providers["anthropic"].send = never
    preview = ai.preview(AnalysisInput())
    job = ai.start(consent(preview))
    await asyncio.wait_for(ai.job_task, 1)
    state = ai.store.rows("SELECT status,error FROM ai_requests WHERE id=?", (job["request_id"],))[
        0
    ]
    assert state["status"] == "uncertain" and "deadline" in state["error"]
    assert not ai.lock.locked() and ai.active_request_id is None
    usage = ai.store.rows("SELECT * FROM usage")
    assert len(usage) == 1 and usage[0]["status"] == "uncertain" and usage[0]["cost_usd"] > 0
    assert not ai.providers["openai"].calls
    assert "deadline" in ai.store.get_meta("ai_error")
    await ai.close()


async def test_shutdown_cancellation_records_uncertainty_before_storage_closes(ai):
    entered = asyncio.Event()

    async def never(_body, _key):
        entered.set()
        await asyncio.sleep(60)

    ai.providers["anthropic"].send = never
    preview = ai.preview(AnalysisInput())
    ai.start(consent(preview))
    await entered.wait()
    await ai.close()
    assert ai.store.rows("SELECT status FROM ai_requests")[0]["status"] == "uncertain"
    assert ai.store.rows("SELECT status,cost_usd FROM usage")[0]["cost_usd"] > 0
    assert ai.store.rows("SELECT status FROM usage")[0]["status"] == "uncertain"


async def test_admission_reserves_all_pending_result_space_without_eviction(ai, monkeypatch):
    first, second = ai.preview(AnalysisInput()), ai.preview(AnalysisInput())
    before = ai.store.rows("SELECT id,payload,local_evidence FROM ai_requests ORDER BY id")
    usage = ai.store.ai_storage()
    assert usage["promised_result_bytes"] == 2 * AI_RESULT_RESERVE_BYTES
    cap = usage["stored_bytes"] + usage["promised_result_bytes"]
    monkeypatch.setattr("vision.ai.AI_MAX_STORAGE_BYTES", cap)
    with pytest.raises(AIError, match="storage admission"):
        ai.preview(AnalysisInput())
    assert ai.store.rows("SELECT id,payload,local_evidence FROM ai_requests ORDER BY id") == before
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.send(consent(first))
    after = ai.store.ai_storage()
    assert after["stored_bytes"] + after["promised_result_bytes"] <= cap
    assert after["promised_result_bytes"] == AI_RESULT_RESERVE_BYTES
    assert len(ai.store.rows("SELECT * FROM analyses")) == 1
    assert ai.store.rows("SELECT payload FROM ai_requests WHERE id=?", (second["request_id"],))
    # A new lower cap blocks admission, never deletes existing completed history.
    monkeypatch.setattr("vision.ai.AI_MAX_REQUESTS", 1)
    with pytest.raises(AIError, match="storage admission"):
        ai.preview(AnalysisInput())
    assert (
        len(ai.store.rows("SELECT * FROM analyses")) == 1
        and len(ai.store.rows("SELECT * FROM ai_requests")) == 2
    )
    await ai.close()


async def test_expired_unused_cleanup_preserves_transmitted_and_completed_bodies(ai):
    completed = ai.preview(AnalysisInput())
    await ai.send(consent(completed))
    unused = ai.preview(AnalysisInput())
    ai.store.execute("UPDATE ai_requests SET expires=0")
    retained = ai.store.rows(
        "SELECT payload,local_evidence FROM ai_requests WHERE id=?", (completed["request_id"],)
    )
    ai.store.prune(90)
    assert not ai.store.rows("SELECT * FROM ai_requests WHERE id=?", (unused["request_id"],))
    assert (
        ai.store.rows(
            "SELECT payload,local_evidence FROM ai_requests WHERE id=?", (completed["request_id"],)
        )
        == retained
    )
    assert len(ai.store.rows("SELECT * FROM usage")) == 1
    await ai.close()


async def test_400_day_receipt_survives_90_day_body_prune_and_restart(tmp_path):
    store = Store(tmp_path / "vision.db")
    settings, redactor = configured(), Redactor()
    monitor = Monitor(store, settings, SimpleNamespace(token=""), redactor)
    ai = Intelligence(
        store,
        settings,
        monitor,
        redactor,
        {provider: SyntheticProvider() for provider in ("anthropic", "openai")},
    )
    preview = ai.preview(AnalysisInput())
    await ai.send(consent(preview))
    old = time.time() - 120 * 86400
    for table in ("ai_requests", "analyses", "usage", "ai_billing_receipts"):
        ai.store.execute("UPDATE " + table + " SET created=?", (old,))
    receipt = ai.store.rows("SELECT * FROM ai_billing_receipts")[0]
    assert receipt["digest"] == preview["digest"] and receipt["round"] == 1
    ai.store.prune(90)
    assert not ai.store.rows("SELECT * FROM ai_requests") and not ai.store.rows(
        "SELECT * FROM ai_attempts"
    )
    assert ai.store.rows("SELECT * FROM ai_billing_receipts") == [receipt]
    path = ai.store.path
    await ai.close()
    ai.store.close()
    restored = Store(path)
    assert restored.rows("SELECT * FROM ai_billing_receipts") == [receipt]
    assert restored.rows("SELECT cost_usd FROM usage")[0]["cost_usd"] > 0
    restored.execute("UPDATE usage SET created=?", (time.time() - 410 * 86400,))
    restored.prune(90)
    assert not restored.rows("SELECT * FROM usage") and not restored.rows(
        "SELECT * FROM ai_billing_receipts"
    )
    restored.close()


def test_schema_seven_backfills_existing_six_attempts_without_body_changes(tmp_path):
    path = tmp_path / "vision.db"
    with sqlite3.connect(path) as db:
        for version in range(1, 7):
            for statement in MIGRATIONS[version]:
                db.execute(statement)
        db.execute("PRAGMA user_version=6")
        db.execute("INSERT INTO usage VALUES (1,1,'openai','legacy',NULL,NULL,.4,'uncertain')")
        db.execute(
            "INSERT INTO ai_requests VALUES ('old',1,2,'revoked','conversation',2,'audit',"
            "NULL,'compact',NULL,NULL,'binding','digest','exact payload',"
            "'private evidence',NULL,NULL)"
        )
        db.execute("INSERT INTO ai_attempts VALUES (1,'old','openai',3)")
    store = Store(path)
    assert store.rows("SELECT * FROM ai_billing_receipts") == [
        {
            "usage_id": 1,
            "created": 1,
            "request_id": "old",
            "conversation_id": "conversation",
            "round": 2,
            "digest": "digest",
            "provider": "openai",
            "attempt": 3,
            "revoked": 1,
        }
    ]
    assert store.rows("SELECT payload,local_evidence FROM ai_requests") == [
        {"payload": "exact payload", "local_evidence": "private evidence"}
    ]
    store.close()


def test_settings_assignment_validation_is_atomic_and_generation_never_resurrects():
    settings = Settings(ai_enabled=True, daily_audit=True)
    before = settings.model_dump()
    with pytest.raises(ValidationError):
        settings.ai_enabled = False
    assert settings.model_dump() == before and settings._consent_generation == 0
    with pytest.raises(ValidationError):
        settings.ai_privacy = "unsafe"
    assert settings.model_dump() == before and settings._consent_generation == 0
    settings.daily_audit = False
    settings.ai_enabled = False
    settings.ai_enabled = True
    assert settings._consent_generation == 2
    settings.max_output_tokens = 65536
    with pytest.raises(ValidationError):
        settings.max_output_tokens = 65537
    assert settings.max_output_tokens == 65536


async def test_revoked_inflight_response_keeps_promised_space_and_never_fails_over(ai, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def technical(body, key):
        ai.providers["anthropic"].calls.append((body, key))
        entered.set()
        await release.wait()
        from vision.ai_provider import ProviderError

        raise ProviderError("technical")

    ai.providers["anthropic"].send = technical
    preview = ai.preview(AnalysisInput())
    ai.start(consent(preview))
    await entered.wait()
    ai.revoke(preview["request_id"])
    capacity = ai.store.ai_storage()
    assert capacity["promised_result_bytes"] == AI_RESULT_RESERVE_BYTES
    monkeypatch.setattr(
        "vision.ai.AI_MAX_STORAGE_BYTES",
        capacity["stored_bytes"] + 3 * AI_RESULT_RESERVE_BYTES // 2,
    )
    with pytest.raises(AIError, match="storage admission"):
        ai.preview(AnalysisInput())
    release.set()
    await ai.job_task
    assert ai.store.rows("SELECT status FROM ai_requests")[0]["status"] == "revoked"
    assert ai.store.rows("SELECT revoked FROM ai_billing_receipts") == [{"revoked": 1}]
    assert ai.store.rows("SELECT status FROM usage") == [{"status": "uncertain"}]
    assert not ai.providers["openai"].calls
    await ai.close()


def test_receipt_insert_failure_rolls_back_ledger_and_attempt(ai, monkeypatch):
    preview = ai.preview(AnalysisInput())
    payload = preview["preview"]
    execute = ai.store.execute

    def reject(sql, args=()):
        if sql.startswith("INSERT INTO ai_billing_receipts"):
            raise sqlite3.IntegrityError("synthetic receipt failure")
        return execute(sql, args)

    monkeypatch.setattr(ai.store, "execute", reject)
    with pytest.raises(sqlite3.IntegrityError):
        ai.reserve(
            "anthropic",
            "synthetic-a",
            payload["requests"]["anthropic"]["body_utf8"],
            payload["policy"],
            request_id=preview["request_id"],
            attempt=1,
        )
    assert not ai.store.rows("SELECT * FROM usage")
    assert not ai.store.rows("SELECT * FROM ai_attempts")
    assert not ai.store.rows("SELECT * FROM ai_billing_receipts")


async def test_full_valid_stored_result_fits_reserved_bytes_and_size_guard_keeps_usage(
    ai, monkeypatch
):
    from vision.ai_contract import Diagnosis

    preview = ai.preview(AnalysisInput())
    ref = next(iter(preview["preview"]["bundle"]["evidence"]))
    symbol = "🚨"
    result = diagnosis(ref)
    result["summary"] = symbol * 2000
    finding = result["diagnoses"][0]
    finding.update(
        finding=symbol * 1500,
        uncertainty=symbol * 1000,
        unknowns=[symbol * 500] * 10,
        next_step=symbol * 1500,
        validation=symbol * 1000,
        evidence=[ref] * 20,
        counter_evidence=[ref] * 20,
    )
    result.update(diagnoses=[finding] * 12, unknowns=[symbol * 500] * 12)
    Diagnosis.model_validate(result)
    ai.providers["anthropic"].replies = [result]
    await ai.send(consent(preview))
    row = ai.store.rows("SELECT result,evidence FROM analyses")[0]
    assert len(row["result"].encode()) + len(row["evidence"].encode()) <= AI_RESULT_RESERVE_BYTES
    # Even a future larger schema cannot consume more than its reserved space.
    fresh = ai.preview(AnalysisInput())
    monkeypatch.setattr("vision.ai.AI_RESULT_RESERVE_BYTES", 100)
    with pytest.raises(AIError, match="retained result bound"):
        await ai.send(consent(fresh))
    assert (
        ai.store.rows("SELECT status,cost_usd FROM usage ORDER BY id DESC LIMIT 1")[0]["cost_usd"]
        > 0
    )
    assert (
        ai.store.rows("SELECT status FROM usage ORDER BY id DESC LIMIT 1")[0]["status"]
        == "invalid_diagnosis"
    )
    assert len(ai.store.rows("SELECT * FROM analyses")) == 1
    await ai.close()


async def test_recent_list_is_thin_and_legacy_mapping_is_loaded_only_on_explicit_detail(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), Settings(), connect=False
    )
    async with app.router.lifespan_context(app):
        result = json.dumps(
            {"summary": "Legacy retained summary", "diagnoses": [], "legacy_detail": "x" * 50000}
        )
        evidence = json.dumps(
            {"mapping": {"E1": "retained original mapping"}, "legacy_detail": "y" * 50000}
        )
        for _ in range(55):
            app.state.store.execute(
                "INSERT INTO analyses VALUES (NULL,?,'audit',NULL,'openai','legacy',?,?)",
                (time.time(), result, evidence),
            )
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
        async with httpx.AsyncClient(transport=transport, base_url="http://vision") as client:
            queries = []
            app.state.store.db.set_trace_callback(queries.append)
            response = await client.get("/api/intelligence")
            app.state.store.db.set_trace_callback(None)
            rows = response.json()["analyses"]
            assert len(rows) == 50 and len(response.content) < 32000
            assert all("evidence" not in row and "result" not in row for row in rows)
            assert not any(
                "SELECT * FROM analyses" in query or "sum(length" in query for query in queries
            )
            detail = (await client.get("/api/intelligence/analyses/" + str(rows[0]["id"]))).json()
            assert detail["evidence"] == evidence and detail["result"] == result
            assert not detail["can_continue"]
            history = (
                await client.get("/api/history/page?kind=analyses&q=Legacy%20retained")
            ).json()
            assert history["next_cursor"] and len(history["items"]) == 50


async def test_available_only_target_does_not_qualify_as_an_offline_investigation(ai):
    ai.monitor.observe_state({"entity_id": "sensor.online_only", "state": "on", "attributes": {}})
    preview = ai.preview(AnalysisInput(kind="availability", target="sensor.online_only"))
    assert not preview["preview"]["readiness"]["supported"]
    with pytest.raises(AIError, match="needs retained evidence"):
        await ai.send(consent(preview))
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.close()


async def test_unexpected_background_failure_has_safe_breadcrumb_and_uncertain_receipt(ai):
    async def broken(_body, _key):
        raise RuntimeError("private_exception_canary sensor.private_entity")

    ai.providers["anthropic"].send = broken
    preview = ai.preview(AnalysisInput())
    ai.start(consent(preview))
    await ai.job_task
    row = ai.store.rows("SELECT status,error FROM ai_requests")[0]
    assert row == {"status": "failed", "error": "Analysis failed"}
    assert "inspect the retained request" in ai.store.get_meta("ai_error")
    assert "canary" not in json.dumps(row) + ai.store.get_meta("ai_error")
    assert ai.store.rows("SELECT status,cost_usd FROM usage")[0]["cost_usd"] > 0
    assert len(ai.store.rows("SELECT * FROM ai_billing_receipts")) == 1
    await ai.close()
