"""Corrective contracts; synthetic mocks only, no HA/provider connection."""

import json
import sqlite3

import httpx
import pytest
from pydantic import ValidationError
from test_ai_pipeline import ai as ai
from test_ai_pipeline import consent, diagnosis, mixed, prompt_of

from vision.ai import AIError
from vision.ai_contract import AnalysisInput
from vision.ai_evidence import compact
from vision.ai_privacy import DiagnosticAliases
from vision.ai_provider import HTTPProvider, ProviderError, ProviderResult
from vision.config import Settings
from vision.security import Redactor


async def test_compact_followup_keeps_sanitized_conclusion_without_historical_refs(ai):
    mixed(ai)
    request = AnalysisInput(kind="timeout", target="automation.example", run_id="mixed")
    first = ai.preview(request)
    old_ref = next(iter(first["preview"]["bundle"]["evidence"]))
    result = diagnosis(old_ref)
    result["summary"] = "A wait boundary needs manual inspection."
    result["diagnoses"][0].update(
        finding='Inspect sensor.private_fixture {"token":"unconfigured_secret_canary"}',
        uncertainty="A later successful run may disprove the hypothesis.",
        unknowns=["No physical device observation"],
        next_step="Review the retained wait condition in the HA editor.",
        validation="Inspect a later run; previous reference " + old_ref,
    )
    ai.providers["anthropic"].replies = [result]
    await ai.send(consent(first))
    second = ai.preview(request.model_copy(update={"conversation_id": first["conversation_id"]}))
    for value in second["preview"]["requests"].values():
        prompt = prompt_of(value["body_utf8"])
        answer = prompt["context"]["messages"][1]["content"]
        assert answer["summary"] == result["summary"]
        finding = answer["historical_findings"][0]
        assert finding["uncertainty"] == result["diagnoses"][0]["uncertainty"]
        assert finding["unknowns"] == ["No physical device observation"]
        assert "Review the retained wait" in finding["next_step"]
        assert "evidence" not in finding and "counter_evidence" not in finding
        text = json.dumps(prompt["context"])
        assert old_ref not in text and "sensor.private_fixture" not in text
        assert "unconfigured_secret_canary" not in text
        body = json.loads(value["body_utf8"])
        schema = (body.get("output_config", {}).get("format") or body["text"]["format"])["schema"]
        for field in ("evidence", "counter_evidence"):
            assert set(schema["$defs"]["Finding"]["properties"][field]["items"]["enum"]) == set(
                prompt["bundle"]["evidence"]
            )
    await ai.client.aclose()


@pytest.mark.parametrize(
    "kind",
    [
        "timeout",
        "template_error",
        "device_communication",
        "condition_stop",
        "mode_conflict",
        "optimization",
        "missing_target",
    ],
)
async def test_unsupported_preview_remains_local_before_claim_reserve_or_network(ai, kind):
    ai.monitor.save_trace(
        "automation.example",
        {
            "run_id": "clean",
            "script_execution": "finished",
            "trace": {},
            "config": {"actions": [{"delay": 1}]},
        },
    )
    value = ai.preview(AnalysisInput(kind=kind, target="automation.example", run_id="clean"))
    assert value["preview"]["readiness"]["supported"] is False
    assert value["preview"]["readiness"]["reason"]
    with pytest.raises(AIError, match="needs retained evidence"):
        await ai.send(consent(value))
    assert not ai.store.rows("SELECT * FROM usage")
    assert not ai.store.rows("SELECT * FROM ai_attempts")
    assert ai.store.rows("SELECT status FROM ai_requests")[0]["status"] == "preview"
    assert not any(provider.calls for provider in ai.providers.values())
    await ai.client.aclose()


