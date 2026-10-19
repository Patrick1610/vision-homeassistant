"""Observation, not inference: availability intervals and distinct run outcomes."""

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime

from .ha import HAClient, HAError

BAD = {"unavailable", "unknown"}
OUTCOMES = {"succeeded", "condition_stopped", "stopped", "blocked", "failed", "running", "unknown"}


def timestamp(value, fallback=None):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return time.time() if fallback is None else fallback


def trace_outcome(trace):
    if trace.get("error") or trace.get("script_execution") == "error":
        return "failed"
    if trace.get("state") == "running":
        return "running"
    execution = trace.get("script_execution")
    step = trace.get("last_step") or ""
    nodes = trace.get("trace", {}).get(step, [])
    if any(node.get("result", {}).get("error") is True for node in nodes):
        return "failed"
    if trace.get("not_triggered"):
        return "unknown"  # Evaluated trigger that did not fire is not a failed run.
    if execution in {"failed_single", "failed_max_runs", "disallowed_recursion_detected"}:
        return "blocked"
    if execution == "started" and not trace.get("timestamp", {}).get("finish"):
        return "running"
    if execution == "failed_conditions" or (
        execution == "aborted"
        and (
            step.startswith("condition")
            or "/condition" in step
            or any(node.get("result", {}).get("result") is False for node in nodes)
        )
    ):
        return "condition_stopped"
    if execution in {"aborted", "cancelled"}:
        return "stopped"
    if execution == "finished":
        if any("stop" in node.get("result", {}) for node in nodes):
            return "stopped"
        return "succeeded"
    return "unknown"


def structure(config):
    """Retain shape/dependencies only. Never values, templates, targets or secrets."""
    counts = {}
    for plural, singular in (
        ("triggers", "trigger"),
        ("conditions", "condition"),
        ("actions", "action"),
    ):
        value = config.get(plural, config.get(singular, []))
        counts[plural] = len(value) if isinstance(value, list) else int(bool(value))
    references = set()

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "entity_id":
                    candidates = child if isinstance(child, list) else [child]
                    references.update(
                        s
                        for s in candidates
                        if isinstance(s, str)
                        and len(s) < 200
                        and s.count(".") == 1
                        and "{{" not in s
                    )
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(config)
    return {
        **counts,
        "referenced_entities": sorted(references)[:200],
        "mode": config.get("mode")
        if config.get("mode") in {"single", "restart", "queued", "parallel"}
        else "single",
    }


