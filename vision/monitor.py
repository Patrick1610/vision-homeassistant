"""Observation, not inference: availability intervals and distinct run outcomes."""

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime

from .evidence import MAX_STEPS, dependency_graph, fingerprint, structure, trace_summary, trace_time
from .ha import IDENTIFIER, HAClient, HAError
from .insights import Insights
from .reliability import BINARY_CLASSES, DIAGNOSTIC_CLASSES, MEASUREMENT_CLASSES, DeviceReliability

BAD = {"unavailable", "unknown"}
OUTCOMES = {"succeeded", "condition_stopped", "stopped", "blocked", "failed", "running", "unknown"}
TRACE_FETCHES_PER_SYNC = 12
TRACE_FETCH_SECONDS_PER_SYNC = 5
TRACE_FETCH_TIMEOUT = 2
TRACE_RETRY_BASE = 60
TRACE_RETRY_MAX = 3600


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
    execution = execution if isinstance(execution, str) else None
    step = trace.get("last_step") or ""
    step = step if isinstance(step, str) else ""
    tree = trace.get("trace")
    tree = tree if isinstance(tree, dict) else {}
    nodes = tree.get(step, [])
    nodes = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
    results = [node["result"] for node in nodes if isinstance(node.get("result"), dict)]
    if any(result.get("error") is True for result in results):
        return "failed"
    if trace.get("not_triggered"):
        return "unknown"  # Evaluated trigger that did not fire is not a failed run.
    if execution in {"failed_single", "failed_max_runs", "disallowed_recursion_detected"}:
        return "blocked"
    timing = trace.get("timestamp")
    timing = timing if isinstance(timing, dict) else {}
    if execution == "started" and not timing.get("finish"):
        return "running"
    if execution == "failed_conditions" or (
        execution == "aborted"
        and (
            # HA last_step is the last inserted path, not the latest execution
            # when a loop revisits an earlier path. Step timestamps are starts,
            # so parallel branches/errors veto false-condition inference.
            decisive_condition_stop(tree)
            or (
                step.startswith("condition")
                and not any(str(path).startswith("action/") for path in tree)
            )
        )
    ):
        return "condition_stopped"
    if execution in {"aborted", "cancelled"}:
        return "stopped"
    if execution == "finished":
        if any("stop" in result for result in results):
            return "stopped"
        return "succeeded"
    return "unknown"


def decisive_condition_stop(tree):
    observations = []
    inspected = 0
    for path, elements in tree.items():
        if isinstance(path, str) and "parallel" in path.split("/"):
            return False  # Start order cannot establish parallel completion order.
        for element in elements if isinstance(elements, list) else []:
            inspected += 1
            if inspected > MAX_STEPS:
                return False
            if isinstance(element, dict):
                result = element.get("result")
                result = result if isinstance(result, dict) else {}
                if (
                    element.get("error")
                    or element.get("template_errors")
                    or result.get("timeout")
                    or result.get("error") is True
                ):
                    return False
                at = trace_time(element.get("timestamp"))
                if at is not None:
                    observations.append((at, str(path), element))
    if not observations:
        return False
    latest = max(item[0] for item in observations)
    terminal = [item for item in observations if item[0] == latest]
    return all(
        isinstance(element.get("result"), dict) and element["result"].get("result") is False
        for _, _, element in terminal
    )


