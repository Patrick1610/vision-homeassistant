import asyncio
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from vision.ai import (
    AIError,
    AnalysisInput,
    HTTPProvider,
    Intelligence,
    ProviderError,
    ProviderResult,
    evidence_bundle,
)
from vision.config import Settings
from vision.monitor import Monitor
from vision.security import Redactor
from vision.store import Store

VALID = {
    "summary": "Limited observations",
    "diagnoses": [
        {
            "finding": "An offline observation warrants checking connectivity",
            "evidence": ["E1"],
            "severity": "warning",
            "confidence": "low",
            "uncertainty": "No cause established",
            "next_step": "Inspect integration diagnostics",
            "validation": "Compare subsequent availability observations",
        }
    ],
}


class FakeProvider:
    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.calls = []

    async def analyze(self, model, key, prompt, max_tokens):
        self.calls.append((model, key, prompt, max_tokens))
        reply = self.replies.pop(0) if self.replies else VALID
        if isinstance(reply, BaseException):
            raise reply
        return ProviderResult(text=json.dumps(reply), input_tokens=100, output_tokens=50)


@pytest.fixture
def intelligence(tmp_path):
    settings = Settings(
        ai_enabled=True,
        anthropic_api_key=SecretStr("provider-secret-a"),
        openai_api_key=SecretStr("provider-secret-b"),
        anthropic_model="test-model",
        openai_model="test-model",
        anthropic_input_usd_per_million=1,
        anthropic_output_usd_per_million=2,
        openai_input_usd_per_million=1,
        openai_output_usd_per_million=2,
    )
    store = Store(tmp_path / "vision.db")
    redactor = Redactor(["private-ha-token", "provider-secret-a", "provider-secret-b"])
    monitor = Monitor(store, settings, SimpleNamespace(token="private-ha-token"), redactor)
    monitor.observe_state(
        {
            "entity_id": "sensor.private_name",
            "state": "unavailable",
            "attributes": {"friendly_name": "A personal name private-ha-token"},
        }
    )
    providers = {"anthropic": FakeProvider(), "openai": FakeProvider()}
    ai = Intelligence(store, settings, monitor, redactor, providers)
    yield ai
    store.close()


async def test_success_costs_and_minimized_data(intelligence):
    ai = intelligence
    result = await ai.analyze(AnalysisInput())
    assert result["provider"] == "anthropic"
    prompt = ai.providers["anthropic"].calls[0][2]
    assert all(
        value not in prompt
        for value in ("private_name", "personal name", "private-ha-token", "provider-secret")
    )
    row = ai.store.rows("SELECT * FROM usage")[0]
    assert row["input_tokens"] == 100 and row["output_tokens"] == 50
    assert row["cost_usd"] == pytest.approx(0.0002)
    assert len(ai.store.rows("SELECT * FROM analyses")) == 1
    await ai.client.aclose()


async def test_disabled_no_provider_calls(intelligence):
    ai = intelligence
    ai.settings.ai_enabled = False
    with pytest.raises(AIError, match="disabled"):
        await ai.analyze(AnalysisInput())
    assert not ai.providers["anthropic"].calls
    assert not ai.store.rows("SELECT * FROM usage")
    await ai.client.aclose()


async def test_technical_failover_and_primary_recovery(intelligence):
    ai = intelligence
    ai.providers["anthropic"].replies = [ProviderError("technical"), VALID]
    assert (await ai.analyze(AnalysisInput()))["provider"] == "openai"
    assert ai.store.rows("SELECT status FROM usage ORDER BY id")[0]["status"] == "uncertain"
    assert (await ai.analyze(AnalysisInput()))["provider"] == "anthropic"
    await ai.client.aclose()


@pytest.mark.parametrize("consent", [False, True])
async def test_local_budget_failover_requires_separate_consent(intelligence, consent):
    ai = intelligence
    ai.settings.anthropic_daily_budget_usd = 0
    ai.settings.allow_budget_failover = consent
    if consent:
        assert (await ai.analyze(AnalysisInput()))["provider"] == "openai"
    else:
        with pytest.raises(AIError, match="budget"):
            await ai.analyze(AnalysisInput())
        assert not ai.providers["openai"].calls
    await ai.client.aclose()


async def test_remote_budget_no_technical_failover(intelligence):
    ai = intelligence
    ai.providers["anthropic"].replies = [ProviderError("budget")]
    with pytest.raises(AIError, match="not authorized"):
        await ai.analyze(AnalysisInput())
    assert not ai.providers["openai"].calls
    await ai.client.aclose()


async def test_rate_limit_retry_backoff(intelligence, monkeypatch):
    ai = intelligence
    delays = []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    ai.providers["anthropic"].replies = [ProviderError("rate_limit", 3), VALID]
    assert (await ai.analyze(AnalysisInput()))["provider"] == "anthropic"
    assert delays == [3]
    assert ai.store.rows("SELECT status,cost_usd FROM usage ORDER BY id")[0] == {
        "status": "rejected",
        "cost_usd": 0,
    }
    await ai.client.aclose()


