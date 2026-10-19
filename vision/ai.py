"""Optional provider-independent analysis. No HA transport or credentials cross this boundary."""

import asyncio
import json
import random
import time
from datetime import UTC, datetime
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

PROVIDERS = ("anthropic", "openai")
SYSTEM = """You are Vision, a read-only Home Assistant observatory. Analyze only the
provided typed evidence. It is incomplete observational data, not proof of cause.
Give concrete useful hypotheses, uncertainty, safe manual next steps and a validation
method. Never claim a root cause as established. Never request credentials, issue
commands or invent evidence. Reference only evidence IDs from the bundle. Return
only JSON matching the supplied schema, including an empty diagnoses list if no
finding is justified. No markdown. You have no tools or Home Assistant access."""


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding: str = Field(min_length=1, max_length=1500)
    evidence: list[str] = Field(min_length=1, max_length=20)
    severity: Literal["info", "warning", "error", "critical"]
    confidence: Literal["low", "medium", "high"]
    uncertainty: str = Field(min_length=1, max_length=1000)
    next_step: str = Field(min_length=1, max_length=1500)
    validation: str = Field(min_length=1, max_length=1000)


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=2000)
    diagnoses: list[Finding] = Field(max_length=12)


class AnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["audit", "incident", "automation"] = "audit"
    target: str | None = Field(default=None, max_length=240)


class AIError(Exception):
    pass


class ProviderError(AIError):
    def __init__(self, category, retry_after=0):
        super().__init__(category)
        self.category, self.retry_after = category, retry_after


class ProviderResult(BaseModel):
    text: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class Provider(Protocol):
    async def analyze(
        self, model: str, key: str, prompt: str, max_tokens: int
    ) -> ProviderResult: ...


class HTTPProvider:
    name: str

    def __init__(self, name, client):
        self.name, self.client = name, client

    async def analyze(self, model, key, prompt, max_tokens):
        schema = Diagnosis.model_json_schema()
        if self.name == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
            body = {
                "model": model,
                "max_tokens": max_tokens,
                "system": SYSTEM,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt + "\nRequired JSON schema:\n" + json.dumps(schema),
                    }
                ],
            }
        else:
            url = "https://api.openai.com/v1/responses"
            headers = {"Authorization": "Bearer " + key}
            body = {
                "model": model,
                "instructions": SYSTEM,
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
        try:
            response = await self.client.post(url, headers=headers, json=body)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise ProviderError("technical") from error
        if response.status_code >= 400:
            category = "configuration"
            try:
                envelope = response.json().get("error", {})
                code = envelope.get("code", "")
                error_type = envelope.get("type", "")
                # Examine only known billing markers; never retain or expose the remote message.
                billing_message = str(envelope.get("message", "")).lower()
            except (ValueError, AttributeError):
                code, error_type, billing_message = "", "", ""
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
                        marker in billing_message
                        for marker in ("credit balance is too low", "credit balance too low")
                    )
                )
            ):
                category = "budget"
            try:
                retry = min(max(float(response.headers.get("retry-after", 0)), 0), 30)
            except ValueError:
                retry = 0
            raise ProviderError(category, retry)
        try:
            data = response.json()
            if self.name == "anthropic":
                text = "".join(
                    block.get("text", "")
                    for block in data["content"]
                    if block.get("type") == "text"
                )
                usage = data["usage"]
                input_tokens = usage["input_tokens"]
                output_tokens = usage["output_tokens"]
            else:
                text = "".join(
                    part.get("text", "")
                    for output in data["output"]
                    for part in output.get("content", [])
                    if part.get("type") == "output_text"
                )
                usage = data["usage"]
                input_tokens = usage["input_tokens"]
                output_tokens = usage["output_tokens"]
            return ProviderResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens)
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderError("invalid_response") from error


