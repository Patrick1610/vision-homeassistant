"""Real bounded HTTP adapters over synthetic public/private facts; no external requests."""

import asyncio
import base64
import copy
import json
import time

import httpx
import pytest
from test_ai_pipeline import ai as ai
from test_ai_pipeline import diagnosis, prompt_of

from vision.ai_contract import AnalysisInput, SendInput, provider_schema
from vision.ai_provider import AIError
from vision.research import QUOTA_KEY, ResearchError, ResearchStart
from vision.research_sources import allowed_request, canonical, source_hash


def device_request(ai):
    monitor = ai.monitor
    monitor.connected = True
    monitor.ha_version, monitor.ha_version_observed_at = "2026.10.2", time.time()
    monitor.devices = [{"id": "private-device-canary"}, {"id": "healthy-peer"}]
    monitor.registry = {
        "light.private_unavailable": {"device_id": "private-device-canary", "platform": "zha"},
        "light.private_healthy": {"device_id": "private-device-canary", "platform": "zha"},
        "light.peer": {"device_id": "healthy-peer", "platform": "zha"},
    }
    for entity, state in (
        ("light.private_unavailable", "unavailable"),
        ("light.private_healthy", "on"),
        ("light.peer", "on"),
    ):
        monitor.observe_state({"entity_id": entity, "state": state}, track_device=False)
    monitor.reliability.refresh(time.time())
    return AnalysisInput(kind="availability", target_type="device", target="private-device-canary")


class PublicMock:
    def __init__(self):
        self.calls, self.count = [], 8
        self.extra_text = (
            "zha mqtt esphome zwave_js configuration.yaml mqtt.publish platform: zha "
            'light.private_healthy private-device-canary {"token":"public-secret-canary"}'
        )

    async def __call__(self, request):
        self.calls.append(request)
        path = request.url.path
        headers = {"Set-Cookie": "private_session=must-not-replay; Path=/", "ETag": '"public-v1"'}
        if request.url.host == "www.home-assistant.io":
            return httpx.Response(
                200,
                text="<html><title>Public integration</title><script>NEVER RETAIN</script>"
                "<main><h2>Troubleshooting</h2><p>Check power and expected sleep before "
                "inferring any network cause. " + self.extra_text + "</p></main></html>",
                headers=headers,
            )
        if "manifest.json" in path:
            return httpx.Response(
                200,
                json={
                    "sha": "a" * 40,
                    "encoding": "base64",
                    "content": base64.b64encode(
                        json.dumps({"domain": "zha", "requirements": ["zha==2.3.1"]}).encode()
                    ).decode(),
                },
                headers=headers,
            )
        if path == "/search/issues":
            repo = "zigpy/zha" if "zigpy/zha" in request.url.params["q"] else "home-assistant/core"
            return httpx.Response(
                200,
                json={
                    "incomplete_results": False,
                    "items": [
                        {"number": 12, "url": f"https://api.github.com/repos/{repo}/issues/12"}
                    ],
                },
                headers=headers,
            )
        if path.endswith("/comments"):
            assert request.url.params == httpx.QueryParams({"per_page": 3, "page": 3})
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 101 + i,
                        "issue_url": "https://api.github.com/repos/zigpy/zha/issues/12",
                        "body": body,
                        "updated_at": "2026-10-20T10:00:00Z",
                    }
                    for i, body in enumerate(
                        [
                            "Check device power and integration availability manually.",
                            "This still fails after a power check; the cause is unconfirmed.",
                            "A third unreviewed response is omitted by the source limit.",
                        ]
                    )
                ],
                headers=headers,
            )
        return httpx.Response(
            200,
            json={
                "number": 12,
                "url": "https://api.github.com/repos/zigpy/zha/issues/12",
                "title": "Public availability issue",
                "body": "Compare integration symptoms and known healthy device counterevidence "
                "before assuming the same cause.",
                "comments": self.count,
                "state": "closed",
                "updated_at": "2026-10-20T10:00:00Z",
            },
            headers=headers,
        )


