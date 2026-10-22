"""Durable one-click boundaries using real ASGI, SQLite and native mock HTTP."""

import asyncio
import hashlib
import json
import sqlite3
import time
import uuid
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from test_ai_pipeline import diagnosis, prompt_of
from test_home_experience import seed
from test_public_research import PublicMock

from vision.ai import Intelligence
from vision.ai_contract import AnalysisInput, provider_schema, result_contract
from vision.ai_provider import AIConflict, HTTPProvider, encoded, request_body
from vision.app import create_app
from vision.config import Settings
from vision.home import problem_id
from vision.oneclick import HIGHWATER, VERSION, ConsentInput, StartInput
from vision.store import MIGRATIONS, Store


def human_result(prompt):
    result = diagnosis(next(iter(prompt["bundle"]["evidence"])))
    finding = result["diagnoses"][0]
    finding.update(
        title="Controleer voeding",
        core_explanation="De oorzaak is nog onbekend.",
        next_check="Vergelijk dit apparaat met een werkend apparaat.",
    )
    sources = [
        p["ref"]
        for source in prompt.get("research", {}).get("sources", [])
        for p in source["excerpts"]
    ]
    if sources:
        finding.update(
            source_refs=sources[:1],
            manual_plan={
                "prerequisites": ["Voer zelf een controle uit"],
                "steps": [
                    {
                        "instruction": "Controleer voeding en verwacht slaapgedrag.",
                        "source_refs": sources[:1],
                    },
                    {
                        "instruction": "Vergelijk de integratiestatus met een gezond apparaat.",
                        "source_refs": sources[:1],
                    },
                ],
            },
        )
    return result


@pytest.fixture
async def runtime(tmp_path):
    settings = Settings(
        ai_enabled=True,
        primary_provider="anthropic",
        anthropic_api_key=SecretStr("synthetic-key"),
        anthropic_model="synthetic",
        anthropic_input_usd_per_million=1,
        anthropic_output_usd_per_million=2,
        openai_api_key=SecretStr("synthetic-backup"),
        openai_model="synthetic",
        openai_input_usd_per_million=1,
        openai_output_usd_per_million=2,
    )
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), settings, connect=False
    )
    async with app.router.lifespan_context(app):
        ai, m = app.state.ai, app.state.monitor
        seed(m)
        for row in m.registry.values():
            row["platform"] = "zha"
        m.reliability.refresh(time.time())
        await m.reliability.wait_cache()
        m.home.refresh()
        m.ha_version, m.ha_version_observed_at = "2026.10.2", time.time()
        public, native, barriers = PublicMock(), [], {}
        public.extra_text += ' light.local_0 d0 {"token":"local-public-canary"}'
        await ai.research.client.aclose()
        ai.research.client = httpx.AsyncClient(transport=httpx.MockTransport(public))

        async def provider(request):
            native.append(request)
            # A separate connection must see committed operation/freeze/receipt before dispatch.
            with sqlite3.connect(tmp_path / "vision.db") as observer:
                op = observer.execute(
                    "SELECT status,final_request_id FROM home_investigations "
                    "WHERE final_request_id=?",
                    (ai.active_request_id,),
                ).fetchone()
                assert op is not None
                assert op[0] == "sending"
                assert observer.execute(
                    "SELECT count(*) FROM ai_attempts WHERE request_id=?", (op[1],)
                ).fetchone()[0]
                assert observer.execute(
                    "SELECT count(*) FROM ai_billing_receipts WHERE request_id=?", (op[1],)
                ).fetchone()[0]
                payload = json.loads(
                    observer.execute(
                        "SELECT payload FROM ai_requests WHERE id=?", (op[1],)
                    ).fetchone()[0]
                )
                name = "anthropic" if request.url.host == "api.anthropic.com" else "openai"
                assert request.content == payload["requests"][name]["body_utf8"].encode()
            if barriers.get("entered"):
                barriers["entered"].set()
                await barriers["release"].wait()
            if barriers.get("fail_primary") and name == "anthropic":
                return httpx.Response(503)
            result = human_result(prompt_of(request.content))
            if name == "anthropic":
                return httpx.Response(
                    200,
                    json={
                        "content": [{"type": "text", "text": json.dumps(result)}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 10, "output_tokens": 20},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": json.dumps(result)}],
                        }
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as transport:
            ai.providers = {p: HTTPProvider(p, transport) for p in ("anthropic", "openai")}
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)),
                base_url="http://vision",
                headers={"x-vision-request": "1"},
            ) as client:
                yield client, app, public, native, barriers