@pytest.mark.parametrize("ending", ["success", "technical", "refusal", "invalid"])
async def test_revoked_inflight_keeps_withdrawal_and_usage_result(ai, ending):
    preview = ai.preview(AnalysisInput())
    provider = ai.providers["anthropic"]

    async def respond(body, key):
        provider.calls.append((body, key))
        assert ai.revoke(preview["request_id"])["revoked"]
        if ending == "technical":
            raise ProviderError("technical")
        return ProviderResult(
            text=json.dumps(diagnosis(next(iter(prompt_of(body)["bundle"]["evidence"]))))
            if ending != "invalid"
            else "{}",
            input_tokens=100,
            output_tokens=20,
            termination="refusal" if ending == "refusal" else "complete",
        )

    provider.send = respond
    if ending == "success":
        result = await ai.send(consent(preview))
        assert result["id"] is not None
        assert (
            ai.store.rows("SELECT analysis_id FROM ai_requests")[0]["analysis_id"] == result["id"]
        )
    else:
        with pytest.raises(AIError):
            await ai.send(consent(preview))
    assert ai.store.rows("SELECT status FROM ai_requests")[0]["status"] == "revoked"
    usage = ai.store.rows("SELECT * FROM usage")
    assert len(usage) == 1 and usage[0]["cost_usd"] > 0
    assert len(ai.store.rows("SELECT * FROM ai_attempts")) == 1
    assert len(provider.calls) == 1 and not ai.providers["openai"].calls
    await ai.client.aclose()


def test_redacted_dictionary_keys_preserve_every_value_without_leaking_raw_keys():
    aliases = DiagnosticAliases(Redactor())
    result = aliases.clean(
        {
            "https://private.one/a": 1,
            "https://private.two/b": 2,
            "redacted_key_0": 3,
            "sensor.missing_target": 4,
        }
    )
    assert len(result) == 4 and sorted(result.values()) == [1, 2, 3, 4]
    assert "https://" not in json.dumps(result) and "sensor.missing_target" not in json.dumps(
        result
    )
    assert any(
        row["local_reference"] == "sensor.missing_target" for row in aliases.mapping.values()
    )


def test_typed_compact_extra_sections_are_distinct_and_never_pass_raw_fields():
    dep = compact(
        "dependencies",
        {
            "source": "automation.private",
            "target": "entity:sensor.private",
            "relation": "targets",
            "target_present": False,
            "message": "canary",
        },
        0,
    )
    assert dep == {
        "source_kind": "unknown",
        "target_kind": "entity",
        "relation": "targets",
        "source_present": None,
        "target_present": False,
    }
    assert (
        compact(
            "dependencies",
            {"source": "automation:private", "target": "device:private", "relation": "contains"},
            0,
        )["target_kind"]
        == "device"
    )
    assert compact(
        "changes",
        {"kind": "changed", "source": "retained_trace", "observed_at": 20, "message": "canary"},
        0,
    ) == {"kind": "changed", "source": "retained_trace"}
    assert (
        compact("changes", {"kind": "current_baseline", "source": "current_config"}, 0)["kind"]
        == "current_baseline"
    )
    assert compact("siblings", {"availability": "available", "entity_id": "sensor.private"}, 0) == {
        "availability": "available"
    }
    assert compact("siblings", {"availability": "unavailable"}, 0) != compact(
        "siblings", {"availability": "available"}, 0
    )
    assert compact("changes", {"kind": "canary", "source": "canary"}, 0) == {
        "kind": "unknown",
        "source": "unknown",
    }
    assert "canary" not in json.dumps(dep)


def test_reservation_and_attempt_link_are_one_transaction(ai):
    preview = ai.preview(AnalysisInput())
    payload = preview["preview"]
    with pytest.raises(sqlite3.IntegrityError):
        ai.reserve(
            "anthropic",
            "synthetic-a",
            payload["requests"]["anthropic"]["body_utf8"],
            payload["policy"],
            request_id="missing",
            attempt=1,
        )
    assert not ai.store.rows("SELECT * FROM usage")
    reservation = ai.reserve(
        "anthropic",
        "synthetic-a",
        payload["requests"]["anthropic"]["body_utf8"],
        payload["policy"],
        request_id=preview["request_id"],
        attempt=1,
    )
    assert ai.store.rows("SELECT usage_id FROM ai_attempts")[0]["usage_id"] == reservation