async def researched(ai, request=None, mock=None):
    request = request or device_request(ai)
    mock = mock or PublicMock()
    await ai.research.client.aclose()
    ai.research.client = httpx.AsyncClient(transport=httpx.MockTransport(mock))
    base = ai.preview(request)
    plan = ai.research.plan(SendInput(request_id=base["request_id"], digest=base["digest"]))
    status = ai.research.start(
        ResearchStart(plan_id=plan["plan_id"], plan_digest=plan["plan_digest"])
    )
    await ai.research.task
    detail = ai.research.status(status["research_id"], detail=True)
    return request, base, plan, detail, mock


@pytest.mark.asyncio
async def test_six_real_http_attempts_current_version_comments_hash_privacy_and_exact_bodies(ai):
    request, base, plan, result, mock = await researched(ai)
    assert result["status"] == "completed", result
    assert result["attempts"] == len(mock.calls) == 6
    snapshot = result["snapshot"]
    assert snapshot["technical_context"]["core_version"] == "2026.10.2"
    assert snapshot["technical_context"]["selected_run_version"] is None
    assert len(snapshot["sources"]) == 5
    assert snapshot["coverage"]["comments_pages"] == 1
    assert snapshot["coverage"]["comments_retained"] == 2
    for call in mock.calls:
        assert call.method == "GET" and "cookie" not in call.headers
        assert (
            not {"authorization", "x-api-key", "proxy-authorization", "referer"}
            & call.headers.keys()
        )
        assert "private" not in str(call.url) and call.headers["accept-encoding"] == "identity"
    encoded = canonical(snapshot)
    assert not any(
        canary in encoded
        for canary in (
            "public-secret-canary",
            "light.private_healthy",
            "private-device-canary",
            "NEVER RETAIN",
        )
    )
    assert all(source_hash(source) == source["content_sha256"] for source in snapshot["sources"])
    selected = ai.monitor.reliability.current[request.target]["state"]
    ai.monitor.observe_state({"entity_id": "light.private_unavailable", "state": "on"})
    attached = ai.preview(
        request.model_copy(
            update={
                "research_id": result["research_id"],
                "research_digest": result["research_digest"],
            }
        )
    )
    assert attached["preview"]["schema_version"] == "vision-diagnosis-3"
    row = ai.store.rows(
        "SELECT local_evidence FROM ai_requests WHERE id=?", (attached["request_id"],)
    )[0]
    frozen = json.loads(row["local_evidence"])
    assert frozen["snapshot"]["sections"]["target"][0]["availability"] == selected == "partial"
    for provider in attached["preview"]["requests"].values():
        prompt = prompt_of(provider["body_utf8"])
        assert prompt["research"] == attached["preview"]["research"]
        assert all(
            source_hash(source) == source["content_sha256"]
            for source in prompt["research"]["sources"]
        )
    assert len(mock.calls) == 6 and not ai.store.rows("SELECT * FROM usage")
    assert len(ai.store.get_meta(QUOTA_KEY)["attempts"]) == 6
    await ai.close()