class Monitor:
    def __init__(self, store, settings, runtime, redactor):
        self.store, self.settings, self.runtime, self.redactor = store, settings, runtime, redactor
        self.entities = {}
        self.devices = []
        self.registry = {}
        self.structures = {}
        self.config_attempts = {}
        self.connected = False
        self.last_sync = None
        self.capabilities = {}
        self.started = time.time()
        self.store.set_meta("monitor_started", self.started)
        self.gap()

    def gap(self):
        now = time.time()
        # Open intervals end at last proven observation, not at reconnection time.
        last = self.store.get_meta("last_observation", now)
        self.store.execute(
            "UPDATE availability SET ended=?,uncertain=1 WHERE ended IS NULL", (last,)
        )
        self.store.set_meta("last_gap", now)

    def observe_state(self, state, now=None):
        if not state or not isinstance(state.get("entity_id"), str):
            return
        now = time.time() if now is None else now
        entity_id = state["entity_id"]
        previous = self.entities.get(entity_id)
        updated = timestamp(state.get("last_updated"), now)
        if previous and updated < previous["updated"]:
            return
        attrs = state.get("attributes", {})
        # No numeric sensor states or arbitrary attributes are stored.
        status = state.get("state", "unknown")
        availability = status if status in BAD else "available"
        entity = {
            "entity_id": entity_id,
            "name": self.redactor.text(attrs.get("friendly_name", entity_id)),
            "availability": availability,
            "updated": updated,
            "device_id": self.registry.get(entity_id, {}).get("device_id"),
        }
        if entity_id.startswith("automation."):
            entity.update(
                {
                    "enabled": status == "on",
                    "last_triggered": attrs.get("last_triggered"),
                    "automation_id": str(attrs.get("id", "")),
                }
            )
        self.entities[entity_id] = entity
        open_rows = self.store.rows(
            "SELECT * FROM availability WHERE entity_id=? AND ended IS NULL",
            (entity_id,),
        )
        if not open_rows or open_rows[0]["state"] != availability:
            with self.store.transaction():
                self.store.db.execute(
                    "UPDATE availability SET ended=? WHERE entity_id=? AND ended IS NULL",
                    (now, entity_id),
                )
                self.store.db.execute(
                    "INSERT INTO availability(entity_id,state,started) VALUES (?,?,?)",
                    (entity_id, availability, now),
                )
        if availability in BAD and not self.store.expected(entity_id, now):
            self.store.issue(
                "availability:" + entity_id,
                "availability",
                "warning",
                entity["name"] + " is " + availability,
                {"entity_id": entity_id, "state": availability},
                now,
            )
        else:
            self.store.execute(
                "UPDATE issues SET active=0 WHERE key=?", ("availability:" + entity_id,)
            )
        self.store.set_meta("last_observation", now)

    def event(self, event):
        kind = event.get("event_type")
        data = event.get("data", {})
        if kind == "state_changed":
            if data.get("new_state"):
                self.observe_state(data["new_state"])
            elif data.get("entity_id"):
                self.entities.pop(data["entity_id"], None)
                self.store.execute(
                    "UPDATE availability SET ended=?,uncertain=1 "
                    "WHERE entity_id=? AND ended IS NULL",
                    (time.time(), data["entity_id"]),
                )
        elif kind == "automation_triggered":
            entity_id = data.get("entity_id")
            context = event.get("context", {}).get("id")
            if entity_id and context:
                existing = self.store.rows(
                    "SELECT run_id FROM runs WHERE entity_id=? AND context_id=?",
                    (entity_id, context),
                )
                if existing:
                    self.store.execute(
                        "UPDATE runs SET triggered=1 WHERE entity_id=? AND context_id=?",
                        (entity_id, context),
                    )
                else:
                    self.store.execute(
                        "INSERT OR IGNORE INTO runs VALUES (?,?,?,?,?,1,?)",
                        (
                            entity_id,
                            "event:" + context,
                            context,
                            timestamp(event.get("time_fired")),
                            "unknown",
                            "{}",
                        ),
                    )

    def log_issue(self, log):
        level = str(log.get("level", "WARNING")).lower()
        if level not in {"warning", "error", "critical"}:
            return None
        message = log.get("message", [])
        text = self.redactor.text(
            " ".join(map(str, message)) if isinstance(message, list) else str(message)
        )
        source = self.redactor.text(str(log.get("name", "system_log")))
        # HA groups by logger, source and final traceback frame, not its rolling messages.
        # Hash locations for grouping; never persist raw paths or tracebacks.
        frames = re.findall(
            r'File "([^"]+)", line (\d+), in ([^\n]+)', str(log.get("exception", ""))
        )
        group = [
            str(log.get("name", "system_log")),
            log.get("source"),
            frames[-1] if frames else None,
        ]
        if not log.get("source"):
            group.append(text)
        key = "log:" + hashlib.sha256(json.dumps(group).encode()).hexdigest()[:24]
        count = max(1, int(log.get("count", 1)))
        marker = log.get("first_occurred", 0)
        counter_key = (
            "counter:" + key + ":" + hashlib.sha256(json.dumps(marker).encode()).hexdigest()[:16]
        )
        with self.store.transaction():
            previous = self.store.get_meta(counter_key)
            delta = count
            if previous and previous["first"] == marker:
                delta = max(count - previous["count"], 0)
                count = max(count, previous["count"])
            old = self.store.rows("SELECT occurrences FROM issues WHERE key=?", (key,))
            total = (old[0]["occurrences"] if old else 0) + delta
            self.store.issue(key, "log", level, source, {"message": text}, occurrences=total)
            self.store.set_meta(counter_key, {"first": marker, "count": count})
        return key

    def save_trace(self, entity_id, trace):
        run_id = trace.get("run_id")
        if not run_id or trace.get("not_triggered"):
            return
        context = trace.get("context", {}).get("id")
        started = timestamp(trace.get("timestamp", {}).get("start"))
        outcome = trace_outcome(trace)
        detail = self.redactor.clean(
            {k: trace.get(k) for k in ("last_step", "script_execution", "error")}
        )
        triggered = 0
        if context:
            old = self.store.rows(
                "SELECT triggered FROM runs WHERE entity_id=? AND context_id=?",
                (entity_id, context),
            )
            triggered = int(any(row["triggered"] for row in old))
        with self.store.transaction():
            if context:
                self.store.db.execute(
                    "DELETE FROM runs WHERE entity_id=? AND run_id=?",
                    (entity_id, "event:" + context),
                )
            self.store.db.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(entity_id,run_id) DO UPDATE SET "
                "outcome=excluded.outcome,detail=excluded.detail,context_id=excluded.context_id,"
                "triggered=max(runs.triggered,excluded.triggered)",
                (entity_id, run_id, context, started, outcome, triggered, json.dumps(detail)),
            )
        if outcome == "failed":
            self.store.issue(
                "automation:" + entity_id,
                "automation",
                "error",
                "Automation execution failed",
                {"entity_id": entity_id, "run_id": run_id},
            )
        elif outcome == "succeeded":
            self.store.execute(
                "UPDATE issues SET active=0 WHERE key=?", ("automation:" + entity_id,)
            )

    async def optional(self, ha, command, **params):
        capability = command
        if command == "subscribe_events":
            capability += ":" + params["event_type"]
        try:
            result = await ha.read(command, **params)
            self.capabilities[capability] = "available"
            return result
        except (HAError, TimeoutError):
            self.capabilities[capability] = "unavailable (permission, component or version)"
            return None

    async def sync(self, ha):
        devices = await self.optional(ha, "config/device_registry/list")
        if devices is not None:
            self.devices = [
                self.redactor.clean(
                    {
                        k: d.get(k)
                        for k in (
                            "id",
                            "name",
                            "name_by_user",
                            "manufacturer",
                            "model",
                            "disabled_by",
                        )
                    }
                )
                for d in devices
            ]
        registry = await self.optional(ha, "config/entity_registry/list")
        if registry is not None:
            self.registry = {
                e["entity_id"]: {
                    "device_id": e.get("device_id"),
                    "disabled_by": e.get("disabled_by"),
                }
                for e in registry
            }
        states = await ha.read("get_states")
        present = set()
        with self.store.transaction():
            for state in states:
                present.add(state["entity_id"])
                self.observe_state(state)
        for removed in self.entities.keys() - present:
            self.entities.pop(removed, None)
            self.store.execute(
                "UPDATE availability SET ended=?,uncertain=1 WHERE entity_id=? AND ended IS NULL",
                (time.time(), removed),
            )
        repairs = await self.optional(ha, "repairs/list_issues")
        if repairs is not None:
            active = []
            for issue in repairs.get("issues", []):
                if issue.get("ignored"):
                    continue
                key = "repair:" + issue["domain"] + ":" + issue["issue_id"]
                active.append(key)
                self.store.issue(
                    key,
                    "repair",
                    issue.get("severity", "warning"),
                    self.redactor.text(issue["domain"] + ": " + issue["issue_id"]),
                    self.redactor.clean(
                        {k: issue.get(k) for k in ("domain", "issue_id", "is_fixable")}
                    ),
                )
            for row in self.store.rows("SELECT key FROM issues WHERE source='repair' AND active=1"):
                if row["key"] not in active:
                    self.store.execute("UPDATE issues SET active=0 WHERE key=?", (row["key"],))
        logs = await self.optional(ha, "system_log/list")
        if logs is not None:
            for log in logs:
                self.log_issue(log)
        traces = await self.optional(ha, "trace/list", domain="automation")
        if traces is not None:
            mapping = {
                e.get("automation_id"): e["entity_id"]
                for e in self.entities.values()
                if e["entity_id"].startswith("automation.") and e.get("automation_id")
            }
            # Only fetch new/running traces; raw variables/config never leave this method.
            for trace in traces:
                entity_id = mapping.get(str(trace.get("item_id")))
                if not entity_id or trace.get("not_triggered"):
                    continue
                old = self.store.rows(
                    "SELECT outcome FROM runs WHERE entity_id=? AND run_id=?",
                    (entity_id, trace["run_id"]),
                )
                if old and old[0]["outcome"] not in {"running", "unknown"}:
                    continue
                full = await self.optional(
                    ha,
                    "trace/get",
                    domain="automation",
                    item_id=str(trace["item_id"]),
                    run_id=trace["run_id"],
                )
                self.save_trace(entity_id, full if full else trace)
                if full and isinstance(full.get("config"), dict):
                    self.structures[entity_id] = structure(full["config"])
        for entity in list(self.entities.values()):
            entity_id = entity["entity_id"]
            if entity.get("automation_id") and (
                time.time() - self.config_attempts.get(entity_id, 0) >= 3600
            ):
                self.config_attempts[entity_id] = time.time()
                try:
                    config = await ha.automation_config(entity["automation_id"])
                    self.structures[entity_id] = structure(config)
                except (HAError, TimeoutError):
                    pass  # Both positive and negative lookups have an hourly refresh TTL.
        total = sum(bool(e.get("automation_id")) for e in self.entities.values())
        resolved = sum(
            e in self.structures for e in self.entities if self.entities[e].get("automation_id")
        )
        self.capabilities["automation_config"] = (
            f"{resolved}/{total} structural summaries; missing UI configs retry hourly"
        )
        self.last_sync = time.time()
        self.store.set_meta("last_sync", self.last_sync)
        self.store.prune(self.settings.retention_days)

    async def run(self):
        if not self.runtime.token:
            self.capabilities["connection"] = "No HA credential configured"
            return
        delay = 1
        while True:
            try:
                async with HAClient(
                    self.runtime.ha_url,
                    self.runtime.token,
                    self.event,
                    websocket_url=getattr(self.runtime, "websocket_url", None),
                ) as ha:
                    self.connected = True
                    self.capabilities["connection"] = "available"
                    for event_type in ("state_changed", "automation_triggered"):
                        await self.optional(ha, "subscribe_events", event_type=event_type)
                    while True:
                        await self.sync(ha)
                        delay = 1
                        try:
                            await asyncio.wait_for(
                                asyncio.shield(ha.reader), self.settings.poll_seconds
                            )
                        except TimeoutError:
                            continue
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # Deliberately record only class, never remote messages/URLs/tokens.
                self.capabilities["connection"] = "Disconnected: " + type(error).__name__
            finally:
                self.connected = False
                self.gap()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    def entity_view(self, entity_id):
        if entity_id in self.entities:
            return self.entities[entity_id]
        if entity_id in self.registry:
            registered = self.registry[entity_id]
            return {
                "entity_id": entity_id,
                "name": self.redactor.text(entity_id),
                "device_id": registered.get("device_id"),
                "updated": None,
                "availability": "disabled" if registered.get("disabled_by") else "not_loaded",
                "enabled": None,
                "last_triggered": None,
                "automation_id": "",
            }
        return None

    def inventory(self):
        stats = {
            row["entity_id"]: row
            for row in self.store.rows(
                "SELECT entity_id,count(*) episodes,sum(coalesce(ended,?)-started) seconds "
                "FROM availability WHERE state IN ('unknown','unavailable') GROUP BY entity_id",
                (time.time(),),
            )
        }
        result = []
        for entity_id in self.entities.keys() | self.registry.keys():
            entity = self.entity_view(entity_id)
            result.append(
                {
                    **entity,
                    "expected_offline": self.store.expected(entity["entity_id"]),
                    "outages": stats.get(entity["entity_id"], {"episodes": 0, "seconds": 0}),
                }
            )
        return sorted(result, key=lambda e: (e["availability"] == "available", e["entity_id"]))

    def automation_detail(self, entity_id):
        entity = self.entity_view(entity_id)
        if not entity or not entity_id.startswith("automation."):
            return None
        stats = self.store.rows(
            "SELECT outcome,count(*) count,sum(triggered) observed_triggers FROM runs "
            "WHERE entity_id=? GROUP BY outcome",
            (entity_id,),
        )
        return {
            **entity,
            "stats": stats,
            "structure": self.structures.get(entity_id),
            "runs": self.store.rows(
                "SELECT * FROM runs WHERE entity_id=? ORDER BY started DESC LIMIT 100", (entity_id,)
            ),
            "possibly_unused": entity["availability"] not in {"disabled", "not_loaded"}
            and not entity.get("last_triggered"),
            "coverage": "Retained HA traces and observed events only; downtime is a gap.",
        }
