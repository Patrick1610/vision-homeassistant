"""Last bounded release guards: punctuation, refreshed plans and committed quota."""

import json
import sqlite3
import time
from contextlib import closing

import httpx
import pytest
from test_ai_pipeline import prompt_of
from test_public_research import PublicMock, device_request, researched
from test_public_research import ai as ai

from vision.ai_contract import SendInput
from vision.ai_privacy import DiagnosticAliases
from vision.research import (
    MAX_CONTEXT_BYTES,
    QUOTA_KEY,
    PublicResearch,
    ResearchError,
    ResearchStart,
)
from vision.research_sources import canonical, public_text, source_hash


@pytest.mark.parametrize("punctuation", [".", ",", ")", "-", "--"])
def test_public_known_id_before_terminal_punctuation_is_removed(ai, punctuation):
    aliases = DiagnosticAliases(ai.redactor, {"light.private_healthy": "entity"})
    result = public_text("Inspect light.private_healthy" + punctuation, aliases, 3000)
    assert result == "Inspect [I1]" + punctuation
    assert "light.private_healthy" not in result


@pytest.mark.parametrize(
    "longer",
    [
        "light.private_healthy_more",
        "light.private_healthy.child",
        "light.private_healthy-more",
        "light.private_healthy--more",
        "prefix.light.private_healthy",
        "prefix-light.private_healthy",
    ],
)
def test_public_id_is_not_replaced_inside_longer_entity_or_domain(ai, longer):
    aliases = DiagnosticAliases(ai.redactor, {"light.private_healthy": "entity"})
    assert public_text(longer, aliases, 3000) == longer
    assert not aliases.mapping


@pytest.mark.asyncio
async def test_unused_plan_changes_only_when_backoff_or_current_auth_basis_changes(ai):
    prepared = ai.preview(device_request(ai))
    send = SendInput(request_id=prepared["request_id"], digest=prepared["digest"])
    first = ai.research.plan(send)
    assert ai.research.plan(send) == first
    ai.research.backoff("api.github.com", httpx.Headers({"Retry-After": "300"}))
    current = ai.research.plan(send)
    assert current["plan_digest"] != first["plan_digest"]
    assert len(ai.research.plans) == 1 and first["plan_id"] not in ai.research.plans
    with pytest.raises(ResearchError, match="digest mismatch"):
        ai.research.start(ResearchStart(plan_id=first["plan_id"], plan_digest=first["plan_digest"]))
    for version, stamp, connected in [
        ("2026.10.2", time.time() + 1, True),
        ("2026.11.0b1", time.time() + 2, True),
        ("2026.11.0b1", time.time() + 2, False),
    ]:
        old = current
        ai.monitor.ha_version, ai.monitor.ha_version_observed_at = version, stamp
        ai.monitor.connected = connected
        current = ai.research.plan(send)
        assert current["plan_digest"] != old["plan_digest"]
        assert current["plan"]["technical_context"]["core_version"] == (
            version if connected else None
        )
        assert current["plan"]["technical_context"]["version_observed_at"] == (
            stamp if connected else None
        )
        assert len(ai.research.plans) == 1 and old["plan_id"] not in ai.research.plans
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.close()


@pytest.mark.asyncio
async def test_far_valid_backoff_commits_once_before_refusal_and_keeps_ledgers_exact(ai):
    preview = ai.preview(device_request(ai))
    await ai.send(SendInput(request_id=preview["request_id"], digest=preview["digest"]))
    tables = ("usage", "ai_attempts", "ai_billing_receipts", "ai_requests")
    before = {table: ai.store.rows("SELECT * FROM " + table) for table in tables}
    now = time.time()
    record = {
        "attempts": [now - 100, now - 50],
        "searches": [now - 10],
        "backoff": {"api.github.com": now + 999999},
    }
    ai.store.set_meta(QUOTA_KEY, record)
    with pytest.raises(ResearchError, match="backoff"):
        ai.research.claim_quota("api.github.com", True)

    def independent_record():
        with closing(sqlite3.connect(ai.store.path.as_uri() + "?mode=ro", uri=True)) as reader:
            return json.loads(
                reader.execute("SELECT value FROM meta WHERE key=?", (QUOTA_KEY,)).fetchone()[0]
            )

    normalized = independent_record()
    assert now + 86399 <= normalized["backoff"]["api.github.com"] <= time.time() + 86400
    assert (
        normalized["attempts"] == record["attempts"]
        and normalized["searches"] == record["searches"]
    )
    restarted = PublicResearch(ai)
    try:
        for _ in range(3):
            with pytest.raises(ResearchError, match="backoff"):
                restarted.claim_quota("api.github.com", True)
            assert independent_record() == normalized
    finally:
        await restarted.close()
    assert {table: ai.store.rows("SELECT * FROM " + table) for table in tables} == before
    await ai.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [True, -1, float("nan"), "tomorrow"])
async def test_backoff_normalization_does_not_admit_malformed_quota(ai, bad):
    record = {"attempts": [], "searches": [], "backoff": {"api.github.com": bad}}
    ai.store.set_meta(QUOTA_KEY, record)
    before = ai.store.rows("SELECT value FROM meta WHERE key=?", (QUOTA_KEY,))
    with pytest.raises(ResearchError, match="quota state unavailable"):
        ai.research.claim_quota("api.github.com", False)
    assert ai.store.rows("SELECT value FROM meta WHERE key=?", (QUOTA_KEY,)) == before
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.close()


@pytest.mark.asyncio
async def test_full_final_sources_plus_two_late_backoff_gaps_fit_both_exact_previews(ai):
    mock = PublicMock()
    text = "Review zha in configuration.yaml and mqtt.publish manually. " * 50

    async def large(call):
        response = await mock(call)
        if call.url.host == "www.home-assistant.io":
            return httpx.Response(
                200,
                text="<main><h2>Availability</h2><p>"
                + text[:1000]
                + "</p><h2>Sleep</h2><p>"
                + text[:1000]
                + "</p></main>",
            )
        if call.url.path.endswith("/comments"):
            comments = response.json()
            for row in comments:
                row["body"] = text[:1500]
            ai.research.backoff("www.home-assistant.io", httpx.Headers({"Retry-After": "999999"}))
            ai.research.backoff("api.github.com", httpx.Headers({"Retry-After": "999999"}))
            return httpx.Response(200, json=comments)
        if "/issues/" in call.url.path and not call.url.path.endswith("/comments"):
            issue = response.json()
            issue["body"] = text[:1500]
            return httpx.Response(200, json=issue)
        return response

    request, _, _, result, _ = await researched(ai, mock=large)
    assert result["status"] == "completed" and result["source_count"] == 5
    snapshot = result["snapshot"]
    assert len(canonical(snapshot).encode()) <= MAX_CONTEXT_BYTES
    assert len([g for g in snapshot["gaps"] if g["reason"] == "upstream_backoff"]) == 2
    attached = ai.preview(
        request.model_copy(
            update={
                "research_id": result["research_id"],
                "research_digest": result["research_digest"],
            }
        )
    )
    for provider in attached["preview"]["requests"].values():
        research = prompt_of(provider["body_utf8"])["research"]
        assert len(canonical(research).encode()) <= MAX_CONTEXT_BYTES
        assert len(research["sources"]) == 5
        assert all(
            source_hash(source) == source["content_sha256"] for source in research["sources"]
        )
    await ai.close()
