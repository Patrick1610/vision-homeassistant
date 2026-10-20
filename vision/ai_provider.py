"""Fixed provider endpoints and exact credential-free request serialization."""

import json
import math
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field

from .ai_contract import provider_schema

PROVIDERS = ("anthropic", "openai")
ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/responses",
}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class AIError(Exception):
    pass


class AIConflict(AIError):
    """The reviewed request no longer matches the current investigation state."""


FAILURE_HELP = {
    "request_invalid": (
        "Check the model, request parameters/schema and account spending settings in "
        "the provider console; the cause is unconfirmed."
    ),
    "authentication": "Check the configured provider credential in Supervisor options.",
    "permission": "Check model and workspace permissions in the provider console.",
    "resource_unavailable": (
        "Check the exact configured model and account/workspace access in the provider console."
    ),
    "conflict": "Review provider request availability before creating a new preview.",
    "request_too_large": (
        "Use a smaller retained evidence selection or output limit in a new preview."
    ),
    "rate_limit": "Review provider rate and spending limits; automatic retries remain bounded.",
    "billing": (
        "Check provider credits and account spending limits; budget failover requires "
        "configured consent."
    ),
    "server_error": "Check provider service availability; technical billing may be uncertain.",
    "timeout": "The provider response timed out; billing may be uncertain.",
    "overloaded": "The provider is overloaded; technical billing may be uncertain.",
    "unknown": "Review provider settings and service availability; no remote cause is confirmed.",
}


class ProviderError(AIError):
    def __init__(self, category, retry_after=0, *, http_status=None, reason="unknown"):
        super().__init__(category)
        self.category, self.retry_after = category, retry_after
        self.http_status = (
            http_status if type(http_status) is int and 400 <= http_status <= 599 else None
        )
        self.reason = reason if reason in FAILURE_HELP else "unknown"

    def safe_detail(self):
        status = f"HTTP {self.http_status}; " if self.http_status is not None else ""
        return f"{self.category} ({status}{self.reason}). {FAILURE_HELP[self.reason]}"


class ProviderResult(BaseModel):
    text: str
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)
    termination: Literal["complete", "refusal", "incomplete"] = "complete"


class Provider(Protocol):
    async def send(self, body: str, key: str) -> ProviderResult: ...


def request_body(provider, model, system, prompt, max_tokens, *, evidence_refs=None):
    schema = provider_schema(provider, evidence_refs)
    if provider == "anthropic":
        return encoded(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "output_config": {"format": {"type": "json_schema", "schema": schema}},
            }
        )
    return encoded(
        {
            "model": model,
            "instructions": system,
            "input": prompt,
            "max_output_tokens": max_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "vision_diagnosis",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
    )


class HTTPProvider:
    def __init__(self, name, client):
        if name not in ENDPOINTS:
            raise ValueError("Unknown provider")
        self.name, self.client = name, client

    async def send(self, body, key):
        headers = {"Content-Type": "application/json"}
        if self.name == "anthropic":
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        else:
            headers["Authorization"] = "Bearer " + key
        try:
            async with self.client.stream(
                "POST", ENDPOINTS[self.name], headers=headers, content=body.encode()
            ) as response:
                data = bytearray()
                limit = 8192 if response.status_code >= 400 else 4 * 1024 * 1024
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > limit:
                        raise ProviderError("invalid_response")
                    data.extend(chunk)
                if response.status_code >= 400:
                    self.raise_error(response, data)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise ProviderError(
                "technical",
                reason="timeout" if isinstance(error, httpx.TimeoutException) else "unknown",
            ) from error
        try:
            value = json.loads(data)
            usage = value["usage"]
            if self.name == "anthropic":
                text = "".join(
                    b.get("text", "") for b in value["content"] if b.get("type") == "text"
                )
                termination = {
                    "max_tokens": "incomplete",
                    "model_context_window_exceeded": "incomplete",
                    "refusal": "refusal",
                    "pause_turn": "incomplete",
                }.get(value.get("stop_reason"), "complete")
            else:
                parts = [part for output in value["output"] for part in output.get("content", [])]
                text = "".join(
                    part.get("text", "") for part in parts if part.get("type") == "output_text"
                )
                termination = (
                    "refusal"
                    if any(p.get("type") == "refusal" for p in parts)
                    else (
                        "incomplete"
                        if value.get("status") in {"incomplete", "failed"}
                        else "complete"
                    )
                )
            return ProviderResult(
                text=text,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                termination=termination,
            )
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ProviderError("invalid_response") from error

    def raise_error(self, response, data):
        category = "configuration"
        try:
            envelope = json.loads(data).get("error", {})
            code, error_type = envelope.get("code", ""), envelope.get("type", "")
            code = code if isinstance(code, str) and len(code) <= 100 else ""
            error_type = (
                error_type if isinstance(error_type, str) and len(error_type) <= 100 else ""
            )
            # Recognize only known billing markers; never retain the response message.
            message = envelope.get("message", "")
            message = message.lower() if isinstance(message, str) else ""
        except (ValueError, AttributeError):
            code, error_type, message = "", "", ""
        if response.status_code in {408, 409} or response.status_code >= 500:
            category = "technical"
        if response.status_code in {401, 403}:
            category = "authentication"
        if response.status_code in {402, 429}:
            category = (
                "budget"
                if response.status_code == 402
                or code
                in {
                    "insufficient_quota",
                    "billing_hard_limit_reached",
                    "credits_exhausted",
                }
                else "rate_limit"
            )
        if self.name == "anthropic" and (
            error_type == "billing_error"
            or (
                response.status_code == 400
                and error_type == "invalid_request_error"
                and any(
                    marker in message
                    for marker in ("credit balance is too low", "credit balance too low")
                )
            )
        ):
            category = "budget"
        try:
            retry = float(response.headers.get("retry-after", 0))
            retry = min(max(retry, 0), 30) if math.isfinite(retry) else 0
        except ValueError:
            retry = 0
        # Only closed typed values and numeric status leave this boundary.
        reason = {
            400: "request_invalid",
            401: "authentication",
            402: "billing",
            403: "permission",
            404: "resource_unavailable",
            408: "timeout",
            409: "conflict",
            413: "request_too_large",
            422: "request_invalid",
            429: "rate_limit",
            529: "overloaded",
        }.get(response.status_code, "server_error" if response.status_code >= 500 else "unknown")
        if category == "budget":
            reason = "billing"
        raise ProviderError(category, retry, http_status=response.status_code, reason=reason)
