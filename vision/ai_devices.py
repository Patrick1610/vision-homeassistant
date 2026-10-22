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


def capture_group(monitor, request):
    """One aggregate per exact group device, never per-member entity fanout."""
    if (
        request.kind != "availability"
        or request.profile != "compact"
        or request.run_id
        or request.compare
    ):
        raise ValueError("A group supports compact availability only, without run/comparison")
    detail = monitor.home.dossier(request.target)
    group = detail["problem"]
    service = monitor.reliability
    if (
        group["kind"] != "group"
        or not detail["current"]
        or detail["pending"]
        or group.get("stale")
        or not service.reliable
        or service.cache_state != "ready"
        or service.snapshot()["cache_pending"]
        or detail.get("member_detail_unknown")
    ):
        raise ValueError("Selected group needs current covered retained member evidence")
    members = detail["members"]
    if len(members) < 2:
        raise ValueError("A group requires at least two distinct affected devices")
    registered = {d["id"] for d in monitor.devices}
    ids = {member["target"] for member in members}
    if len(ids) != len(members) or not ids <= registered:
        raise ValueError("Selected group member binding changed")
    times = [member.get("observed_since") for member in members]
    if any(not finite(at) for at in times) or max(times) - min(times) > 300:
        raise ValueError("Selected group lacks the covered five-minute transition basis")
    for member in members:
        row = service.current.get(member["target"])
        if (
            not row
            or row["cohort"] != member["cohort"]
            or row["state"] not in {"offline", "partial"}
            or not member.get("changed")
            or member.get("retained_only")
        ):
            raise ValueError("Selected group is no longer the same covered member cohort")
    selected = sorted(members, key=lambda r: r["target"])[:12]
    peers = sorted(
        (
            row
            for key, row in service.current.items()
            if key not in ids
            and key in registered
            and row["state"] == "online"
            and group["target"] in row["platforms"]
        ),
        key=lambda r: r["device_id"],
    )
    healthy = peers[:4]
    sections = {name: [] for name in SECTIONS}
    sections["target"] = [
        {
            "type": "registered_group",
            "affected_total": group["member_count"],
            "affected_selected": len(selected),
            "affected_omitted": group["member_count"] - len(selected),
            "reliable_now": True,
        }
    ]
    for member in selected:
        row = service.current[member["target"]]
        evidence = row["evidence"]
        sections["target"].append(
            {
                "type": "group_member",
                "device_id": member["target"],
                "availability": row["state"],
                "platforms": row["platforms"],
                "meaningful": evidence["meaningful"],
                "unavailable": evidence["unavailable"],
                "unknown": evidence["unknown"],
                "unassessed_members": evidence.get("unassessed_members"),
                "covered_transition": True,
            }
        )
    sections["siblings"] = [
        {
            "type": "correlated_device",
            "device_id": row["device_id"],
            "availability": "online",
            "platforms": row["platforms"],
            "relation": "same_integration_only",
        }
        for row in healthy
    ]
    sections["coverage"] = [
        {
            "type": "group_coverage",
            "connected": monitor.connected,
            "reliable_now": True,
            "cache_pending": False,
            "prerequisite_supported": True,
            "covered_transition_group": True,
            "group_affected_total": group["member_count"],
            "group_affected_selected": len(selected),
            "group_affected_omitted": group["member_count"] - len(selected),
            "group_healthy_total": len(peers),
            "group_healthy_selected": len(healthy),
            "group_healthy_omitted": len(peers) - len(healthy),
        }
    ]
    return {
        "captured_at": time.time(),
        "sections": sections,
        "entity": None,
        "group": request.target,
        "target_type": "group",
        "run_id": None,
        "compare": None,
        "selection_basis": "exact_covered_group",
        "selected_outcome": None,
    }