async def start(runtime, *, enable=True, key=None):
    client, app, *_ = runtime
    key = key or problem_id("device", "d0")
    if enable:
        assert (
            await client.post(
                "/api/home/investigation-consent", json={"version": VERSION, "enabled": True}
            )
        ).status_code == 200
    context = (await client.get(f"/api/problems/{key}/investigation-context")).json()
    payload = {
        "operation_id": f"op1_{context['slot']}_{uuid.uuid4().hex}",
        "revision": context["revision"],
        "language": "nl",
    }
    answer = await client.post(f"/api/problems/{key}/investigate", json=payload)
    return key, payload, answer


async def test_default_off_context_is_readonly_then_exactly_one_durable_round_and_duplicate(
    runtime,
):
    client, app, public, native, _ = runtime
    db = app.state.store
    before = db.db.total_changes
    key = problem_id("device", "d0")
    for _ in range(2):
        context = (await client.get(f"/api/problems/{key}/investigation-context")).json()
        assert not context["consent"]["enabled"]
    assert db.db.total_changes == before and not native and not public.calls
    _, _, refused = await start(runtime, enable=False)
    assert refused.status_code == 400 and not db.rows("SELECT * FROM home_investigations")
    key, value, response = await start(runtime)
    assert response.status_code == 202, response.text
    same = await client.post(f"/api/problems/{key}/investigate", json=value)
    assert same.json()["operation_id"] == value["operation_id"]
    await asyncio.wait_for(app.state.ai.oneclick.task, 2)
    status = (await client.get(response.json()["status_url"])).json()
    assert status["status"] == "completed", status
    assert not {"plan", "scope", "payload", "preview"}.intersection(status)
    assert len(public.calls) == 6 and len(native) == 1
    requests = db.rows("SELECT * FROM ai_requests ORDER BY created")
    assert len(requests) == 2 and requests[-1]["analysis_id"] == status["analysis_id"]
    payload = json.loads(requests[-1]["payload"])
    assert payload["schema_version"] == "vision-diagnosis-4" and payload["language"] == "nl"
    assert payload["variant"] == "sources"
    assert payload["research"]["sources"]
    for canary in ("Friendly lamp", "Living room", "light.local_0", "local-public-canary"):
        assert canary not in native[0].content.decode()
    final = json.loads(requests[-1]["local_evidence"])
    base = json.loads(requests[0]["local_evidence"])
    assert final["snapshot"] == base["snapshot"]
    value["language"] = "en"
    assert (await client.post(f"/api/problems/{key}/investigate", json=value)).status_code == 409
    assert len(native) == 1


async def test_oneclick_pins_base_against_preview_gc_and_blocks_manual_claim(runtime):
    client, app, _, native, _ = runtime
    entered, release = asyncio.Event(), asyncio.Event()
    original = app.state.ai.research.get

    async def gate(job, request):
        entered.set()
        await release.wait()
        return await original(job, request)

    app.state.ai.research.get = gate
    _, _, response = await start(runtime)
    assert response.status_code == 202
    await entered.wait()
    ai = app.state.ai
    base = ai.oneclick.status(response.json()["operation_id"])["base_request_id"]
    for _ in range(33):
        preview = ai.preview(AnalysisInput())
    assert ai.store.rows("SELECT 1 FROM ai_requests WHERE id=?", (base,))
    assert (
        await client.post(
            "/api/intelligence", json={k: preview[k] for k in ("request_id", "digest")}
        )
    ).status_code == 409
    release.set()
    await ai.oneclick.task
    assert len(native) == 1


