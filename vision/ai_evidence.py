"""Task-focused bounded local evidence. This module has no HA/network transport."""

import copy
import json
import re
import time

from .ai_contract import TASKS
from .ai_privacy import DiagnosticAliases
from .evidence import fingerprint
from .insights import STATUS_SQL, decoded

MAX_RECORDS = 120
MAX_BUNDLE_BYTES = 48000
COMMUNICATION = re.compile(
    r"(?i)did not respond|failed to send|communication (?:error|failed|failure|timeout)|"
    r"no response|device.{0,30}timed? out"
)


def is_communication_error(error):
    return error.get("kind") != "template_error" and bool(
        COMMUNICATION.search(error.get("message", ""))
    )


def resolve(monitor, request):
    if request.kind == "audit":
        if request.target or request.run_id or request.compare:
            raise ValueError("An audit has no dossier or run selection")
        return None, None
    if not request.target:
        raise ValueError("Select a retained dossier or entity")
    rows = monitor.store.rows("SELECT * FROM issues WHERE key=?", (request.target,))
    case = rows[0] if rows else None
    detail = decoded(case["detail"], {}) if case else {}
    entity = detail.get("entity_id") if case else request.target
    if not case and not monitor.entity_view(entity):
        raise ValueError("Target is outside the local inventory and retained cases")
    if request.kind in {"automation", "optimization"} and not (
        entity and entity.startswith("automation.")
    ):
        raise ValueError("Select an automation for this task")
    if (request.run_id or request.compare) and not (entity and entity.startswith("automation.")):
        raise ValueError("Run selection requires the dossier's automation")
    if request.compare and not request.run_id:
        raise ValueError("Select the first run before a comparison")
    return entity, case


def communication_context(monitor, sections):
    """A failing action's declared physical targets supply device context, not the automation."""
    paths = sorted(
        {error["path"] for error in sections["errors"] if is_communication_error(error)},
        key=len,
        reverse=True,
    )
    run_shapes = [shape for shape in sections["structure"] if shape["source"] == "selected_run"]
    refs = [
        ref
        for shape in run_shapes
        for ref in shape["references"]
        if ref["kind"] in {"entity", "device"} and ref.get("role") in {"action", "declared"}
    ]
    targets, devices, platforms = set(), set(), set()
    for path in paths:
        matching = [ref for ref in refs if ref["path"] == path]
        for ref in matching[:8]:
            if ref["kind"] == "entity":
                targets.add(ref["id"])
            else:
                devices.add(ref["id"])
        if matching:
            break  # The most specific failed path, rather than an enclosing branch.
    # Expand explicit device targets only. Entity targets keep their sibling entities
    # as contrary/confirming context instead of reclassifying every device member.
    explicit_devices = set(devices)
    members = [
        entity
        for entity, entry in sorted(monitor.registry.items())
        if entry.get("device_id") in explicit_devices and not entity.startswith("automation.")
    ]
    targets.update(members[:8])
    for entity in targets:
        entry = monitor.registry.get(entity, {})
        if entry.get("device_id"):
            devices.add(entry["device_id"])
        if entry.get("platform"):
            platforms.add(entry["platform"])
    siblings = []
    for entity, entry in sorted(monitor.registry.items()):
        if entity.startswith("automation.") or entity in targets:
            continue
        if entry.get("device_id") in devices or entry.get("platform") in platforms:
            view = monitor.entity_view(entity) or {}
            siblings.append(
                {
                    "entity_id": entity,
                    "device_id": entry.get("device_id"),
                    "platform": entry.get("platform"),
                    "availability": view.get("availability"),
                }
            )
    healthy = [row for row in siblings if row["availability"] == "available"]
    unhealthy = [row for row in siblings if row["availability"] != "available"]
    sections["siblings"] = healthy[:8] + unhealthy[:8]
    sections["availability"] = []
    sections["dependencies"] = []
    for entity in sorted(targets)[:8]:
        entry = monitor.registry.get(entity, {})
        sections["target"].append(
            {
                "entity_id": entity,
                "device_id": entry.get("device_id"),
                "platform": entry.get("platform"),
                "role": "failing_declared_target",
                "availability": (monitor.entity_view(entity) or {}).get("availability"),
            }
        )
        rows = monitor.store.rows(
            "SELECT state,started,ended,uncertain FROM availability WHERE entity_id=? "
            "ORDER BY started DESC,id DESC LIMIT 4",
            (entity,),
        )
        sections["availability"].extend({**row, "entity_id": entity} for row in rows)
        sections["dependencies"].extend(monitor.insights.impact(entity)["relations"][:4])
    sections["coverage"].append(
        {
            "physical_target_context_known": bool(targets or devices),
            "physical_target_members_omitted": max(0, len(members) - 8),
            "siblings_omitted": max(0, len(siblings) - len(sections["siblings"])),
        }
    )


