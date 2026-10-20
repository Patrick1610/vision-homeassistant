"""Provider-contract mocks: no paid requests or credentials."""

import json

import httpx
import pytest

from vision.ai_contract import provider_schema
from vision.ai_provider import HTTPProvider, ProviderError, request_body


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("ending", ["complete", "refusal", "incomplete"])
async def test_exact_native_request_bytes_and_billed_termination(provider, ending):
    captured = []
    body = request_body(
        provider, "configured-model", "Distinct task instruction", '{"evidence":"é"}', 512
    )

    async def handle(request):
        captured.append(request)
        if provider == "anthropic":
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "{}"}],
                    "stop_reason": {
                        "complete": "end_turn",
                        "refusal": "refusal",
                        "incomplete": "max_tokens",
                    }[ending],
                    "usage": {"input_tokens": 11, "output_tokens": 17},
                },
            )
        parts = (
            [{"type": "refusal", "refusal": "No"}]
            if ending == "refusal"
            else [{"type": "output_text", "text": "{}"}]
        )
        return httpx.Response(
            200,
            json={
                "status": "incomplete" if ending == "incomplete" else "completed",
                "output": [{"type": "message", "content": parts}],
                "usage": {"input_tokens": 11, "output_tokens": 17},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await HTTPProvider(provider, client).send(body, "synthetic-header-secret")
    assert captured[0].content == body.encode("utf-8")
    assert "synthetic-header-secret" not in body
    payload = json.loads(captured[0].content)
    assert not any(key in payload for key in ("tools", "tool_choice", "metadata"))
    if provider == "anthropic":
        assert payload["output_config"]["format"] == {
            "type": "json_schema",
            "schema": provider_schema(provider),
        }
        assert captured[0].headers["x-api-key"] == "synthetic-header-secret"
    else:
        assert payload["store"] is False and payload["text"]["format"]["strict"] is True
        assert payload["text"]["format"]["schema"] == provider_schema(provider)
    assert result.termination == ending
    assert (result.input_tokens, result.output_tokens) == (11, 17)


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"usage": {"input_tokens": -1, "output_tokens": 3}, "output": []},
        {"usage": {"input_tokens": "3", "output_tokens": 4}, "output": []},
        {"usage": None, "output": []},
    ],
)
async def test_malformed_or_unknown_billed_response_is_uncertain_not_free_retry(response):
    async def handle(_):
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError, match="invalid_response"):
            await HTTPProvider("openai", client).send("{}", "synthetic")


async def test_oversized_response_and_provider_error_messages_never_escape():
    async def oversized(_):
        return httpx.Response(200, content=b"x" * (4 * 1024 * 1024 + 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(oversized)) as client:
        with pytest.raises(ProviderError, match="invalid_response"):
            await HTTPProvider("openai", client).send("{}", "synthetic")

    async def secret(_):
        return httpx.Response(
            429,
            json={"error": {"code": "insufficient_quota", "message": "synthetic-private-message"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(secret)) as client:
        with pytest.raises(ProviderError) as error:
            await HTTPProvider("openai", client).send("{}", "synthetic")
    assert error.value.category == "budget" and "synthetic-private-message" not in str(error.value)
