"""Durable, bounded intent around existing frozen research/provider execution."""

import asyncio
import hashlib
import json
import re
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ai_contract import AnalysisInput, SendInput
from .ai_provider import AIConflict, AIError, encoded
from .research import ResearchAttach, ResearchStart

VERSION = "vision-oneclick-compact-1"
ACTIVE = ("admitted", "preparing", "researching", "freezing", "sending")
MAX_OPERATIONS = 1000
MAX_SECONDS = 960
SLOT_SECONDS = 900
HIGHWATER = "oneclick-slothighwater"
ID = re.compile(r"^op1_(0|[1-9][0-9]{0,12})_([a-f0-9]{32})$")


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["vision-oneclick-compact-1"]
    enabled: bool = Field(strict=True)


class StartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str = Field(pattern=r"^op1_(0|[1-9][0-9]{0,12})_[a-f0-9]{32}$")
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    language: Literal["nl", "en"]


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class OneClick:
    def __init__(self, ai):
        self.ai, self.store = ai, ai.store
        self.task = None
        self.active_id = None
        # Restart is a status transition, never a new capture/research/dispatch.
        with self.store.transaction():
            self.store.execute(
                "UPDATE home_investigations SET status=CASE WHEN status='revoked' THEN status "
                "WHEN EXISTS "
                "(SELECT 1 FROM ai_attempts a WHERE a.request_id=final_request_id) "
                "THEN 'uncertain' ELSE 'interrupted' END,error='process_restarted',"
                "in_flight=0,updated=? "
                "WHERE in_flight=1 OR status IN "
                "('admitted','preparing','researching','freezing','sending')",
                (time.time(),),
            )

    def consent(self):
        rows = self.store.rows("SELECT * FROM home_ai_consent WHERE id=1")
        row = rows[0] if rows else {"enabled": 0, "generation": 0, "version": VERSION}
        return {
            "version": VERSION,
            "enabled": bool(row["enabled"] and row["version"] == VERSION),
            "generation": row["generation"],
            "profile": "compact",
            "policy": "One explicit click authorizes one frozen problem, bounded generic public "
            "GET research and one AI round. Policy-authorized, not an exact-body review. "
            "Technical retries/failover use the existing configured budgets/rates. "
            "Transmitted costs can remain uncertain. Revoke stops later dispatch, "
            "not a request already sent. Diagnostic still requires a fresh manual preview.",
        }

    def set_consent(self, value):
        with self.store.transaction():
            previous = self.consent()
            self.store.execute(
                "INSERT INTO home_ai_consent VALUES (1,?,?,?,?) ON CONFLICT(id) DO UPDATE "
                "SET version=excluded.version,enabled=excluded.enabled,"
                "generation=excluded.generation,updated=excluded.updated",
                (VERSION, int(value.enabled), previous["generation"] + 1, time.time()),
            )
            if not value.enabled:
                for row in self.store.rows(
                    "SELECT id FROM home_investigations WHERE status IN "
                    "('admitted','preparing','researching','freezing','sending')"
                ):
                    self.revoke(row["id"])
        return self.consent()

    def slot(self):
        highwater = self.store.get_meta(HIGHWATER, 0)
        if type(highwater) is not int or highwater < 0:
            raise AIError("One-click clock state is unavailable")
        return max(int(time.time() // SLOT_SECONDS), highwater)

    def scope(self, problem_id):
        try:
            detail = self.ai.monitor.home.dossier(problem_id)
        except LookupError:
            raise AIConflict("Selected problem is no longer retained") from None
        problem = detail["problem"]
        selection = problem["selection"]
        revision = digest(
            {"problem_id": problem_id, "episode": problem["episode"], "selection": selection}
        )
        return detail, revision

    def selection(self, problem_id):
        detail, revision = self.scope(problem_id)
        p = detail["problem"]
        if not detail["current"] or detail["pending"] or p.get("stale"):
            raise AIConflict("Selected problem needs current coherent observations")
        value = p["selection"]
        kind = value["kind"]
        if kind == "device":
            request = AnalysisInput(
                kind="availability", target=value["device_id"], target_type="device"
            )
        elif kind == "device_group":
            request = AnalysisInput(kind="availability", target=problem_id, target_type="group")
        elif kind == "source_case":
            cases = self.store.rows(
                "SELECT first_seen FROM issues WHERE key=?", (value["case_key"],)
            )
            if not cases or cases[0]["first_seen"] != value["case_first_seen"]:
                raise AIConflict("Selected source episode is no longer retained")
            request = AnalysisInput(kind="incident", target=value["case_key"])
        elif kind == "automation_run":
            if not self.store.rows(
                "SELECT 1 FROM runs WHERE entity_id=? AND run_id=?",
                (value["entity_id"], value["run_id"]),
            ):
                raise AIConflict("Selected execution is no longer retained")
            request = AnalysisInput(
                kind="incident", target=value["entity_id"], run_id=value["run_id"]
            )
        else:
            raise AIConflict("Selected problem scope is unsupported")
        return detail, revision, request

    def context(self, problem_id):
        # No capture, preview, pin, highwater update or work occurs in this GET.
        detail, revision = self.scope(problem_id)
        language = self.ai.monitor.home.preferences()["locale"]
        settings = self.ai.settings
        operations = self.store.rows(
            "SELECT id FROM home_investigations WHERE problem_id=? ORDER BY "
            "(in_flight=1 OR status IN ('admitted','preparing','researching',"
            "'freezing','sending')) DESC,rowid DESC LIMIT 1",
            (problem_id,),
        )
        return {
            "problem_id": problem_id,
            "operation": self.status(operations[0]["id"]) if operations else None,
            "episode": detail["problem"]["episode"],
            "revision": revision,
            "selection": detail["problem"]["selection"],
            "selection_current": bool(
                detail["current"] and not detail["pending"] and not detail["problem"].get("stale")
            ),
            "language": language if language in {"nl", "en"} else None,
            "slot": self.slot(),
            "consent": self.consent(),
            "outbound_enabled": settings.ai_enabled and settings.ai_privacy != "local_only",
            "busy": self.busy(),
            "providers": {
                p: {
                    "model": self.ai.redactor.text(getattr(settings, p + "_model")),
                    "configured": bool(settings.key(p)),
                    "input_usd_per_million": getattr(settings, p + "_input_usd_per_million"),
                    "output_usd_per_million": getattr(settings, p + "_output_usd_per_million"),
                    "daily_budget_usd": getattr(settings, p + "_daily_budget_usd"),
                }
                for p in ("anthropic", "openai")
            },
            "monthly_budget_usd": settings.monthly_budget_usd,
            "allow_budget_failover": settings.allow_budget_failover,
            "limits": {
                "operations": MAX_OPERATIONS,
                "retention_days": 90,
                "operation_metadata_bytes": 32768,
                "total_seconds": MAX_SECONDS,
                "public_gets": 6,
                "public_seconds": 30,
                "provider_seconds": 900,
            },
        }

    def busy(self, owner=None):
        rows = self.store.rows(
            "SELECT id FROM home_investigations WHERE in_flight=1 OR status IN "
            "('admitted','preparing','researching','freezing','sending') LIMIT 1"
        )
        return bool(rows and rows[0]["id"] != owner) or bool(
            self.task and not self.task.done() and self.active_id != owner
        )

    def check(self, operation_id):
        rows = self.store.rows(
            "SELECT status,consent_generation,config_binding FROM home_investigations WHERE id=?",
            (operation_id,),
        )
        consent = self.consent()
        if not rows or rows[0]["status"] not in ACTIVE:
            raise AIError("One-click investigation withdrawn or interrupted")
        if (
            not consent["enabled"]
            or consent["generation"] != rows[0]["consent_generation"]
            or rows[0]["config_binding"] != self.ai.configuration()
            or not self.ai.settings.ai_enabled
            or self.ai.settings.ai_privacy == "local_only"
        ):
            raise AIError("One-click authorization changed; no further dispatch is allowed")
        return rows[0]

    def prune(self):
        with self.store.transaction():
            slot = self.slot()
            self.store.set_meta(HIGHWATER, slot)
            self.store.execute(
                "DELETE FROM home_investigations WHERE status NOT IN "
                "('admitted','preparing','researching','freezing','sending') "
                "AND in_flight=0 AND created<? AND start_slot<?",
                (time.time() - 90 * 86400, slot - 1),
            )

    def start(self, problem_id, value):
        binding = digest(
            {"problem_id": problem_id, "revision": value.revision, "language": value.language}
        )
        with self.store.transaction():
            old = self.store.rows(
                "SELECT input_digest FROM home_investigations WHERE id=?", (value.operation_id,)
            )
            if old:
                if old[0]["input_digest"] != binding:
                    raise AIConflict(
                        "Operation identifier is bound to a different selection/language"
                    )
                return self.status(value.operation_id)
            slot = self.slot()
            given = int(ID.fullmatch(value.operation_id)[1])
            if given not in {slot, slot - 1}:
                raise ExpiredOperation(
                    "Operation start window expired; choose a new explicit action"
                )
            detail, revision, request = self.selection(problem_id)
            if revision != value.revision:
                raise AIConflict("Selected problem revision changed; inspect it before starting")
            language = self.ai.monitor.home.preferences()["locale"]
            if language in {"nl", "en"} and language != value.language:
                raise AIConflict("Saved language changed; reopen the selected problem")
            consent = self.consent()
            if (
                not consent["enabled"]
                or not self.ai.settings.ai_enabled
                or self.ai.settings.ai_privacy == "local_only"
            ):
                raise AIError("Enable the separate compact one-click authorization first")
            if (
                self.busy()
                or self.ai.lock.locked()
                or self.store.rows("SELECT 1 FROM ai_requests WHERE status='sending' LIMIT 1")
                or self.ai.job_task
                and not self.ai.job_task.done()
                or self.ai.research.task
                and not self.ai.research.task.done()
            ):
                raise AIConflict("An investigation is already running; inspect its status")
            self.prune()
            if (
                self.store.rows("SELECT count(*) n FROM home_investigations")[0]["n"]
                >= MAX_OPERATIONS
            ):
                raise AIError("Local investigation capacity reached; history is retained")
            scope = encoded(
                {
                    "selection": detail["problem"]["selection"],
                    "input": request.model_dump(exclude_defaults=True),
                }
            )
            if len(scope.encode()) > 8192:
                raise AIError("Selected investigation scope exceeds its bound")
            now = time.time()
            self.store.set_meta(HIGHWATER, slot)
            self.store.execute(
                "INSERT INTO home_investigations(id,problem_id,episode,revision,language,"
                "input_digest,config_binding,consent_generation,start_slot,created,updated,"
                "status,in_flight,scope) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,'admitted',1,?)",
                (
                    value.operation_id,
                    problem_id,
                    detail["problem"]["episode"],
                    revision,
                    value.language,
                    binding,
                    self.ai.configuration(),
                    consent["generation"],
                    given,
                    now,
                    now,
                    scope,
                ),
            )
        self.active_id = value.operation_id
        self.task = asyncio.create_task(self.run(value.operation_id))
        return self.status(value.operation_id)

    def update(self, operation_id, **values):
        values["updated"] = time.time()
        self.store.execute(
            "UPDATE home_investigations SET "
            + ",".join(key + "=?" for key in values)
            + " WHERE id=?",
            (*values.values(), operation_id),
        )

    def status(self, operation_id, *, audit=False):
        rows = self.store.rows(
            "SELECT id operation_id,problem_id,episode,revision,language,"
            "created,updated,status,error,base_request_id,final_request_id,"
            "analysis_id FROM home_investigations WHERE id=?",
            (operation_id,),
        )
        if not rows:
            raise LookupError("Investigation is not retained")
        result = rows[0]
        result["in_flight"] = self.active_id == operation_id and bool(
            self.task and not self.task.done()
        )
        result["status_url"] = "api/home/investigations/" + operation_id
        if audit:
            row = self.store.rows(
                "SELECT scope,plan FROM home_investigations WHERE id=?", (operation_id,)
            )[0]
            result.update(
                scope=json.loads(row["scope"]),
                plan=json.loads(row["plan"]) if row["plan"] else None,
                authorization_mode="policy-authorized compact one-click",
            )
        return result

    def revoke(self, operation_id):
        self.status(operation_id)
        row = self.store.rows(
            "SELECT final_request_id,base_request_id,research_id FROM "
            "home_investigations WHERE id=?",
            (operation_id,),
        )[0]
        with self.store.transaction():
            self.update(operation_id, status="revoked", error="owner_withdrawn")
            for request_id in {row["final_request_id"], row["base_request_id"]} - {None}:
                self.ai.revoke(request_id)
                self.store.execute(
                    "UPDATE ai_requests SET status='revoked' WHERE id=? AND status='completed'",
                    (request_id,),
                )
                self.store.execute(
                    "UPDATE ai_billing_receipts SET revoked=1 WHERE request_id=?", (request_id,)
                )
        if row["research_id"] in self.ai.research.jobs:
            self.ai.research.revoke(row["research_id"])
        return self.status(operation_id)

    async def run(self, operation_id):
        try:
            async with asyncio.timeout(MAX_SECONDS):
                self.check(operation_id)
                row = self.store.rows(
                    "SELECT * FROM home_investigations WHERE id=?", (operation_id,)
                )[0]
                self.update(operation_id, status="preparing")
                _, revision, selected = self.selection(row["problem_id"])
                if (
                    revision != row["revision"]
                    or selected.model_dump(exclude_defaults=True)
                    != json.loads(row["scope"])["input"]
                ):
                    raise AIConflict("Selected problem changed before the local freeze")
                request = AnalysisInput(
                    **json.loads(row["scope"])["input"],
                    output_contract="human-v4",
                    language=row["language"],
                )
                # Admission and scope are already durable; freeze exactly once.
                preview = self.ai.preview(request)
                self.update(operation_id, base_request_id=preview["request_id"])
                if not preview["preview"]["readiness"]["supported"]:
                    raise AIError("Selected problem lacks supported retained evidence")
                primary = preview["preview"]["policy"]["primary_provider"]
                rates = preview["preview"]["policy"]["providers"].get(primary)
                if (
                    not rates
                    or min(rates["input_usd_per_million"], rates["output_usd_per_million"]) <= 0
                ):
                    raise AIError("Primary provider key, model and positive prices are required")
                self.check(operation_id)
                consent = SendInput(request_id=preview["request_id"], digest=preview["digest"])
                plan = self.ai.research.plan(consent)
                if len(encoded(plan).encode()) > 12288:
                    raise AIError("Public plan exceeds retained metadata bound")
                self.ai.research.plans[plan["plan_id"]]["operation_id"] = operation_id
                self.update(operation_id, status="researching", plan=encoded(plan))
                job = self.ai.research.start(
                    ResearchStart(plan_id=plan["plan_id"], plan_digest=plan["plan_digest"])
                )
                self.update(operation_id, research_id=job["research_id"])
                await self.ai.research.task
                self.check(operation_id)
                research = self.ai.research.status(job["research_id"], detail=True)
                if research["status"] != "completed":
                    raise AIError("Public research did not complete; no AI request was sent")
                self.update(operation_id, status="freezing")
                final_input = self.ai.research.preview_input(
                    job["research_id"], ResearchAttach(research_digest=research["research_digest"])
                )
                final = self.ai.preview(final_input)
                self.update(operation_id, final_request_id=final["request_id"])
                self.check(operation_id)
                # Final request/operation CAS commit together, before reserve/network.
                with self.store.transaction():
                    claimed = self.ai.claim(
                        SendInput(request_id=final["request_id"], digest=final["digest"]),
                        operation_id=operation_id,
                    )
                    self.update(operation_id, status="sending")
                answer = await self.ai.bounded_send(claimed)
                status = self.status(operation_id)["status"]
                self.update(
                    operation_id,
                    status="revoked" if status == "revoked" else "completed",
                    analysis_id=answer["id"],
                )
        except BaseException as error:
            current = self.status(operation_id)
            if current["status"] != "revoked":
                attempts = self.store.rows(
                    "SELECT u.status FROM ai_attempts a JOIN usage u ON u.id=a.usage_id "
                    "WHERE a.request_id=?",
                    (current["final_request_id"],),
                )
                uncertain = any(r["status"] in {"reserved", "uncertain"} for r in attempts)
                state = (
                    "uncertain"
                    if uncertain
                    else ("interrupted" if isinstance(error, asyncio.CancelledError) else "failed")
                )
                self.update(
                    operation_id,
                    status=state,
                    error="deadline_or_interruption"
                    if isinstance(error, (asyncio.CancelledError, TimeoutError))
                    else "investigation_failed",
                )
            if isinstance(error, asyncio.CancelledError):
                raise
        finally:
            row = self.store.rows(
                "SELECT base_request_id,final_request_id FROM home_investigations WHERE id=?",
                (operation_id,),
            )
            if row:
                # Freeze-only bodies remain auditable, but cannot become a second paid round.
                for request_id in {row[0]["base_request_id"], row[0]["final_request_id"]} - {None}:
                    self.store.execute(
                        "UPDATE ai_requests SET status='revoked' WHERE id=? AND status='preview'",
                        (request_id,),
                    )
                self.update(operation_id, in_flight=0)
            self.active_id = None

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


class ExpiredOperation(AIError):
    pass
