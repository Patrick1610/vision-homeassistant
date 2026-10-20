"""Human-started closed public research, independent from provider/HA transports."""

import asyncio
import base64
import copy
import hashlib
import hmac
import json
import math
import re
import time
import uuid
from collections import OrderedDict
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .ai_contract import AnalysisInput, SendInput
from .ai_evidence import is_communication_error
from .ai_privacy import DiagnosticAliases
from .ai_provider import AIError
from .research_sources import (
    CATALOG,
    DOCS,
    TERMS,
    allowed_request,
    canonical,
    core_version,
    digest,
    document_excerpts,
    plain,
    public_text,
    source_hash,
)

MAX_GETS, MAX_SOURCES, MAX_CONTEXT_BYTES = 6, 5, 12288
MAX_RESPONSE_BYTES, MAX_JOB_SECONDS = 524288, 30
MAX_RECORDS, TTL = 32, 1800
MAX_CACHE_ENTRIES, MAX_CACHE_BYTES = 64, 8 * 1048576
QUOTA_KEY = "public_research_quota_v1"
VERSION = "vision-public-research-1"


class ResearchStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    plan_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class ResearchAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    diagnostic_consent: bool = Field(default=False, strict=True)


class ResearchError(AIError):
    def __init__(self, code):
        self.code = code
        # All callers use internal fixed categories, never remote exception text.
        super().__init__("Public research unavailable: " + code.replace("_", " "))


def positive(value):
    return type(value) is int and 0 < value <= 9007199254740991


def safe_time(value, maximum=86400):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= maximum
    )