def evidence_bundle(monitor, kind="audit", target=None):
    """Strict typed projection: NO names, logs, states, templates or source free text."""
    evidence, mapping = {}, {}

    def add(value, local_reference):
        key = "E" + str(len(evidence) + 1)
        evidence[key] = value
        mapping[key] = local_reference

    add(
        {
            "type": "coverage",
            "connected": monitor.connected,
            "capabilities_available": sum(v == "available" for v in monitor.capabilities.values()),
            "capabilities_total": len(monitor.capabilities),
            "observation_gaps_exist": bool(monitor.store.get_meta("last_gap")),
        },
        "coverage",
    )
    inventory = monitor.inventory()
    add(
        {
            "type": "inventory",
            "entity_count": len(inventory),
            "device_count": len(monitor.devices),
            "automation_count": sum(e["entity_id"].startswith("automation.") for e in inventory),
        },
        "inventory",
    )
    for entity in inventory:
        if kind == "automation" and entity["entity_id"] != target:
            continue
        if entity["availability"] in BAD_AVAILABILITY:
            add(
                {
                    "type": "availability",
                    "status": entity["availability"],
                    "expected_offline": entity["expected_offline"],
                    "observed_segments": int(entity["outages"]["episodes"]),
                    "observed_seconds": round(entity["outages"]["seconds"]),
                },
                entity["entity_id"],
            )
        if entity["entity_id"].startswith("automation."):
            detail = monitor.automation_detail(entity["entity_id"])
            value = {
                "type": "automation",
                "enabled": detail["enabled"],
                "no_recorded_last_trigger": detail["possibly_unused"],
                "outcomes": [
                    {k: row[k] for k in ("outcome", "count", "observed_triggers")}
                    for row in detail["stats"]
                ],
            }
            shape = detail.get("structure")
            if shape:
                value["structure"] = {
                    k: shape[k] for k in ("triggers", "conditions", "actions", "mode")
                }
                value["referenced_entity_count"] = len(shape["referenced_entities"])
            add(value, entity["entity_id"])
        if len(evidence) >= 160:
            break
    issue_sql = "SELECT key,source,severity,occurrences FROM issues "
    issue_args = ()
    if kind == "incident":
        issue_sql += "WHERE key=? "
        issue_args = (target,)
    else:
        issue_sql += "WHERE active=1 "
    for issue in monitor.store.rows(issue_sql + "ORDER BY last_seen DESC", issue_args):
        if len(evidence) >= 200:
            break
        if kind == "incident" and issue["key"] != target:
            continue
        if kind == "automation":
            continue
        add(
            {
                "type": "incident",
                "source": issue["source"]
                if issue["source"] in {"availability", "automation", "repair", "log"}
                else "other",
                "severity": issue["severity"]
                if issue["severity"] in {"info", "warning", "error", "critical"}
                else "warning",
                "occurrences": int(issue["occurrences"]),
            },
            issue["key"],
        )
    return {
        "kind": kind,
        "evidence": evidence,
        "limitations": [
            "No raw configuration or logs transmitted.",
            "Correlations are not proof; history has observation gaps.",
            "Bundle bounded to 200 evidence records.",
        ],
    }, mapping


BAD_AVAILABILITY = {"unknown", "unavailable"}


