"""Public fidelity and conservative local scope; synthetic transport and records only."""

import base64
import copy
import json
import time

import httpx
import pytest
from test_ai_pipeline import prompt_of
from test_public_research import PublicMock, device_request, research_reply, researched
from test_public_research import ai as ai

from vision.ai_contract import SendInput
from vision.ai_privacy import DiagnosticAliases
from vision.research import QUOTA_KEY, PublicResearch, ResearchError
from vision.research_sources import (
    CATALOG,
    PUBLIC_TERMS,
    canonical,
    document_excerpts,
    public_text,
    source_hash,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["compact", "diagnostic"])
@pytest.mark.parametrize("integration", sorted(CATALOG))
async def test_public_terms_survive_private_alias_seed_in_both_bodies_retention_and_followup(
    ai, profile, integration
):
    request = device_request(ai).model_copy(
        update={"profile": profile, "diagnostic_consent": profile == "diagnostic"}
    )
    for member in ai.monitor.registry.values():
        member["platform"] = integration
    ai.monitor.registry["light.unrelated_private"] = {"platform": "household_custom_canary"}
    ai.monitor.reliability.refresh(time.time())
    mock = PublicMock()
    mock.extra_text += " household_custom_canary"

    async def public(call):
        response = await mock(call)
        if "manifest.json" in call.url.path:
            value = response.json()
            value["content"] = base64.b64encode(
                json.dumps({"domain": integration, "requirements": []}).encode()
            ).decode()
            return httpx.Response(200, json=value)
        return response

    request, base, _, completed, _ = await researched(ai, request, public)
    assert completed["status"] == "completed"
    local_before = json.loads(
        ai.store.rows("SELECT local_evidence FROM ai_requests WHERE id=?", (base["request_id"],))[
            0
        ]["local_evidence"]
    )
    if profile == "diagnostic":
        assert any(
            item["local_reference"] == integration for item in local_before["aliases"].values()
        )
    snapshot = completed["snapshot"]
    public_doc = snapshot["sources"][0]
    text = canonical(public_doc["excerpts"])
    for term in PUBLIC_TERMS | {"platform: zha"}:
        assert term in text, (term, text)
    for private in (
        "light.private_healthy",
        "private-device-canary",
        "household_custom_canary",
        "public-secret-canary",
    ):
        assert private not in text
    assert source_hash(public_doc) == public_doc["content_sha256"]
    value = ai.preview(
        request.model_copy(
            update={
                "research_id": completed["research_id"],
                "research_digest": completed["research_digest"],
            }
        )
    )
    expected = value["preview"]["research"]
    for entry in value["preview"]["requests"].values():
        assert prompt_of(entry["body_utf8"])["research"] == expected
    ai.providers["anthropic"].replies.append(research_reply(value["preview"]))
    received = await ai.send(SendInput(request_id=value["request_id"], digest=value["digest"]))
    retained = json.loads(
        ai.store.rows("SELECT evidence FROM analyses WHERE id=?", (received["id"],))[0]["evidence"]
    )
    assert retained["research"] == expected
    next_round = ai.preview(
        request.model_copy(update={"conversation_id": value["conversation_id"]})
    )
    actual = next_round["preview"]["research"]
    assert actual["sources"][0]["content_sha256"] == public_doc["content_sha256"]
    assert [
        {k: v for k, v in e.items() if k != "ref"} for e in actual["sources"][0]["excerpts"]
    ] == public_doc["excerpts"]
    assert len(mock.calls) <= 6
    await ai.close()


def test_public_projection_does_not_discover_doc_tokens_or_reintroduce_prior_public_aliases(ai):
    prior = {
        f"[I{i}]": {"local_reference": term, "kinds": ["integration"]}
        for i, term in enumerate(sorted(PUBLIC_TERMS), 1)
    }
    aliases = DiagnosticAliases(
        ai.redactor,
        {
            "known-household": "device",
            "device-zha-household-canary": "device",
            "custom_household_platform": "integration",
        },
        prior,
    )
    original = copy.deepcopy(aliases.mapping)
    text = (
        "zha mqtt esphome zwave_js configuration.yaml mqtt.publish platform: zha "
        "service: mqtt.publish arbitrary.public_token known-household "
        'device-zha-household-canary custom_household_platform {"token":"private-source-secret"}'
    )
    projected = public_text(text, aliases, 3000)
    for term in PUBLIC_TERMS | {"arbitrary.public_token", "platform: zha", "service: mqtt.publish"}:
        assert term in projected
    assert all(
        term not in projected
        for term in (
            "known-household",
            "device-zha-household-canary",
            "custom_household_platform",
            "private-source-secret",
        )
    )
    assert all(aliases.mapping[key] == value for key, value in original.items())
    added = [row["local_reference"] for key, row in aliases.mapping.items() if key not in original]
    assert set(added) == {
        "known-household",
        "device-zha-household-canary",
        "custom_household_platform",
    }


def test_full_void_markup_is_not_depth_and_real_deep_nesting_remains_an_honest_gap():
    voids = (
        "<area><base><br><col><embed><hr><img><input><keygen>"
        "<link><meta><param><source><track><wbr>"
    )
    body = (
        "<title>Public docs</title><main><h2>Availability</h2>"
        + voids * 200
        + "<p>Check power and expected sleep manually before inferring any cause.</p></main>"
    ).encode()
    _, excerpts = document_excerpts(body, "availability")
    assert len(excerpts) == 1 and "expected sleep" in excerpts[0]["text"]
    with pytest.raises(ValueError, match="nesting limit"):
        document_excerpts(("<main>" + "<div>" * 129 + "no conclusion").encode(), "availability")


