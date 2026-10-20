"""Local investigations over retained observations; no network or AI dependency."""

import base64
import json
import math
import time
from datetime import UTC, datetime, timedelta

from .evidence import fingerprint
from .store import CASE_NOTES_PER_CASE

STATIC_PER_AUTOMATION = 20
STATIC_TOTAL = 500

STATUS_SQL = (
    "CASE WHEN i.active=0 THEN 'resolved' "
    "WHEN a.status IS NOT NULL AND (a.expires IS NULL OR a.expires>?) THEN a.status "
    "WHEN i.source='static' AND json_extract(i.detail,'$.coverage.static_selection_limited')=1 "
    "THEN 'limited' "
    "WHEN i.source='availability' AND EXISTS (SELECT 1 FROM exceptions x "
    "WHERE x.entity_id=json_extract(i.detail,'$.entity_id') "
    "AND (x.expires IS NULL OR x.expires>?)) THEN 'expected' ELSE 'review' END"
)
RANK_SQL = (
    "CASE WHEN i.severity='critical' THEN 0 "
    "WHEN i.severity='info' THEN 8 "
    "WHEN i.source IN ('automation','automation_step') AND i.severity='error' THEN 1 "
    "WHEN i.severity='error' THEN 2 WHEN i.source='repair' THEN 3 "
    "WHEN i.source IN ('automation','automation_step') THEN 3 "
    "WHEN i.source='static' THEN 4 WHEN i.source='availability' THEN 6 ELSE 5 END"
)
STATUSES = {"attention", "all", "review", "known", "expected", "snoozed", "resolved", "limited"}
SOURCES = {"all", "automation", "automation_step", "availability", "repair", "log", "static"}


def decoded(value, default=None):
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return default


def retained_summary(value):
    """Legacy/corrupt retained rows are unknown evidence, never an empty clean trace."""
    if value is None:
        return None, "No step evidence is retained."
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("coverage"), dict)
        or not isinstance(value.get("steps"), list)
        or not isinstance(value.get("errors"), list)
    ):
        return None, "Retained step evidence has an unknown or incomplete shape."
    if any(
        not isinstance(step, dict)
        or not isinstance(step.get("path"), str)
        or not isinstance(step.get("iteration"), int)
        for step in value["steps"]
    ):
        return None, "Retained step observations have an unknown shape."
    if any(
        not isinstance(error, dict)
        or not isinstance(error.get("path"), str)
        or not isinstance(error.get("message"), str)
        for error in value["errors"]
    ):
        return None, "Retained error observations have an unknown shape."
    result = {**value, "coverage": dict(value["coverage"])}
    if not isinstance(result["coverage"].get("error_count_is_lower_bound"), bool):
        result["coverage"]["error_count_is_lower_bound"] = True
    return result, None


def configuration_delta(before, after, kind):
    if not before or kind != "changed":
        return {
            "summary": "Observed structural baseline; no HA edit time is known.",
            "items": [],
            "truncated": False,
        }
    old = {node["path"]: node for node in before.get("nodes", [])}
    new = {node["path"]: node for node in after.get("nodes", [])}
    items = []
    for path in sorted(old.keys() | new.keys()):
        a, b = old.get(path), new.get(path)
        if a != b:

            def label(node):
                if node is None:
                    return "Absent from retained projection"
                operands = {
                    key: node[key]
                    for key in (
                        "service",
                        "predicate",
                        "timeout",
                        "delay_seconds",
                        "continue_on_error",
                        "continue_on_timeout",
                    )
                    if key in node
                }
                return node["kind"] + (
                    " · " + json.dumps(operands, sort_keys=True) if operands else ""
                )

            items.append({"path": path, "before": label(a), "after": label(b)})
    old_refs = {json.dumps(ref, sort_keys=True) for ref in before.get("references", [])}
    new_refs = {json.dumps(ref, sort_keys=True) for ref in after.get("references", [])}
    for ref in sorted(old_refs ^ new_refs):
        item = json.loads(ref)
        value = item["kind"] + ":" + item["id"]
        items.append(
            {
                "path": item["path"],
                "before": value if ref in old_refs else "Not declared",
                "after": value if ref in new_refs else "Not declared",
            }
        )
    return {
        "summary": f"{len(items)} observed structural differences; omitted source may also differ.",
        "items": items[:20],
        "truncated": len(items) > 20,
    }


