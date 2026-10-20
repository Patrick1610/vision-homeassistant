"""Bounded structural evidence. Never evaluate templates or retain action payloads."""

import hashlib
import json
import re
from datetime import datetime

ENTITY_ID = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z0-9_]+$")
OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SERVICE = ENTITY_ID
BRANCHES = {"choose", "default", "if", "then", "else", "sequence", "parallel", "while", "until"}
TRACE_TOKENS = BRANCHES | {
    "trigger",
    "condition",
    "action",
    "conditions",
    "repeat",
    "wait_for_trigger",
    "wait_template",
    "stop",
    "event",
    "variables",
    "delay",
}
_PATH_TOKEN = r"(?:\d+|" + "|".join(sorted(TRACE_TOKENS)) + ")"
PATH = re.compile("^" + _PATH_TOKEN + "(?:/" + _PATH_TOKEN + ")*$")
MAX_NODES = 1000
MAX_STEPS = 500
MAX_ERRORS = 100
MAX_DEPTH = 20
# Official HA helpers/trace.py: each action path deque keeps at most 20 elements.
HA_ACTION_PATH_LIMIT = 20
SAFE_STATES = {
    "on",
    "off",
    "open",
    "closed",
    "locked",
    "unlocked",
    "available",
    "unavailable",
    "unknown",
}
TRIGGERS = {
    "state",
    "numeric_state",
    "time",
    "time_pattern",
    "sun",
    "event",
    "homeassistant",
    "mqtt",
    "webhook",
    "zone",
    "geo_location",
    "device",
    "calendar",
    "conversation",
    "template",
    "persistent_notification",
    "tag",
}
CONDITIONS = {
    "and",
    "or",
    "not",
    "state",
    "numeric_state",
    "sun",
    "time",
    "zone",
    "template",
    "trigger",
    "device",
}


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def contains_template(value, depth=0):
    if depth > MAX_DEPTH:
        return True  # Uninspected input cannot prove static completeness.
    if isinstance(value, str):
        return any(marker in value for marker in ("{{", "{%", "{#"))
    if isinstance(value, dict):
        return any(contains_template(v, depth + 1) for v in value.values())
    if isinstance(value, list):
        return any(contains_template(v, depth + 1) for v in value)
    return False