@pytest.mark.asyncio
async def test_native_v3_manual_plan_is_validated_and_retained_after_request_prune(ai):
    request, _, _, result, mock = await researched(ai)
    preview = ai.preview(
        request.model_copy(
            update={
                "research_id": result["research_id"],
                "research_digest": result["research_digest"],
            }
        )
    )
    payload = preview["preview"]
    local_ref = next(iter(payload["bundle"]["evidence"]))
    source_ref = payload["research"]["sources"][0]["excerpts"][0]["ref"]
    reply = diagnosis(local_ref)
    reply["diagnoses"][0].update(
        source_refs=[source_ref],
        manual_plan={
            "prerequisites": ["Confirm the same integration and applicable version"],
            "steps": [
                {
                    "instruction": "Inspect device power and expected sleep manually",
                    "source_refs": [source_ref],
                },
                {
                    "instruction": "Compare integration status with the retained healthy member",
                    "source_refs": [source_ref],
                },
            ],
        },
    )
    ai.providers["anthropic"].replies.append(reply)
    received = await ai.send(SendInput(request_id=preview["request_id"], digest=preview["digest"]))
    evidence = json.loads(
        ai.store.rows("SELECT evidence FROM analyses WHERE id=?", (received["id"],))[0]["evidence"]
    )
    assert evidence["research"] == payload["research"] and evidence["source_mapping"][source_ref]
    assert len(mock.calls) == 6
    ai.store.execute("UPDATE ai_requests SET created=created-100*86400,expires=0")
    ai.store.prune(90)
    assert not ai.store.rows("SELECT id FROM ai_requests WHERE id=?", (preview["request_id"],))
    assert ai.store.rows("SELECT evidence FROM analyses WHERE id=?", (received["id"],))
    await ai.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, None, True, -1, "8", 1.5])
async def test_comment_count_never_guesses_page_one_and_zero_fetches_no_comments(ai, count):
    mock = PublicMock()
    mock.count = count
    _, _, _, result, _ = await researched(ai, mock=mock)
    assert result["status"] == "completed"
    assert len(mock.calls) == 5 and not any(r.url.path.endswith("/comments") for r in mock.calls)
    if count != 0 or type(count) is not int:
        assert "comment_count_unknown_no_page_fallback" in canonical(result["snapshot"])
    await ai.close()


@pytest.mark.asyncio
async def test_custom_platform_remains_local_and_uses_generic_docs_only(ai):
    request = device_request(ai)
    for row in ai.monitor.registry.values():
        row["platform"] = "custom-private-platform-canary"
    ai.monitor.reliability.refresh(time.time())
    _, _, plan, result, mock = await researched(ai, request)
    assert len(mock.calls) == 1
    assert all("custom-private" not in str(call.url) for call in mock.calls)
    assert plan["plan"]["technical_context"]["integration"] is None
    assert "custom-private-platform-canary" not in canonical(result["snapshot"])
    await ai.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "device_communication"},
        {"run_id": "old"},
        {"compare": "other"},
        {"target": "missing-device"},
    ],
)
async def test_device_scope_is_explicit_and_never_uses_a_representative_entity(ai, changes):
    request = device_request(ai)
    with pytest.raises(AIError):
        ai.preview(request.model_copy(update=changes))
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.close()


@pytest.mark.asyncio
async def test_member_cap_keeps_primary_healthy_and_unavailable_counterevidence(ai):
    from vision.ai_evidence import capture

    request = device_request(ai)
    for index in range(100):
        entity = f"sensor.aaa_diagnostic_{index}"
        ai.monitor.registry[entity] = {
            "device_id": request.target,
            "platform": "zha",
            "entity_category": "diagnostic",
        }
        ai.monitor.observe_state({"entity_id": entity, "state": "unknown"}, track_device=False)
    ai.monitor.reliability.refresh(time.time())
    snapshot = capture(ai.monitor, request)
    members = snapshot["sections"]["target"][1:]
    assert len(members) == 32
    assert any(m["role"] == "primary" and m["availability"] == "available" for m in members)
    assert any(m["role"] == "primary" and m["availability"] == "unavailable" for m in members)
    assert snapshot["sections"]["coverage"][0]["device_members_omitted"] == 70
    assert all(s["relation"] == "same_integration_only" for s in snapshot["sections"]["siblings"])
    await ai.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke", ["base", "job", "off_on"])