def capture(monitor, request):
    """Frozen enum-section snapshot: only bounded projections already retained locally."""
    if request.target_type == "device":
        from .ai_devices import capture_device

        return capture_device(monitor, request)
    entity, case = resolve(monitor, request)
    insights, store = monitor.insights, monitor.store
    sections = {
        name: []
        for name in (
            "coverage",
            "inventory",
            "target",
            "outcomes",
            "availability",
            "case",
            "steps",
            "errors",
            "structure",
            "dependencies",
            "changes",
            "comparison",
            "siblings",
        )
    }
    sections["coverage"] = [
        {
            "type": "coverage",
            "connected": monitor.connected,
            "capabilities_available": sum(v == "available" for v in monitor.capabilities.values()),
            "capabilities_total": len(monitor.capabilities),
            "observation_gaps_exist": bool(store.get_meta("last_gap")),
            "step_time_semantics": "step_start",
            "raw_source_not_retained": True,
        }
    ]
    sections["inventory"] = [
        {
            "type": "inventory",
            "entity_count": len(monitor.entities.keys() | monitor.registry.keys()),
            "device_count": len(monitor.devices),
            "automation_count": sum(key.startswith("automation.") for key in monitor.entities),
        }
    ]
    selected = None
    run_id = request.run_id
    if not run_id and case:
        run_id = decoded(case["detail"], {}).get("run_id")
    selection_basis = "explicit" if request.run_id else "linked_case"
    current_case = bool(case and case["source"] == "static")
    if current_case and not run_id:
        selection_basis = "current_configuration_only"
    if entity and entity.startswith("automation."):
        if not run_id and not current_case:
            rows = store.rows(
                "SELECT r.run_id FROM runs r LEFT JOIN run_timing t USING(entity_id,run_id) "
                "WHERE r.entity_id=? AND r.run_id NOT LIKE 'event:%' "
                "ORDER BY (t.start_source='ha_trace') DESC,r.started DESC,r.run_id DESC LIMIT 1",
                (entity,),
            )
            run_id = rows[0]["run_id"] if rows else None
            selection_basis = "latest_retained" if run_id else "none"
        if run_id:
            selected = insights.run(entity, run_id)
        sections["outcomes"] = store.rows(
            "SELECT outcome,count(*) count,sum(triggered) observed_triggers FROM runs "
            "WHERE entity_id=? GROUP BY outcome ORDER BY outcome LIMIT 10",
            (entity,),
        )
    elif request.kind == "audit":
        sections["outcomes"] = store.rows(
            "SELECT outcome,count(*) count,sum(triggered) observed_triggers FROM runs "
            "GROUP BY outcome ORDER BY outcome LIMIT 10"
        )
    if entity:
        view = monitor.entity_view(entity) or {
            "entity_id": entity,
            "availability": "not_in_inventory",
        }
        registry = monitor.registry.get(entity, {})
        sections["target"] = [
            {
                "type": "target",
                "entity_id": entity,
                "availability": view.get("availability"),
                "device_id": registry.get("device_id"),
                "platform": registry.get("platform"),
                "disabled": bool(registry.get("disabled_by")),
                "expected_offline": store.expected(entity),
                "run_id": run_id,
                "outcome": selected["outcome"] if selected else None,
                "start_source": selected["start_source"] if selected else "unknown",
            }
        ]
        sections["availability"] = store.rows(
            "SELECT state,started,ended,uncertain FROM availability WHERE entity_id=? "
            "ORDER BY started DESC,id DESC LIMIT 20",
            (entity,),
        )
        for row in sections["availability"]:
            row["entity_id"] = entity
        related = []
        for other, entry in sorted(monitor.registry.items()):
            if other == entity:
                continue
            same = bool(
                registry.get("device_id") and entry.get("device_id") == registry["device_id"]
            )
            same |= bool(registry.get("platform") and entry.get("platform") == registry["platform"])
            if same:
                other_view = monitor.entity_view(other) or {}
                related.append(
                    {
                        "entity_id": other,
                        "device_id": entry.get("device_id"),
                        "platform": entry.get("platform"),
                        "availability": other_view.get("availability"),
                    }
                )
        # Include healthy and unavailable siblings instead of only confirming observations.
        healthy = [row for row in related if row["availability"] == "available"]
        unhealthy = [row for row in related if row["availability"] != "available"]
        sections["siblings"] = healthy[:8] + unhealthy[:8]
        if len(related) > len(sections["siblings"]):
            sections["coverage"].append(
                {"siblings_omitted": len(related) - len(sections["siblings"])}
            )
        impact = insights.impact(entity)
        sections["dependencies"] = impact["relations"][:30]
        sections["coverage"].append(
            {
                "dependency_relations_omitted": impact["truncated"]
                or len(impact["relations"]) > 30,
                "entity_registry_available": monitor.capabilities.get("config/entity_registry/list")
                == "available",
                "area_label_expansion": "unknown",
            }
        )
        rows = store.rows(
            "SELECT observed_at,kind,source FROM configuration_changes WHERE entity_id=? "
            "ORDER BY observed_at DESC,id DESC LIMIT 8",
            (entity,),
        )
        sections["changes"] = rows
    cases = (
        [case]
        if case
        else (
            store.rows(
                "SELECT * FROM issues WHERE json_extract(detail,'$.entity_id')=? "
                "ORDER BY active DESC,last_seen DESC,key LIMIT 8",
                (entity,),
            )
            if entity
            else insights.cases(limit=16)["items"]
        )
    )
    status_keys = [item["key"] for item in cases if "status" not in item]
    statuses = {
        row["key"]: row["status"]
        for row in (
            store.rows(
                "SELECT i.key," + STATUS_SQL + " status FROM issues i "
                "LEFT JOIN case_annotations a ON a.key=i.key "
                "AND a.case_first_seen=i.first_seen WHERE i.key IN ("
                + ",".join("?" for _ in status_keys)
                + ")",
                (time.time(), time.time(), *status_keys),
            )
            if status_keys
            else []
        )
    }
    for item in cases:
        detail = decoded(item["detail"], {})
        sections["case"].append(
            {
                "source": item["source"],
                "severity": item["severity"],
                "active": bool(item["active"]),
                "occurrences": item["occurrences"],
                "first_seen": item["first_seen"],
                "last_seen": item["last_seen"],
                "rule": detail.get("rule"),
                "domain": detail.get("domain"),
                "issue_id": detail.get("issue_id"),
                "entity_id": detail.get("entity_id"),
                "run_id": detail.get("run_id"),
                "path": detail.get("path"),
                "target": detail.get("target"),
                "message": detail.get("message"),
                "coverage": detail.get("coverage"),
                "local_status": item.get("status", statuses.get(item["key"], "unknown")),
            }
        )
    shapes = []
    if selected and selected.get("configuration"):
        shapes.append(("selected_run", selected["configuration"], selected["configuration_digest"]))
    current = (
        store.rows(
            "SELECT s.projection,s.digest,c.source FROM automation_current c "
            "JOIN automation_structures s ON s.id=c.structure_id WHERE c.entity_id=?",
            (entity,),
        )
        if entity
        else []
    )
    if current and current[0]["source"] == "current_config":
        shapes.append(
            ("current_observed", decoded(current[0]["projection"], {}), current[0]["digest"])
        )
    elif not shapes and monitor.structures.get(entity):
        shape = monitor.structures[entity]
        shapes.append(("historical_unbound", shape, fingerprint(shape)))
    for source, shape, digest in shapes:
        refs = copy.deepcopy(shape.get("references", [])[:1000])
        for ref in refs:
            if ref["kind"] == "entity":
                entry = monitor.registry.get(ref["id"])
                ref["present"] = (
                    True
                    if ref["id"] in monitor.entities or entry is not None
                    else (
                        False
                        if monitor.capabilities.get("config/entity_registry/list") == "available"
                        else None
                    )
                )
                ref["disabled"] = bool((entry or {}).get("disabled_by"))
            elif ref["kind"] == "device":
                ref["present"] = (
                    True
                    if any(d.get("id") == ref["id"] for d in monitor.devices)
                    else (
                        False
                        if monitor.capabilities.get("config/device_registry/list") == "available"
                        else None
                    )
                )
            else:
                ref["present"] = None  # Dynamic/area/label expansion is not available.
        sections["structure"].append(
            {
                "source": source,
                "configuration_digest": digest,
                "mode": shape.get("mode"),
                "max_runs": shape.get("max_runs"),
                "triggers": shape.get("triggers"),
                "conditions": shape.get("conditions"),
                "actions": shape.get("actions"),
                "nodes": shape.get("nodes", [])[:1000],
                "references": refs,
                "coverage": shape.get("coverage", {}),
            }
        )
    if selected:
        summary = selected["evidence"] or {}
        sections["steps"] = summary.get("steps", [])[:500]
        sections["errors"] = summary.get("errors", [])[:100]
        sections["coverage"].append(
            {
                "run_id": run_id,
                "start_source": selected["start_source"],
                "coverage": summary.get("coverage"),
                "unknown": selected["evidence_unknown_reason"],
                "completed_with_errors": summary.get("completed_with_errors"),
            }
        )
    if request.kind == "device_communication":
        communication_context(monitor, sections)
    if request.compare:
        compared = insights.comparison(entity, run_id, request.compare)
        right = compared["right"]
        sections["comparison"] = [
            {
                "run_id": right["run_id"],
                "outcome": right["outcome"],
                "configuration_digest": right["configuration_digest"],
                "same_configuration": compared["comparable"],
                "coverage_limited": compared["coverage_limited"],
                "steps": (right["evidence"] or {}).get("steps", [])[:500],
                "errors": (right["evidence"] or {}).get("errors", [])[:100],
            }
        ]
    return {
        "captured_at": time.time(),
        "sections": relevant(request.kind, sections, selected["outcome"] if selected else None),
        "entity": entity,
        "run_id": run_id,
        "compare": request.compare,
        "selection_basis": selection_basis,
        "selected_outcome": selected["outcome"] if selected else None,
    }


