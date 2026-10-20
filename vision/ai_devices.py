"""Frozen registered-device availability evidence; never a representative entity."""

import copy
import time

from .reliability import finite, seconds, union_intervals

SECTIONS = (
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


def balanced(rows, limit, field="availability"):
    priority = []
    for state in ("unavailable", "available", "offline", "online", "unknown", "partial"):
        match = next(
            (r for r in rows if r.get(field) == state and r.get("role") in {None, "primary"}), None
        )
        if match is not None:
            priority.append(match)
    remaining = [r for r in rows if r not in priority]
    if len(priority) >= limit:
        return priority[:limit]
    healthy = [r for r in remaining if r.get(field) in {"available", "online"}]
    other = [r for r in remaining if r.get(field) not in {"available", "online"}]
    selected = healthy[: limit // 2] + other[: limit // 2]
    selected += healthy[limit // 2 :] + other[limit // 2 :]
    return (priority + selected)[:limit]


def capture_device(monitor, request):
    if request.kind != "availability" or request.run_id or request.compare:
        raise ValueError("A device target supports availability only, without run/comparison")
    if not request.target or not any(d.get("id") == request.target for d in monitor.devices):
        raise ValueError("Select an exact currently registered device")
    service = monitor.reliability
    detail = service.device(request.target)
    expected = monitor.store.expected_entities()
    members = []
    for member in service.members.get(request.target, []):
        entry = monitor.registry.get(member["entity_id"], {})
        members.append(
            {
                **copy.deepcopy(member),
                "type": "device_member",
                "device_id": request.target,
                "disabled": bool(entry.get("disabled_by")),
                "expected_offline": member["entity_id"] in expected,
            }
        )
    own = balanced(members, 32)
    platforms = set(detail["platforms"])
    related = [
        {
            "type": "correlated_device",
            "device_id": item["device_id"],
            "availability": item["state"] if service.reliable else "unknown",
            "platforms": list(item["platforms"]),
            "relation": "same_integration_only",
        }
        for key, item in sorted(service.current.items())
        if key != request.target
        and item.get("registry_present", True)
        and platforms.intersection(item["platforms"])
    ]
    siblings = balanced(related, 16)
    sections = {name: [] for name in SECTIONS}
    sections["target"] = [
        {
            "type": "registered_device",
            "device_id": request.target,
            "availability": detail["state"],
            "platforms": detail["platforms"],
            "attention": detail["attention"],
            "power_expectation": detail["power"],
            "meaningful": detail["evidence"]["meaningful"],
            "unknown": detail["evidence"]["unknown"],
            "unavailable": detail["evidence"]["unavailable"],
            "unassessed_members": detail["evidence"].get("unassessed_members"),
            "registry_complete": detail["evidence"].get("registry_complete", False),
            "member_count": len(members),
            "reliable_now": detail["reliable_now"],
        },
        *own,
    ]
    sections["siblings"] = siblings
    captured_at = time.time()
    for row in detail["history"][:20]:
        start = row.get("started")
        watermark = service.cache_as_of
        end = row.get("ended")
        end = min(end, watermark) if finite(end) and finite(watermark) else watermark
        duration_known = (
            finite(start) and finite(end) and end >= start and not service.intervals_limited
        )
        observed = (
            seconds(union_intervals(service.coverage, start, end)) if duration_known else None
        )
        sections["availability"].append(
            {
                "device_id": request.target,
                "state": row["state"],
                "started": row["started"],
                "ended": end,
                "observed_seconds": round(observed, 3) if observed is not None else None,
                "uncertain": not detail["reliable_now"] or bool(detail["coverage_gaps"]),
                "observation_scope": "registered_device",
            }
        )
    sections["coverage"] = [
        {
            "type": "device_coverage",
            "connected": monitor.connected,
            "reliable_now": detail["reliable_now"],
            "cache_pending": detail["cache_pending"],
            "measurement_started": detail["coverage_start"] is not None,
            "coverage_available": detail["coverage_start"] is not None
            and service.cache_as_of is not None,
            "device_members_observed": len(members),
            "device_members_omitted": len(members) - len(own),
            "device_history_omitted": max(0, len(detail["history"]) - 20),
            "device_coverage_gaps": len(detail["coverage_gaps"]),
            "device_coverage_gaps_limited": detail["coverage_gaps_limited"],
            "correlated_devices_observed": len(related),
            "correlated_devices_omitted": len(related) - len(siblings),
            "prerequisite_supported": bool(members)
            and detail["state"] in {"offline", "partial", "unknown"},
            "coverage_start": detail["coverage_start"],
            "source_as_of": service.as_of,
            "configuration_digest": detail["cohort"],
            "gaps": detail["coverage_gaps"],
        }
    ]
    return {
        "captured_at": captured_at,
        "sections": sections,
        "entity": None,
        "device": request.target,
        "target_type": "device",
        "run_id": None,
        "compare": None,
        "selection_basis": "exact_registered_device",
        "selected_outcome": None,
    }