async def test_withdraw_during_primary_keeps_usage_and_result_and_prevents_failover(runtime):
    client, app, _, native, barriers = runtime
    barriers.update(entered=asyncio.Event(), release=asyncio.Event(), fail_primary=True)
    _, _, response = await start(runtime)
    await barriers["entered"].wait()
    op = response.json()["operation_id"]
    assert (await client.post(f"/api/home/investigations/{op}/revoke")).status_code == 200
    # Revocation cannot release live result promises or request pins while native
    # transmission is still outstanding, including ordinary expired-preview GC.
    db = app.state.store
    db.execute(
        "UPDATE home_investigations SET created=? WHERE id=?", (time.time() - 100 * 86400, op)
    )
    db.execute("UPDATE ai_requests SET created=?,expires=0", (time.time() - 100 * 86400,))
    app.state.ai.oneclick.prune()
    with db.transaction():
        db.cleanup_ai_previews()
    assert len(db.rows("SELECT id FROM ai_requests")) == 2
    assert app.state.ai.oneclick.status(op)["in_flight"]
    assert app.state.ai.oneclick.busy()
    barriers["release"].set()
    await app.state.ai.oneclick.task
    assert app.state.ai.oneclick.status(op)["status"] == "revoked"
    assert len(native) == 1
    assert app.state.store.rows("SELECT status,cost_usd FROM usage")[0]["cost_usd"] > 0
    assert app.state.store.rows("SELECT revoked FROM ai_billing_receipts")[0]["revoked"] == 1


async def test_manual_v4_followup_keeps_contract_language_sources_and_frozen_private_base(runtime):
    client, app, public, native, _ = runtime
    _, _, response = await start(runtime)
    await app.state.ai.oneclick.task
    status = app.state.ai.oneclick.status(response.json()["operation_id"])
    db = app.state.store
    initial = db.rows("SELECT * FROM ai_requests WHERE id=?", (status["final_request_id"],))[0]
    conversation = (
        await client.get("/api/intelligence/conversations/" + initial["conversation_id"])
    ).json()
    assert conversation["rounds"][0]["output_contract"] == "human-v4"
    assert conversation["rounds"][0]["language"] == "nl"
    value = {
        "kind": "availability",
        "target": "d0",
        "target_type": "device",
        "profile": "compact",
        "conversation_id": initial["conversation_id"],
        "output_contract": "human-v4",
        "language": "nl",
    }
    assert (
        await client.post("/api/intelligence/preview", json={**value, "language": "en"})
    ).status_code == 400
    followup = await client.post("/api/intelligence/preview", json=value)
    assert followup.status_code == 200, followup.text
    row = db.rows("SELECT * FROM ai_requests WHERE id=?", (followup.json()["request_id"],))[0]
    payload = json.loads(row["payload"])
    assert payload["schema_version"] == "vision-diagnosis-4" and payload["language"] == "nl"
    assert (
        json.loads(row["local_evidence"])["snapshot"]
        == json.loads(initial["local_evidence"])["snapshot"]
    )
    assert (
        payload["research"]["sources"][0]["content_sha256"]
        == json.loads(initial["payload"])["research"]["sources"][0]["content_sha256"]
    )
    assert len(public.calls) == 6 and len(native) == 1


async def test_technical_failover_uses_both_native_bodies_with_one_final_claim(runtime):
    _, app, _, native, barriers = runtime
    barriers["fail_primary"] = True
    _, _, response = await start(runtime)
    await app.state.ai.oneclick.task
    assert app.state.ai.oneclick.status(response.json()["operation_id"])["status"] == "completed"
    assert len(native) == 2 and len(app.state.store.rows("SELECT * FROM ai_requests")) == 2
    assert [r["status"] for r in app.state.store.rows("SELECT * FROM usage ORDER BY id")] == [
        "uncertain",
        "response_received",
    ]