def relevant(kind, sections, outcome):
    """Distinct path/error selection, not only a task label or section-name change."""
    steps, errors = sections["steps"], sections["errors"]
    if kind == "missing_target":
        sections = copy.deepcopy(sections)
        sections["structure"] = [
            s for s in sections["structure"] if s["source"] == "current_observed"
        ]
    if kind == "template_error":
        errors = [e for e in errors if e.get("kind") == "template_error"]
    elif kind == "device_communication":
        errors = [e for e in errors if is_communication_error(e)]
    elif kind == "timeout":
        wait_paths = {
            s["path"]
            for s in steps
            if s.get("timeout") or s.get("wait_timed_out") or "wait_completed" in s
        }
        wait_paths.update(
            node["path"]
            for shape in sections["structure"]
            if shape["source"] == "selected_run"
            for node in shape["nodes"]
            if node["kind"] in {"wait_template", "wait_for_trigger"}
        )
        errors = [
            e
            for e in errors
            if e.get("kind") == "timeout"
            and e["path"] in wait_paths
            and not is_communication_error(e)
        ]
    if kind in {"template_error", "device_communication", "timeout"}:
        paths = {e["path"] for e in errors}
        if kind == "timeout":
            paths.update(s["path"] for s in steps if s.get("timeout") or s.get("wait_timed_out"))
        steps = [s for s in steps if s["path"] in paths]
    elif kind == "condition_stop":
        steps = (
            [s for s in steps if s.get("result") is False] if outcome == "condition_stopped" else []
        )
        errors = []
    elif kind == "optimization":
        delay_paths = {
            n["path"]
            for shape in sections["structure"]
            for n in shape["nodes"]
            if n["kind"] == "delay"
        }
        steps = [
            s
            for s in steps
            if s["path"] in delay_paths
            or any(key in s for key in ("wait_completed", "wait_timed_out"))
        ]
    else:
        paths = {e["path"] for e in errors}
        steps = sorted(steps, key=lambda s: (s["path"] not in paths, s["path"], s["iteration"]))
    result = copy.deepcopy(sections)
    result["steps"], result["errors"] = steps[:32], errors[:20]
    focus = {s["path"] for s in steps[:32]} | {e["path"] for e in errors[:20]}
    for shape in result["structure"]:
        nodes = shape["nodes"]
        if kind == "missing_target":
            refs = shape["references"]
            missing_paths = {ref["path"] for ref in refs if ref.get("present") is False}
            focus.update(missing_paths or {ref["path"] for ref in refs})
        shape["nodes"] = sorted(nodes, key=lambda n: (n["path"] not in focus, n["path"]))[:40]
        shape["references"] = [
            r for r in shape["references"] if r["path"] in {n["path"] for n in shape["nodes"]}
        ][:40]
        shape["coverage"] = {**shape["coverage"], "nodes_omitted": len(nodes) - len(shape["nodes"])}
    for comparison in result["comparison"]:
        comparison["steps"] = [s for s in comparison["steps"] if s["path"] in focus][:32]
        comparison["errors"] = [e for e in comparison["errors"] if e["path"] in focus][:20]
        if not comparison["same_configuration"]:
            comparison["steps"], comparison["errors"] = [], []
    supported = True
    if kind in {"template_error", "timeout", "device_communication", "condition_stop"}:
        supported = bool(steps or errors)
    elif kind == "optimization":
        supported = bool(steps) and any(c["same_configuration"] for c in result["comparison"])
    elif kind == "mode_conflict":
        supported = outcome == "blocked"
    elif kind == "missing_target":
        supported = any(
            ref.get("present") is False
            for shape in result["structure"]
            for ref in shape["references"]
        )
    elif kind == "availability":
        supported = any(
            row.get("state") in {"unknown", "unavailable"} for row in result["availability"]
        ) or any(
            target.get("availability") in {"unknown", "unavailable"} for target in result["target"]
        )
    result["coverage"].append(
        {
            "task_matching_steps": len(steps),
            "task_matching_errors": len(errors),
            "selected_steps_omitted": max(0, len(steps) - 32),
            "selected_errors_omitted": max(0, len(errors) - 20),
            "prerequisite_supported": supported,
        }
    )
    return result