class Insights:
    def __init__(self, monitor):
        self.monitor = monitor
        self.store = monitor.store
        self.run_revision = None

    def refresh(self):
        """Monitor-owned write boundary. Public GET paths never call this method."""
        self.refresh_rules()
        revision = self.store.get_meta("runs_revision", 0)
        if revision != self.run_revision:
            self.refresh_run_findings()
            self.run_revision = revision

    def save_rule_coverage(self, summary, details):
        """Only the ephemeral detail namespace follows current rule observations."""
        prefix = "local_rule_coverage:"
        values = [(prefix + entity, json.dumps(value)) for entity, value in details.items()]
        keep = {key for key, _ in values}
        previous = self.store.rows("SELECT key FROM meta WHERE key GLOB 'local_rule_coverage:*'")
        self.store.db.executemany(
            "INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            values,
        )
        self.store.db.executemany(
            "DELETE FROM meta WHERE key=?",
            [(row["key"],) for row in previous if row["key"] not in keep],
        )
        self.store.set_meta("local_rules_coverage", summary)

    def refresh_rules(self):
        """Gate on small identities; only changed inputs justify loading AST payloads."""
        current = self.store.rows(
            "SELECT c.entity_id,c.source,c.structure_id,s.digest FROM automation_current c "
            "JOIN automation_structures s ON s.id=c.structure_id ORDER BY c.entity_id"
        )
        inventory = self.monitor.entities.keys() | self.monitor.registry.keys()
        devices = {item["id"] for item in self.monitor.devices if item.get("id")}
        registry_ready = self.monitor.capabilities.get("config/entity_registry/list") == "available"
        devices_ready = self.monitor.capabilities.get("config/device_registry/list") == "available"
        digest = fingerprint(
            [current, sorted(inventory), sorted(devices), registry_ready, devices_ready]
        )
        if digest == self.store.get_meta("local_rules_digest"):
            previous_coverage = self.store.get_meta("local_rules_coverage", {})
            if "automations_limited" in previous_coverage:
                # Compact the earlier unpublished B format once at the write boundary.
                with self.store.transaction():
                    details = previous_coverage.pop("automations_limited")
                    previous_coverage["automations_limited_count"] = len(details)
                    current_entities = {
                        row["entity_id"] for row in current if row["source"] == "current_config"
                    }
                    self.save_rule_coverage(
                        previous_coverage,
                        {
                            entity: value
                            for entity, value in details.items()
                            if entity in current_entities
                        },
                    )
            return
        projections = {
            row["id"]: decoded(row["projection"], {})
            for row in self.store.rows(
                "SELECT s.id,s.projection FROM automation_structures s JOIN automation_current c "
                "ON c.structure_id=s.id WHERE c.source='current_config'"
            )
        }
        previous = {
            row["key"]: row for row in self.store.rows("SELECT * FROM issues WHERE source='static'")
        }
        candidates, observed = [], {}
        for row in current:
            if row["source"] != "current_config":
                continue
            projection = projections.get(row["structure_id"], {})
            coverage = projection.get("coverage", {})
            per_entity = []
            observed[row["entity_id"]] = 0

            def finding(
                rule,
                path,
                title,
                fact,
                check,
                severity="warning",
                target=None,
                row=row,
                coverage=coverage,
                per_entity=per_entity,
            ):
                observed[row["entity_id"]] += 1
                if len(per_entity) >= STATIC_PER_AUTOMATION:
                    return
                key = (
                    "rule:"
                    + fingerprint([row["entity_id"], row["digest"], rule, path, target])[:32]
                )
                per_entity.append(
                    {
                        "key": key,
                        "source": "static",
                        "severity": severity,
                        "title": title,
                        "detail": {
                            "entity_id": row["entity_id"],
                            "rule": rule,
                            "path": path,
                            "fact": fact,
                            "manual_check": check,
                            "target": target,
                            "configuration_digest": row["digest"],
                            "coverage": coverage,
                        },
                    }
                )

            # Concrete absent references get the per-automation budget before advice.
            for ref in projection.get("references", []):
                missing = (
                    ref["kind"] == "entity" and registry_ready and ref["id"] not in inventory
                ) or (ref["kind"] == "device" and devices_ready and ref["id"] not in devices)
                if missing:
                    finding(
                        "missing_target",
                        ref["path"],
                        "Declared reference absent from inventory",
                        f"Declared {ref['kind']} {ref['id']} was absent from the registry.",
                        "Check this reference in the HA editor; verify registry freshness.",
                        target=ref["kind"] + ":" + ref["id"],
                    )
            for node in projection.get("nodes", []):
                if node.get("continue_on_error"):
                    finding(
                        "continued_errors",
                        node["path"],
                        "Step allows execution after errors",
                        "This step explicitly enables continue_on_error.",
                        "Check errors and whether later actions remain valid after failure.",
                        severity="info",
                    )
                if node.get("kind") in {"wait_template", "wait_for_trigger"} and not node.get(
                    "timeout"
                ):
                    finding(
                        "unbounded_wait",
                        node["path"],
                        "Wait has no declared timeout",
                        "The retained structural projection has no timeout on this wait.",
                        "Check whether indefinite waiting fits this automation's mode.",
                        severity="info",
                    )
            candidates.extend(per_entity)
        candidates.sort(
            key=lambda item: (item["severity"] == "info", item["detail"]["entity_id"], item["key"])
        )
        selected = candidates[:STATIC_TOTAL]
        active = {item["key"] for item in selected}
        retained = {}
        for item in selected:
            entity = item["detail"]["entity_id"]
            retained[entity] = retained.get(entity, 0) + 1
        limited = {
            entity: {
                "observed": count,
                "retained": retained.get(entity, 0),
                "omitted": count - retained.get(entity, 0),
            }
            for entity, count in observed.items()
            if count > retained.get(entity, 0)
        }
        status = {
            "per_automation_limit": STATIC_PER_AUTOMATION,
            "global_limit": STATIC_TOTAL,
            "retained": len(selected),
            "observed": sum(observed.values()),
            "omitted": sum(observed.values()) - len(selected),
            "truncated": bool(limited),
            "automations_limited_count": len(limited),
            "observed_at": time.time(),
        }
        now = time.time()
        updates = []
        for item in selected:
            detail = item["detail"]
            if detail["entity_id"] in limited:
                detail["coverage"] = {
                    **detail["coverage"],
                    "static_findings_truncated": True,
                    "static_findings_omitted": limited[detail["entity_id"]]["omitted"],
                }
            old = previous.get(item["key"])
            if not old or not old["active"] or decoded(old["detail"]) != detail:
                updates.append(
                    (
                        item["key"],
                        "static",
                        item["severity"],
                        item["title"],
                        json.dumps(detail),
                        old["first_seen"] if old else now,
                        now,
                        old["occurrences"] + (not old["active"]) if old else 1,
                        1,
                    )
                )
        current_by_entity = {row["entity_id"]: row for row in current}
        with self.store.transaction():
            self.store.db.executemany(
                "INSERT INTO issues VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
                "severity=excluded.severity,title=excluded.title,detail=excluded.detail,"
                "last_seen=excluded.last_seen,occurrences=excluded.occurrences,active=1",
                updates,
            )
            for key, old in previous.items():
                if not old["active"] or key in active:
                    continue
                detail = decoded(old["detail"], {})
                entity = detail.get("entity_id")
                observation = current_by_entity.get(entity)
                if not observation or observation["source"] != "current_config":
                    continue
                projection = projections.get(observation["structure_id"], {})
                target_kind = (detail.get("target") or "").split(":")[0]
                reference_known = (
                    detail.get("rule") != "missing_target"
                    or (target_kind == "entity" and registry_ready)
                    or (target_kind == "device" and devices_ready)
                )
                if (
                    detail.get("configuration_digest") == observation["digest"]
                    and entity in limited
                ):
                    # A budget omission is unknown coverage, never a resolution fact.
                    coverage = {**detail.get("coverage", {}), "static_selection_limited": True}
                    if detail.get("coverage") != coverage:
                        self.store.execute(
                            "UPDATE issues SET detail=? WHERE key=?",
                            (json.dumps({**detail, "coverage": coverage}), key),
                        )
                elif reference_known and not projection.get("coverage", {}).get("truncated"):
                    self.store.execute("UPDATE issues SET active=0 WHERE key=?", (key,))
            self.store.set_meta("local_rules_digest", digest)
            self.save_rule_coverage(
                status,
                {
                    entity: {
                        "observed": count,
                        "retained": retained.get(entity, 0),
                        "omitted": count - retained.get(entity, 0),
                        "per_automation_limit": STATIC_PER_AUTOMATION,
                        "observed_at": now,
                    }
                    for entity, count in observed.items()
                },
            )

    def refresh_run_findings(self):
        latest = self.store.rows(
            "SELECT entity_id,run_id,outcome,started FROM ("
            "SELECT r.entity_id,r.run_id,r.outcome,r.started,"
            "row_number() OVER(PARTITION BY r.entity_id ORDER BY r.started DESC,r.run_id DESC) n "
            "FROM runs r JOIN run_timing t USING(entity_id,run_id) "
            "WHERE t.start_source IN ('ha_trace','event') "
            "AND r.run_id NOT LIKE 'event:%') WHERE n=1 ORDER BY entity_id"
        )
        unordered = self.store.rows(
            "SELECT r.entity_id,min(r.run_id) run_id,'blocked' outcome,NULL started "
            "FROM runs r LEFT JOIN run_timing t USING(entity_id,run_id) WHERE r.outcome='blocked' "
            "AND (r.started IS NULL OR coalesce(t.start_source,'legacy_unverified') "
            "NOT IN ('ha_trace','event')) GROUP BY r.entity_id ORDER BY r.entity_id"
        )
        # A refused start is still an observed fact without a proven run time.
        # A later-looking success cannot establish resolution of that observation.
        by_entity = {row["entity_id"]: row for row in latest}
        by_entity.update({row["entity_id"]: row for row in unordered})
        latest = [by_entity[key] for key in sorted(by_entity)]
        digest = fingerprint(latest)
        if self.store.get_meta("local_run_rules_digest") == digest:
            return
        with self.store.transaction():
            for row in latest:
                key = "mode_conflict:" + row["entity_id"]
                if row["outcome"] == "blocked":
                    previous = self.store.rows(
                        "SELECT active,detail FROM issues WHERE key=?", (key,)
                    )
                    if (
                        previous
                        and previous[0]["active"]
                        and decoded(previous[0]["detail"], {}).get("run_id") == row["run_id"]
                    ):
                        continue
                    self.store.issue(
                        key,
                        "automation",
                        "warning",
                        "Automation start refused",
                        {
                            "entity_id": row["entity_id"],
                            "run_id": row["run_id"],
                            "rule": "mode_conflict",
                            "fact": "HA reported a refused start for this retained run.",
                            "manual_check": "Check the rejection and concurrency settings. "
                            "Cancellation alone does not prove a restart-mode conflict.",
                        },
                    )
                elif row["outcome"] not in {"unknown", "running"}:
                    self.store.execute("UPDATE issues SET active=0 WHERE key=?", (key,))
            self.store.set_meta("local_run_rules_digest", digest)

    def cases(self, *, status="attention", source="all", q="", page=1, limit=25):
        if (
            status not in STATUSES
            or source not in SOURCES
            or not 1 <= page <= 10000
            or not 1 <= limit <= 100
        ):
            raise ValueError("Invalid case filter or page")
        now = time.time()
        where, args = [], [now, now]
        if source != "all":
            where.append("source=?")
            args.append(source)
        if status == "attention":
            where.append("status='review'")
        elif status != "all":
            where.append("status=?")
            args.append(status)
        if q:
            where.append("(instr(lower(title),lower(?))>0 OR instr(lower(key),lower(?))>0)")
            args.extend([q, q])
        cte = (
            "WITH cases AS (SELECT i.*,a.note,a.expires,a.status annotation_status, "
            + STATUS_SQL
            + " status,"
            + RANK_SQL
            + " priority FROM issues i LEFT JOIN case_annotations a ON a.key=i.key "
            "AND a.case_first_seen=i.first_seen) "
        )
        filters = " WHERE " + " AND ".join(where) if where else ""
        total = self.store.rows(cte + "SELECT count(*) n FROM cases" + filters, args)[0]["n"]
        rows = self.store.rows(
            cte + "SELECT * FROM cases" + filters + " ORDER BY priority,last_seen DESC,key "
            "LIMIT ? OFFSET ?",
            (*args, limit, (page - 1) * limit),
        )
        for row in rows:
            row["detail"] = decoded(row["detail"], {})
        runs = self.case_runs(rows)
        for row in rows:
            row["source_active"] = bool(row["active"])
            self.case_context(row, now, runs)
        return {
            "items": rows,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": page * limit < total,
            "rule_coverage": self.store.get_meta("local_rules_coverage", {}),
        }

    def case_runs(self, cases):
        pairs = sorted(
            {
                identity
                for row in cases
                if (identity := self.case_run_identity(row["detail"])) is not None
            }
        )
        if not pairs:
            return {}
        rows = self.store.rows(
            "WITH wanted(entity_id,run_id) AS (VALUES "
            + ",".join("(?,?)" for _ in pairs)
            + ") SELECT r.*,coalesce(t.start_source,'legacy_unverified') start_source,"
            "t.observed_at,e.summary,NULL configuration_digest,NULL configuration "
            "FROM wanted JOIN runs r USING(entity_id,run_id) "
            "LEFT JOIN run_timing t USING(entity_id,run_id) "
            "LEFT JOIN run_evidence e USING(entity_id,run_id)",
            tuple(value for pair in pairs for value in pair),
        )
        return {(row["entity_id"], row["run_id"]): self.decode_run(row) for row in rows}

    @staticmethod
    def case_run_identity(detail):
        entity, run = detail.get("entity_id"), detail.get("run_id")
        if isinstance(entity, str) and isinstance(run, (str, int)) and not isinstance(run, bool):
            return (entity, str(run)) if entity and str(run) else None
        return None

    def case_context(self, row, now, runs=None):
        detail = row["detail"]
        row["local_status"] = (
            row.get("annotation_status")
            if (row.get("annotation_status") and (row["expires"] is None or row["expires"] > now))
            else ("expected" if row["status"] == "expected" else "review")
        )
        row["summary"] = detail.get("fact") or detail.get("entity_id") or row["title"]
        row["manual_check"] = detail.get("manual_check") or {
            "repair": "Open this HA Repair and inspect its instructions manually.",
            "availability": "Check power, connectivity, expected sleep and affected relations.",
            "log": "Inspect the message and matching integration logs around this time.",
        }.get(row["source"], "Inspect this retained step and compare a completed run.")
        if row["source"] == "repair":
            row["summary"] = (
                " · ".join(str(detail[key]) for key in ("domain", "issue_id") if detail.get(key))
                or row["title"]
            )
        if row["source"] == "log" and detail.get("message"):
            row["summary"] = self.monitor.redactor.text(str(detail["message"]), 220)
        if identity := self.case_run_identity(detail):
            try:
                if runs is None:
                    run = self.run(*identity, configuration=False)
                else:
                    run = runs.get(identity)
                    if run is None:
                        raise LookupError("Retained run not found")
                evidence = run["evidence"] or {}
                errors = sorted(
                    evidence.get("errors", []),
                    key=lambda item: len(item.get("path", "unknown")),
                    reverse=True,
                )
                row["run_outcome"] = run["outcome"]
                row["summary"] = run["outcome"] + (
                    " · Completed with step errors" if evidence.get("completed_with_errors") else ""
                )
                if errors:
                    error = errors[0]
                    row["step_path"] = error["path"]
                    row["summary"] += (
                        " · "
                        + error.get("path", "unknown")
                        + " · "
                        + self.monitor.redactor.text(
                            error.get("message", "Unknown error text"), 220
                        )
                    )
                    if error.get("kind") == "timeout":
                        row["manual_check"] = (
                            "Inspect the wait/timeout behavior; compare a completed run."
                        )
                if run["start_source"] not in {"ha_trace", "event"}:
                    row["summary"] += " · Run start is unverified; chronology is unknown."
                if run.get("evidence_unknown_reason"):
                    row["summary"] += " · " + run["evidence_unknown_reason"]
            except LookupError:
                row["summary"] += " · linked run no longer retained"
        if detail.get("blocked_by_unknown_time_run"):
            row["summary"] += (
                " · Historical error start is unverified; automatic resolution is blocked."
            )

    def annotate(self, key, status, note, hours=24):
        if status not in {"review", "known", "expected", "snoozed"}:
            raise ValueError("Unknown local status")
        episode = self.store.rows("SELECT first_seen FROM issues WHERE key=?", (key,))
        if not episode:
            raise LookupError("Case not found")
        now = time.time()
        expires = now + hours * 3600 if status == "snoozed" else None
        with self.store.transaction():
            if status == "review":
                self.store.execute("DELETE FROM case_annotations WHERE key=?", (key,))
            else:
                self.store.execute(
                    "INSERT INTO case_annotations(key,status,note,updated,expires,case_first_seen) "
                    "VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET "
                    "status=excluded.status,note=excluded.note,"
                    "updated=excluded.updated,expires=excluded.expires,"
                    "case_first_seen=excluded.case_first_seen",
                    (
                        key,
                        status,
                        self.monitor.redactor.text(note, 300),
                        now,
                        expires,
                        episode[0]["first_seen"],
                    ),
                )
            self.store.execute(
                "INSERT INTO case_notes(key,created,status,note,expires,case_first_seen) "
                "VALUES (?,?,?,?,?,?)",
                (
                    key,
                    now,
                    status,
                    self.monitor.redactor.text(note, 300),
                    expires,
                    episode[0]["first_seen"],
                ),
            )
            self.store.execute(
                "DELETE FROM case_notes WHERE key=? AND id NOT IN "
                "(SELECT id FROM case_notes WHERE key=? ORDER BY created DESC,id DESC LIMIT ?)",
                (key, key, CASE_NOTES_PER_CASE),
            )
        return self.dossier(key)

    def run(self, entity, run_id, *, configuration=True):
        fields = (
            "s.digest configuration_digest,s.projection configuration"
            if configuration
            else ("NULL configuration_digest,NULL configuration")
        )
        joins = (
            (
                "LEFT JOIN run_structures rs USING(entity_id,run_id) "
                "LEFT JOIN automation_structures s ON s.id=rs.structure_id "
            )
            if configuration
            else ""
        )
        rows = self.store.rows(
            "SELECT r.*,coalesce(t.start_source,'legacy_unverified') start_source,t.observed_at,"
            "e.summary," + fields + " "
            "FROM runs r LEFT JOIN run_timing t USING(entity_id,run_id) "
            "LEFT JOIN run_evidence e USING(entity_id,run_id) "
            + joins
            + "WHERE r.entity_id=? AND r.run_id=?",
            (entity, run_id),
        )
        if not rows:
            raise LookupError("Retained run not found")
        return self.decode_run(rows[0])

    @staticmethod
    def decode_run(row):
        row["detail"] = decoded(row["detail"], {})
        if not isinstance(row["detail"], dict):
            row["detail"] = {}
        raw = decoded(row.pop("summary"), None)
        if raw is None:
            raw = row["detail"].get("_vision_evidence")
        row["evidence"], row["evidence_unknown_reason"] = retained_summary(raw)
        row["configuration"] = decoded(row["configuration"])
        if not row["configuration_digest"] and row["evidence"]:
            row["configuration_digest"] = row["evidence"].get("configuration_digest")
        return row

    def comparison(self, entity, left_id, right_id):
        left, right = self.run(entity, left_id), self.run(entity, right_id)
        comparable = bool(
            left["configuration_digest"]
            and left["configuration_digest"] == right["configuration_digest"]
        )
        differences = []
        if comparable:
            observations = []
            for run in (left, right):
                observations.append(
                    {
                        (s["path"], s["iteration"]): s
                        for s in (run["evidence"] or {}).get("steps", [])
                    }
                )
            for key in sorted(observations[0].keys() | observations[1].keys()):
                a, b = (o.get(key) for o in observations)
                fields = ("result", "wait_completed", "wait_timed_out", "timeout", "errors")
                if a is None or b is None or any(a.get(k) != b.get(k) for k in fields):
                    differences.append({"path": key[0], "iteration": key[1], "left": a, "right": b})
        return {
            "left": left,
            "right": right,
            "comparable": comparable,
            "limitation": "Same retained configuration; retained differences do not prove a cause."
            if comparable
            else "Configuration digest missing/changed; runs remain separate with unmatched paths.",
            "differences": differences[:100],
            "truncated": len(differences) > 100,
            "coverage_limited": any(
                not run["evidence"]
                or run["evidence"].get("coverage", {}).get("error_count_is_lower_bound")
                or run["evidence"].get("coverage", {}).get("details_compacted")
                for run in (left, right)
            ),
        }

    def impact(self, entity, kind="entity"):
        if kind not in {"entity", "device", "integration", "automation"}:
            raise ValueError("Unknown dependency kind")
        keys = [kind + ":" + entity]
        if kind in {"entity", "automation"} and entity.startswith("automation."):
            keys = ["entity:" + entity]
            keys.append("automation:" + entity)
        else:
            keys.append(keys[0])
        rows = self.store.rows(
            "SELECT e.*,n.kind target_kind,n.identifier target_identifier "
            "FROM dependency_edges e JOIN dependency_nodes n ON n.key=e.target "
            "WHERE e.source IN (?,?) OR e.target IN (?,?) "
            "ORDER BY e.source,e.target,e.relation,e.path LIMIT 101",
            (*keys, *keys),
        )
        affected = self.store.rows(
            "SELECT DISTINCT e.source,e.target,e.relation,e.path FROM dependency_edges e "
            "WHERE e.source LIKE 'automation:%' AND e.relation!='represented_by' AND ("
            "e.target IN (?,?) OR e.target IN (SELECT target FROM dependency_edges "
            "WHERE source IN (?,?) AND relation IN ('contains','provides') "
            "ORDER BY target LIMIT 200)) ORDER BY e.source,e.target,e.path LIMIT 101",
            (*keys, *keys),
        )
        inventory = self.monitor.entities.keys() | self.monitor.registry.keys()
        for row in rows + affected:
            for side in ("source", "target"):
                node_kind, identifier = row[side].split(":", 1)
                row[side + "_present"] = (
                    identifier in inventory if node_kind in {"entity", "automation"} else True
                )
        members = self.store.rows(
            "SELECT DISTINCT target FROM dependency_edges WHERE source IN (?,?) "
            "AND relation IN ('contains','provides') ORDER BY target LIMIT 201",
            keys,
        )
        return {
            "relations": rows[:100],
            "truncated": len(rows) > 100,
            "affected_automations": affected[:100],
            "affected_truncated": len(affected) > 100,
            "members_truncated": len(members) > 200,
            "observed_at": self.store.get_meta("dependencies_observed_at"),
            "coverage": "Observed relation only; area/label expansion and causation are unknown.",
        }

    def dossier(self, key):
        now = time.time()
        rows = self.store.rows(
            "SELECT i.*,a.note,a.expires,a.status annotation_status,"
            + STATUS_SQL
            + " status FROM issues i "
            "LEFT JOIN case_annotations a ON a.key=i.key AND a.case_first_seen=i.first_seen "
            "WHERE i.key=?",
            (now, now, key),
        )
        if not rows:
            raise LookupError("Case not found")
        case = rows[0]
        detail = decoded(case["detail"], {})
        case.update(detail=detail, source_active=bool(case["active"]))
        self.case_context(case, now)
        entity = detail.get("entity_id")
        timeline = [
            {
                "at": case["first_seen"],
                "kind": "first_observation",
                "summary": "First retained observation of this case",
                "source": "vision_observation",
            }
        ]
        timeline.extend(
            {
                "at": row["created"],
                "kind": "local_status",
                "summary": row["status"] + ": " + row["note"],
                "source": "vision_local",
            }
            for row in self.store.rows(
                "SELECT * FROM case_notes WHERE key=? AND case_first_seen=? "
                "ORDER BY id DESC LIMIT 25",
                (key, case["first_seen"]),
            )
        )
        unknowns = ["Observation gaps cannot be reconstructed; no source cause has been proven."]
        if not self.monitor.connected:
            unknowns.append("Home Assistant is disconnected; current observations may be stale.")
        if detail.get("blocked_by_unknown_time_run"):
            unknowns.append(
                "Resolution is blocked by run "
                + str(detail.get("blocking_run_id"))
                + " with unproven start time."
            )
        evidence = None
        if entity and detail.get("run_id"):
            try:
                evidence = self.run(entity, detail["run_id"])
            except LookupError:
                unknowns.append("The linked run is outside retained history.")
        recurrence = {
            "reported": case["occurrences"],
            "meaning": "Retained reopen segments; repeated polls are not new occurrences.",
        }
        if case["source"] == "log":
            recurrence["meaning"] = (
                "HA-reported log counter; buffer eviction/reset limits recurrence history."
            )
        if entity:
            for row in self.store.rows(
                "SELECT * FROM availability WHERE entity_id=? ORDER BY id DESC LIMIT 20",
                (entity,),
            ):
                timeline.append(
                    {
                        "at": row["started"],
                        "kind": "availability",
                        "summary": row["state"],
                        "ended": row["ended"],
                        "uncertain": bool(row["uncertain"]),
                        "source": "vision_observation",
                    }
                )
            for row in self.store.rows(
                "SELECT r.run_id,r.started,r.outcome,"
                "coalesce(t.start_source,'legacy_unverified') start_source "
                "FROM runs r LEFT JOIN run_timing t USING(entity_id,run_id) WHERE entity_id=? "
                "ORDER BY r.started DESC,r.run_id DESC LIMIT 20",
                (entity,),
            ):
                timeline.append(
                    {
                        "at": row["started"],
                        "kind": "automation_run",
                        "summary": row["outcome"],
                        "run_id": row["run_id"],
                        "source": row["start_source"],
                    }
                )
            recurrence["retained_runs"] = self.store.rows(
                "SELECT count(*) n FROM runs WHERE entity_id=?",
                (entity,),
            )[0]["n"]
            for change in self.store.rows(
                "SELECT observed_at,kind,source FROM configuration_changes WHERE entity_id=? "
                "ORDER BY observed_at DESC,id DESC LIMIT 10",
                (entity,),
            ):
                timeline.append(
                    {
                        "at": change["observed_at"],
                        "kind": "structural_" + change["kind"],
                        "summary": "Observed structural projection; not an HA edit timestamp",
                        "source": change["source"],
                    }
                )
            recurrence["retained_error_runs"] = self.store.rows(
                "SELECT count(*) n FROM runs r LEFT JOIN run_evidence e USING(entity_id,run_id) "
                "WHERE r.entity_id=? AND (r.outcome='failed' OR coalesce("
                "json_extract(e.summary,'$.error_count'),"
                "json_extract(r.detail,'$._vision_evidence.error_count'),0)>0)",
                (entity,),
            )[0]["n"]
        if evidence:
            coverage = (evidence["evidence"] or {}).get("coverage", {})
            if coverage.get("error_count_is_lower_bound") or not evidence["evidence"]:
                unknowns.append(
                    "Step evidence is incomplete; missing errors cannot prove an error-free run."
                )
            if evidence.get("evidence_unknown_reason"):
                unknowns.append(evidence["evidence_unknown_reason"])
            if evidence["start_source"] not in {"ha_trace", "event"}:
                unknowns.append(
                    "Run start time is unknown/unverified; its place in the timeline is uncertain."
                )
        if detail.get("coverage", {}).get("dynamic_references"):
            unknowns.append("Templates/targets were not executed or expanded; coverage is partial.")
        timeline.sort(key=lambda item: (item["at"] is None, -(item["at"] or 0), item["kind"]))
        check = case["manual_check"]
        return {
            "case": case,
            "facts": [
                case["summary"],
                "The source observation is active."
                if case["active"]
                else "The retained source case is inactive.",
            ],
            "hypotheses": [],
            "unknowns": unknowns,
            "manual_checks": [check],
            "timeline": timeline[:60],
            "timeline_truncated": len(timeline) > 60,
            "last_observation_gap": self.store.get_meta("last_gap"),
            "recurrence": recurrence,
            "run": evidence,
            "affected": [entity] if entity else [],
            "impact": self.impact(entity) if entity else None,
        }

    def automation(self, entity, run_id=None, compare=None):
        detail = self.monitor.automation_detail(entity)
        if not detail:
            raise LookupError("Automation not in current inventory")
        detail["local_cases"] = self.store.rows(
            "SELECT key,title,severity,active,detail FROM issues "
            "WHERE json_extract(detail,'$.entity_id')=? "
            "ORDER BY active DESC,last_seen DESC,key LIMIT 50",
            (entity,),
        )
        detail["impact"] = self.impact(entity)
        detail["run"] = self.run(entity, run_id) if run_id else None
        detail["comparison"] = (
            self.comparison(entity, run_id, compare) if run_id and compare else None
        )
        detail["configuration_changes"] = self.store.rows(
            "SELECT c.id,c.observed_at,c.kind,c.source,"
            "b.digest before_digest,a.digest after_digest,b.projection before_projection,"
            "a.projection after_projection "
            "FROM configuration_changes c LEFT JOIN automation_structures b ON b.id=c.before_id "
            "JOIN automation_structures a ON a.id=c.after_id WHERE c.entity_id=? "
            "ORDER BY c.observed_at DESC,c.id DESC LIMIT 20",
            (entity,),
        )
        for change in detail["configuration_changes"]:
            change["delta"] = configuration_delta(
                decoded(change.pop("before_projection")),
                decoded(change.pop("after_projection"), {}),
                change["kind"],
            )
        detail["structure_coverage"] = (detail.get("structure") or {}).get("coverage", {})
        detail["structure_coverage"] = {
            **detail["structure_coverage"],
            "local_rule_selection": self.store.get_meta("local_rule_coverage:" + entity, {}),
            "area_label_membership": "not expanded",
            "current_configuration_available": (detail.get("structure_observation") or {}).get(
                "source"
            )
            == "current_config",
            "entity_registry_available": self.monitor.capabilities.get(
                "config/entity_registry/list"
            )
            == "available",
        }
        detail["configuration_limit"] = (
            "Observed structural projections only; baseline time is not a Home Assistant edit time."
        )
        return detail

    def overview(self):
        cases = self.cases(limit=8)
        grouped = []
        for case in cases["items"]:
            detail = case["detail"]
            identity = (detail.get("entity_id"), detail.get("run_id"))
            related = next(
                (
                    item
                    for item in grouped
                    if identity[0]
                    and identity[1]
                    and (item["detail"].get("entity_id"), item["detail"].get("run_id")) == identity
                ),
                None,
            )
            if related:
                related.setdefault("related_case_keys", []).append(case["key"])
            else:
                grouped.append(case)
        cases["items"] = grouped
        groups = self.store.rows(
            "SELECT source,count(*) n FROM issues WHERE active=1 GROUP BY source ORDER BY source"
        )
        changes = self.store.rows(
            "SELECT count(*) n FROM configuration_changes WHERE kind='changed' AND observed_at>=?",
            (time.time() - 86400,),
        )[0]["n"]
        return {
            "cases": cases,
            "active_sources": groups,
            "structural_changes_24h": changes,
            "availability_count": next(
                (r["n"] for r in groups if r["source"] == "availability"), 0
            ),
        }

    def history(self, kind, *, q="", entity="", outcome="", cursor=None, limit=50, day=None):
        """Closed query map, bounded keyset pages; no arbitrary SQL or transport."""
        tables = {
            "runs": (
                "runs r LEFT JOIN run_timing t USING(entity_id,run_id)",
                "r.*,coalesce(t.start_source,'legacy_unverified') start_source,t.observed_at",
                "r.started",
                "r.rowid",
                "r.entity_id",
                "r.outcome",
            ),
            "availability": (
                "availability r",
                "r.*",
                "r.started",
                "r.id",
                "r.entity_id",
                "r.state",
            ),
            "issues": ("issues r", "r.*", "r.last_seen", "r.rowid", "r.title", "r.source"),
            "changes": (
                "configuration_changes r LEFT JOIN automation_structures b ON b.id=r.before_id "
                "JOIN automation_structures a ON a.id=r.after_id",
                "r.*,b.projection before_projection,a.projection after_projection",
                "r.observed_at",
                "r.id",
                "r.entity_id",
                "r.kind",
            ),
            "usage": ("usage r", "r.*", "r.created", "r.id", "r.model", "r.status"),
            "analyses": ("analyses r", "r.*", "r.created", "r.id", "r.kind", "r.provider"),
        }
        if (
            kind not in tables
            or not 1 <= limit <= 100
            or len(q) > 200
            or len(entity) > 200
            or len(outcome) > 100
        ):
            raise ValueError("Invalid history filter")
        table, fields, clock, identity, search, category = tables[kind]
        where, args = [], []
        if q:
            where.append(f"instr(lower({search}),lower(?))>0")
            args.append(q)
        if entity:
            if kind not in {"runs", "availability", "changes"}:
                raise ValueError("Entity filter unavailable for this history")
            where.append("r.entity_id=?")
            args.append(entity)
        if outcome:
            where.append(category + "=?")
            args.append(outcome)
        if day:
            try:
                start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                raise ValueError("Day must be YYYY-MM-DD in UTC") from None
            where.extend([clock + ">=?", clock + "<?"])
            args.extend([start.timestamp(), (start + timedelta(days=1)).timestamp()])
        sort = f"coalesce({clock},-1)"
        if cursor:
            try:
                if len(cursor) > 400:
                    raise ValueError
                position = json.loads(base64.urlsafe_b64decode(cursor))
                at, row_id = position["at"], position["id"]
                if (
                    position["kind"] != kind
                    or not isinstance(at, (float, int))
                    or not math.isfinite(at)
                    or not isinstance(row_id, int)
                ):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise ValueError("Invalid history cursor") from None
            where.append(f"({sort}<? OR ({sort}=? AND {identity}<?))")
            args.extend([at, at, row_id])
        filters = " WHERE " + " AND ".join(where) if where else ""
        rows = self.store.rows(
            f"SELECT {fields},{sort} _sort,{identity} _id FROM {table}"
            + filters
            + f" ORDER BY {sort} DESC,{identity} DESC LIMIT ?",
            (*args, limit + 1),
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = None
        if more:
            last = rows[-1]
            next_cursor = base64.urlsafe_b64encode(
                json.dumps({"kind": kind, "at": last["_sort"], "id": last["_id"]}).encode()
            ).decode()
        for row in rows:
            row.pop("_sort")
            row.pop("_id")
            if kind == "changes":
                row["delta"] = configuration_delta(
                    decoded(row.pop("before_projection")),
                    decoded(row.pop("after_projection"), {}),
                    row["kind"],
                )
        return {
            "kind": kind,
            "items": rows,
            "next_cursor": next_cursor,
            "limit": limit,
            "day_basis": "UTC",
            "coverage": "Retained observations only. Unknown run starts sort last; "
            "legacy timestamps remain unverified.",
        }