async def test_expired_missing_operation_never_resurrects_after_prune_clock_rollback(
    runtime, monkeypatch
):
    client, app, public, native, _ = runtime
    key, value, response = await start(runtime)
    await app.state.ai.oneclick.task
    slot = int(value["operation_id"].split("_")[1])
    advanced = (slot + 10000) * 900
    monkeypatch.setattr("vision.oneclick.time.time", lambda: advanced)
    app.state.ai.oneclick.prune()
    assert not app.state.store.rows("SELECT * FROM home_investigations")
    monkeypatch.setattr("vision.oneclick.time.time", lambda: slot * 900)
    before = (len(public.calls), len(native), app.state.store.db.total_changes)
    rejected = await client.post(f"/api/problems/{key}/investigate", json=value)
    assert rejected.status_code == 410
    assert before == (len(public.calls), len(native), app.state.store.db.total_changes)
    assert app.state.store.get_meta(HIGHWATER) == slot + 10000


async def test_explicit_group_freezes_multiple_members_and_healthy_counterevidence_without_names(
    runtime,
):
    client, app, _, native, _ = runtime
    monitor = app.state.monitor
    at = time.time() - 200
    seed(monitor, ("on", "on", "on"), now=at)
    for row in monitor.registry.values():
        row["platform"] = "zha"
    monitor.reliability.refresh(at + 1)
    for index in range(2):
        monitor.observe_state(
            {"entity_id": f"light.local_{index}", "state": "unavailable"},
            at + 150,
            track_device=False,
        )
    monitor.reliability.refresh(at + 150)
    await monitor.reliability.wait_cache()
    monitor.home.refresh()
    group = next(
        p for p in (await client.get("/api/today")).json()["priorities"] if p["kind"] == "group"
    )
    _, _, answer = await start(runtime, key=group["problem_id"])
    assert answer.status_code == 202
    await app.state.ai.oneclick.task
    status = app.state.ai.oneclick.status(answer.json()["operation_id"])
    assert status["status"] == "completed", status
    request = app.state.store.rows(
        "SELECT local_evidence,payload FROM ai_requests WHERE id=?", (status["final_request_id"],)
    )[0]
    local, payload = json.loads(request["local_evidence"]), json.loads(request["payload"])
    sections = local["snapshot"]["sections"]
    assert local["snapshot"]["selection_basis"] == "exact_covered_group"
    assert {r["device_id"] for r in sections["target"] if r["type"] == "group_member"} == {
        "d0",
        "d1",
    }
    assert sections["siblings"][0]["device_id"] == "d2"
    assert len(sections["target"]) + len(sections["siblings"]) - 1 <= 16
    values = list(payload["bundle"]["evidence"].values())
    coverage = next(v["value"] for v in values if v["section"] == "coverage")
    assert coverage["group_affected_selected"] == 2 and coverage["group_healthy_selected"] == 1
    assert "Friendly lamp" not in native[0].content.decode()
    assert group["problem_id"] not in native[0].content.decode()


async def test_pending_revision_and_missing_exact_run_stop_without_fallback(runtime):
    client, app, public, native, _ = runtime
    monitor = app.state.monitor
    ai = app.state.ai
    ai.oneclick.set_consent(ConsentInput(version=VERSION, enabled=True))
    key = problem_id("device", "d0")
    ctx = ai.oneclick.context(key)
    value = StartInput(
        operation_id=f"op1_{ctx['slot']}_{uuid.uuid4().hex}",
        revision=ctx["revision"],
        language="nl",
    )
    monitor.home.pending = True
    assert (
        await client.post(f"/api/problems/{key}/investigate", json=value.model_dump())
    ).status_code == 409
    monitor.home.pending = False
    now = time.time()
    for entity in ("automation.first", "automation.second"):
        monitor.entities[entity] = {"name": entity}
        app.state.store.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
            (entity, "same-run", None, now, "failed", 1, "{}"),
        )
        app.state.store.execute(
            "INSERT INTO run_timing VALUES (?,?,?,?)", (entity, "same-run", now, "ha_trace")
        )
        app.state.store.issue(
            "automation:" + entity,
            "automation",
            "error",
            "Failed",
            {"entity_id": entity, "run_id": "same-run"},
            now,
        )
    monitor.home.refresh()
    rows = [p for p in monitor.home.cache if p["selection"]["kind"] == "automation_run"]
    assert len(rows) == 2
    selections = [ai.oneclick.selection(p["problem_id"])[2] for p in rows]
    assert {r.target for r in selections} == {"automation.first", "automation.second"}
    assert all(r.run_id == "same-run" for r in selections)
    app.state.store.execute(
        "DELETE FROM runs WHERE entity_id=? AND run_id=?", (selections[0].target, "same-run")
    )
    with pytest.raises(AIConflict, match="execution"):
        ai.oneclick.selection(rows[0]["problem_id"])
    assert not public.calls and not native