def duration(value):
    """Only literal duration shapes; templates remain unknown."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and 0 <= value <= 31536000:
        return float(value)
    if isinstance(value, str) and re.fullmatch(r"\d{1,3}:\d{2}:\d{2}(?:\.\d+)?", value):
        hours, minutes, seconds = map(float, value.split(":"))
        return hours * 3600 + minutes * 60 + seconds if minutes < 60 and seconds < 60 else None
    if isinstance(value, dict) and set(value) <= {
        "days",
        "hours",
        "minutes",
        "seconds",
        "milliseconds",
    }:
        factors = {"days": 86400, "hours": 3600, "minutes": 60, "seconds": 1, "milliseconds": 0.001}
        if all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
            for v in value.values()
        ):
            total = sum(value[k] * factors[k] for k in value)
            return float(total) if total <= 31536000 else None
    return None


def structure(config):
    """Project automation control flow/references, excluding arbitrary text/payloads."""
    nodes, references = [], []
    coverage = {
        "truncated": False,
        "dynamic_references": False,
        "reference_scan": "AST nodes and recursively bounded target/data values",
    }

    def refs(value, path, role, depth=0):
        if depth > MAX_DEPTH or len(references) >= MAX_NODES:
            coverage["truncated"] = True
            return
        if isinstance(value, dict):
            for key in sorted(value):
                child = value[key]
                if key in {"entity_id", "device_id", "area_id", "label_id"}:
                    for candidate in child if isinstance(child, list) else [child]:
                        if not isinstance(candidate, str):
                            coverage["dynamic_references"] = True
                        elif contains_template(candidate):
                            coverage["dynamic_references"] = True
                        elif (ENTITY_ID if key == "entity_id" else OPAQUE_ID).fullmatch(candidate):
                            if len(references) < MAX_NODES:
                                references.append(
                                    {"kind": key[:-3], "id": candidate, "path": path, "role": role}
                                )
                            else:
                                coverage["truncated"] = True
                        else:
                            coverage["dynamic_references"] = True
                elif key in {"target", "data"} or depth:
                    # Data can contain declared references; never retain its other values.
                    refs(child, path, role if key == "target" else "declared", depth + 1)
        elif isinstance(value, list):
            for child in value:
                if len(references) >= MAX_NODES:
                    coverage["truncated"] = True
                    break
                refs(child, path, role, depth + 1)

    def walk(value, path, role, depth=0):
        if depth > MAX_DEPTH or len(nodes) >= MAX_NODES:
            coverage["truncated"] = True
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                if len(nodes) >= MAX_NODES:
                    coverage["truncated"] = True
                    break
                walk(child, f"{path}/{index}", role, depth + 1)
            return
        if not isinstance(value, dict):
            if contains_template(value):
                coverage["dynamic_references"] = True
                nodes.append(
                    {
                        "path": path,
                        "role": role,
                        "kind": "template",
                        "has_template": True,
                        "predicate_coverage": "source omitted",
                    }
                )
            return
        node = {"path": path, "role": role, "kind": role}
        trigger = value.get("trigger", value.get("platform"))
        condition = value.get("condition")
        if role == "trigger":
            node["kind"] = (
                trigger if isinstance(trigger, str) and trigger in TRIGGERS else "unknown_trigger"
            )
        elif isinstance(condition, str):
            node["kind"] = condition if condition in CONDITIONS else "unknown_condition"
        else:
            for key in (
                "choose",
                "if",
                "repeat",
                "parallel",
                "wait_template",
                "wait_for_trigger",
                "delay",
                "stop",
                "event",
                "variables",
            ):
                if key in value:
                    node["kind"] = key
                    break
            service = value.get("action", value.get("service"))
            if isinstance(service, str) and SERVICE.fullmatch(service):
                node.update(kind="service", service=service)
            elif service is not None:
                node["kind"] = "dynamic_service"
        if "continue_on_error" in value:
            node["continue_on_error"] = value["continue_on_error"] is True
        if "timeout" in value:
            node["timeout"] = {"present": True, "seconds": duration(value["timeout"])}
            node["continue_on_timeout"] = value.get("continue_on_timeout", True) is not False
        if "delay" in value:
            node["delay_seconds"] = duration(value["delay"])
        if role in {"trigger", "condition"} or isinstance(condition, str):
            predicate = {}
            omitted = []
            for key in ("above", "below"):
                operand = value.get(key)
                if (
                    isinstance(operand, (int, float))
                    and not isinstance(operand, bool)
                    and -1e12 <= operand <= 1e12
                ):
                    predicate[key] = operand
                elif isinstance(operand, str) and ENTITY_ID.fullmatch(operand):
                    predicate[key] = {"entity_reference": operand}
                    if len(references) < MAX_NODES:
                        references.append(
                            {"kind": "entity", "id": operand, "path": path, "role": role}
                        )
                    else:
                        coverage["truncated"] = True
                elif key in value:
                    omitted.append(key)
            for key in ("state", "from", "to"):
                operand = value.get(key)
                if isinstance(operand, str) and operand in SAFE_STATES:
                    predicate[key] = operand
                elif key in value:
                    omitted.append(key)
            if "for" in value:
                predicate["for_seconds"] = duration(value["for"])
                if predicate["for_seconds"] is None:
                    omitted.append("for")
            at = value.get("at")
            if isinstance(at, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", at):
                predicate["at"] = at
            elif "at" in value:
                omitted.append("at")
            if predicate:
                node["predicate"] = predicate
            if any(
                key in value
                for key in ("value_template", "attribute", "zone", "event_data", "payload")
            ):
                omitted.append("additional predicate source")
            node["predicate_coverage"] = "partial" if omitted else "typed operands only"
            if omitted:
                node["omitted_predicates"] = omitted
        if contains_template(value):
            node["has_template"] = True
            coverage["dynamic_references"] = True
        nodes.append(node)
        refs(value, path, role)
        for key in sorted(BRANCHES | {"conditions", "wait_for_trigger"}):
            if key in value:
                child_role = (
                    "condition" if key in {"if", "while", "until", "conditions"} else "action"
                )
                if key == "wait_for_trigger":
                    child_role = "trigger"
                walk(value[key], path + "/" + key, child_role, depth + 1)
        repeat = value.get("repeat")
        if isinstance(repeat, dict):
            for key in ("sequence", "while", "until"):
                if key in repeat:
                    walk(
                        repeat[key],
                        path + "/repeat/" + key,
                        "condition" if key != "sequence" else "action",
                        depth + 1,
                    )

    counts = {}
    for plural, singular in (
        ("triggers", "trigger"),
        ("conditions", "condition"),
        ("actions", "action"),
    ):
        value = config.get(plural, config.get(singular, []))
        counts[plural] = len(value) if isinstance(value, list) else int(bool(value))
        walk(value, singular, singular)
    mode = config.get("mode")
    result = {
        "schema_version": 1,
        **counts,
        "mode": mode
        if isinstance(mode, str) and mode in {"single", "restart", "queued", "parallel"}
        else "single",
        "nodes": nodes,
        "references": references,
        "referenced_entities": sorted({r["id"] for r in references if r["kind"] == "entity"}),
        "coverage": coverage,
    }
    max_runs = config.get("max")
    if isinstance(max_runs, int) and not isinstance(max_runs, bool) and 1 <= max_runs <= 10000:
        result["max_runs"] = max_runs
    return result


def error_kind(message):
    text = str(message).lower()
    if any(word in text for word in ("template", "undefinederror", "jinja")):
        return "template_error"
    if any(word in text for word in ("timeout", "timed out")):
        return "timeout"
    if any(
        word in text for word in ("not found", "unknown entity", "unavailable entity", "no entity")
    ):
        return "missing_target"
    return "step_error"


def trace_summary(trace, redactor, outcome):
    """All retained steps, separately from whole-run outcome; no variables/config."""
    steps, errors = [], []
    count = 0
    error_count = 0
    truncated = False
    malformed = False
    errors_truncated = False
    source_truncated = False
    unrecognized_paths = 0
    start_time = trace.get("timestamp")
    start_time = trace_time(start_time.get("start")) if isinstance(start_time, dict) else None
    raw_steps = trace.get("trace")
    for path, elements in raw_steps.items() if isinstance(raw_steps, dict) else []:
        if not isinstance(elements, list):
            malformed = True
            continue
        count += len(elements)
        if (
            isinstance(path, str)
            and path.startswith("action/")
            and len(elements) >= HA_ACTION_PATH_LIMIT
        ):
            source_truncated = True
        if isinstance(path, str) and len(path) <= 200 and PATH.fullmatch(path):
            safe_path = path
        else:
            unrecognized_paths += 1
            safe_path = "unrecognized_path:" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
        for index, element in enumerate(elements):
            if len(steps) >= MAX_STEPS:
                truncated = True
                break
            if not isinstance(element, dict):
                malformed = True
                continue
            item = {"path": safe_path, "iteration": index}
            observed_at = trace_time(element.get("timestamp"))
            if observed_at is not None:
                item["observed_at"] = observed_at
                if start_time is not None:
                    item["offset_seconds"] = observed_at - start_time
            result = element.get("result")
            result = result if isinstance(result, dict) else {}
            for key in ("result", "done", "timeout", "error"):
                if isinstance(result.get(key), bool):
                    item[key] = result[key]
            wait = result.get("wait")
            if isinstance(wait, dict) and isinstance(wait.get("completed"), bool):
                item["wait_completed"] = wait["completed"]
                if (
                    wait["completed"] is False
                    and not isinstance(wait.get("remaining"), bool)
                    and wait.get("remaining") == 0
                ):
                    item["wait_timed_out"] = True
            if "stop" in result:
                item["explicit_stop"] = True
            messages = []
            if element.get("error"):
                messages.append(("error", element["error"]))
            template_errors = element.get("template_errors")
            template_messages = (
                template_errors
                if isinstance(template_errors, list)
                else ([template_errors] if template_errors else [])
            )
            observed_errors = len(messages) + len(template_messages)
            if observed_errors > 10:
                errors_truncated = True
            for message in template_messages[:10]:
                messages.append(("template_error", message))
            if result.get("error") is True and not element.get("error"):
                messages.append(("error", "Explicit stop with error"))
                observed_errors += 1
            if observed_errors > 10:
                errors_truncated = True
            error_count += observed_errors
            retained_before = len(errors)
            for kind, message in messages[:10]:
                # Only strings are useful; arbitrary nested result data is never copied.
                safe = (
                    redactor.text(message, 800)
                    if isinstance(message, str)
                    else "Execution step error"
                )
                if len(errors) < MAX_ERRORS:
                    errors.append(
                        {
                            "path": safe_path,
                            "iteration": index,
                            "kind": kind if kind == "template_error" else error_kind(safe),
                            "message": safe,
                        }
                    )
                else:
                    errors_truncated = True
            item["errors"] = observed_errors
            item["errors_observed"] = observed_errors
            item["errors_retained"] = len(errors) - retained_before
            steps.append(item)
    timestamps = trace.get("timestamp")
    elapsed = None
    if isinstance(timestamps, dict):
        try:
            start, finish = (
                datetime.fromisoformat(timestamps[k].replace("Z", "+00:00"))
                for k in ("start", "finish")
            )
            elapsed = max(0, (finish - start).total_seconds())
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
    return {
        "schema_version": 1,
        "steps": steps,
        "step_count": count,
        "errors": errors,
        "error_count": error_count,
        "duration_seconds": elapsed,
        "completed_with_errors": outcome == "succeeded" and error_count > 0,
        "coverage": {
            "full_trace_available": isinstance(raw_steps, dict),
            "step_timestamp_semantics": "step_start",
            "abort_reason_unknown": trace.get("script_execution") == "aborted"
            and outcome == "stopped",
            "truncated": truncated,
            "errors_truncated": errors_truncated,
            "malformed_elements": malformed,
            "source_path_limit_reached": source_truncated,
            "unrecognized_paths": unrecognized_paths,
            "error_count_is_lower_bound": truncated
            or malformed
            or source_truncated
            or unrecognized_paths > 0
            or not isinstance(raw_steps, dict),
        },
    }


def trace_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def dependency_graph(entities, registry, devices, structures):
    """Typed observed inventory and declared targets; area/label expansion is unknown."""
    nodes, edges = {}, set()

    def node(kind, identifier):
        key = kind + ":" + identifier
        nodes[key] = {"key": key, "kind": kind, "identifier": identifier}
        return key

    def edge(source, target, relation, path=""):
        edges.add((source, target, relation, path))

    for device in devices:
        if isinstance(device.get("id"), str):
            node("device", device["id"])
    for entity_id in entities.keys() | registry.keys():
        entity = node("entity", entity_id)
        entry = registry.get(entity_id, {})
        device_id = entry.get("device_id")
        platform = entry.get("platform")
        if isinstance(device_id, str):
            edge(node("device", device_id), entity, "contains")
        if isinstance(platform, str) and re.fullmatch(r"[a-z0-9_]{1,100}", platform):
            integration = node("integration", platform)
            edge(integration, entity, "provides")
            if isinstance(device_id, str):
                edge(integration, node("device", device_id), "provides")
        if entity_id.startswith("automation."):
            edge(node("automation", entity_id), entity, "represented_by")
    for entity_id, projection in structures.items():
        source = node("automation", entity_id)
        for ref in projection.get("references", []):
            kind = ref["kind"]
            if kind in {"entity", "device"}:
                target = node(kind, ref["id"])
            else:
                target = node("target", kind + ":" + ref["id"])
            edge(
                source,
                target,
                {"trigger": "triggered_by", "condition": "condition_uses", "action": "targets"}.get(
                    ref["role"], "declares"
                ),
                ref["path"],
            )
    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["key"]),
        "edges": [
            {"source": s, "target": t, "relation": r, "path": p} for s, t, r, p in sorted(edges)
        ],
        "coverage": "Declared static references only; templates and area/label membership "
        "are not expanded.",
    }