async def test_revoke_during_actual_public_http_allows_no_following_dispatch(ai, revoke):
    request = device_request(ai)
    entered, release = asyncio.Event(), asyncio.Event()
    mock = PublicMock()

    async def gated(call):
        reply = await mock(call)
        entered.set()
        await release.wait()
        return reply

    await ai.research.client.aclose()
    ai.research.client = httpx.AsyncClient(transport=httpx.MockTransport(gated))
    base = ai.preview(request)
    plan = ai.research.plan(SendInput(request_id=base["request_id"], digest=base["digest"]))
    start = ResearchStart(plan_id=plan["plan_id"], plan_digest=plan["plan_digest"])
    job = ai.research.start(start)
    await entered.wait()
    with pytest.raises(ResearchError):
        ai.research.start(start)
    if revoke == "base":
        ai.revoke(base["request_id"])
    elif revoke == "job":
        ai.research.revoke(job["research_id"])
    else:
        ai.settings.ai_enabled = False
        ai.settings.ai_enabled = True
    release.set()
    await ai.research.task
    assert ai.research.status(job["research_id"])["status"] == "revoked"
    assert len(mock.calls) == len(ai.store.get_meta(QUOTA_KEY)["attempts"]) == 1
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["full", "malformed", "atomic_failure"])
async def test_persistent_quota_claim_fails_closed_before_any_wire_request(ai, monkeypatch, mode):
    request = device_request(ai)
    mock = PublicMock()
    original = ai.store.set_meta
    record = (
        {"attempts": [time.time()] * 20, "searches": [], "backoff": {}}
        if mode == "full"
        else {"attempts": [True], "searches": [], "backoff": {}}
    )
    ai.store.set_meta(QUOTA_KEY, record)
    if mode == "atomic_failure":
        ai.store.set_meta(QUOTA_KEY, {})
        record = {}

        def fail_claim(key, value):
            if key == QUOTA_KEY:
                raise RuntimeError("Synthetic private database failure")
            return original(key, value)

        monkeypatch.setattr(ai.store, "set_meta", fail_claim)
    _, _, _, result, _ = await researched(ai, request, mock)
    assert not mock.calls and result["attempts"] == 0
    assert ai.store.get_meta(QUOTA_KEY) == record
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.close()


class CountingStream(httpx.AsyncByteStream):
    def __init__(self):
        self.chunks, self.closed = 0, False

    async def __aiter__(self):
        for _ in range(10000):
            self.chunks += 1
            yield b"x" * 16384

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["oversize", "gzip", "redirect", "rate"])
async def test_real_stream_bounds_redirects_and_rate_backoff_never_load_or_follow_more(ai, mode):
    request = device_request(ai)
    for value in ai.monitor.registry.values():
        value["platform"] = "uncataloged"
    ai.monitor.reliability.refresh(time.time())
    stream, calls = CountingStream(), []

    async def handler(call):
        calls.append(call)
        if mode == "redirect":
            return httpx.Response(302, headers={"location": "http://private.invalid/ha-secret"})
        if mode == "rate":
            return httpx.Response(429, headers={"Retry-After": "300"})
        return httpx.Response(
            200, stream=stream, headers={"content-encoding": "gzip"} if mode == "gzip" else {}
        )

    _, _, _, result, _ = await researched(ai, request, handler)
    assert result["status"] == "completed" and len(calls) == 1
    if mode == "oversize":
        assert stream.closed and stream.chunks <= 33
        assert "response_byte_limit" in canonical(result["snapshot"])
    elif mode == "gzip":
        assert stream.closed and stream.chunks == 0
        assert "unsupported_response_encoding" in canonical(result["snapshot"])
    elif mode == "redirect":
        assert "redirect_blocked" in canonical(result["snapshot"])
    else:
        assert ai.store.get_meta(QUOTA_KEY)["backoff"]["www.home-assistant.io"] > time.time() + 290
    await ai.close()