class PublicResearch:
    def __init__(self, ai, *, client=None):
        self.ai = ai
        self.store = ai.store
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3, read=8, write=3, pool=3),
            follow_redirects=False,
            trust_env=False,
        )
        self.plans, self.jobs, self.cache = {}, {}, OrderedDict()
        self.task, self.active = None, None

    def cleanup(self):
        now = time.time()
        for collection in (self.plans, self.jobs):
            for key, row in list(collection.items()):
                if row["created"] + TTL <= now and key != self.active:
                    del collection[key]

    def base(self, value):
        rows = self.store.rows("SELECT * FROM ai_requests WHERE id=?", (value.request_id,))
        if not rows:
            raise ResearchError("base_not_retained")
        row = rows[0]
        if row["status"] != "preview" or row["round"] != 1 or row["expires"] <= time.time():
            raise ResearchError("base_not_unused_or_expired")
        if not hmac.compare_digest(row["digest"], value.digest):
            raise ResearchError("base_digest_mismatch")
        if row["config_binding"] != self.ai.configuration():
            raise ResearchError("configuration_changed")
        try:
            payload, local = json.loads(row["payload"]), json.loads(row["local_evidence"])
            intact = isinstance(payload, dict) and isinstance(local, dict)
            intact = intact and digest(payload) == row["digest"]
        except (ValueError, TypeError):
            intact = False
        if not intact:
            raise ResearchError("base_integrity_failed")
        if (
            not self.ai.settings.ai_enabled
            or self.ai.settings.ai_privacy == "local_only"
            or row["profile"] == "local_only"
        ):
            raise ResearchError("outbound_disabled")
        if payload.get("research") or payload.get("scheduled") or row["kind"] == "audit":
            raise ResearchError("choose_one_initial_problem")
        if not payload["readiness"]["supported"]:
            raise ResearchError("unsupported_local_prerequisite")
        return row, payload, local

    def plan(self, value: SendInput):
        self.cleanup()
        row, payload, local = self.base(value)
        monitor = self.ai.monitor
        version = core_version(getattr(monitor, "ha_version", None)) if monitor.connected else None
        version_at = getattr(monitor, "ha_version_observed_at", None)
        version_at = version_at if version and safe_time(version_at, time.time() + 60) else None
        backoffs = self.active_backoffs()
        for plan_id, existing in list(self.plans.items()):
            if not existing["claimed"] and existing["base"] == value.model_dump():
                self.valid(existing)
                context = existing["public"]["technical_context"]
                old_backoffs = [
                    {"host": gap["host"], "until": gap["until"]}
                    for gap in existing["public"]["gaps"]
                    if gap["reason"] == "upstream_backoff"
                ]
                if (context["core_version"], context["version_observed_at"], old_backoffs) == (
                    version,
                    version_at,
                    backoffs,
                ):
                    return {
                        "plan_id": plan_id,
                        "plan_digest": existing["digest"],
                        "plan": copy.deepcopy(existing["public"]),
                    }
                del self.plans[plan_id]
        if len(self.plans) >= MAX_RECORDS:
            raise ResearchError("plan_capacity")
        snapshot = local["snapshot"]
        kind = row["kind"]
        sections = snapshot["sections"]
        if kind == "incident":
            errors = sections["errors"]
            kind = (
                "template_error"
                if any(e.get("kind") == "template_error" for e in errors)
                else (
                    "device_communication"
                    if any(is_communication_error(e) for e in errors)
                    else "timeout"
                    if any(s.get("wait_timed_out") or s.get("timeout") for s in sections["steps"])
                    else "incident"
                )
            )
        platforms = set()
        if kind in {"availability", "device_communication"}:
            for target in sections["target"]:
                if (
                    kind == "device_communication"
                    and target.get("role") != "failing_declared_target"
                ):
                    continue
                platforms.update(target.get("platforms", []))
                if target.get("platform"):
                    platforms.add(target["platform"])
        integration = (
            next(iter(platforms)) if len(platforms) == 1 and platforms <= CATALOG.keys() else None
        )
        context = {
            "integration": integration,
            "core_version": version,
            "version_basis": "current_authenticated_server" if version else "unknown",
            "version_observed_at": version_at,
            "selected_run_version": None,
        }
        docs = "/integrations/" + integration + "/" if integration else DOCS[kind]
        requests = [{"kind": "official_docs", "url": "https://www.home-assistant.io" + docs}]
        gaps = [{"adapter": "reddit", "reason": "authentication_required"}]
        gaps.extend(
            {"adapter": "public_transport", "reason": "upstream_backoff", **entry}
            for entry in backoffs
        )
        if not integration:
            gaps.append(
                {
                    "adapter": "catalog",
                    "reason": "unknown_or_multiple_integrations_generic_docs_only",
                }
            )
        if not version:
            gaps.append({"adapter": "version", "reason": "current_authenticated_version_unknown"})
        if snapshot.get("run_id"):
            gaps.append({"adapter": "version", "reason": "historical_run_version_unknown"})
        if integration and version:
            requests.append(
                {
                    "kind": "core_manifest",
                    "url": "https://api.github.com/repos/home-assistant/core/contents/homeassistant/components/"
                    + integration
                    + "/manifest.json?"
                    + urlencode({"ref": version}),
                }
            )
        repositories = ["home-assistant/core"] + (
            [CATALOG[integration]["upstream"]]
            if integration and CATALOG[integration]["upstream"]
            else []
        )
        if integration:
            for repo in repositories:
                query = f"repo:{repo} is:issue {integration} {TERMS[kind]}"
                requests.append(
                    {
                        "kind": "issue_search",
                        "repo": repo,
                        "url": "https://api.github.com/search/issues?"
                        + urlencode({"q": query, "per_page": 2}),
                    }
                )
        plan_id = uuid.uuid4().hex
        public = {
            "plan_id": plan_id,
            "research_version": VERSION,
            "task": row["kind"],
            "problem_class": kind,
            "technical_context": context,
            "requests": requests,
            "followup": {
                "repositories": repositories if integration else [],
                "issue_selection": "first_valid_upstream_else_core_candidate",
                "issue_detail": "/repos/<catalogrepo>/issues/<positive-found-number>",
                "comments": "one found issue; per_page=3; page=ceil(public comments/3); "
                "invalid count=no GET",
                "comment_sources_max": 2,
                "thread_complete": False,
            },
            "limits": {
                "get_attempts": MAX_GETS,
                "searches": 2,
                "sources": MAX_SOURCES,
                "seconds": MAX_JOB_SECONDS,
                "response_bytes": MAX_RESPONSE_BYTES,
                "public_context_bytes": MAX_CONTEXT_BYTES,
                "gets_per_hour": 20,
                "gets_per_day": 60,
                "searches_per_minute": 2,
            },
            "gaps": gaps,
        }
        plan_digest = digest(public)
        identifiers = self.ai.identifiers()
        if len(canonical(identifiers).encode()) > 2 * 1048576:
            raise ResearchError("private_redaction_map_limit")
        self.plans[plan_id] = {
            "created": time.time(),
            "public": public,
            "digest": plan_digest,
            "base": value.model_dump(),
            "configuration": row["config_binding"],
            "identifiers": identifiers,
            "claimed": False,
        }
        return {"plan_id": plan_id, "plan_digest": plan_digest, "plan": copy.deepcopy(public)}

    def valid(self, row):
        if row.get("revoked") or row["configuration"] != self.ai.configuration():
            raise ResearchError("revoked_or_configuration_changed")
        return self.base(SendInput(**row["base"]))

    def start(self, value: ResearchStart):
        self.cleanup()
        row = self.plans.get(value.plan_id)
        if not row or not hmac.compare_digest(row["digest"], value.plan_digest):
            raise ResearchError("plan_expired_or_digest_mismatch")
        self.valid(row)
        if row["claimed"] or self.task and not self.task.done():
            raise ResearchError("job_already_claimed_or_busy")
        if len(self.jobs) >= MAX_RECORDS:
            raise ResearchError("job_capacity")
        research_id = uuid.uuid4().hex
        job = {
            **row,
            "research_id": research_id,
            "status": "running",
            "phase": "public_reads",
            "attempts": 0,
            "source_count": 0,
            "error": None,
            "snapshot": None,
            "research_digest": None,
        }
        row["claimed"] = True
        row["identifiers"] = {}
        self.jobs[research_id] = job
        self.active = research_id
        self.task = asyncio.create_task(self.run(job))
        return {
            "research_id": research_id,
            "status": "running",
            "status_url": "api/intelligence/research/" + research_id + "/status",
        }

    def status(self, research_id, *, detail=False):
        self.cleanup()
        job = self.jobs.get(research_id)
        if not job:
            raise ResearchError("job_not_retained")
        result = {
            key: job[key]
            for key in (
                "research_id",
                "status",
                "phase",
                "attempts",
                "source_count",
                "error",
                "created",
            )
        }
        if detail:
            result.update(
                snapshot=copy.deepcopy(job["snapshot"]), research_digest=job["research_digest"]
            )
        return result

    def revoke(self, research_id):
        job = self.jobs.get(research_id)
        if not job:
            raise ResearchError("job_not_retained")
        job["revoked"], job["status"] = True, "revoked"
        return {"research_id": research_id, "revoked": True}

    def claim_quota(self, host, search):
        now = time.time()
        refusal = None
        with self.store.transaction():
            record = self.store.get_meta(QUOTA_KEY, {})
            if not isinstance(record, dict) or any(
                not isinstance(record.get(k, []), list)
                or len(record.get(k, [])) > 60
                or any(not safe_time(t, now + 86400) for t in record.get(k, []))
                for k in ("attempts", "searches")
            ):
                raise ResearchError("quota_state_unavailable")
            attempts = [t for t in record.get("attempts", []) if t > now - 86400]
            searches = [t for t in record.get("searches", []) if t > now - 60]
            backoff = record.get("backoff", {})
            if not isinstance(backoff, dict) or any(
                host_key not in {"www.home-assistant.io", "api.github.com"}
                or not safe_time(until, math.inf)
                for host_key, until in backoff.items()
            ):
                raise ResearchError("quota_state_unavailable")
            normalized = {key: min(until, now + 86400) for key, until in backoff.items()}
            if normalized != backoff:
                # Commit only the valid deadline correction, even when this claim is
                # refused. Preserve the existing attempt/search ledger byte-for-byte.
                self.store.set_meta(QUOTA_KEY, {**record, "backoff": normalized})
            backoff = normalized
            if backoff.get(host, 0) > now:
                refusal = "upstream_backoff"
            elif (
                len(attempts) >= 60
                or sum(t > now - 3600 for t in attempts) >= 20
                or search
                and len(searches) >= 2
            ):
                refusal = "public_quota_reached"
            else:
                self.store.set_meta(
                    QUOTA_KEY,
                    {
                        "attempts": [*attempts, now],
                        "searches": [*searches, now] if search else searches,
                        "backoff": backoff,
                    },
                )
        if refusal:
            raise ResearchError(refusal)

    def backoff(self, host, headers):
        now, wait = time.time(), 60.0
        value = headers.get("retry-after", "")
        try:
            parsed = (
                float(value)
                if re.fullmatch(r"[0-9]{1,6}", value)
                else parsedate_to_datetime(value).timestamp() - now
            )
            if safe_time(parsed, 999999):
                wait = max(wait, min(86400, parsed))
        except (ValueError, TypeError, OverflowError):
            pass
        reset = headers.get("x-ratelimit-reset", "")
        if re.fullmatch(r"[0-9]{1,12}", reset):
            wait = max(wait, min(86400, max(0, int(reset) - now)))
        with self.store.transaction():
            record = self.store.get_meta(QUOTA_KEY, {})
            record.setdefault("backoff", {})[host] = now + wait
            self.store.set_meta(QUOTA_KEY, record)

    def active_backoffs(self):
        record = self.store.get_meta(QUOTA_KEY, {})
        values = record.get("backoff", {}) if isinstance(record, dict) else {}
        if not isinstance(values, dict):
            return []
        now = time.time()
        return [
            {"host": host, "until": until}
            for host, until in sorted(values.items())
            if host in {"www.home-assistant.io", "api.github.com"}
            and safe_time(until, now + 86401)
            and until > now
        ]

    def cache_failure(self, url, code):
        self.cache[url] = {"error": code, "body": b"", "expires": time.time() + 300}
        self.cache.move_to_end(url)
        while len(self.cache) > MAX_CACHE_ENTRIES:
            self.cache.popitem(last=False)

    async def get(self, job, request):
        self.valid(job)
        url = request["url"]
        parsed = httpx.URL(url)
        if not allowed_request(url):
            raise ResearchError("closed_transport_policy")
        # Only server-created initial/follow-up requests can call this method.
        cached = self.cache.get(url)
        now = time.time()
        if cached and cached["expires"] > now:
            self.cache.move_to_end(url)
            if cached.get("error"):
                raise ResearchError(cached["error"])
            return {**cached, "cache_hit": True}
        if job["attempts"] >= MAX_GETS:
            raise ResearchError("job_read_limit")
        headers = {
            "User-Agent": "Vision-Public-Research/0.2.1",
            "Accept-Encoding": "identity",
            "Connection": "close",
            "Accept": "application/vnd.github+json"
            if parsed.host == "api.github.com"
            else "text/html",
        }
        if parsed.host == "api.github.com":
            headers["X-GitHub-Api-Version"] = "2026-03-10"
        if cached and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        self.claim_quota(parsed.host, request["kind"] == "issue_search")
        job["attempts"] += 1
        # A standalone Request bypasses client cookies/default headers/auth entirely.
        response = None
        try:
            response = await self.client.send(
                httpx.Request("GET", url, headers=headers),
                auth=None,
                stream=True,
                follow_redirects=False,
            )
            if response.status_code in {403, 429}:
                self.backoff(parsed.host, response.headers)
                raise ResearchError("upstream_rate_limited")
            if response.status_code == 304 and cached and not cached.get("error"):
                saved = {
                    **cached,
                    "expires": now + cached["ttl"],
                    "validated_at": now,
                    "cache_hit": True,
                }
                self.cache[url] = saved
                return saved
            if 300 <= response.status_code < 400:
                raise ResearchError("redirect_blocked")
            if response.status_code != 200:
                raise ResearchError(
                    "source_not_found" if response.status_code == 404 else "source_http_failure"
                )
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ResearchError("unsupported_response_encoding")
            body = bytearray()
            async for part in response.aiter_bytes(chunk_size=16384):
                if len(body) + len(part) > MAX_RESPONSE_BYTES:
                    raise ResearchError("response_byte_limit")
                body.extend(part)
            etag = response.headers.get("etag", "")
            etag = (
                etag
                if 0 < len(etag) <= 256 and not any(ord(c) < 32 or ord(c) > 126 for c in etag)
                else None
            )
            ttl = 86400 if request["kind"] in {"official_docs", "core_manifest"} else 1800
            saved = {
                "body": bytes(body),
                "response_sha256": hashlib.sha256(body).hexdigest(),
                "retrieved_at": now,
                "expires": now + ttl,
                "ttl": ttl,
                "etag": etag,
                "cache_hit": False,
            }
            self.cache[url] = saved
            self.cache.move_to_end(url)
            while (
                len(self.cache) > MAX_CACHE_ENTRIES
                or sum(len(v["body"]) for v in self.cache.values()) > MAX_CACHE_BYTES
            ):
                self.cache.popitem(last=False)
            return saved
        except ResearchError as error:
            if error.code != "upstream_rate_limited":
                self.cache_failure(url, error.code)
            raise
        except (httpx.TimeoutException, httpx.TransportError):
            self.cache_failure(url, "public_transport_timeout_or_failure")
            raise ResearchError("public_transport_timeout_or_failure") from None
        finally:
            if response is not None:
                await response.aclose()
            self.client.cookies.clear()

    @staticmethod
    def decoded(response):
        try:
            return json.loads(response["body"])
        except (ValueError, UnicodeError, RecursionError):
            raise ResearchError("invalid_public_json") from None

    @staticmethod
    def source(kind, url, title, response, excerpts, **metadata):
        return {
            "source_key": hashlib.sha256(url.encode()).hexdigest()[:16],
            "kind": kind,
            "url": url,
            "title": plain(title)[:200],
            "retrieved_at": response["retrieved_at"],
            "response_sha256": response["response_sha256"],
            "revision": None,
            "applicability": "unverified",
            "excerpts": excerpts,
            "cache_hit": response["cache_hit"],
            **metadata,
        }

    def finalize(self, job, snapshot, raw_sources):
        _, _, local = self.valid(job)
        aliases = DiagnosticAliases(self.ai.redactor, job["identifiers"], local["aliases"])
        for source in raw_sources:
            candidate = copy.deepcopy(source)
            candidate["title"] = public_text(candidate["title"], aliases, 200)
            for excerpt in candidate["excerpts"]:
                excerpt["heading"] = public_text(excerpt["heading"], aliases, 200)
                excerpt["text"] = public_text(excerpt["text"], aliases, 3000)
            candidate["excerpts"] = [e for e in candidate["excerpts"] if e["text"].strip()]
            while candidate["excerpts"]:
                candidate["content_sha256"] = source_hash(candidate)
                if (
                    len(
                        canonical(
                            {**snapshot, "sources": [*snapshot["sources"], candidate]}
                        ).encode()
                    )
                    <= MAX_CONTEXT_BYTES - 1024
                ):
                    snapshot["sources"].append(candidate)
                    break
                snapshot["coverage"]["excerpts_truncated"] = True
                text = candidate["excerpts"][-1]["text"]
                if len(text) < 300:
                    candidate["excerpts"].pop()
                else:
                    candidate["excerpts"][-1]["text"] = text[:-200].rstrip() + " [excerpt limited]"
            else:
                snapshot["coverage"]["sources_omitted"] += 1
        job["aliases"] = aliases.mapping
        snapshot["coverage"]["comments_retained"] = sum(
            source["kind"] == "github_comment" for source in snapshot["sources"]
        )
        for entry in self.active_backoffs():
            gap = {"adapter": "public_transport", "reason": "upstream_backoff", **entry}
            if gap not in snapshot["gaps"]:
                snapshot["gaps"].append(gap)
        if len(canonical(snapshot).encode()) > MAX_CONTEXT_BYTES:
            raise ResearchError("public_context_byte_limit")
        job["source_count"] = len(snapshot["sources"])
        job["snapshot"], job["research_digest"] = snapshot, digest(snapshot)

    async def run(self, job):
        public = job["public"]
        snapshot = {
            "research_version": VERSION,
            "plan_digest": job["digest"],
            "task": public["task"],
            "technical_context": public["technical_context"],
            "query_plan": public,
            "sources": [],
            "gaps": copy.deepcopy(public["gaps"]),
            "coverage": {
                "queries_incomplete": False,
                "sources_omitted": 0,
                "excerpts_truncated": False,
                "thread_complete": False,
                "comments_pages": 0,
                "comments_returned": 0,
                "comments_retained": 0,
                "issue_candidates_unread": 0,
            },
        }
        raw_sources, candidates = [], []
        try:
            async with asyncio.timeout(MAX_JOB_SECONDS):
                for request in public["requests"]:
                    try:
                        response = await self.get(job, request)
                        kind, url = request["kind"], request["url"]
                        if kind == "official_docs":
                            try:
                                title, excerpts = document_excerpts(
                                    response["body"], public["problem_class"]
                                )
                            except ValueError:
                                raise ResearchError("invalid_public_document") from None
                            if not excerpts:
                                raise ResearchError("no_relevant_document_excerpt")
                            raw_sources.append(self.source(kind, url, title, response, excerpts))
                        elif kind == "core_manifest":
                            value = self.decoded(response)
                            content = value.get("content") if isinstance(value, dict) else None
                            if (
                                not isinstance(value, dict)
                                or value.get("encoding") != "base64"
                                or not isinstance(content, str)
                            ):
                                raise ResearchError("manifest_projection_unavailable")
                            try:
                                manifest = json.loads(
                                    base64.b64decode("".join(content.split()), validate=True)
                                )
                            except (ValueError, TypeError, UnicodeError, RecursionError):
                                raise ResearchError("manifest_projection_unavailable") from None
                            integration = public["technical_context"]["integration"]
                            if (
                                not isinstance(manifest, dict)
                                or manifest.get("domain") != integration
                            ):
                                raise ResearchError("manifest_integration_mismatch")
                            raw_requirements = manifest.get("requirements", [])
                            if not isinstance(raw_requirements, list):
                                raise ResearchError("manifest_projection_unavailable")
                            requirements = [
                                r
                                for r in raw_requirements[:20]
                                if isinstance(r, str)
                                and re.fullmatch(
                                    r"[A-Za-z0-9_.-]{1,100}==[A-Za-z0-9_.+!-]{1,80}", r
                                )
                            ]
                            version = public["technical_context"]["core_version"]
                            revision = value.get("sha")
                            raw_sources.append(
                                self.source(
                                    kind,
                                    "https://github.com/home-assistant/core/blob/"
                                    + version
                                    + "/homeassistant/components/"
                                    + integration
                                    + "/manifest.json",
                                    "Version-pinned integration manifest",
                                    response,
                                    [
                                        {
                                            "excerpt_key": "p1",
                                            "heading": "Technical version basis",
                                            "text": "Current authenticated Core version "
                                            f"{version}; "
                                            f"integration {integration}; pinned requirements: "
                                            f"{', '.join(requirements) or 'not available'}. "
                                            "This is not the historical run version "
                                            "or device firmware.",
                                        }
                                    ],
                                    revision=revision
                                    if isinstance(revision, str)
                                    and re.fullmatch(r"[a-f0-9]{40}", revision)
                                    else None,
                                    applicability="matched_metadata",
                                )
                            )
                        else:
                            value = self.decoded(response)
                            if not isinstance(value, dict) or not isinstance(
                                value.get("items"), list
                            ):
                                raise ResearchError("invalid_search_response")
                            snapshot["coverage"]["queries_incomplete"] |= (
                                value.get("incomplete_results") is not False
                            )
                            repo = request["repo"]
                            for item in value["items"][:2]:
                                if (
                                    not isinstance(item, dict)
                                    or "pull_request" in item
                                    or not positive(item.get("number"))
                                ):
                                    continue
                                number = item["number"]
                                if (
                                    item.get("url")
                                    == f"https://api.github.com/repos/{repo}/issues/{number}"
                                ):
                                    candidates.append((repo, number))
                    except ResearchError as error:
                        if error.code in {
                            "invalid_public_document",
                            "no_relevant_document_excerpt",
                            "invalid_public_json",
                            "manifest_projection_unavailable",
                            "manifest_integration_mismatch",
                            "invalid_search_response",
                        }:
                            self.cache_failure(request["url"], error.code)
                        snapshot["gaps"].append({"adapter": request["kind"], "reason": error.code})
                        if error.code in {
                            "revoked_or_configuration_changed",
                            "upstream_rate_limited",
                            "upstream_backoff",
                            "public_quota_reached",
                        }:
                            break
                candidates = list(dict.fromkeys(candidates))
                snapshot["coverage"]["issue_candidates_unread"] = max(0, len(candidates) - 1)
                if candidates:
                    # Prefer the one explicitly cataloged upstream, then the Core candidate.
                    repo, number = sorted(candidates, key=lambda x: x[0] == "home-assistant/core")[
                        0
                    ]
                    await self.issue(job, snapshot, raw_sources, repo, number)
                elif any(r["kind"] == "issue_search" for r in public["requests"]):
                    snapshot["gaps"].append(
                        {
                            "adapter": "github",
                            "reason": "no_valid_issue_candidates_in_bounded_search",
                        }
                    )
                self.finalize(job, snapshot, raw_sources[:MAX_SOURCES])
                self.valid(job)
                job["status"], job["phase"] = "completed", "ready_for_new_preview"
        except TimeoutError:
            snapshot["gaps"].append({"adapter": "job", "reason": "whole_job_deadline"})
            try:
                self.finalize(job, snapshot, raw_sources[:MAX_SOURCES])
                job["status"] = "completed"
            except ResearchError:
                job["status"] = "revoked"
            job["error"], job["phase"] = "whole_job_deadline", "stopped"
        except ResearchError as error:
            job["status"], job["phase"], job["error"] = "revoked", "stopped", error.code
        except asyncio.CancelledError:
            job["status"], job["phase"], job["error"] = (
                "revoked" if job.get("revoked") else "failed",
                "stopped",
                "cancelled",
            )
            raise
        except Exception:
            job["status"], job["phase"], job["error"] = (
                "failed",
                "stopped",
                "public_projection_failed",
            )
        finally:
            self.active = None
            job.pop("identifiers", None)

    async def issue(self, job, snapshot, sources, repo, number):
        api_url = f"https://api.github.com/repos/{repo}/issues/{number}"
        request = {"kind": "issue_detail", "url": api_url}
        try:
            response = await self.get(job, request)
            issue = self.decoded(response)
            if (
                not isinstance(issue, dict)
                or not positive(issue.get("number"))
                or issue.get("number") != number
                or issue.get("url") != api_url
                or "pull_request" in issue
            ):
                raise ResearchError("invalid_issue_identity")
            text = plain(issue.get("body"))
            if len(text) >= 20:
                sources.append(
                    self.source(
                        "github_issue",
                        f"https://github.com/{repo}/issues/{number}",
                        plain(issue.get("title")),
                        response,
                        [
                            {
                                "excerpt_key": "p1",
                                "heading": "Public issue report (unverified locally)",
                                "text": text[:3000],
                            }
                        ],
                        issue_number=number,
                        revision=issue.get("updated_at")
                        if isinstance(issue.get("updated_at"), str)
                        and re.fullmatch(r"[0-9T:Z.-]{10,40}", issue["updated_at"])
                        else None,
                        issue_state=issue.get("state")
                        if issue.get("state") in {"open", "closed"}
                        else "unknown",
                    )
                )
            else:
                snapshot["gaps"].append(
                    {"adapter": "issue_detail", "reason": "no_usable_issue_text"}
                )
            count = issue.get("comments")
            if count == 0 and type(count) is int:
                return
            if not positive(count) or count > 1000000000:
                raise ResearchError("comment_count_unknown_no_page_fallback")
            page = (count + 2) // 3
            response = await self.get(
                job,
                {
                    "kind": "issue_comments",
                    "url": api_url + "/comments?" + urlencode({"per_page": 3, "page": page}),
                },
            )
            comments = self.decoded(response)
            if not isinstance(comments, list):
                raise ResearchError("invalid_comments_response")
            snapshot["coverage"].update(comments_pages=1, comments_returned=min(3, len(comments)))
            snapshot["gaps"].append(
                {
                    "adapter": "issue_comments",
                    "reason": "single_page_incomplete_thread_count_may_change",
                }
            )
            valid, ids = [], set()
            for comment in comments[:3]:
                if (
                    not isinstance(comment, dict)
                    or comment.get("issue_url") != api_url
                    or not positive(comment.get("id"))
                    or comment["id"] in ids
                ):
                    continue
                ids.add(comment["id"])
                text = plain(comment.get("body"))
                if len(text) >= 20:
                    valid.append((comment, text))
            # Keep one observed contradiction when present, without interpreting it as fact.
            contrary = [
                c for c in valid if re.search(r"(?i)\b(?:not|still|failed|fails|doesn.t)\b", c[1])
            ]
            selected = (contrary[:1] + [c for c in valid if c not in contrary[:1]])[:2]
            for comment, text in selected:
                if len(sources) >= MAX_SOURCES:
                    snapshot["coverage"]["sources_omitted"] += 1
                    continue
                sources.append(
                    self.source(
                        "github_comment",
                        f"https://github.com/{repo}/issues/{number}#issuecomment-{comment['id']}",
                        "Sampled public issue comment",
                        response,
                        [
                            {
                                "excerpt_key": "p1",
                                "heading": "Public comment claim (unverified locally)",
                                "text": text[:2000],
                            }
                        ],
                        issue_number=number,
                        comment_id=comment["id"],
                        comments_count=count,
                        page=page,
                        per_page=3,
                        thread_complete=False,
                        revision=comment.get("updated_at")
                        if isinstance(comment.get("updated_at"), str)
                        and re.fullmatch(r"[0-9T:Z.-]{10,40}", comment["updated_at"])
                        else None,
                    )
                )
            snapshot["coverage"]["comments_retained"] = sum(
                s["kind"] == "github_comment" for s in sources
            )
            if not valid:
                snapshot["gaps"].append(
                    {"adapter": "issue_comments", "reason": "no_usable_comments_on_sampled_page"}
                )
        except ResearchError as error:
            snapshot["gaps"].append({"adapter": request["kind"], "reason": error.code})

    def attach(self, request):
        self.cleanup()
        job = self.jobs.get(request.research_id)
        if (
            not job
            or job["status"] != "completed"
            or not hmac.compare_digest(job["research_digest"] or "", request.research_digest or "")
        ):
            raise ResearchError("research_not_completed_or_digest_mismatch")
        row, payload, local = self.valid(job)
        for key, expected in (
            ("kind", request.kind),
            ("target", request.target),
            ("profile", request.profile),
            ("run_id", request.run_id),
            ("compare_id", request.compare),
        ):
            if row[key] != expected:
                raise ResearchError("research_scope_mismatch")
        if (
            request.target_type != payload.get("target_type", "entity")
            or request.conversation_id
            or request.sections
        ):
            raise ResearchError("research_scope_mismatch")
        if digest(job["snapshot"]) != request.research_digest:
            raise ResearchError("research_integrity_failed")
        return (
            copy.deepcopy(local["snapshot"]),
            copy.deepcopy(job["snapshot"]),
            copy.deepcopy(job["aliases"]),
        )

    def preview_input(self, research_id, consent):
        job = self.jobs.get(research_id)
        if not job:
            raise ResearchError("job_not_retained")
        row, payload, _ = self.valid(job)
        try:
            return AnalysisInput(
                kind=row["kind"],
                target=row["target"],
                profile=row["profile"],
                run_id=row["run_id"],
                compare=row["compare_id"],
                target_type=payload.get("target_type", "entity"),
                question=payload["question"],
                followup_focus=payload["followup_focus"],
                diagnostic_consent=consent.diagnostic_consent,
                research_id=research_id,
                research_digest=consent.research_digest,
            )
        except (ValidationError, ValueError, TypeError, KeyError):
            raise ResearchError("stored_preview_reconstruction_failed") from None

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await self.client.aclose()