async def test_restart_preserves_operation_lookup_and_uncertain_attempt_without_replay(
    runtime, tmp_path
):
    _, app, _, native, barriers = runtime
    barriers.update(entered=asyncio.Event(), release=asyncio.Event())
    key, value, response = await start(runtime)
    await barriers["entered"].wait()
    clone = tmp_path / "crash-copy.db"
    with sqlite3.connect(clone) as target:
        app.state.store.db.backup(target)
    db = Store(clone)
    restarted = Intelligence(db, app.state.ai.settings, app.state.monitor, app.state.redactor)
    try:
        status = restarted.oneclick.status(response.json()["operation_id"])
        assert status["status"] == "uncertain"
        assert (
            restarted.oneclick.start(key, StartInput(**value))["operation_id"]
            == status["operation_id"]
        )
        assert restarted.oneclick.task is None
        assert db.rows("SELECT status,cost_usd FROM usage")[0]["status"] == "uncertain"
        assert len(native) == 1
    finally:
        await restarted.close()
        db.close()
        barriers["release"].set()
        await app.state.ai.oneclick.task


async def test_revoke_off_on_during_public_wait_keeps_old_operation_blocked(runtime):
    client, app, public, native, _ = runtime
    entered, release = asyncio.Event(), asyncio.Event()
    original = app.state.ai.research.get

    async def gate(job, request):
        entered.set()
        await release.wait()
        return await original(job, request)

    app.state.ai.research.get = gate
    _, _, response = await start(runtime)
    await entered.wait()
    for enabled in (False, True):
        assert (
            await client.post(
                "/api/home/investigation-consent", json={"version": VERSION, "enabled": enabled}
            )
        ).status_code == 200
    release.set()
    await app.state.ai.oneclick.task
    assert app.state.ai.oneclick.status(response.json()["operation_id"])["status"] == "revoked"
    assert not native and not public.calls and not app.state.store.rows("SELECT * FROM usage")
    job = next(iter(app.state.ai.research.jobs.values()))
    assert job["status"] == "revoked"
    assert job["error"] == "revoked_or_configuration_changed"


async def test_operation_capacity_refuses_without_erasing_history_or_dispatch(runtime, monkeypatch):
    _, app, public, native, _ = runtime
    monkeypatch.setattr("vision.oneclick.MAX_OPERATIONS", 0)
    _, _, response = await start(runtime)
    assert response.status_code == 400
    assert not public.calls and not native
    assert not app.state.store.rows("SELECT * FROM home_investigations")


async def test_operation_retention_uses_admitted_slot_not_rollback_created_time(
    runtime, monkeypatch
):
    _, app, _, native, _ = runtime
    _, _, response = await start(runtime)
    await app.state.ai.oneclick.task
    op = response.json()["operation_id"]
    db = app.state.store
    slot = int(op.split("_")[1])
    # A backward wall clock can make created old while this ID's start slot is still open.
    db.execute(
        "UPDATE home_investigations SET created=? WHERE id=?", (time.time() - 100 * 86400, op)
    )
    db.set_meta(HIGHWATER, slot)
    app.state.ai.oneclick.prune()
    assert db.rows("SELECT 1 FROM home_investigations WHERE id=?", (op,))
    db.set_meta(HIGHWATER, slot + 2)
    app.state.ai.oneclick.prune()
    assert not db.rows("SELECT 1 FROM home_investigations WHERE id=?", (op,))
    assert len(native) == 1