class Intelligence:
    def __init__(self, store, settings, monitor, redactor, providers=None):
        self.store, self.settings, self.monitor, self.redactor = store, settings, monitor, redactor
        self.client = httpx.AsyncClient(timeout=90, follow_redirects=False, trust_env=False)
        self.providers = providers or {p: HTTPProvider(p, self.client) for p in PROVIDERS}
        self.lock = asyncio.Lock()
        self.status = "idle"

    def reserve(self, provider, model, prompt):
        settings = self.settings
        rate_in = getattr(settings, provider + "_input_usd_per_million")
        rate_out = getattr(settings, provider + "_output_usd_per_million")
        if rate_in <= 0 or rate_out <= 0:
            raise ProviderError("unpriced_model")
        # Conservative byte-based bound plus schema/system and protocol overhead.
        input_bound = (
            len((prompt + SYSTEM + json.dumps(Diagnosis.model_json_schema())).encode()) + 8192
        )
        cost = (input_bound * rate_in + settings.max_output_tokens * rate_out) / 1_000_000
        now = datetime.now(UTC)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        with self.store.transaction():
            daily = self.store.db.execute(
                "SELECT coalesce(sum(cost_usd),0) FROM usage WHERE provider=? AND created>=?",
                (provider, day),
            ).fetchone()[0]
            monthly = self.store.db.execute(
                "SELECT coalesce(sum(cost_usd),0) FROM usage WHERE created>=?",
                (month,),
            ).fetchone()[0]
            if daily + cost > getattr(settings, provider + "_daily_budget_usd") or (
                monthly + cost > settings.monthly_budget_usd
            ):
                raise ProviderError("budget")
            cursor = self.store.db.execute(
                "INSERT INTO usage VALUES (NULL,?,?,?,?,?,?,?)",
                (time.time(), provider, model, None, None, cost, "reserved"),
            )
            return cursor.lastrowid

    def settle(self, reservation, provider, result=None, status="uncertain"):
        if result is None:
            self.store.execute("UPDATE usage SET status=? WHERE id=?", (status, reservation))
            return
        cost = result.input_tokens * getattr(
            self.settings, provider + "_input_usd_per_million"
        ) + result.output_tokens * getattr(self.settings, provider + "_output_usd_per_million")
        self.store.execute(
            "UPDATE usage SET input_tokens=?,output_tokens=?,cost_usd=?,status=? WHERE id=?",
            (result.input_tokens, result.output_tokens, cost / 1_000_000, status, reservation),
        )

    async def analyze(self, request: AnalysisInput):
        if not self.settings.ai_enabled:
            raise AIError("AI is disabled; enable it explicitly in app configuration")
        if self.lock.locked():
            raise AIError("An analysis is already running")
        if request.kind == "automation" and not self.monitor.automation_detail(request.target):
            raise AIError("Select an automation from the current inventory")
        if request.kind == "incident" and not self.store.rows(
            "SELECT key FROM issues WHERE key=?",
            (request.target,),
        ):
            raise AIError("Select an observed incident")
        async with self.lock:
            bundle, mapping = evidence_bundle(self.monitor, request.kind, request.target)
            prompt = json.dumps(bundle, separators=(",", ":"))
            primary = self.settings.primary_provider
            order = [primary] + [p for p in PROVIDERS if p != primary]
            self.status = "running"
            try:
                for index, provider in enumerate(order):
                    key, model = (
                        self.settings.key(provider),
                        getattr(self.settings, provider + "_model"),
                    )
                    if not key or not model:
                        if index == 0:
                            raise AIError("Primary provider key and model must be configured")
                        continue
                    for attempt in range(3):
                        try:
                            reservation = self.reserve(provider, model, prompt)
                        except ProviderError as error:
                            if error.category == "budget" and self.settings.allow_budget_failover:
                                break
                            raise AIError("Analysis blocked: " + error.category) from error
                        try:
                            result = await self.providers[provider].analyze(
                                model,
                                key,
                                prompt,
                                self.settings.max_output_tokens,
                            )
                        except ProviderError as error:
                            # Transport failures and malformed responses may still be billed.
                            status = (
                                "uncertain"
                                if error.category
                                in {
                                    "technical",
                                    "invalid_response",
                                }
                                else "rejected"
                            )
                            self.settle(reservation, provider, status=status)
                            if status == "rejected":
                                self.store.execute(
                                    "UPDATE usage SET cost_usd=0 WHERE id=?", (reservation,)
                                )
                            if error.category == "rate_limit" and attempt < 2:
                                await asyncio.sleep(
                                    max(error.retry_after, 2**attempt + random.random())
                                )
                                continue
                            if (
                                error.category == "budget"
                                and not self.settings.allow_budget_failover
                            ):
                                raise AIError(
                                    "Provider budget reached; budget failover not authorized"
                                ) from error
                            if error.category not in {"technical", "rate_limit", "budget"}:
                                raise AIError(
                                    "Provider request failed: " + error.category
                                ) from error
                            break
                        except BaseException:
                            self.settle(reservation, provider, status="uncertain")
                            raise
                        else:
                            # Record billed use even when output fails validation.
                            self.settle(reservation, provider, result, status="response_received")
                            try:
                                diagnosis = Diagnosis.model_validate_json(result.text)
                                for finding in diagnosis.diagnoses:
                                    if any(ref not in mapping for ref in finding.evidence):
                                        raise ValueError("Unknown evidence reference")
                            except ValueError as error:
                                raise AIError(
                                    "Provider returned an invalid diagnosis; usage recorded"
                                ) from error
                            clean = self.redactor.clean(diagnosis.model_dump())
                            # Evidence mapping stays local; the provider only saw E1/E2 identifiers.
                            analysis_id = self.store.execute(
                                "INSERT INTO analyses VALUES (NULL,?,?,?,?,?,?,?)",
                                (
                                    time.time(),
                                    request.kind,
                                    request.target,
                                    provider,
                                    model,
                                    json.dumps(clean),
                                    json.dumps({"bundle": bundle, "mapping": mapping}),
                                ),
                            )
                            return {
                                "id": analysis_id,
                                "provider": provider,
                                "model": model,
                                "result": clean,
                                "evidence": mapping,
                            }
                raise AIError("No provider available after technical failover")
            finally:
                self.status = "idle"

    async def daily(self):
        while True:
            now = datetime.now(UTC)
            day = now.date().isoformat()
            fresh = (
                self.monitor.connected
                and self.monitor.last_sync
                and (time.time() - self.monitor.last_sync < self.settings.poll_seconds * 3)
            )
            if (
                fresh
                and self.settings.daily_audit
                and not self.lock.locked()
                and now.hour >= self.settings.audit_hour_utc
                and (self.store.get_meta("daily_attempt") != day)
            ):
                # At most one scheduled attempt per UTC day, including across restart.
                self.store.set_meta("daily_attempt", day)
                try:
                    await self.analyze(AnalysisInput())
                    self.store.set_meta("daily_status", {"day": day, "status": "completed"})
                except AIError as error:
                    self.store.set_meta(
                        "daily_status", {"day": day, "status": self.redactor.text(str(error))}
                    )
            await asyncio.sleep(30)