class Monitor:
    def __init__(self, store, settings, runtime, redactor):
        self.store, self.settings, self.runtime, self.redactor = store, settings, runtime, redactor
        self.entities = {}
        self.devices = []
        self.registry = {}
        self.registry_digests = {}
        self.availability_metadata = {}
        self.structures = self.store.structures()
        self.config_attempts = {}
        self.connected = False
        self.last_sync = None
        self.ha_version, self.ha_version_observed_at = None, None
        self.capabilities = {}
        self.started = time.time()
        self.store.set_meta("monitor_started", self.started)
        self.reliability = DeviceReliability(self)
        self.gap()
        self.insights = Insights(self)
        self.insights.refresh()

    def gap(self):
        now = time.time()
        # Open intervals end at last proven observation, not at reconnection time.
        last = self.store.get_meta("last_observation", now)
        self.store.execute(
            "UPDATE availability SET ended=?,uncertain=1 WHERE ended IS NULL", (last,)
        )
        self.store.set_meta("last_gap", now)
        self.reliability.gap(now)

    def observe_state(self, state, now=None, *, track_device=True):
        if not state or not isinstance(state.get("entity_id"), str):
            return
        now = time.time() if now is None else now
        entity_id = state["entity_id"]
        previous = self.entities.get(entity_id)
        updated = timestamp(state.get("last_updated"), now)
        if previous and updated < previous["updated"]:
            return
        attrs = state.get("attributes", {})
        attrs = attrs if isinstance(attrs, dict) else {}
        device_class = attrs.get("device_class")
        self.availability_metadata[entity_id] = {
            "device_class": device_class
            if isinstance(device_class, str)
            and device_class in (DIAGNOSTIC_CLASSES | MEASUREMENT_CLASSES | BINARY_CLASSES)
            else None
            if device_class is None
            else "unrecognized"
        }
        # No numeric sensor states or arbitrary attributes are stored.
        status = state.get("state", "unknown")
        status = status if isinstance(status, str) else "unknown"
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
        if availability in BAD:
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
        if track_device:
            self.reliability.observe(entity_id, now)

    def event(self, event):
        kind = event.get("event_type")
        data = event.get("data", {})
        if kind == "state_changed":
            if data.get("new_state"):
                self.observe_state(data["new_state"])
            elif data.get("entity_id"):
                self.entities.pop(data["entity_id"], None)
                self.availability_metadata.pop(data["entity_id"], None)
                self.reliability.observe(data["entity_id"], time.time())
                self.store.execute(
                    "UPDATE availability SET ended=?,uncertain=1 "
                    "WHERE entity_id=? AND ended IS NULL",
                    (time.time(), data["entity_id"]),
                )
        elif kind == "automation_triggered":
            entity_id = data.get("entity_id")
            context = event.get("context", {}).get("id")
            if entity_id and context:
                with self.store.transaction():
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
                                trace_time(event.get("time_fired")),
                                "unknown",
                                "{}",
                            ),
                        )
                        self.store.execute(
                            "INSERT OR IGNORE INTO run_timing VALUES (?,?,?,?)",
                            (
                                entity_id,
                                "event:" + context,
                                time.time(),
                                "event"
                                if trace_time(event.get("time_fired")) is not None
                                else "unknown",
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
        if not isinstance(run_id, str) or not 1 <= len(run_id) <= 200 or trace.get("not_triggered"):
            return
        context = trace.get("context")
        context = context.get("id") if isinstance(context, dict) else None
        context = context if isinstance(context, str) and len(context) <= 200 else None
        timing = trace.get("timestamp")
        started = trace_time(timing.get("start")) if isinstance(timing, dict) else None
        outcome = trace_outcome(trace)
        summary = trace_summary(trace, self.redactor, outcome)
        structure_id = None
        if isinstance(trace.get("config"), dict):
            projection = structure(trace["config"])
            structure_id = self.record_structure(
                entity_id, trace["config"], "retained_trace", projection=projection
            )
            summary["configuration_digest"] = fingerprint(projection)
            summary["configuration_source"] = "retained_trace"
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
            previous = self.store.rows(
                "SELECT * FROM runs WHERE entity_id=? AND run_id=?", (entity_id, run_id)
            )
            if previous:
                old_detail = json.loads(previous[0]["detail"])
                old_detail.update(
                    {key: value for key, value in detail.items() if value is not None}
                )
                detail = old_detail
                if outcome == "unknown":
                    outcome = previous[0]["outcome"]
            if context:
                self.store.db.execute(
                    "DELETE FROM runs WHERE entity_id=? AND run_id=?",
                    (entity_id, "event:" + context),
                )
            self.store.db.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(entity_id,run_id) DO UPDATE SET "
                "outcome=excluded.outcome,detail=excluded.detail,"
                "context_id=coalesce(excluded.context_id,runs.context_id),"
                "started=coalesce(excluded.started,runs.started),"
                "triggered=max(runs.triggered,excluded.triggered)",
                (entity_id, run_id, context, started, outcome, triggered, json.dumps(detail)),
            )
            self.store.db.execute(
                "INSERT INTO run_timing VALUES (?,?,?,?) ON CONFLICT(entity_id,run_id) "
                "DO UPDATE SET start_source=CASE WHEN excluded.start_source='ha_trace' "
                "THEN excluded.start_source ELSE run_timing.start_source END",
                (entity_id, run_id, time.time(), "ha_trace" if started is not None else "unknown"),
            )
            summary = self.store.save_run_evidence(entity_id, run_id, summary, outcome)
            if structure_id is not None:
                self.store.db.execute(
                    "INSERT OR REPLACE INTO run_structures VALUES (?,?,?)",
                    (entity_id, run_id, structure_id),
                )
        newest = self.store.rows(
            "SELECT r.run_id FROM runs r JOIN run_timing t USING(entity_id,run_id) "
            "WHERE r.entity_id=? AND r.started IS NOT NULL "
            "AND t.start_source IN ('ha_trace','event') "
            "AND r.run_id NOT LIKE 'event:%' "
            "ORDER BY r.started DESC,r.run_id DESC LIMIT 1",
            (entity_id,),
        )
        latest = bool(newest and newest[0]["run_id"] == run_id)
        existing_issue = self.store.rows(
            "SELECT active FROM issues WHERE key=?", ("automation:" + entity_id,)
        )
        if outcome == "failed" and (
            latest or (started is None and (not existing_issue or not existing_issue[0]["active"]))
        ):
            self.store.issue(
                "automation:" + entity_id,
                "automation",
                "error",
                "Automation execution failed",
                {"entity_id": entity_id, "run_id": run_id},
            )
        elif outcome == "succeeded" and latest:
            blocking = self.store.rows(
                "SELECT r.run_id,coalesce(t.start_source,'legacy_unverified') start_source "
                "FROM runs r LEFT JOIN run_timing t USING(entity_id,run_id) "
                "WHERE r.entity_id=? AND r.outcome='failed' AND (r.started IS NULL "
                "OR coalesce(t.start_source,'legacy_unverified') "
                "NOT IN ('ha_trace','event')) ORDER BY r.run_id LIMIT 1",
                (entity_id,),
            )
            self.resolve_or_block_incident("automation:" + entity_id, blocking)
        existing_step = self.store.rows(
            "SELECT active FROM issues WHERE key=?", ("automation_step:" + entity_id,)
        )
        if summary["error_count"] and (
            latest or (started is None and (not existing_step or not existing_step[0]["active"]))
        ):
            self.store.issue(
                "automation_step:" + entity_id,
                "automation_step",
                "warning",
                "Automation trace contains step errors",
                {
                    "entity_id": entity_id,
                    "run_id": run_id,
                    "outcome": outcome,
                    "error_count": summary["error_count"],
                    "completed_with_errors": summary["completed_with_errors"],
                },
            )
        elif latest and not summary["coverage"]["error_count_is_lower_bound"]:
            blocking = self.store.rows(
                "SELECT r.run_id,coalesce(t.start_source,'legacy_unverified') start_source "
                "FROM runs r LEFT JOIN run_evidence e USING(entity_id,run_id) "
                "LEFT JOIN run_timing t USING(entity_id,run_id) WHERE r.entity_id=? "
                "AND (r.started IS NULL OR coalesce(t.start_source,'legacy_unverified') "
                "NOT IN ('ha_trace','event')) AND coalesce("
                "json_extract(e.summary,'$.error_count'),"
                "json_extract(r.detail,'$._vision_evidence.error_count'),0)>0 "
                "ORDER BY r.run_id LIMIT 1",
                (entity_id,),
            )
            self.resolve_or_block_incident("automation_step:" + entity_id, blocking)

    def resolve_or_block_incident(self, key, blocking):
        rows = self.store.rows("SELECT detail FROM issues WHERE key=? AND active=1", (key,))
        if not rows:
            return
        detail = json.loads(rows[0]["detail"])
        if blocking:
            detail.update(
                blocked_by_unknown_time_run=True,
                blocking_run_id=blocking[0]["run_id"],
                blocking_start_source=blocking[0]["start_source"],
            )
            self.store.execute("UPDATE issues SET detail=? WHERE key=?", (json.dumps(detail), key))
        else:
            for field in (
                "blocked_by_unknown_time_run",
                "blocking_run_id",
                "blocking_start_source",
            ):
                detail.pop(field, None)
            self.store.execute(
                "UPDATE issues SET active=0,detail=? WHERE key=?", (json.dumps(detail), key)
            )

    def record_structure(self, entity_id, config, source, *, projection=None):
        projection = structure(config) if projection is None else projection
        version_id = self.store.save_structure(entity_id, projection, source)
        if source == "current_config" or entity_id not in self.structures:
            self.structures[entity_id] = projection
        return version_id

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

    async def sync_traces(self, ha, traces):
        """Bounded fair reads, persistent backoff and a single capability probe."""
        mapping = {
            e.get("automation_id"): e["entity_id"]
            for e in self.entities.values()
            if e["entity_id"].startswith("automation.") and e.get("automation_id")
        }
        now = time.time()
        groups, heads = {}, {}
        pending_pairs = set()
        pending = 0
        for trace in traces:
            entity_id = mapping.get(str(trace.get("item_id")))
            run_id = trace.get("run_id")
            if (
                not entity_id
                or trace.get("not_triggered")
                or not isinstance(run_id, str)
                or not IDENTIFIER.fullmatch(run_id)
            ):
                continue
            timing = trace.get("timestamp")
            start = trace_time(timing.get("start")) if isinstance(timing, dict) else None
            rank = (start is not None, start or 0, run_id)
            if entity_id not in heads or rank > heads[entity_id][0]:
                heads[entity_id] = (rank, run_id)
            old = self.store.rows(
                "SELECT r.outcome,r.detail,r.started,r.context_id,e.summary,"
                "coalesce(t.start_source,'legacy_unverified') start_source "
                "FROM runs r LEFT JOIN run_evidence e "
                "ON e.entity_id=r.entity_id AND e.run_id=r.run_id "
                "LEFT JOIN run_timing t ON t.entity_id=r.entity_id AND t.run_id=r.run_id "
                "WHERE r.entity_id=? AND r.run_id=?",
                (entity_id, run_id),
            )
            retained = (
                json.loads(old[0]["summary"])
                if old and old[0]["summary"]
                else json.loads(old[0]["detail"]).get("_vision_evidence")
                if old
                else None
            )
            if (
                old
                and old[0]["outcome"] not in {"running", "unknown"}
                and retained
                and retained["coverage"].get("full_trace_available")
            ):
                continue
            # Save the small list observation even if detail reads are deferred.
            if not old or self.trace_list_changed(trace, old[0]):
                self.save_trace(entity_id, trace)
            pending += 1
            pending_pairs.add((entity_id, run_id))
            attempt = self.store.rows(
                "SELECT * FROM trace_fetches WHERE entity_id=? AND run_id=?", (entity_id, run_id)
            )
            if attempt and attempt[0]["next_attempt"] > now:
                continue
            groups.setdefault(entity_id, []).append((trace, attempt[0] if attempt else None))

        def rotated(keys, meta):
            keys = sorted(keys)
            cursor = self.store.get_meta(meta, "")
            return [key for key in keys if key > cursor] + [key for key in keys if key <= cursor]

        latest, backfill = {}, {}
        for entity_id, group in groups.items():
            for pair in group:
                if pair[0]["run_id"] == heads[entity_id][1]:
                    latest[entity_id] = pair
                else:
                    backfill.setdefault(entity_id, []).append(pair)
        for group in backfill.values():
            group.sort(
                key=lambda pair: (
                    trace_outcome(pair[0]) not in {"failed", "blocked"},
                    pair[1]["last_attempt"] if pair[1] else 0,
                    pair[0]["run_id"],
                )
            )
        latest_queue = [
            ("latest", entity, latest[entity])
            for entity in rotated(latest, "trace_fetch_latest_cursor")
        ]
        backfill_order = rotated(backfill, "trace_fetch_cursor")
        backfill_queue = [
            ("backfill", entity, backfill[entity][index])
            for index in range(max((len(g) for g in backfill.values()), default=0))
            for entity in backfill_order
            if index < len(backfill[entity])
        ]
        # Reserve one of twelve count slots for old error evidence while giving
        # newest runs an independent fair lane. Alternate which lane starts so
        # the five-second deadline cannot always cut off the same trailing lane.
        latest_count = min(len(latest_queue), TRACE_FETCHES_PER_SYNC - bool(backfill_queue))
        backfill_count = min(len(backfill_queue), TRACE_FETCHES_PER_SYNC - latest_count)
        turn = self.store.get_meta("trace_fetch_lane_turn", 0)
        latest_queue, backfill_queue = latest_queue[:latest_count], backfill_queue[:backfill_count]
        queue = backfill_queue + latest_queue if turn else latest_queue + backfill_queue
        self.store.set_meta("trace_fetch_lane_turn", 1 - turn)
        circuit = self.store.get_meta("trace_fetch_circuit", {"failures": 0, "next_probe": 0})
        attempted = 0
        lane_reads = {"latest": 0, "backfill": 0}
        inspected = 0
        started = time.monotonic()
        if now >= circuit["next_probe"]:
            for lane, entity_id, (trace, previous) in queue:
                remaining = TRACE_FETCH_SECONDS_PER_SYNC - (time.monotonic() - started)
                if attempted >= TRACE_FETCHES_PER_SYNC or remaining <= 0:
                    break
                attempted += 1
                self.store.set_meta(
                    "trace_fetch_latest_cursor" if lane == "latest" else "trace_fetch_cursor",
                    entity_id,
                )
                lane_reads[lane] += 1
                category = None
                try:
                    async with asyncio.timeout(min(TRACE_FETCH_TIMEOUT, remaining)):
                        full = await ha.read(
                            "trace/get",
                            domain="automation",
                            item_id=str(trace["item_id"]),
                            run_id=trace["run_id"],
                        )
                except (HAError, TimeoutError) as error:
                    full = None
                    category = "read_timeout" if isinstance(error, TimeoutError) else str(error)
                    if category not in {
                        "capability_unavailable",
                        "connection_lost",
                        "read_not_found",
                        "read_timeout",
                    }:
                        category = "read_unavailable"
                if not isinstance(full, dict) or full.get("run_id") != trace["run_id"]:
                    full = None
                if full is not None:
                    self.save_trace(entity_id, full)
                complete = isinstance(full, dict) and isinstance(full.get("trace"), dict)
                self.capabilities["trace/get"] = (
                    "available" if complete else "degraded (retained detail unavailable)"
                )
                failures = 0 if complete else min(16, (previous["attempts"] if previous else 0) + 1)
                next_attempt = (
                    0
                    if complete
                    else time.time() + min(TRACE_RETRY_MAX, TRACE_RETRY_BASE * 2 ** (failures - 1))
                )
                self.store.execute(
                    "INSERT INTO trace_fetches VALUES (?,?,?,?,?) ON CONFLICT(entity_id,run_id) "
                    "DO UPDATE SET attempts=excluded.attempts,last_attempt=excluded.last_attempt,"
                    "next_attempt=excluded.next_attempt",
                    (entity_id, trace["run_id"], failures, time.time(), next_attempt),
                )
                if complete:
                    inspected += 1
                    circuit = {"failures": 0, "next_probe": 0}
                elif category in {"capability_unavailable", "connection_lost", "read_timeout"}:
                    failures = min(16, circuit["failures"] + 1)
                    circuit = {
                        "failures": failures,
                        "next_probe": time.time()
                        + min(TRACE_RETRY_MAX, TRACE_RETRY_BASE * 2 ** (failures - 1)),
                    }
                    self.capabilities["trace/get"] = (
                        "unavailable (capability or transport); bounded probes"
                    )
                    break  # One unavailable capability probe, never a fan-out.
        self.store.set_meta("trace_fetch_circuit", circuit)
        status = {
            "observed_at": time.time(),
            "pending": max(0, pending - inspected),
            "latest_pending_at_cycle_start": sum(
                (entity, head[1]) in pending_pairs for entity, head in heads.items()
            ),
            "latest_eligible_at_cycle_start": len(latest),
            "latest_reads": lane_reads["latest"],
            "backfill_reads": lane_reads["backfill"],
            "attempted": attempted,
            "per_cycle_limit": TRACE_FETCHES_PER_SYNC,
            "time_budget_seconds": TRACE_FETCH_SECONDS_PER_SYNC,
            "next_capability_probe": circuit["next_probe"] or None,
        }
        self.store.set_meta("trace_fetch_status", status)
        self.capabilities["trace_detail_coverage"] = (
            f"{status['pending']} pending; {attempted}/{TRACE_FETCHES_PER_SYNC} "
            "detail reads this cycle; retries bounded"
        )

    def trace_list_changed(self, trace, old):
        outcome = trace_outcome(trace)
        if outcome != "unknown" and outcome != old["outcome"]:
            return True
        timing = trace.get("timestamp")
        started = trace_time(timing.get("start")) if isinstance(timing, dict) else None
        if started is not None and (started != old["started"] or old["start_source"] != "ha_trace"):
            return True
        context = trace.get("context")
        context = context.get("id") if isinstance(context, dict) else None
        if isinstance(context, str) and context != old["context_id"]:
            return True
        previous = json.loads(old["detail"])
        incoming = self.redactor.clean(
            {key: trace.get(key) for key in ("last_step", "script_execution", "error")}
        )
        return any(
            value is not None and previous.get(key) != value for key, value in incoming.items()
        )

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
                            "area_id",
                            "via_device_id",
                        )
                    }
                )
                for d in devices
            ]
        registry = await self.optional(ha, "config/entity_registry/list")
        if registry is not None:
            current, digests = {}, {}
            for entry in registry:
                entity_id = entry["entity_id"]
                projection = {
                    key: entry.get(key)
                    for key in ("device_id", "disabled_by", "platform", "entity_category")
                }
                digest = fingerprint(projection)
                current[entity_id] = (
                    self.registry[entity_id]
                    if entity_id in self.registry and self.registry_digests.get(entity_id) == digest
                    else self.redactor.clean(projection)
                )
                digests[entity_id] = digest
            self.registry, self.registry_digests = current, digests
        states = await ha.read("get_states")
        present = set()
        with self.store.transaction():
            for state in states:
                present.add(state["entity_id"])
                self.observe_state(state, track_device=False)
        for removed in self.entities.keys() - present:
            self.entities.pop(removed, None)
            self.availability_metadata.pop(removed, None)
            self.store.execute(
                "UPDATE availability SET ended=?,uncertain=1 WHERE entity_id=? AND ended IS NULL",
                (time.time(), removed),
            )
        self.reliability.refresh(
            time.time(), registry_complete=devices is not None and registry is not None
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
            await self.sync_traces(ha, traces)
        for entity in list(self.entities.values()):
            entity_id = entity["entity_id"]
            if entity.get("automation_id") and (
                time.time() - self.config_attempts.get(entity_id, 0) >= 3600
            ):
                self.config_attempts[entity_id] = time.time()
                try:
                    config = await ha.automation_config(entity["automation_id"])
                    self.record_structure(entity_id, config, "current_config")
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
        self.store.replace_graph(
            dependency_graph(
                self.entities,
                self.registry,
                self.devices,
                {
                    key: value
                    for key, value in self.structures.items()
                    if key in self.entities or key in self.registry
                },
            ),
            self.last_sync,
        )
        self.store.set_meta("last_sync", self.last_sync)
        self.store.prune(self.settings.retention_days)
        self.insights.refresh()

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
                    self.ha_version = ha.server_version
                    self.ha_version_observed_at = ha.version_observed_at
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
        expected = self.store.expected_entities()
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
                    "expected_offline": entity["entity_id"] in expected,
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
            "structure_observation": next(
                iter(
                    self.store.rows(
                        "SELECT observed_at,source FROM automation_current WHERE entity_id=?",
                        (entity_id,),
                    )
                ),
                None,
            ),
            "runs": self.store.rows(
                "SELECT r.*,coalesce(t.start_source,'legacy_unverified') start_source,"
                "t.observed_at FROM runs r LEFT JOIN run_timing t USING(entity_id,run_id) "
                "WHERE r.entity_id=? ORDER BY started DESC LIMIT 100",
                (entity_id,),
            ),
            "possibly_unused": entity["availability"] not in {"disabled", "not_loaded"}
            and not entity.get("last_triggered"),
            "coverage": "Retained HA traces and observed events only; downtime is a gap.",
        }

    def automation_index(self):
        stats = {}
        for row in self.store.rows(
            "SELECT entity_id,outcome,count(*) count,sum(triggered) observed_triggers "
            "FROM runs GROUP BY entity_id,outcome"
        ):
            entity_id = row.pop("entity_id")
            stats.setdefault(entity_id, []).append(row)
        result = []
        for entity_id in sorted(self.entities.keys() | self.registry.keys()):
            if not entity_id.startswith("automation."):
                continue
            entity = self.entity_view(entity_id)
            result.append(
                {
                    **entity,
                    "stats": stats.get(entity_id, []),
                    "possibly_unused": entity["availability"] not in {"disabled", "not_loaded"}
                    and not entity.get("last_triggered"),
                }
            )
        return result