@pytest.mark.parametrize("field", ["ai_enabled", "ai_privacy"])
async def test_existing_ai_or_local_only_gates_never_inherit_oneclick_power(runtime, field):
    _, app, public, native, _ = runtime
    setattr(app.state.ai.settings, field, False if field == "ai_enabled" else "local_only")
    _, _, response = await start(runtime)
    assert response.status_code == 400 and not native and not public.calls
    assert not app.state.store.rows("SELECT * FROM home_investigations")


async def test_all_public_gaps_use_v4_local_variant_without_empty_source_enum(runtime):
    _, app, _, native, _ = runtime

    async def unavailable(_request):
        return httpx.Response(503)

    await app.state.ai.research.client.aclose()
    app.state.ai.research.client = httpx.AsyncClient(transport=httpx.MockTransport(unavailable))
    _, _, response = await start(runtime)
    await app.state.ai.oneclick.task
    status = app.state.ai.oneclick.status(response.json()["operation_id"])
    assert status["status"] == "completed"
    final = json.loads(
        app.state.store.rows(
            "SELECT payload FROM ai_requests WHERE id=?", (status["final_request_id"],)
        )[0]["payload"]
    )
    assert final["variant"] == "local" and final["schema_version"] == "vision-diagnosis-4"
    assert not final["research"]["sources"] and final["research"]["gaps"]
    assert '"source_refs"' not in json.dumps(json.loads(native[0].content)["output_config"])


async def test_paid_invalid_v4_reference_stops_without_an_extra_logical_round(runtime):
    _, app, _, native, _ = runtime

    async def invalid(body, _key):
        from vision.ai_provider import ProviderResult

        native.append(body)
        result = human_result(prompt_of(body))
        result["diagnoses"][0]["evidence"] = ["old-round:E1"]
        return ProviderResult(text=json.dumps(result), input_tokens=10, output_tokens=20)

    app.state.ai.providers["anthropic"].send = invalid
    _, _, response = await start(runtime)
    await app.state.ai.oneclick.task
    status = app.state.ai.oneclick.status(response.json()["operation_id"])
    assert status["status"] == "failed" and len(native) == 1
    assert (
        app.state.store.rows("SELECT status,cost_usd FROM usage")[0]["status"]
        == "invalid_diagnosis"
    )
    assert app.state.store.rows("SELECT status,cost_usd FROM usage")[0]["cost_usd"] > 0
    assert not app.state.store.rows("SELECT * FROM analyses")


async def test_whole_deadline_cancels_inflight_and_preserves_uncertain_reservation(
    runtime, monkeypatch
):
    _, app, _, native, barriers = runtime
    barriers.update(entered=asyncio.Event(), release=asyncio.Event())
    monkeypatch.setattr("vision.oneclick.MAX_SECONDS", 0.5)
    _, _, response = await start(runtime)
    await app.state.ai.oneclick.task
    status = app.state.ai.oneclick.status(response.json()["operation_id"])
    assert status["status"] == "uncertain", status
    assert len(native) == 1 and not app.state.ai.lock.locked()
    assert app.state.store.rows("SELECT status,cost_usd FROM usage")[0]["status"] == "uncertain"
    assert app.state.store.rows("SELECT status,cost_usd FROM usage")[0]["cost_usd"] > 0


def test_v4_contracts_are_explicit_and_native_defaults_keep_old_schema_fields():
    for provider in ("anthropic", "openai"):
        old = json.loads(
            request_body(provider, "model", "system", "prompt", 2048, evidence_refs=["E1"])
        )
        assert "HumanFinding" not in json.dumps(old) and "core_explanation" not in json.dumps(old)
        schema = provider_schema(provider, ["E1"], output_contract="human-v4")
        assert schema["$defs"]["HumanFinding"]["properties"]["evidence"]["items"]["enum"] == ["E1"]
        assert schema["$defs"]["HumanFinding"]["properties"]["title"]
    with pytest.raises(ValueError):
        result_contract("unknown")
    with pytest.raises(ValueError):
        result_contract("vision-diagnosis-4", "unknown")