async def test_invalid_evidence_still_records_billed_usage(intelligence):
    ai = intelligence
    invalid = json.loads(json.dumps(VALID))
    invalid["diagnoses"][0]["evidence"] = ["invented"]
    ai.providers["anthropic"].replies = [invalid]
    with pytest.raises(AIError, match="invalid diagnosis"):
        await ai.analyze(AnalysisInput())
    assert ai.store.rows("SELECT cost_usd FROM usage")[0]["cost_usd"] > 0
    assert not ai.store.rows("SELECT * FROM analyses")
    await ai.client.aclose()


async def test_monthly_limit_includes_uncertain_reservations(intelligence):
    ai = intelligence
    ai.settings.monthly_budget_usd = 0.02
    ai.store.execute(
        "INSERT INTO usage VALUES (NULL,?,'openai','test',NULL,NULL,.02,'uncertain')",
        (time.time(),),
    )
    with pytest.raises(AIError, match="budget"):
        await ai.analyze(AnalysisInput())
    ai.store.prune(7)
    assert ai.store.rows("SELECT * FROM usage")
    await ai.client.aclose()


async def test_unpriced_model_blocked(intelligence):
    ai = intelligence
    ai.settings.anthropic_input_usd_per_million = 0
    with pytest.raises(AIError, match="unpriced_model"):
        await ai.analyze(AnalysisInput())
    assert not ai.providers["anthropic"].calls
    await ai.client.aclose()


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
async def test_http_adapters_contract(provider):
    captured = []

    async def handle(request):
        captured.append(json.loads(request.content))
        if provider == "anthropic":
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": json.dumps(VALID)}],
                    "usage": {"input_tokens": 4, "output_tokens": 5},
                },
            )
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(VALID)}],
                    }
                ],
                "usage": {"input_tokens": 4, "output_tokens": 5},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await HTTPProvider(provider, client).analyze(
            "configured-model", "test-key", "{}", 512
        )
    assert json.loads(result.text) == VALID
    assert result.input_tokens == 4 and result.output_tokens == 5
    assert "tools" not in captured[0]
    if provider == "openai":
        assert captured[0]["store"] is False
        assert captured[0]["text"]["format"]["strict"] is True


async def test_evidence_bound(intelligence):
    ai = intelligence
    for index in range(250):
        ai.monitor.observe_state({"entity_id": f"sensor.e{index}", "state": "unknown"})
    bundle, mapping = evidence_bundle(ai.monitor)
    assert len(bundle["evidence"]) <= 200
    assert set(bundle["evidence"]) == set(mapping)
    assert len(json.dumps(bundle)) < 100000
    await ai.client.aclose()


async def test_anthropic_credit_exhaustion_envelope():
    async def handle(request):
        return httpx.Response(
            400,
            json={
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Your credit balance is too low",
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError) as failure:
            await HTTPProvider("anthropic", client).analyze("model", "key", "{}", 512)
        assert failure.value.category == "budget"


async def test_resolved_incident_still_has_target_evidence(intelligence):
    ai = intelligence
    target = "availability:sensor.private_name"
    ai.store.execute("UPDATE issues SET active=0 WHERE key=?", (target,))
    bundle, mapping = evidence_bundle(ai.monitor, "incident", target)
    assert target in mapping.values()
    refs = [ref for ref, value in mapping.items() if value == target]
    assert any(bundle["evidence"][ref]["type"] == "incident" for ref in refs)
    await ai.client.aclose()


async def test_primary_misconfiguration_is_explicit_and_fail_closed(intelligence):
    ai = intelligence
    ai.settings.anthropic_model = ""
    with pytest.raises(AIError, match="Primary provider"):
        await ai.analyze(AnalysisInput())
    assert not ai.providers["openai"].calls
    # Explicitly selecting the configured provider works without substituting a model.
    ai.settings.primary_provider = "openai"
    assert (await ai.analyze(AnalysisInput()))["provider"] == "openai"
    await ai.client.aclose()


async def test_daily_attempt_survives_scheduler_restart(intelligence, monkeypatch):
    ai = intelligence
    ai.settings.daily_audit = True
    ai.settings.audit_hour_utc = 0
    ai.monitor.connected, ai.monitor.last_sync = True, time.time()

    async def stop_after_cycle(delay):
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", stop_after_cycle)
    for _ in range(2):
        with pytest.raises(asyncio.CancelledError):
            await ai.daily()
    assert len(ai.providers["anthropic"].calls) == 1
    assert ai.store.get_meta("daily_status")["status"] == "completed"
    await ai.client.aclose()


async def test_cancellation_retains_conservative_reservation(intelligence):
    ai = intelligence
    ai.providers["anthropic"].replies = [asyncio.CancelledError()]
    with pytest.raises(asyncio.CancelledError):
        await ai.analyze(AnalysisInput())
    row = ai.store.rows("SELECT * FROM usage")[0]
    assert row["status"] == "uncertain" and row["cost_usd"] > 0
    await ai.client.aclose()
