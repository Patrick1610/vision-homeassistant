"""Pseudonymous diagnostic projection. Exact preview is still required for consent."""

import re

from .security import SENSITIVE

IDENTIFIER_FIELDS = {
    "entity_id": "entity",
    "issue_id": "issue",
    "device_id": "device",
    "area_id": "area",
    "label_id": "label",
    "service": "service",
    "platform": "integration",
    "domain": "integration",
    "configuration_digest": "configuration",
    "before_digest": "configuration",
    "after_digest": "configuration",
    "run_id": "run",
    "context_id": "context",
    "config_entry_id": "configuration_entry",
    "config_subentry_id": "configuration_entry",
}
SAFE_ENUM_FIELDS = {
    "type",
    "kind",
    "severity",
    "outcome",
    "mode",
    "role",
    "state",
    "availability",
    "status",
    "confidence",
    "start_source",
    "rule",
    "path",
    "predicate_coverage",
}
STRUCTURAL_KEYS = (
    set(IDENTIFIER_FIELDS)
    | SAFE_ENUM_FIELDS
    | {
        "id",
        "target",
        "source",
        "references",
        "nodes",
        "coverage",
        "predicate",
        "above",
        "below",
        "from",
        "to",
        "at",
        "for_seconds",
        "timeout",
        "seconds",
        "present",
        "continue_on_error",
        "continue_on_timeout",
        "delay_seconds",
        "result",
        "done",
        "error",
        "errors",
        "message",
        "wait_completed",
        "wait_timed_out",
        "explicit_stop",
        "iteration",
        "offset_seconds",
        "full_trace_available",
        "truncated",
        "error_count_is_lower_bound",
        "observed_at",
    }
)
ENTITY = re.compile(r"(?<![A-Za-z0-9_.-])[a-z_][a-z0-9_]*\.[a-z0-9_]+(?![A-Za-z0-9_.-])")
ASSIGNMENT = re.compile(
    r"""(?i)["']?("""
    + "|".join(sorted(IDENTIFIER_FIELDS))
    + r""")["']?\s*[:=]\s*["']?([A-Za-z0-9_.:-]{1,200})"""
)


class DiagnosticAliases:
    def __init__(self, redactor, identifiers=None, previous=None):
        self.redactor = redactor
        self.identifiers = identifiers or {}
        self.by_value = {}
        self.mapping = {}
        for alias, record in (previous or {}).items():
            self.mapping[alias] = {**record, "kinds": list(record["kinds"])}
            self.by_value[record["local_reference"]] = alias
            self.identifiers.setdefault(record["local_reference"], record["kinds"][0])

    def alias(self, value, kind="identifier"):
        if not isinstance(value, str):
            return value
        self.identifiers.setdefault(value, kind)
        # Brackets/colon cannot equal a valid HA entity, service or opaque ID.
        if value not in self.by_value:
            alias = f"[I{len(self.by_value) + 1}]"
            self.by_value[value] = alias
            self.mapping[alias] = {"kinds": [], "local_reference": value}
        alias = self.by_value[value]
        if kind not in self.mapping[alias]["kinds"]:
            self.mapping[alias]["kinds"].append(kind)
        return alias

    def text(self, value, limit=800):
        text = self.redactor.text(str(value), limit)
        for match in ASSIGNMENT.finditer(text):
            self.identifiers.setdefault(match[2], IDENTIFIER_FIELDS[match[1].lower()])
        for match in ENTITY.finditer(text):
            self.identifiers.setdefault(match[0], "identifier")
        present = sorted(
            (value for value in self.identifiers if value in text),
            key=lambda item: (-len(item), item),
        )
        if present:
            # One substitution pass cannot reinterpret a generated alias as another raw ID.
            pattern = (
                r"(?<![A-Za-z0-9_.\[\-])(?:"
                + "|".join(map(re.escape, present))
                + r")(?![A-Za-z0-9_.\]\-])"
            )
            text = re.sub(pattern, lambda m: self.alias(m[0], self.identifiers[m[0]]), text)
        return self.redactor.text(text, limit)

    def clean(self, value, depth=0, field=None):
        if depth > 16:
            return "[DEPTH LIMIT]"
        if isinstance(value, dict):
            result = {}
            # A redacted key must never silently overwrite another retained value.
            # Reserve original structural names too, so a malicious original key
            # cannot later collide with a generated disambiguation name.
            reserved = {str(key) for key in value}
            for index, (key, item) in enumerate(value.items()):
                safe_key = key if key in STRUCTURAL_KEYS else self.text(key, 200)
                if safe_key != str(key) or safe_key in result:
                    safe_key = f"redacted_key_{index}"
                    while safe_key in result or safe_key in reserved:
                        safe_key += "_"
                if SENSITIVE.search(str(key)) or SENSITIVE.search(safe_key):
                    result[safe_key] = "[REDACTED]"
                elif key == "id" and value.get("kind") in {
                    "entity",
                    "device",
                    "area",
                    "label",
                    "service",
                    "integration",
                    "configuration",
                    "run",
                }:
                    result[safe_key] = self.alias(item, value["kind"])
                else:
                    result[safe_key] = self.clean(item, depth + 1, key)
            return result
        if isinstance(value, list):
            return [self.clean(item, depth + 1, field) for item in value[:200]]
        if isinstance(value, str):
            if field in IDENTIFIER_FIELDS:
                return self.alias(value, IDENTIFIER_FIELDS[field])
            if field == "source" and value in {
                "selected_run",
                "current_observed",
                "historical_unbound",
                "automation",
                "automation_step",
                "availability",
                "repair",
                "log",
                "static",
            }:
                return value
            if field in SAFE_ENUM_FIELDS:
                return value
            return self.text(value)
        return value