@pytest.mark.parametrize(
    "version,variant",
    [
        ("unknown", None),
        ("vision-diagnosis-4", "unknown"),
        ("vision-diagnosis-2", "bad"),
        ("vision-diagnosis-3", "bad"),
    ],
)
async def test_unsupported_stored_contract_is_rejected_before_claim_or_any_reservation(
    runtime, version, variant
):
    client, app, public, native, _ = runtime
    ai = app.state.ai
    preview = ai.preview(AnalysisInput())
    payload = preview["preview"]
    payload["schema_version"] = version
    if variant is not None:
        payload["variant"] = variant
    body = encoded(payload)
    digest = hashlib.sha256(body.encode()).hexdigest()
    ai.store.execute(
        "UPDATE ai_requests SET payload=?,digest=? WHERE id=?",
        (body, digest, preview["request_id"]),
    )
    response = await client.post(
        "/api/intelligence", json={"request_id": preview["request_id"], "digest": digest}
    )
    assert response.status_code == 400
    assert not public.calls and not native and not ai.store.rows("SELECT * FROM usage")
    assert (
        ai.store.rows("SELECT status FROM ai_requests WHERE id=?", (preview["request_id"],))[0][
            "status"
        ]
        == "preview"
    )


def test_migration_eleven_preserves_all_32_tables_and_literal_old_request_bytes(tmp_path):
    path = tmp_path / "vision.db"
    with sqlite3.connect(path) as db:
        for v in range(1, 11):
            for sql in MIGRATIONS[v]:
                db.execute(sql)
        db.execute("PRAGMA user_version=10")
        db.execute("INSERT INTO meta VALUES ('owner-old','42')")
        db.execute("INSERT INTO meta VALUES ('run_evidence_bytes','0')")
        db.execute(
            "INSERT INTO analyses VALUES (1,1,'audit',NULL,'mock','mock',?,?)",
            ('{"summary":"Keep prose"}', "{}"),
        )
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        old = {
            name: db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() for name in tables
        }
        assert len(tables) == 32
    for _ in range(2):
        store = Store(path)
        assert store.rows("PRAGMA user_version")[0]["user_version"] == 11
        for table, rows in old.items():
            assert [
                tuple(row) for row in store.db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
            ] == rows
        store.close()


async def test_context_discovers_exact_problem_operation_readonly_by_admission_not_wallclock(
    runtime,
):
    client, app, _, _, barriers = runtime
    key, _, first = await start(runtime)
    await app.state.ai.oneclick.task
    old = first.json()["operation_id"]
    db = app.state.store
    # A skewed wall clock on an older record cannot outrank a later admission.
    db.execute("UPDATE home_investigations SET created=? WHERE id=?", (time.time() + 999999, old))
    barriers.update(entered=asyncio.Event(), release=asyncio.Event())
    _, _, second = await start(runtime)
    assert second.status_code == 202, second.text
    await asyncio.wait_for(barriers["entered"].wait(), 2)
    current = second.json()["operation_id"]
    tables = [
        r["name"]
        for r in db.rows(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    assert len(tables) == 34

    def snapshot():
        return {name: db.rows('SELECT * FROM "' + name + '"') for name in tables}

    before, changes = snapshot(), db.db.total_changes
    for _ in range(2):
        context = (await client.get(f"/api/problems/{key}/investigation-context")).json()
        assert context["operation"]["operation_id"] == current
        assert context["operation"]["in_flight"] is True
        assert not {"scope", "plan", "payload"}.intersection(context["operation"])
        other = (
            await client.get(f"/api/problems/{problem_id('device', 'd1')}/investigation-context")
        ).json()
        assert other["operation"] is None
    assert snapshot() == before and db.db.total_changes == changes
    barriers["release"].set()
    await app.state.ai.oneclick.task
    context = (await client.get(f"/api/problems/{key}/investigation-context")).json()
    assert context["operation"]["operation_id"] == current
    assert context["operation"]["status"] == "completed"