PREREQUISITE_REASONS = {
    "template_error": "No matching retained template-error step is available.",
    "device_communication": "No matching retained device-communication error is available.",
    "timeout": "No matching retained wait-timeout observation is available.",
    "condition_stop": "No decisive retained condition-stop observation is available.",
    "optimization": "No matching retained wait/delay and comparable configuration are available.",
    "mode_conflict": "No retained refused-start outcome is available.",
    "missing_target": "No explicit currently missing reference is established within coverage.",
    "availability": "No retained offline episode or current offline observation is available.",
}


def readiness(snapshot, kind):
    supported = not any(
        row.get("prerequisite_supported") is False for row in snapshot["sections"]["coverage"]
    )
    return {
        "supported": supported,
        "reason": None
        if supported
        else PREREQUISITE_REASONS.get(kind, "The required retained observations are unavailable."),
    }


def compact(section, value, captured_at):
    """The compact profile excludes source text, identifiers, operands and raw steps."""
    if section in {"coverage", "inventory"}:
        if section == "inventory":
            return value
        safe = {
            k: v
            for k, v in value.items()
            if k
            in {
                "type",
                "connected",
                "capabilities_available",
                "capabilities_total",
                "observation_gaps_exist",
                "prerequisite_supported",
                "task_matching_steps",
                "task_matching_errors",
                "selected_steps_omitted",
                "selected_errors_omitted",
                "completed_with_errors",
                "entity_registry_available",
                "dependency_relations_omitted",
                "start_source",
                "reliable_now",
                "cache_pending",
                "device_members_observed",
                "device_members_omitted",
                "device_history_omitted",
                "device_coverage_gaps",
                "device_coverage_gaps_limited",
                "correlated_devices_observed",
                "correlated_devices_omitted",
                "measurement_started",
                "coverage_available",
            }
        }
        if "coverage" in value:
            safe["trace_coverage"] = {
                k: v
                for k, v in (value.get("coverage") or {}).items()
                if isinstance(v, (bool, int)) or k == "step_timestamp_semantics"
            }
            safe["trace_coverage_unknown"] = bool(value.get("unknown")) or not value.get("coverage")
        return safe
    if section == "case":
        return {
            k: value[k] for k in ("source", "severity", "active", "occurrences", "local_status")
        }
    if section == "outcomes":
        return value
    if section == "availability":
        return {
            "status": value["state"],
            "gap": bool(value.get("uncertain")),
            "observed_seconds": value.get("observed_seconds")
            if value.get("observation_scope") == "registered_device"
            else round(max(0, (value["ended"] or captured_at) - value["started"])),
        }
    if section == "target":
        if value.get("type") in {"registered_device", "device_member"}:
            return {
                key: value[key]
                for key in (
                    "type",
                    "availability",
                    "attention",
                    "power_expectation",
                    "meaningful",
                    "unknown",
                    "unavailable",
                    "member_count",
                    "reliable_now",
                    "role",
                    "disabled",
                    "expected_offline",
                    "unassessed_members",
                    "registry_complete",
                )
                if key in value
            }
        return {
            k: value.get(k) for k in ("availability", "expected_offline", "outcome", "disabled")
        }
    if section == "structure":
        return {k: value.get(k) for k in ("source", "triggers", "conditions", "actions", "mode")}
    if section == "comparison":
        return {k: value.get(k) for k in ("outcome", "same_configuration", "coverage_limited")}
    if section == "errors":
        return {"error_kind": value.get("kind", "unknown"), "observations": 1}
    if section == "steps":
        return {
            k: value[k]
            for k in ("result", "wait_completed", "wait_timed_out", "timeout", "errors")
            if k in value
        }
    if section == "dependencies":
        kinds = {"entity", "device", "integration", "automation", "target"}
        relations = {
            "contains",
            "provides",
            "represented_by",
            "triggered_by",
            "condition_uses",
            "targets",
            "declares",
        }

        def node_kind(side):
            source = value.get(side)
            kind = source.split(":", 1)[0] if isinstance(source, str) else None
            return kind if kind in kinds else "unknown"

        return {
            "source_kind": node_kind("source"),
            "target_kind": node_kind("target"),
            "relation": value.get("relation") if value.get("relation") in relations else "unknown",
            "source_present": value.get("source_present")
            if isinstance(value.get("source_present"), bool)
            else None,
            "target_present": value.get("target_present")
            if isinstance(value.get("target_present"), bool)
            else None,
        }
    if section == "changes":
        return {
            "kind": value.get("kind")
            if value.get("kind") in {"baseline", "current_baseline", "changed"}
            else "unknown",
            "source": value.get("source")
            if value.get("source") in {"current_config", "retained_trace"}
            else "unknown",
        }
    if section == "siblings":
        availability = value.get("availability")
        safe = {
            "availability": availability
            if availability
            in {"available", "unavailable", "unknown", "online", "offline", "partial", "excluded"}
            else "unknown"
        }
        if value.get("type") == "correlated_device":
            safe.update(type="correlated_device", relation="same_integration_only")
        return safe
    raise ValueError("Unknown compact evidence section")