@pytest.mark.parametrize("value", [32768, 65536])
def test_expanded_output_limit_preserves_default_and_old_settings(value):
    assert Settings(max_output_tokens=value).max_output_tokens == value
    assert Settings().max_output_tokens == 2048
    assert Settings(max_output_tokens=8192).max_output_tokens == 8192
    with pytest.raises(ValidationError):
        Settings(max_output_tokens=65537)


async def test_context_window_stop_is_billed_incomplete_and_large_response_is_bounded():
    async def handle(_):
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "thinking", "thinking": "not the answer"},
                    {"type": "text", "text": "x" * (1024 * 1024 + 1)},
                ],
                "stop_reason": "model_context_window_exceeded",
                "usage": {"input_tokens": 11, "output_tokens": 17},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await HTTPProvider("anthropic", client).send("{}", "synthetic")
        assert result.termination == "incomplete" and len(result.text) > 1024 * 1024
        assert result.input_tokens == 11 and result.output_tokens == 17

    async def too_large(_):
        return httpx.Response(200, content=b"x" * (4 * 1024 * 1024 + 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(too_large)) as client:
        with pytest.raises(ProviderError, match="invalid_response"):
            await HTTPProvider("openai", client).send("{}", "synthetic")


@pytest.mark.parametrize(
    "status,reason",
    [
        (400, "request_invalid"),
        (401, "authentication"),
        (402, "billing"),
        (403, "permission"),
        (404, "resource_unavailable"),
        (408, "timeout"),
        (409, "conflict"),
        (413, "request_too_large"),
        (429, "rate_limit"),
        (500, "server_error"),
        (529, "overloaded"),
    ],
)
async def test_safe_http_status_and_closed_help_never_leak_remote_content(status, reason):
    async def handle(_):
        return httpx.Response(
            status,
            json={
                "error": {
                    "type": "untrusted_type_canary",
                    "code": "untrusted_code_canary",
                    "message": "private_ha_canary sensor.private_entity",
                }
            },
            headers={"request-id": "private_header_canary"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError) as caught:
            await HTTPProvider("anthropic", client).send("{}", "synthetic")
    assert caught.value.http_status == status and caught.value.reason == reason
    detail = caught.value.safe_detail()
    assert "HTTP " + str(status) in detail and reason in detail
    assert "canary" not in detail and "sensor.private_entity" not in detail


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "not-an-object",
        {"error": None},
        {"error": []},
        {"error": {"code": [], "type": {}, "message": ["canary"]}},
    ],
)
async def test_malformed_error_envelope_and_retry_header_are_safe(value):
    async def handle(_):
        return httpx.Response(429, json=value, headers={"retry-after": "NaN"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError) as caught:
            await HTTPProvider("anthropic", client).send("{}", "synthetic")
    assert caught.value.category == "rate_limit" and caught.value.retry_after == 0
    assert caught.value.reason == "rate_limit" and "canary" not in caught.value.safe_detail()


@pytest.mark.parametrize("tokens", [32768, 65536])
async def test_large_output_limit_exact_preview_and_reservation_use_configured_rates(ai, tokens):
    ai.settings.max_output_tokens = tokens
    value = ai.preview(AnalysisInput())
    payload = value["preview"]
    for request in payload["requests"].values():
        body = json.loads(request["body_utf8"])
        assert body.get("max_tokens", body.get("max_output_tokens")) == tokens
    await ai.send(consent(value))
    sent = ai.providers["anthropic"].calls[0][0]
    assert sent == payload["requests"]["anthropic"]["body_utf8"]
    # The response's billed usage replaces the bound at the same original rates.
    usage = ai.store.rows("SELECT * FROM usage")[0]
    assert usage["input_tokens"] == 100 and usage["output_tokens"] == 50
    assert usage["cost_usd"] == pytest.approx((100 * 1 + 50 * 2) / 1_000_000)
    await ai.client.aclose()
