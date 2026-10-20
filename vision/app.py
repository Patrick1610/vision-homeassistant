"""Ingress application. Writes are restricted to Vision's own data."""

import asyncio
import html
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .ai import AIError, AnalysisInput, Intelligence, evidence_bundle
from .config import Runtime, Settings
from .monitor import Monitor
from .security import Redactor, protect_logging
from .store import STORAGE_FAILURES, StorageStartupError, Store

STATIC = Path(__file__).parent / "static"


class ExceptionInput(BaseModel):
    entity_id: str = Field(pattern=r"^[a-z_]+\.[A-Za-z0-9_]+$", max_length=200)
    reason: str = Field(min_length=1, max_length=300)
    hours: int = Field(default=24, ge=1, le=8760)


class CaseStatusInput(BaseModel):
    status: Literal["review", "known", "expected", "snoozed"]
    note: str = Field(default="", max_length=300)
    hours: int = Field(default=24, ge=1, le=8760)


def secure_response(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'self'; frame-src 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def create_app(runtime=None, settings=None, *, connect=True):
    runtime = runtime or Runtime()
    configuration_error = None
    if settings is None:
        try:
            settings = Settings.load(runtime.options)
        except (ValueError, OSError):
            # Preserve only a separately validated access list, never partial AI settings.
            try:
                raw = json.loads(runtime.options.read_text())
                settings = Settings(allowed_user_ids=raw.get("allowed_user_ids", []))
            except (ValueError, OSError, AttributeError):
                settings = Settings()
            configuration_error = "Invalid app options; using safe defaults with AI disabled"
    redactor = Redactor([runtime.token, settings.key("anthropic"), settings.key("openai")])
    protect_logging(redactor)

    @asynccontextmanager
    async def lifespan(app):
        try:
            app.state.store = Store(runtime.data / "vision.db")
        except StorageStartupError as error:
            raise RuntimeError(STORAGE_FAILURES[error.code]) from None
        except Exception:
            raise RuntimeError("Vision storage unavailable; check private data volume") from None
        app.state.monitor = Monitor(app.state.store, settings, runtime, redactor)
        app.state.insights = app.state.monitor.insights
        app.state.ai = Intelligence(app.state.store, settings, app.state.monitor, redactor)
        app.state.ai_job = None
        app.state.tasks = []
        if connect:
            app.state.tasks.append(asyncio.create_task(app.state.monitor.run()))
            app.state.tasks.append(asyncio.create_task(app.state.ai.daily()))
        try:
            yield
        finally:
            for task in app.state.tasks:
                task.cancel()
            await asyncio.gather(*app.state.tasks, return_exceptions=True)
            await app.state.ai.client.aclose()
            app.state.store.close()

    app = FastAPI(
        title="Vision",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.redactor = redactor

    @app.middleware("http")
    async def ingress_guard(request: Request, call_next):
        peer = request.client.host if request.client else ""
        allowed = {"172.30.32.2"} if runtime.supervised else {"127.0.0.1", "::1"}
        denied = None
        if peer not in allowed:
            denied = JSONResponse({"detail": "Ingress access only"}, status_code=403)
        elif runtime.supervised and (
            request.headers.get("x-remote-user-id") not in settings.allowed_user_ids
        ):
            user_id = html.escape(request.headers.get("x-remote-user-id", "(not provided)"))
            denied = HTMLResponse(
                "<h1>Vision access is locked</h1><p>Add your Home Assistant user ID to "
                "<code>allowed_user_ids</code> in the Vision app configuration, then restart. "
                "Only explicitly authorized users can view monitoring data.</p><p>Your "
                "Ingress user ID: <code>"
                + user_id
                + "</code></p>"
                + (
                    "<p>" + html.escape(configuration_error) + "</p>" if configuration_error else ""
                ),
                status_code=403,
            )
        elif request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("x-vision-request") != "1":
                denied = JSONResponse({"detail": "Missing request guard"}, status_code=403)
        response = denied if denied is not None else await call_next(request)
        return secure_response(response)

    @app.get("/api/health")
    async def health():
        monitor = app.state.monitor
        app.state.store.rows("SELECT 1")
        return {
            "version": __version__,
            "read_only": True,
            "storage": "ready",
            "storage_journal_mode": app.state.store.journal_mode,
            "connected": monitor.connected,
            "last_sync": monitor.last_sync,
            "capabilities": monitor.capabilities,
            "configuration_error": configuration_error,
            "trace_detail_coverage": app.state.store.get_meta("trace_fetch_status"),
        }

    @app.get("/api/overview")
    async def overview():
        monitor, db = app.state.monitor, app.state.store
        inventory = monitor.inventory()
        issues = db.rows(
            "SELECT * FROM issues WHERE active=1 ORDER BY "
            "CASE severity WHEN 'critical' THEN 0 WHEN 'error' THEN 1 ELSE 2 END,"
            "last_seen DESC LIMIT 100"
        )
        latest = db.rows("SELECT * FROM analyses WHERE kind='audit' ORDER BY id DESC LIMIT 1")
        return {
            "health": await health(),
            "entities": len(inventory),
            "devices": len(monitor.devices),
            "automations": sum(e["entity_id"].startswith("automation.") for e in inventory),
            "unavailable": sum(
                e["availability"] in {"unknown", "unavailable"} and not e["expected_offline"]
                for e in inventory
            ),
            "issues": issues,
            "latest_audit": latest[0] if latest else None,
            "coverage_started": monitor.started,
            "last_gap": db.get_meta("last_gap"),
            "local": app.state.insights.overview(),
        }

    @app.get("/api/devices")
    async def devices():
        return {"devices": app.state.monitor.devices, "entities": app.state.monitor.inventory()}

    @app.get("/api/automations")
    async def automations():
        return app.state.monitor.automation_index()

    @app.get("/api/automations/{entity_id}")
    async def automation(entity_id: str):
        detail = app.state.monitor.automation_detail(entity_id)
        if not detail:
            raise HTTPException(404, "Automation not in current inventory")
        detail["issues"] = app.state.store.rows(
            "SELECT * FROM issues WHERE key=?",
            ("automation:" + entity_id,),
        )
        detail["analyses"] = app.state.store.rows(
            "SELECT * FROM analyses WHERE target=? ORDER BY id DESC LIMIT 20",
            (entity_id,),
        )
        return detail

    @app.get("/api/issues")
    async def issues():
        return app.state.store.rows(
            "SELECT * FROM issues ORDER BY active DESC,last_seen DESC LIMIT 500"
        )

    @app.get("/api/cases")
    async def cases(
        status: str = "attention",
        source: str = "all",
        q: str = Query(default="", max_length=200),
        page: int = Query(default=1, ge=1, le=10000),
        limit: int = Query(default=25, ge=1, le=100),
    ):
        try:
            return app.state.insights.cases(
                status=status, source=source, q=q, page=page, limit=limit
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.get("/api/cases/{key:path}")
    async def case_detail(key: str):
        if len(key) > 500:
            raise HTTPException(422, "Case identifier too long")
        try:
            return app.state.insights.dossier(key)
        except LookupError:
            raise HTTPException(404, "Case not found") from None

    @app.post("/api/cases/{key:path}/status")
    async def case_status(key: str, value: CaseStatusInput):
        if len(key) > 500:
            raise HTTPException(422, "Case identifier too long")
        try:
            return app.state.insights.annotate(key, value.status, value.note, value.hours)
        except LookupError:
            raise HTTPException(404, "Case not found") from None

    @app.get("/api/investigation/{entity_id}")
    async def investigation(
        entity_id: str,
        run_id: str | None = Query(default=None, max_length=200),
        compare: str | None = Query(default=None, max_length=200),
    ):
        try:
            return app.state.insights.automation(entity_id, run_id, compare)
        except LookupError as error:
            raise HTTPException(404, str(error)) from None

    @app.get("/api/dependencies")
    async def dependencies(
        kind: Literal["entity", "automation", "device", "integration"],
        identifier: str = Query(min_length=1, max_length=200),
    ):
        return app.state.insights.impact(identifier, kind)

    @app.get("/api/entities/{entity_id}/investigation")
    async def entity_investigation(entity_id: str):
        entity = app.state.monitor.entity_view(entity_id)
        if not entity:
            raise HTTPException(404, "Entity not in current inventory")
        cases = app.state.store.rows(
            "SELECT key,title,active FROM issues WHERE json_extract(detail,'$.entity_id')=? "
            "ORDER BY active DESC,last_seen DESC,key LIMIT 50",
            (entity_id,),
        )
        return {"entity": entity, "cases": cases, "impact": app.state.insights.impact(entity_id)}

    @app.get("/api/history/page")
    async def history_page(
        kind: str = "runs",
        q: str = Query(default="", max_length=200),
        entity: str = Query(default="", max_length=200),
        outcome: str = Query(default="", max_length=100),
        cursor: str | None = Query(default=None, max_length=400),
        limit: int = Query(default=50, ge=1, le=100),
        day: str | None = Query(default=None, max_length=10),
    ):
        try:
            return app.state.insights.history(
                kind, q=q, entity=entity, outcome=outcome, cursor=cursor, limit=limit, day=day
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.get("/api/history")
    async def history():
        db = app.state.store
        return {
            "availability": db.rows("SELECT * FROM availability ORDER BY id DESC LIMIT 300"),
            "runs": db.rows(
                "SELECT r.*,coalesce(t.start_source,'legacy_unverified') start_source,"
                "t.observed_at FROM runs r LEFT JOIN run_timing t USING(entity_id,run_id) "
                "ORDER BY started DESC LIMIT 300"
            ),
            "analyses": db.rows("SELECT * FROM analyses ORDER BY id DESC LIMIT 100"),
            "usage": db.rows("SELECT * FROM usage ORDER BY id DESC LIMIT 300"),
        }

    @app.get("/api/exceptions")
    async def exceptions():
        return app.state.store.exceptions()

    @app.post("/api/exceptions")
    async def add_exception(value: ExceptionInput):
        if value.entity_id not in app.state.monitor.entities:
            raise HTTPException(404, "Entity not in current inventory")
        with app.state.store.transaction():
            app.state.store.execute(
                "INSERT OR REPLACE INTO exceptions VALUES (?,?,?)",
                (value.entity_id, redactor.text(value.reason), time.time() + value.hours * 3600),
            )
        return {"saved": True}

    @app.delete("/api/exceptions/{entity_id}")
    async def remove_exception(entity_id: str):
        app.state.store.execute("DELETE FROM exceptions WHERE entity_id=?", (entity_id,))
        return {"removed": True}

    @app.exception_handler(Exception)
    async def safe_error(request, error):
        return secure_response(
            JSONResponse({"detail": "Internal error; no HA action was performed"}, status_code=500)
        )

    @app.get("/api/settings")
    async def public_settings():
        result = settings.public()
        for provider in ("anthropic", "openai"):
            result[provider + "_model"] = redactor.text(result[provider + "_model"])
        return result

    @app.get("/api/intelligence")
    async def intelligence():
        db = app.state.store
        job = app.state.ai_job
        return {
            "enabled": settings.ai_enabled,
            "running": bool(job and not job.done()) or app.state.ai.lock.locked(),
            "last_error": db.get_meta("ai_error"),
            "daily": db.get_meta("daily_status"),
            "analyses": db.rows("SELECT * FROM analyses ORDER BY id DESC LIMIT 50"),
            "usage": db.rows(
                "SELECT provider,model,status,sum(input_tokens) input_tokens,"
                "sum(output_tokens) output_tokens,sum(cost_usd) cost_usd "
                "FROM usage GROUP BY provider,model,status"
            ),
        }

    @app.get("/api/intelligence/preview")
    async def preview(kind: str = "audit", target: str | None = None):
        if kind not in {"audit", "incident", "automation"}:
            raise HTTPException(422, "Unknown analysis kind")
        bundle, mapping = evidence_bundle(app.state.monitor, kind, target)
        return {"transmitted": bundle, "local_mapping": mapping}

    @app.post("/api/intelligence", status_code=202)
    async def start_analysis(value: AnalysisInput):
        if not settings.ai_enabled:
            raise HTTPException(400, "Enable AI explicitly in app configuration first")
        if app.state.ai.lock.locked() or (app.state.ai_job and not app.state.ai_job.done()):
            raise HTTPException(409, "An analysis is already running")

        async def run_analysis():
            try:
                app.state.store.set_meta("ai_error", None)
                await app.state.ai.analyze(value)
            except AIError as error:
                app.state.store.set_meta("ai_error", redactor.text(str(error)))
            except Exception:
                app.state.store.set_meta(
                    "ai_error", "Analysis failed; check provider configuration"
                )

        app.state.ai_job = asyncio.create_task(run_analysis())
        app.state.tasks = [task for task in app.state.tasks if not task.done()]
        app.state.tasks.append(app.state.ai_job)
        return {"accepted": True}

    @app.get("/")
    async def index():
        return HTMLResponse(
            (STATIC / "index.html").read_text().replace("{{VISION_VERSION}}", __version__)
        )

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