@pytest.mark.asyncio
async def test_cache_hits_do_not_reset_quota_or_mutate_frozen_sources_and_attachment_scope(ai):
    request, _, _, result, mock = await researched(ai)
    frozen = copy.deepcopy(result["snapshot"])
    for change in (
        {"target": "another-device"},
        {"kind": "incident"},
        {"target_type": "entity"},
        {"compare": "other"},
    ):
        with pytest.raises(ResearchError):
            ai.preview(
                request.model_copy(
                    update={
                        **change,
                        "research_id": result["research_id"],
                        "research_digest": result["research_digest"],
                    }
                )
            )
    base = ai.preview(request)
    plan = ai.research.plan(SendInput(request_id=base["request_id"], digest=base["digest"]))
    job = ai.research.start(ResearchStart(plan_id=plan["plan_id"], plan_digest=plan["plan_digest"]))
    await ai.research.task
    cached = ai.research.status(job["research_id"], detail=True)
    assert cached["status"] == "completed" and cached["attempts"] == 0 and len(mock.calls) == 6
    assert len(ai.store.get_meta(QUOTA_KEY)["attempts"]) == 6
    assert ai.research.status(result["research_id"], detail=True)["snapshot"] == frozen
    await ai.close()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.home-assistant.io/private/",
        "http://api.github.com/search/issues",
        "https://api.github.com/repos/evil/private/issues/1",
        "https://api.github.com/repos/zigpy/zha/issues/1/comments?per_page=3&page=1&since=secret",
        "https://api.github.com/search/issues?q=private_household&per_page=2",
        "https://api.github.com:444/repos/zigpy/zha/issues/1",
        "https://user:secret@api.github.com/repos/zigpy/zha/issues/1",
    ],
)
def test_closed_transport_rejects_arbitrary_paths_queries_credentials_and_ports(url):
    assert not allowed_request(url)


def test_current_source_enums_are_isolated_and_no_empty_dummy_source_is_available():
    for provider in ("anthropic", "openai"):
        first = provider_schema(provider, ["Rabc:E1"], source_refs=["Rabc:S1:P1"])
        second = provider_schema(provider, ["Rdef:E1"], source_refs=["Rdef:S1:P1"])
        assert "Rabc:S1:P1" in canonical(first) and "Rabc:S1:P1" not in canonical(second)
        with pytest.raises(ValueError):
            provider_schema(provider, ["Rabc:E1"], source_refs=[])


def research_reply(payload):
    ref = next(iter(payload["bundle"]["evidence"]))
    source = payload["research"]["sources"][0]["excerpts"][0]["ref"]
    result = diagnosis(ref)
    result["diagnoses"][0].update(
        source_refs=[source],
        manual_plan={
            "prerequisites": ["Check source version applicability"],
            "steps": [
                {
                    "instruction": "Inspect power and expected sleep manually",
                    "source_refs": [source],
                },
                {
                    "instruction": "Compare later covered availability observations",
                    "source_refs": [source],
                },
            ],
        },
    )
    return result