def project(snapshot, request, scope, redactor, identifiers=None, previous_aliases=None):
    task = TASKS[request.kind]
    # Prerequisites and gaps must survive even when large target evidence is omitted.
    allowed = tuple(dict.fromkeys(("coverage", *task.sections, *request.sections)))
    if not set(request.sections) <= set(task.extra):
        raise ValueError("Extra evidence section is outside this task's enum allowlist")
    sections = copy.deepcopy(snapshot["sections"])
    aliases = DiagnosticAliases(redactor, identifiers, previous_aliases)
    # Register every typed reference before scanning errors or dictionary keys.
    for shape in sections["structure"]:
        for ref in shape["references"]:
            aliases.identifiers[ref["id"]] = ref["kind"]
        if shape.get("configuration_digest"):
            aliases.identifiers[shape["configuration_digest"]] = "configuration"
    for name in ("target", "siblings"):
        for value in sections[name]:
            for key, kind in (
                ("entity_id", "entity"),
                ("device_id", "device"),
                ("platform", "integration"),
            ):
                if value.get(key):
                    aliases.identifiers[value[key]] = kind
    for edge in sections["dependencies"]:
        for side in ("source", "target"):
            if isinstance(edge.get(side), str) and ":" in edge[side]:
                kind, identifier = edge[side].split(":", 1)
                aliases.identifiers[identifier] = kind
    evidence, mapping, provenance = {}, {}, {}
    omitted = 0
    for section in allowed:
        for index, value in enumerate(sections[section]):
            safe = (
                compact(section, value, snapshot["captured_at"])
                if request.profile == "compact"
                else aliases.clean(value)
            )
            ref = f"{scope}:E{len(evidence) + 1}"
            candidate = {**evidence, ref: {"section": section, "value": safe}}
            if (
                len(evidence) >= MAX_RECORDS
                or len(json.dumps(candidate, ensure_ascii=False).encode()) > MAX_BUNDLE_BYTES
            ):
                omitted += 1
                continue
            evidence = candidate
            mapping[ref] = {"section": section, "index": index, "local_target": request.target}
            provenance[ref] = {"section": section, "source": "retained_local_projection"}
    bundle = {
        "evidence": evidence,
        "provenance": provenance,
        "captured_at": snapshot["captured_at"],
        "sections": list(allowed),
        "limits": {
            "max_records": MAX_RECORDS,
            "max_bytes": MAX_BUNDLE_BYTES,
            "records_omitted": omitted,
        },
        "limitations": [
            "Incomplete retained observations; source gaps and omitted predicates remain unknown.",
            "Step times are starts, not completion order. Shared dependencies do not prove cause.",
            "Raw templates, numeric states and action payloads are not available.",
        ],
    }
    # The advertised byte limit covers provenance and envelope as well as values.
    while len(json.dumps(bundle, ensure_ascii=False).encode()) > MAX_BUNDLE_BYTES and evidence:
        ref = next(reversed(evidence))
        del evidence[ref], mapping[ref], provenance[ref]
        bundle["limits"]["records_omitted"] += 1
    return bundle, mapping, aliases