@pytest.mark.asyncio
async def test_one_unclaimed_plan_reuses_map_and_backoff_is_visible_bounded_and_persistent(ai):
    preview = ai.preview(device_request(ai))
    send = SendInput(request_id=preview["request_id"], digest=preview["digest"])
    first = ai.research.plan(send)
    mapping = ai.research.plans[first["plan_id"]]["identifiers"]
    for _ in range(40):
        assert ai.research.plan(send) == first
    assert (
        len(ai.research.plans) == 1
        and ai.research.plans[first["plan_id"]]["identifiers"] is mapping
    )
    now = time.time()
    ai.research.backoff(
        "api.github.com",
        httpx.Headers({"Retry-After": "999999", "X-RateLimit-Reset": str(int(now + 999999))}),
    )
    until = ai.store.get_meta(QUOTA_KEY)["backoff"]["api.github.com"]
    assert now + 86399 <= until <= time.time() + 86400
    # A new base gets the current host/expiry in its visible frozen plan.
    second = ai.preview(device_request(ai))
    plan = ai.research.plan(SendInput(request_id=second["request_id"], digest=second["digest"]))
    assert {
        "adapter": "public_transport",
        "reason": "upstream_backoff",
        "host": "api.github.com",
        "until": until,
    } in plan["plan"]["gaps"]
    restarted = PublicResearch(ai)
    try:
        assert restarted.active_backoffs() == [{"host": "api.github.com", "until": until}]
        with pytest.raises(ResearchError, match="backoff"):
            restarted.claim_quota("api.github.com", False)
    finally:
        await restarted.close()
    await ai.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["compact", "diagnostic"])
async def test_member_heavy_device_retains_history_and_healthy_peers_in_native_bundle(ai, profile):
    request = device_request(ai).model_copy(
        update={"profile": profile, "diagnostic_consent": profile == "diagnostic"}
    )
    monitor, service = ai.monitor, ai.monitor.reliability
    for index in range(138):
        entity = f"light.aa_{index:03d}"
        monitor.registry[entity] = {"device_id": request.target, "platform": "zha"}
        monitor.observe_state({"entity_id": entity, "state": "unavailable"}, track_device=False)
    for index in range(20):
        device = f"peer-{index:03d}"
        entity = f"light.peer_{index:03d}"
        monitor.devices.append({"id": device})
        monitor.registry[entity] = {"device_id": device, "platform": "zha"}
        monitor.observe_state(
            {"entity_id": entity, "state": "on" if index == 19 else "unavailable"},
            track_device=False,
        )
    now = time.time()
    service.refresh(now)
    for index in range(31):
        monitor.entities["light.private_healthy"]["availability"] = (
            "unavailable" if index % 2 else "available"
        )
        service.refresh(now + index + 1)
    value = ai.preview(request)
    local = json.loads(
        ai.store.rows("SELECT local_evidence FROM ai_requests WHERE id=?", (value["request_id"],))[
            0
        ]["local_evidence"]
    )
    sections = local["snapshot"]["sections"]
    assert (
        len(sections["target"]) - 1 == 32
        and sections["coverage"][0]["device_members_omitted"] == 108
    )
    assert len(sections["availability"]) == 20 and len(sections["siblings"]) == 16
    for entry in value["preview"]["requests"].values():
        rows = list(prompt_of(entry["body_utf8"])["bundle"]["evidence"].values())
        history = [r for r in rows if r["section"] == "availability"]
        peers = [r["value"] for r in rows if r["section"] == "siblings"]
        targets = [r["value"] for r in rows if r["section"] == "target"]
        assert len(history) == 20 and len(peers) == 16
        assert {p["availability"] for p in peers} >= {"online", "offline"}
        assert any(t.get("type") == "registered_device" for t in targets)
        assert {t.get("availability") for t in targets if t.get("role") == "primary"} >= {
            "available",
            "unavailable",
        }
        assert any(r["section"] == "coverage" for r in rows)
    await ai.close()


@pytest.mark.asyncio
async def test_deep_document_is_explicit_gap_and_final_comment_count_matches_retained_sources(
    ai, monkeypatch
):
    mock = PublicMock()

    async def deep(call):
        if call.url.host == "www.home-assistant.io":
            return httpx.Response(200, text="<main>" + "<div>" * 129 + "deep source")
        return await mock(call)

    _, _, _, result, _ = await researched(ai, mock=deep)
    assert result["status"] == "completed" and result["source_count"] == 4
    assert any(g["reason"] == "invalid_public_document" for g in result["snapshot"]["gaps"])
    import vision.research as module

    job = ai.research.jobs[result["research_id"]]
    snapshot = copy.deepcopy(job["snapshot"])
    raw = snapshot["sources"]
    snapshot["sources"] = []
    monkeypatch.setattr(module, "MAX_CONTEXT_BYTES", 4300)
    job["identifiers"] = ai.identifiers()
    ai.research.finalize(job, snapshot, raw)
    comments = sum(s["kind"] == "github_comment" for s in snapshot["sources"])
    assert comments < 2 and snapshot["coverage"]["comments_retained"] == comments
    assert snapshot["coverage"]["sources_omitted"] > 0
    await ai.close()