@pytest.mark.asyncio
async def test_both_native_provider_bytes_failover_and_frozen_followup_sources(ai):
    from vision.ai_provider import HTTPProvider

    request, _, _, result, public = await researched(ai)
    preview = ai.preview(
        request.model_copy(
            update={
                "research_id": result["research_id"],
                "research_digest": result["research_digest"],
            }
        )
    )
    calls = []
    fail_primary = True

    async def provider(call):
        calls.append(call)
        payload = prompt_of(call.content)
        if call.url.host == "api.anthropic.com" and fail_primary:
            return httpx.Response(503, json={"error": {"type": "api_error"}})
        answer = research_reply(payload)
        if call.url.host == "api.anthropic.com":
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": json.dumps(answer)}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            )
        return httpx.Response(
            200,
            json={
                "output": [{"content": [{"type": "output_text", "text": json.dumps(answer)}]}],
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        ai.providers = {name: HTTPProvider(name, client) for name in ("anthropic", "openai")}
        received = await ai.send(
            SendInput(request_id=preview["request_id"], digest=preview["digest"])
        )
        assert received["provider"] == "openai" and len(calls) == 2
        for call, name in zip(calls, ("anthropic", "openai"), strict=True):
            assert call.content == preview["preview"]["requests"][name]["body_utf8"].encode()
        assert [r["status"] for r in ai.store.rows("SELECT status FROM usage ORDER BY id")] == [
            "uncertain",
            "response_received",
        ]
        fail_primary = False
        before = copy.deepcopy(preview["preview"]["research"])
        followup = ai.preview(
            request.model_copy(
                update={
                    "conversation_id": preview["conversation_id"],
                    "followup_focus": "validation",
                }
            )
        )
        after = followup["preview"]["research"]
        assert [s["content_sha256"] for s in after["sources"]] == [
            s["content_sha256"] for s in before["sources"]
        ]
        assert (
            after["sources"][0]["excerpts"][0]["ref"] != before["sources"][0]["excerpts"][0]["ref"]
        )
        context = json.dumps(followup["preview"]["context"])
        assert before["sources"][0]["excerpts"][0]["ref"] not in context
        second = await ai.send(
            SendInput(request_id=followup["request_id"], digest=followup["digest"])
        )
        assert second["provider"] == "anthropic" and len(public.calls) == 6
        assert (
            calls[-1].content == followup["preview"]["requests"]["anthropic"]["body_utf8"].encode()
        )
    await ai.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid", ["old_source", "unlisted_step", "one_step", "missing_local_evidence"]
)
async def test_billed_invalid_source_or_manual_plan_never_becomes_a_retained_analysis(ai, invalid):
    request, _, _, result, _ = await researched(ai)
    value = ai.preview(
        request.model_copy(
            update={
                "research_id": result["research_id"],
                "research_digest": result["research_digest"],
            }
        )
    )
    reply = research_reply(value["preview"])
    finding = reply["diagnoses"][0]
    if invalid == "old_source":
        finding["source_refs"] = ["Rold:S1:P1"]
    elif invalid == "unlisted_step":
        finding["manual_plan"]["steps"][0]["source_refs"] = [
            value["preview"]["research"]["sources"][1]["excerpts"][0]["ref"]
        ]
    elif invalid == "one_step":
        finding["manual_plan"]["steps"] = finding["manual_plan"]["steps"][:1]
    else:
        finding["evidence"] = []
    ai.providers["anthropic"].replies.append(reply)
    with pytest.raises(AIError):
        await ai.send(SendInput(request_id=value["request_id"], digest=value["digest"]))
    assert not ai.store.rows("SELECT id FROM analyses")
    assert ai.store.rows("SELECT status,input_tokens,output_tokens FROM usage") == [
        {"status": "invalid_diagnosis", "input_tokens": 100, "output_tokens": 50}
    ]
    await ai.close()


@pytest.mark.asyncio
async def test_conditional_cache_304_counts_attempt_preserves_content_and_restart_quota(
    ai, monkeypatch
):
    request, _, _, result, mock = await researched(ai)
    original = copy.deepcopy(result["snapshot"]["sources"][0])
    source_url = original["url"]
    cached = ai.research.cache[source_url]
    cached["expires"] = 0
    calls = []

    async def conditional(call):
        calls.append(call)
        assert call.headers["if-none-match"] == '"public-v1"'
        return httpx.Response(304)

    await ai.research.client.aclose()
    ai.research.client = httpx.AsyncClient(transport=httpx.MockTransport(conditional))
    job = ai.research.jobs[result["research_id"]]
    job["attempts"] = 0
    saved = await ai.research.get(job, {"kind": "official_docs", "url": source_url})
    assert saved["response_sha256"] == original["response_sha256"] and len(calls) == 1
    assert len(ai.store.get_meta(QUOTA_KEY)["attempts"]) == 7
    assert ai.research.status(result["research_id"], detail=True)["snapshot"] == result["snapshot"]
    from vision.research import PublicResearch

    restarted = PublicResearch(ai)
    try:
        with pytest.raises(ResearchError, match="quota reached"):
            restarted.claim_quota("api.github.com", True)
        restarted.backoff("api.github.com", httpx.Headers({"Retry-After": "200000"}))
        assert ai.store.get_meta(QUOTA_KEY)["backoff"]["api.github.com"] <= time.time() + 86400
        with pytest.raises(ResearchError, match="backoff"):
            restarted.claim_quota("api.github.com", False)
    finally:
        await restarted.close()
    await ai.close()


@pytest.mark.asyncio
async def test_whole_public_deadline_stops_stream_and_preserves_usable_source_gap(ai, monkeypatch):
    import vision.research as module

    monkeypatch.setattr(module, "MAX_JOB_SECONDS", 0.03)
    mock = PublicMock()

    async def delayed(call):
        if call.url.host == "api.github.com":
            await asyncio.sleep(1)
        return await mock(call)

    request, _, _, result, _ = await researched(ai, mock=delayed)
    assert result["status"] == "completed" and result["error"] == "whole_job_deadline"
    assert result["source_count"] == 1 and len(mock.calls) == 1
    attached = ai.preview(
        request.model_copy(
            update={
                "research_id": result["research_id"],
                "research_digest": result["research_digest"],
            }
        )
    )
    assert attached["preview"]["schema_version"] == "vision-diagnosis-3"
    assert any(g["reason"] == "whole_job_deadline" for g in attached["preview"]["research"]["gaps"])
    await ai.close()


@pytest.mark.asyncio
async def test_malformed_manifest_degrades_one_source_and_never_broadens_version(ai):
    mock = PublicMock()

    async def malformed(call):
        response = await mock(call)
        if "manifest.json" in call.url.path:
            value = response.json()
            value["content"] = base64.b64encode(b'{"domain":"zha","requirements":null}').decode()
            return httpx.Response(200, json=value)
        return response

    _, _, _, result, _ = await researched(ai, mock=malformed)
    assert result["status"] == "completed" and result["source_count"] == 4
    assert any(g["reason"] == "manifest_projection_unavailable" for g in result["snapshot"]["gaps"])
    await ai.close()


def test_device_history_duration_intersects_retained_coverage_not_interval_span(ai, monkeypatch):
    from vision.ai_devices import capture_device
    from vision.ai_evidence import compact

    request = device_request(ai)
    service = ai.monitor.reliability
    original = service.device

    def with_history(device):
        detail = original(device)
        detail["history"] = [{"state": "partial", "started": 100, "ended": 200}]
        detail["coverage_gaps"] = [{"started": 110, "ended": 190}]
        return detail

    monkeypatch.setattr(service, "device", with_history)
    service.coverage = [(100, 110), (190, 200)]
    service.cache_as_of = 200
    service.intervals_limited = False
    evidence = capture_device(ai.monitor, request)["sections"]["availability"][0]
    assert evidence["observed_seconds"] == 20 and evidence["uncertain"]
    assert compact("availability", evidence, 1000)["observed_seconds"] == 20
    service.intervals_limited = True
    limited = capture_device(ai.monitor, request)["sections"]["availability"][0]
    assert compact("availability", limited, 1000)["observed_seconds"] is None


@pytest.mark.asyncio
async def test_ordinary_public_failure_is_cached_five_minutes_without_a_second_dispatch(ai):
    request = device_request(ai)
    for value in ai.monitor.registry.values():
        value["platform"] = "private-unknown"
    ai.monitor.reliability.refresh(time.time())
    calls = []

    async def failed(call):
        calls.append(call)
        return httpx.Response(500)

    _, _, _, result, _ = await researched(ai, request=request, mock=failed)
    assert result["status"] == "completed" and result["source_count"] == 0
    first = len(ai.store.get_meta(QUOTA_KEY)["attempts"])
    await researched(ai, request=request, mock=failed)
    assert len(calls) == first == len(ai.store.get_meta(QUOTA_KEY)["attempts"]) == 1
    await ai.close()
