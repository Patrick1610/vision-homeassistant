"""Device-level observations, not physical/network diagnoses or HA actions."""

import asyncio
import bisect
import json
import math
import sqlite3
import time
from collections import defaultdict
from contextlib import closing, contextmanager
from urllib.parse import quote

from .evidence import fingerprint

WINDOWS = {"24h": (86400, 24), "7d": (7 * 86400, 28), "30d": (30 * 86400, 60)}
MAX_INTERVALS = 50_000
MAX_DEVICES = 6000
MAX_ENTITIES = 20_000
MAX_CHECKS = 10_000
MAX_COVERAGE = 10_000
MAX_HISTORY_ROWS = 250_000
MAX_HISTORY_BYTES = 128 * 1024 * 1024
MAX_CURRENT_PAYLOAD_BYTES = 8192
MAX_HISTORY_RECORD_BYTES = 8192
MAX_WINDOW_BYTES = 16 * 1024 * 1024
CONTROL_DOMAINS = {
    "light",
    "switch",
    "climate",
    "fan",
    "cover",
    "lock",
    "media_player",
    "vacuum",
    "humidifier",
    "water_heater",
    "siren",
    "valve",
    "remote",
    "camera",
    "text",
    "date",
    "time",
    "alarm_control_panel",
    "lawn_mower",
    "device_tracker",
}
MEASUREMENT_CLASSES = {
    "temperature",
    "humidity",
    "illuminance",
    "pressure",
    "power",
    "energy",
    "current",
    "voltage",
    "moisture",
    "carbon_dioxide",
    "carbon_monoxide",
    "pm25",
    "pm10",
    "gas",
    "water",
    "wind_speed",
    "distance",
    "sound_pressure",
    "atmospheric_pressure",
    "enum",
    "date",
    "timestamp",
}
BINARY_CLASSES = {
    "opening",
    "door",
    "window",
    "motion",
    "occupancy",
    "smoke",
    "carbon_monoxide",
    "gas",
    "moisture",
    "safety",
    "problem",
    "power",
    "connectivity",
    "presence",
    "running",
    "vibration",
    "heat",
    "cold",
    "light",
    "plug",
}
DIAGNOSTIC_CLASSES = {"battery", "signal_strength"}
STATES = {"online", "offline", "partial", "unknown", "excluded"}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def entity_role(entity_id, category=None, device_class=None, disabled=False):
    """Closed rule: no entity-name, numeric-state, silence or hardware-name inference."""
    if disabled:
        return "disabled"
    if not isinstance(entity_id, str) or (category is not None and not isinstance(category, str)):
        return "unclassified"
    if device_class is not None and not isinstance(device_class, str):
        return "unclassified"
    domain = entity_id.split(".", 1)[0]
    if category in {"config", "diagnostic"} or domain in {
        "update",
        "button",
        "number",
        "select",
        "event",
        "image",
    }:
        return "ancillary"
    if device_class in DIAGNOSTIC_CLASSES:
        return "ancillary"
    if category not in {None, "config", "diagnostic"}:
        return "unclassified"
    if domain in CONTROL_DOMAINS:
        return "primary"
    if domain == "sensor" and (device_class is None or device_class in MEASUREMENT_CLASSES):
        return "primary"
    if domain == "binary_sensor" and (device_class is None or device_class in BINARY_CLASSES):
        return "primary"
    return "unclassified"


def classify_device(members, *, registry_complete=True, device_disabled=False):
    primary = [row for row in members if row.get("role") == "primary"]
    bad = sum(row.get("availability") == "unavailable" for row in primary)
    good = sum(row.get("availability") == "available" for row in primary)
    unknown = len(primary) - bad - good
    unclassified = sum(row.get("role") == "unclassified" for row in members)
    blocking_unclassified = sum(
        row.get("role") == "unclassified" and row.get("availability") != "unavailable"
        for row in members
    )
    state = "unknown"
    if device_disabled:
        state = "excluded"
    elif primary and registry_complete:
        if bad == len(primary) and not blocking_unclassified:
            state = "offline"
        elif bad and good:
            state = "partial"
        elif good == len(primary) and not unclassified:
            state = "online"
    return {
        "state": state,
        "meaningful": len(primary),
        "unavailable": bad,
        "unknown": unknown,
        "excluded": len(members) - len(primary),
        "unclassified": unclassified,
        "blocking_unclassified": blocking_unclassified,
        "unclassified_unavailable": unclassified - blocking_unclassified,
        "unassessed_members": unknown + (blocking_unclassified if primary else unclassified),
        "registry_complete": bool(registry_complete),
        "device_disabled": bool(device_disabled),
        "rule": "Device-wide unavailable requires at least one enabled primary signal, all "
        "primary signals explicitly unavailable, and any unclassified enabled members also "
        "explicitly unavailable. Unknown/missing/unclassified-available evidence blocks that "
        "conclusion. Config/diagnostic/disabled/battery/signal and event/image-only signals "
        "do not establish it. These are HA availability observations, not physical reachability.",
    }


def union_intervals(intervals, start, end):
    """Return clipped disjoint [start,end) ranges; corrupt/nonfinite times are not evidence."""
    if not finite(start) or not finite(end) or end <= start:
        return []
    clipped = []
    for left, right in intervals:
        right = end if right is None else right
        if not finite(left) or not finite(right) or right <= left:
            continue
        a, b = max(start, left), min(end, right)
        if b > a:
            clipped.append((a, b))
    result = []
    for a, b in sorted(clipped):
        if result and a <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], b))
        else:
            result.append((a, b))
    return result


def covered_intervals(intervals, coverage, start, end):
    left = union_intervals(intervals, start, end)
    right = union_intervals(coverage, start, end)
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if b > a:
            result.append((a, b))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return result


def seconds(intervals):
    return sum(b - a for a, b in intervals)


def continuous_known(rows, coverage, start, end, cohort):
    """Only one unchanged known-state cohort throughout, including intermediate observations."""
    if not finite(start) or not finite(end) or end <= start or not cohort:
        return False
    active = [
        r for r in rows if r["started"] < end and (r.get("ended") is None or r["ended"] > start)
    ]
    return (
        bool(active)
        and all(
            r.get("cohort") == cohort and r["state"] in {"online", "partial", "offline"}
            for r in active
        )
        and seconds(
            covered_intervals(
                [(r["started"], r.get("ended")) for r in active], coverage, start, end
            )
        )
        >= end - start - 0.001
    )


def observation_category(row, start):
    if row["state"] in {"unknown", "excluded"}:
        return "unknown"
    if row["state"] in {"online", "partial"}:
        return row["state"]
    if row.get("attention") == "expected":
        return "expected"
    if (
        row.get("episode_kind") == "transition"
        and finite(row.get("episode_started"))
        and row["episode_started"] >= start
    ):
        return "new"
    return "persistent"


def summarize_window(intervals, coverage, start, end, buckets=24):
    """Counts sample bucket ends; device-hours union each device and exclude coverage gaps."""
    if not 1 <= buckets <= 72 or not finite(start) or not finite(end) or end <= start:
        raise ValueError("Invalid reliability window")
    valid_coverage = [
        p
        for p in coverage
        if isinstance(p, (list, tuple))
        and len(p) == 2
        and finite(p[0])
        and finite(p[1])
        and p[1] >= p[0]
    ]
    invalid_coverage = len(coverage) - len(valid_coverage)
    coverage = union_intervals(valid_coverage, start, end)
    rows = [
        row
        for row in intervals
        if isinstance(row, dict)
        and finite(row.get("started"))
        and (row.get("ended") is None or finite(row.get("ended")))
        and (row.get("ended") is None or row["ended"] >= row["started"])
        and isinstance(row.get("state"), str)
        and row["state"] in STATES
        and isinstance(row.get("device_id"), str)
    ]
    by_device = defaultdict(list)
    for row in rows:
        if row["started"] < end and (row.get("ended") is None or row["ended"] > start):
            by_device[row["device_id"]].append(row)
    # Identical overlapping states can be unioned. Contradictory states/mappings are
    # corrupt evidence, not a latest-row-wins reconstruction of device health.
    conflicts = 0
    for values in by_device.values():
        previous_end, previous_key = start, None
        for row in sorted(values, key=lambda r: (r["started"], r.get("ended") or end)):
            a, b = (
                max(start, row["started"]),
                min(end, row.get("ended") if row.get("ended") is not None else end),
            )
            if b <= a:
                continue
            key = (
                row["state"],
                row.get("cohort"),
                row.get("attention"),
                observation_category(row, start),
            )
            if a < previous_end and key != previous_key:
                conflicts += 1
            if b >= previous_end:
                previous_end, previous_key = b, key
    device_seconds = expected_seconds = known_seconds = unknown_seconds = 0
    global_bad = []
    for values in by_device.values():
        bad = [(r["started"], r.get("ended")) for r in values if r["state"] == "offline"]
        expected = [
            (r["started"], r.get("ended"))
            for r in values
            if r["state"] == "offline" and r.get("attention") == "expected"
        ]
        known_seconds += seconds(
            covered_intervals(
                [
                    (r["started"], r.get("ended"))
                    for r in values
                    if r["state"] in {"online", "offline", "partial"}
                ],
                coverage,
                start,
                end,
            )
        )
        unknown_seconds += seconds(
            covered_intervals(
                [
                    (r["started"], r.get("ended"))
                    for r in values
                    if r["state"] in {"unknown", "excluded"}
                ],
                coverage,
                start,
                end,
            )
        )
        observed = covered_intervals(bad, coverage, start, end)
        device_seconds += seconds(observed)
        expected_seconds += seconds(covered_intervals(expected, coverage, start, end))
        global_bad.extend(observed)
    width = (end - start) / buckets
    samples = [start + width * (index + 1) - min(0.000001, width / 2) for index in range(buckets)]
    categories = ("persistent", "new", "expected", "unknown", "partial", "online")
    changes = {key: [0] * (buckets + 1) for key in categories}
    for values in by_device.values():
        ranges = defaultdict(list)
        for row in values:
            category = observation_category(row, start)
            ranges[category].append((row["started"], row.get("ended")))
        for category, spans in ranges.items():
            for left, right in union_intervals(spans, start, end):
                first, last = bisect.bisect_left(samples, left), bisect.bisect_left(samples, right)
                changes[category][first] += 1
                changes[category][last] -= 1
    starts = [left for left, _ in coverage]
    prefix, accumulated = [], 0
    for left, right in coverage:
        prefix.append(accumulated)
        accumulated += right - left

    def area(at):
        index = bisect.bisect_right(starts, at) - 1
        return (
            0 if index < 0 else prefix[index] + max(0, min(at, coverage[index][1]) - starts[index])
        )

    counts = dict.fromkeys(categories, 0)
    points = []
    for index, sample in enumerate(samples):
        left, right = start + width * index, start + width * (index + 1)
        cover_index = bisect.bisect_right(starts, sample) - 1
        covered = cover_index >= 0 and sample < coverage[cover_index][1]
        for category in categories:
            counts[category] += changes[category][index]
        point = {"start": left, "end": right, "coverage": (area(right) - area(left)) / width}
        point.update({key: counts[key] if covered else None for key in categories})
        point["observed"] = sum(counts.values()) if covered else None
        points.append(point)
    fully_covered = seconds(coverage) >= end - start - 0.001
    improved = worsened = unchanged = comparable = 0
    before_burden = after_burden = 0
    middle = (start + end) / 2
    for values in by_device.values():
        active = [
            r
            for r in values
            if r["started"] < end and (r.get("ended") is None or r["ended"] > start)
        ]
        cohorts = {r.get("cohort") for r in active}
        observed = union_intervals([(r["started"], r.get("ended")) for r in active], start, end)
        if (
            not fully_covered
            or len(cohorts) != 1
            or not next(iter(cohorts), None)
            or any(r["state"] in {"unknown", "excluded"} for r in active)
            or seconds(observed) < end - start - 0.001
        ):
            continue
        ordered = sorted(active, key=lambda r: r["started"])
        severity = {"online": 0, "partial": 1, "offline": 2}
        before, after = severity[ordered[0]["state"]], severity[ordered[-1]["state"]]
        comparable += 1
        bad = [(r["started"], r.get("ended")) for r in active if r["state"] == "offline"]
        before_burden += seconds(covered_intervals(bad, coverage, start, middle))
        after_burden += seconds(covered_intervals(bad, coverage, middle, end))
        improved += after < before
        worsened += after > before
        unchanged += after == before
    concurrent = peak = 0
    for _, delta in sorted([(a, 1) for a, b in global_bad] + [(b, -1) for a, b in global_bad]):
        concurrent += delta
        peak = max(peak, concurrent)
    result = {
        "start": start,
        "end": end,
        "points": points,
        "peak_offline_devices": peak,
        "invalid_intervals": len(intervals) - len(rows),
        "invalid_coverage": invalid_coverage,
        "conflicting_intervals": conflicts,
        "limited": bool(len(intervals) - len(rows) or invalid_coverage or conflicts),
        "device_hours": device_seconds / 3600,
        "known_device_hours": known_seconds / 3600,
        "unknown_device_hours": unknown_seconds / 3600,
        "offline_share": device_seconds / known_seconds if known_seconds else None,
        "expected_device_hours": expected_seconds / 3600,
        "simultaneous_outage_hours": seconds(union_intervals(global_bad, start, end)) / 3600,
        "covered_hours": seconds(coverage) / 3600,
        "coverage_fraction": seconds(coverage) / (end - start),
        "burden": {
            "comparable_devices": comparable,
            "total_devices": len(by_device),
            "excluded_devices": len(by_device) - comparable,
            "before_device_hours": before_burden / 3600,
            "after_device_hours": after_burden / 3600,
            "denominator_device_hours_per_half": comparable * (end - start) / 7200,
            "direction": "unknown"
            if not comparable
            else "decreased"
            if after_burden < before_burden - 0.001
            else "increased"
            if after_burden > before_burden + 0.001
            else "unchanged",
            "meaning": "Equal first/second halves, only the same known-state cohort fully covered "
            "throughout the selected window. No extrapolation or frequency claim.",
        },
        "trend": {
            "meaning": "First versus last observed status only; "
            "not a duration/frequency comparison.",
            "comparable_devices": comparable,
            "improved": improved,
            "worsened": worsened,
            "unchanged": unchanged,
            "uncompared_devices": len(by_device) - comparable,
        },
        "meaning": "Unique devices at bucket end; expected takes precedence, new requires an "
        "observed transition within this window, otherwise persistent baseline/backlog. "
        "Device-hours are per-device unions clipped to known monitoring coverage.",
    }
    if result["limited"]:
        limit_summary(result, len(by_device))
    return result


def limit_summary(result, devices):
    """A bounded/corrupt selection must not look like complete zero burden or health."""
    for key in (
        "device_hours",
        "expected_device_hours",
        "known_device_hours",
        "unknown_device_hours",
        "offline_share",
        "simultaneous_outage_hours",
        "peak_offline_devices",
    ):
        result[key] = None
    result["burden"].update(
        direction="unknown",
        comparable_devices=0,
        excluded_devices=result["burden"]["total_devices"],
        before_device_hours=None,
        after_device_hours=None,
        denominator_device_hours_per_half=None,
    )
    result["trend"].update(
        comparable_devices=0, improved=0, worsened=0, unchanged=0, uncompared_devices=devices
    )
    for point in result["points"]:
        for key in ("persistent", "new", "expected", "unknown", "partial", "online", "observed"):
            point[key] = None


def unpack(value, fallback):
    try:
        result = json.loads(value) if isinstance(value, str) else value
        return result if isinstance(result, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def history_bytes(row):
    return 64 + sum(
        len(str(row[key]).encode())
        for key in (
            "device_id",
            "state",
            "episode_kind",
            "cohort",
            "attention",
            "platforms",
            "evidence",
            "reason",
        )
    )


def read_cache_input(path, end, current):
    """A separate read-only WAL snapshot; no main-connection/event-loop lock or writes."""
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA busy_timeout=3000")
        db.execute("BEGIN")
        windows = {}
        for window, (duration, buckets) in WINDOWS.items():
            start = end - duration
            where = "started<? AND (ended IS NULL OR ended>?)"
            args = (end + 0.000001, start)
            total = db.execute(
                "SELECT count(DISTINCT device_id) FROM device_observations WHERE " + where, args
            ).fetchone()[0]
            groups = db.execute(
                "SELECT device_id,count(*) n,sum(encoded_bytes) bytes FROM "
                "device_observations WHERE "
                + where
                + " GROUP BY device_id ORDER BY device_id LIMIT ?",
                (*args, MAX_DEVICES + 1),
            ).fetchall()
            selected, count, size = [], 0, 0
            for group in groups[:MAX_DEVICES]:
                if (
                    count + group["n"] <= MAX_INTERVALS
                    and size + group["bytes"] <= MAX_WINDOW_BYTES
                ):
                    selected.append(group["device_id"])
                    count += group["n"]
                    size += group["bytes"]
            rows = []
            for offset in range(0, len(selected), 400):
                ids = selected[offset : offset + 400]
                query = (
                    "SELECT device_id,state,started,ended,episode_started,episode_kind,"
                    "cohort,attention,platforms FROM device_observations WHERE "
                    + where
                    + " AND device_id IN ("
                    + ",".join("?" for _ in ids)
                    + ")"
                )
                rows.extend(dict(row) for row in db.execute(query, (*args, *ids)))
            coverage = [
                dict(row)
                for row in db.execute(
                    "SELECT started,observed_until FROM device_coverage WHERE "
                    "started<? AND observed_until>? ORDER BY started DESC LIMIT ?",
                    (end, start, MAX_COVERAGE + 1),
                )
            ]
            windows[window] = {
                "rows": rows,
                "coverage": coverage[:MAX_COVERAGE],
                "coverage_limited": len(coverage) > MAX_COVERAGE,
                "total": total,
                "included": len(selected),
                "excluded": total - len(selected),
                "row_count": count,
                "bytes": size,
                "start": start,
                "end": end,
                "buckets": buckets,
            }
        first = db.execute(
            "SELECT value FROM meta WHERE key='device_measurement_started'"
        ).fetchone()
        oldest = db.execute(
            "SELECT ended FROM device_observations WHERE ended IS NOT NULL AND id NOT IN "
            "(SELECT observation_id FROM device_current WHERE observation_id IS NOT NULL) "
            "ORDER BY ended LIMIT 1"
        ).fetchone()
        db.rollback()
    return {
        "oldest_retention_ended": oldest[0] if oldest and finite(oldest[0]) else None,
        "windows": windows,
        "current": current,
        "coverage_start": json.loads(first[0]) if first else None,
        "as_of": end,
    }


def compile_cache(data):
    """Pure compile over an immutable captured snapshot, never a live monitor or DB."""
    results, heatmaps = {}, {}
    for window, item in data["windows"].items():
        coverage = [(r["started"], r["observed_until"]) for r in item["coverage"]]
        result = summarize_window(
            item["rows"], coverage, item["start"], item["end"], item["buckets"]
        )
        result["evidence_limited"] = bool(result["limited"] or item["coverage_limited"])
        if result["evidence_limited"] or (item["excluded"] and not item["included"]):
            limit_summary(result, item["included"])
        result["selection"] = {
            "included_devices": item["included"],
            "excluded_devices": item["excluded"],
            "total_devices": item["total"],
            "rows": item["row_count"],
            "encoded_bytes": item["bytes"],
            "reason": "whole-device window selection limit" if item["excluded"] else None,
        }
        result["limited"] = result["evidence_limited"] or bool(item["excluded"])
        result["burden"]["total_devices"] = item["total"]
        result["burden"]["excluded_devices"] = (
            item["total"] - result["burden"]["comparable_devices"]
        )
        result["trend"]["uncompared_devices"] = (
            item["total"] - result["trend"]["comparable_devices"]
        )
        for point in result["points"]:
            point["selection_limited"] = bool(item["excluded"])
        result.update(
            window=window,
            as_of=data["as_of"],
            coverage_start=data["coverage_start"],
            historical_mapping="Only timestamped device observations; earlier entity history"
            " cannot prove historical device membership.",
        )
        results[window] = result
        groups = defaultdict(list)
        for row in data["current"]:
            for platform in row["platforms"]:
                groups[platform].append(row)
        ordered = sorted(
            groups, key=lambda key: (-sum(r["state"] == "offline" for r in groups[key]), key)
        )
        partition = defaultdict(list)
        for row in item["rows"]:
            for platform in unpack(row["platforms"], [])[:8]:
                if isinstance(platform, str):
                    partition[platform].append(row)
        items = []
        for platform in ordered[:12]:
            values = summarize_window(
                partition[platform], coverage, item["start"], item["end"], min(30, item["buckets"])
            )
            points = [
                {
                    "start": p["start"],
                    "end": p["end"],
                    "coverage": p["coverage"],
                    "offline": None
                    if p["persistent"] is None or result["evidence_limited"]
                    else p["persistent"] + p["new"] + p["expected"],
                    "partial": p["partial"],
                    "unknown": p["unknown"],
                    "observed": p["observed"],
                    "selection_limited": bool(item["excluded"]),
                }
                for p in values["points"]
            ]
            members = groups[platform]
            items.append(
                {
                    "platform": platform,
                    "devices": len(members),
                    "offline": sum(r["state"] == "offline" for r in members),
                    "partial": sum(r["state"] == "partial" for r in members),
                    "unknown": sum(r["state"] in {"unknown", "excluded"} for r in members),
                    "points": points,
                    "start": item["start"],
                    "end": item["end"],
                }
            )
        heatmaps[window] = {"total": len(groups), "limited": len(groups) > 12, "items": items}
    return {"results": results, "heatmaps": heatmaps, "input": data}


class DeviceReliability:
    """Timestamped observations, bounded append admission and one coalescing cache worker."""

    def __init__(self, monitor):
        self.monitor, self.store = monitor, monitor.store
        self.current = {}
        for item in self.store.rows(
            "SELECT c.*,o.ended interval_ended FROM device_current c LEFT JOIN "
            "device_observations o ON o.id=c.observation_id ORDER BY "
            "c.device_id LIMIT ?",
            (MAX_DEVICES,),
        ):
            value = {
                "state": "unknown",
                "name": item["device_id"],
                "attention": "review",
                "power": "unknown",
                "started": None,
                "episode_started": None,
                "episode_kind": "none",
                "reason": "retained_current",
                "cohort": "unknown",
                **unpack(item["payload"], {}),
            }
            value.update(
                device_id=item["device_id"],
                id=item["observation_id"],
                interval_ended=item["interval_ended"],
                registry_present=bool(item["registry_present"]),
                removed_at=item["removed_at"],
            )
            if not isinstance(value.get("state"), str) or value["state"] not in STATES:
                value.update(state="unknown", reason="invalid_retained_state")
            if not finite(value.get("episode_started")):
                value["episode_started"] = None
            if value.get("episode_kind") not in ("none", "baseline", "transition"):
                value["episode_kind"] = "none"
            value["platforms"] = [
                p for p in unpack(value.get("platforms"), []) if isinstance(p, str)
            ][:8]
            for key, fallback in (("name", item["device_id"]), ("cohort", "unknown")):
                if not isinstance(value.get(key), str):
                    value[key] = fallback
            value["evidence"] = (
                value.get("evidence") if isinstance(value.get("evidence"), dict) else {}
            )
            self.current[item["device_id"]] = value
        self.measurement_started = self.store.get_meta("device_measurement_started")
        if not finite(self.measurement_started):
            self.measurement_started = None
        self.oldest_retention_ended = None
        self.members, self.policies = {}, {}
        self.reliable, self.as_of = False, None
        self.history_blocked = bool(self.store.get_meta("device_history_blocked", False))
        self.cache, self.heatmaps, self.inputs = {}, {}, {}
        self.coverage, self.intervals = [], {}
        self.intervals_limited = False
        self.compiled_current = {}
        self.inventory_coverage = {"unmapped_entities": 0, "limited": False}
        self.cache_state, self.cache_error, self.cache_as_of = "init", None, None
        self.cache_failure_count, self.cache_error_stage = 0, None
        self._dirty, self._target, self._worker, self._closed = False, time.time(), None, False

    def request_cache(self, now=None, *, schedule=True):
        self._target = time.time() if now is None else now
        self._dirty = True
        if self.cache:
            self.cache_state = "pending"
        if not schedule or self._closed:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._worker is None or self._worker.done():
            self._worker = loop.create_task(self.rebuild())

    async def rebuild(self):
        while self._dirty and not self._closed:
            self._dirty = False
            end = self._target
            current = tuple(
                {
                    "device_id": r["device_id"],
                    "platforms": tuple(r.get("platforms", [])),
                    "cohort": r.get("cohort"),
                    "state": r["state"] if self.reliable else "unknown",
                }
                for r in self.current.values()
            )
            stage = "capture"
            try:
                data = await asyncio.to_thread(read_cache_input, self.store.path, end, current)
                stage = "compile"
                result = await asyncio.to_thread(compile_cache, data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.cache_state, self.cache_error = "failed", "Device chart snapshot unavailable"
                self.cache_failure_count += 1
                self.cache_error_stage = stage
                return
            self.install_cache(result)
        if not self._closed:
            self.cache_state = "ready"

    def build_cache(self, now):
        """Synchronous CLI/test entry; forbidden on an active asyncio loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Use the background reliability worker inside asyncio")
        current = tuple(
            {
                "device_id": r["device_id"],
                "platforms": tuple(r.get("platforms", [])),
                "cohort": r.get("cohort"),
                "state": r["state"] if self.reliable else "unknown",
            }
            for r in self.current.values()
        )
        self.install_cache(compile_cache(read_cache_input(self.store.path, now, current)))
        self._dirty, self.cache_state = False, "ready"

    def install_cache(self, compiled):
        self.cache, self.heatmaps = compiled["results"], compiled["heatmaps"]
        self.inputs = compiled["input"]["windows"]
        self.cache_as_of = compiled["input"]["as_of"]
        self.cache_error = None
        self.cache_failure_count, self.cache_error_stage = 0, None
        self.oldest_retention_ended = compiled["input"].get("oldest_retention_ended")
        if finite(compiled["input"].get("coverage_start")):
            self.measurement_started = compiled["input"]["coverage_start"]
        self.compiled_current = {
            r["device_id"]: (r["state"], r["cohort"]) for r in compiled["input"]["current"]
        }
        old = self.inputs["30d"]
        self.coverage = [(r["started"], r["observed_until"]) for r in old["coverage"]]
        self.intervals = defaultdict(list)
        for row in old["rows"]:
            self.intervals[row["device_id"]].append(row)
        self.intervals_limited = bool(
            old["coverage_limited"] or self.cache["30d"]["evidence_limited"]
        )

    async def close(self):
        self._closed = True
        if self._worker is not None and not self._worker.done():
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)

    async def wait_cache(self):
        """Lifecycle/test readiness only; ordinary HTTP views never wait for compilation."""
        if self._dirty:
            self.request_cache(self._target)
        if self._worker is not None:
            await asyncio.shield(self._worker)

    def gap(self, now=None, reason="observation_gap"):
        now = time.time() if now is None else now
        with self.store.transaction():
            last = self.store.rows("SELECT observed_until FROM device_coverage WHERE ended IS NULL")
            if last:
                stop = min(now, last[0]["observed_until"])
                self.store.execute(
                    "UPDATE device_observations SET ended=max(started,?) WHERE ended IS NULL "
                    + ("" if reason == "history_capacity" else "AND state='offline'"),
                    (stop,),
                )
                self.store.execute(
                    "UPDATE device_coverage SET ended=observed_until,reason=? WHERE ended IS NULL",
                    (reason,),
                )
                for row in self.current.values():
                    if reason != "history_capacity" and row["state"] != "offline":
                        continue
                    row["interval_ended"] = (
                        max(row["started"], stop) if finite(row.get("started")) else stop
                    )
        self.reliable = False
        self.request_cache(now)

    def storage(self):
        value = self.store.rows("SELECT * FROM device_storage WHERE kind='history'")[0]
        return {
            **value,
            "row_limit": MAX_HISTORY_ROWS,
            "encoded_byte_limit": MAX_HISTORY_BYTES,
            "blocked": self.history_blocked,
            "remaining_rows": max(0, MAX_HISTORY_ROWS - value["records"]),
            "remaining_encoded_bytes": max(0, MAX_HISTORY_BYTES - value["bytes"]),
            "retention_days": self.monitor.settings.retention_days,
            "earliest_retention_eligible_at": self.oldest_retention_ended
            + self.monitor.settings.retention_days * 86400
            if finite(self.oldest_retention_ended)
            else None,
            "retention_estimate_as_of": self.cache_as_of,
        }

    def stop_history(self, now):
        if not self.history_blocked:
            self.gap(now, "history_capacity")
            self.history_blocked = True
            # Current evidence is independent of the closed history pointer. Ordinary
            # retention may later reclaim these old closed intervals, never early eviction.
            self.store.execute("UPDATE device_current SET observation_id=NULL")
            for value in self.current.values():
                value["id"] = None
            self.store.set_meta("device_history_blocked", True)

    def can_append(self, amount):
        value = self.storage()
        return (
            amount <= MAX_HISTORY_RECORD_BYTES
            and value["records"] < MAX_HISTORY_ROWS
            and value["bytes"] + amount <= MAX_HISTORY_BYTES
        )

    def persist_current(self, row, *, present=True, removed_at=None):
        value = {
            k: v
            for k, v in row.items()
            if k not in {"id", "interval_ended", "registry_present", "removed_at"}
        }
        value["evidence"] = dict(value["evidence"])
        examples = list(value["evidence"].get("examples", []))
        value["evidence"]["examples"] = examples
        while len(encoded(value).encode()) > MAX_CURRENT_PAYLOAD_BYTES and examples:
            examples.pop()
            value["evidence"]["examples_limited"] = True
        payload = encoded(value)
        if len(payload.encode()) > MAX_CURRENT_PAYLOAD_BYTES:
            value["name"], value["platforms"], value["evidence"] = (
                row["device_id"][:80],
                [],
                {"state": "unknown", "rule": "Current evidence exceeds the local payload bound"},
            )
            value["state"] = "unknown"
            payload = encoded(value)
        self.store.execute(
            "INSERT INTO device_current(device_id,observation_id,payload,"
            "registry_present,removed_at) VALUES (?,?,?,?,?) ON "
            "CONFLICT(device_id) DO UPDATE SET "
            "observation_id=excluded.observation_id,payload=excluded.payload,"
            "registry_present=excluded.registry_present,"
            "removed_at=excluded.removed_at",
            (row["device_id"], row.get("id"), payload, int(present), removed_at),
        )
        self.current[row["device_id"]] = {
            **value,
            "id": row.get("id"),
            "interval_ended": row.get("interval_ended"),
            "registry_present": present,
            "removed_at": removed_at,
        }

    @contextmanager
    def observation_transaction(self, device_id=None):
        previous = self.current.copy() if device_id is None else self.current.get(device_id)
        blocked = self.history_blocked
        try:
            with self.store.transaction():
                yield
        except BaseException:
            if device_id is None:
                self.current = previous
            elif previous is not None:
                self.current[device_id] = previous
            else:
                self.current.pop(device_id, None)
            self.history_blocked, self.reliable = blocked, False
            raise

    def record(
        self,
        device_id,
        evidence,
        cohort,
        attention,
        power,
        name,
        platforms,
        now,
        reason="observed",
        *,
        present=True,
        removed_at=None,
    ):
        old = self.current.get(device_id)
        state = (
            evidence["state"]
            if isinstance(evidence.get("state"), str) and evidence["state"] in STATES
            else "unknown"
        )
        signature = fingerprint([state, cohort, attention, platforms])
        changed = (
            not old
            or old.get("signature") != signature
            or (old.get("interval_ended") is not None and not self.history_blocked)
        )
        metadata = [evidence, cohort, attention, power, name, platforms, present, removed_at]
        if old and not changed and old.get("metadata_signature") == fingerprint(metadata):
            return False
        episode_started, episode_kind = None, "none"
        if state == "offline":
            if (
                old
                and old["state"] == "offline"
                and old.get("interval_ended") is None
                and self.reliable
            ):
                episode_started, episode_kind = (
                    old.get("episode_started"),
                    old.get("episode_kind", "baseline"),
                )
            elif (
                old
                and old["state"] in {"online", "partial"}
                and old.get("interval_ended") is None
                and old["cohort"] == cohort
                and self.reliable
            ):
                episode_started, episode_kind = now, "transition"
            else:
                episode_started, episode_kind = now, "baseline"
        if old and not changed:
            episode_started, episode_kind = (
                old.get("episode_started"),
                old.get("episode_kind", "none"),
            )
        start = now if changed else old["started"]
        row = {
            "device_id": device_id,
            "state": state,
            "started": start,
            "episode_started": episode_started,
            "episode_kind": episode_kind,
            "cohort": cohort,
            "attention": attention,
            "power": power,
            "name": name,
            "platforms": platforms,
            "evidence": evidence,
            "evidence_at": now
            if not old or old["evidence"] != evidence
            else old.get("evidence_at", now),
            "reason": reason if changed else old["reason"],
            "signature": signature,
            "metadata_signature": fingerprint(metadata),
            "id": old.get("id") if old else None,
            "interval_ended": old.get("interval_ended") if old else None,
        }
        if changed and not self.history_blocked:
            coarse = {
                k: evidence.get(k)
                for k in (
                    "meaningful",
                    "unavailable",
                    "unknown",
                    "unclassified",
                    "unassessed_members",
                )
            }
            history = {**row, "platforms": encoded(platforms), "evidence": encoded(coarse)}
            if not self.can_append(history_bytes(history)):
                self.stop_history(now)
                row["interval_ended"] = self.current.get(device_id, {}).get("interval_ended", now)
                row["id"] = None
                if state == "offline":
                    row.update(episode_kind="baseline", episode_started=now)
            else:
                self.store.execute(
                    "UPDATE device_observations SET ended=max(started,?) WHERE "
                    "device_id=? AND ended IS NULL",
                    (now, device_id),
                )
                row["id"] = self.store.execute(
                    "INSERT INTO device_observations(device_id,state,started,"
                    "episode_started,episode_kind,cohort,attention,platforms,evidence,"
                    "reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    tuple(
                        history[k]
                        for k in (
                            "device_id",
                            "state",
                            "started",
                            "episode_started",
                            "episode_kind",
                            "cohort",
                            "attention",
                            "platforms",
                            "evidence",
                            "reason",
                        )
                    ),
                )
                row["interval_ended"] = None
        policy = self.policies.get(device_id)
        if (
            policy
            and attention == "known"
            and policy["baseline_state"] == "partial"
            and policy["baseline_cohort"] == cohort
            and state == "offline"
            and old
            and old["state"] in {"partial", "online"}
            and old.get("interval_ended") is None
            and old["cohort"] == cohort
            and self.reliable
            and not self.history_blocked
        ):
            if policy.get("worsened_at") is None:
                self.store.execute(
                    "UPDATE device_policies SET worsened_at=?,worsened_cohort=? WHERE device_id=?",
                    (now, cohort, device_id),
                )
                policy.update(worsened_at=now, worsened_cohort=cohort)
        self.persist_current(row, present=present, removed_at=removed_at)
        return True

    def refresh(self, now=None, *, registry_complete=True):
        now = time.time() if now is None else now
        if not registry_complete:
            self.gap(now, "registry_unknown")
            return
        registry, entities = self.monitor.registry, self.monitor.entities
        devices = {
            d["id"]: d
            for d in self.monitor.devices
            if isinstance(d, dict) and isinstance(d.get("id"), str) and 0 < len(d["id"]) <= 256
        }
        before = now - self.monitor.settings.retention_days * 86400
        missing = sorted(
            self.current.keys() - devices.keys(),
            key=lambda key: (
                self.current[key]["removed_at"]
                if finite(self.current[key].get("removed_at"))
                else now,
                key,
            ),
        )
        expired = {
            key
            for key in missing
            if finite(self.current[key].get("removed_at"))
            and self.current[key]["removed_at"] < before
        }
        # Active registry identities have priority. Reclaim only current pointers;
        # closed history, durable policy and performed checks remain untouched.
        pressure = max(0, len(self.current.keys() | devices.keys()) - MAX_DEVICES)
        reclaimed = expired | set(missing[:pressure])
        if reclaimed:
            with self.observation_transaction():
                for device_id in sorted(reclaimed):
                    self.store.execute(
                        "UPDATE device_observations SET ended=max(started,?) "
                        "WHERE device_id=? AND ended IS NULL",
                        (now, device_id),
                    )
                    self.store.execute("DELETE FROM device_current WHERE device_id=?", (device_id,))
                    self.current.pop(device_id, None)
        admitted = self.current.keys() | set(
            sorted(devices.keys() - self.current.keys())[: max(0, MAX_DEVICES - len(self.current))]
        )
        grouped, incomplete = defaultdict(list), set()
        for index, entity_id in enumerate(sorted(registry)):
            registered = registry[entity_id]
            device_id = registered.get("device_id")
            if not isinstance(device_id, str) or device_id not in devices:
                continue
            if index >= MAX_ENTITIES:
                incomplete.add(device_id)
                continue
            metadata = self.monitor.availability_metadata.get(entity_id, {})
            grouped[device_id].append(
                {
                    "entity_id": entity_id,
                    "role": entity_role(
                        entity_id,
                        registered.get("entity_category"),
                        metadata.get("device_class"),
                        bool(registered.get("disabled_by")),
                    ),
                    "availability": entities.get(entity_id, {}).get("availability", "not_loaded"),
                    "device_class": metadata.get("device_class"),
                    "platform": registered["platform"]
                    if isinstance(registered.get("platform"), str)
                    and 0 < len(registered["platform"]) <= 100
                    else "unknown",
                }
            )
        self.members = dict(grouped)
        self.inventory_coverage = {
            "unmapped_entities": sum(
                not isinstance(r.get("device_id"), str) or r["device_id"] not in devices
                for r in registry.values()
            )
            + len(entities.keys() - registry.keys()),
            "limited": bool(incomplete or devices.keys() - admitted),
            "omitted_devices": len(devices.keys() - admitted),
            "incomplete_devices": len(incomplete),
            "registry_entities": len(registry),
            "registry_devices": len(devices),
            "remaining_device_slots": max(0, MAX_DEVICES - len(admitted)),
            "retired_current_pointers": len(reclaimed),
        }
        self.policies = {}
        ids = sorted(admitted)
        for offset in range(0, len(ids), 400):
            batch = ids[offset : offset + 400]
            self.policies.update(
                {
                    r["device_id"]: r
                    for r in self.store.rows(
                        "SELECT * FROM device_policies WHERE device_id IN ("
                        + ",".join("?" for _ in batch)
                        + ")",
                        batch,
                    )
                }
            )
        expected = self.store.expected_entities(now)
        with self.observation_transaction():
            if not self.reliable and self.store.rows(
                "SELECT 1 FROM device_coverage WHERE ended IS NULL"
            ):
                self.gap(now, "observation_restart")
            if self.history_blocked:
                usage = self.storage()
                # Reserve one lean complete observation for every retained current identity.
                required = max(1, len(admitted))
                if (
                    usage["records"] + required <= MAX_HISTORY_ROWS
                    and usage["bytes"] + required * MAX_HISTORY_RECORD_BYTES <= MAX_HISTORY_BYTES
                ):
                    self.history_blocked = False
                    self.store.set_meta("device_history_blocked", False)
            if self.store.get_meta("device_measurement_started") is None:
                self.store.set_meta("device_measurement_started", now)
                self.measurement_started = now
            for device_id in sorted(devices.keys() & admitted):
                device = devices[device_id]
                members = grouped.get(device_id, [])
                evidence = classify_device(
                    members,
                    registry_complete=device_id not in incomplete,
                    device_disabled=bool(device.get("disabled_by")),
                )
                primary = [m for m in members if m["role"] == "primary"]
                evidence.update(examples=primary[:12], examples_limited=len(primary) > 12)
                policy = self.policies.get(device_id, {})
                attention = policy.get(
                    "attention",
                    "expected"
                    if primary
                    and device_id not in incomplete
                    and all(m["entity_id"] in expected for m in primary)
                    else "review",
                )
                cohort = fingerprint(
                    [(m["entity_id"], m["role"], m["device_class"]) for m in members]
                    + [bool(device.get("disabled_by"))]
                )
                self.record(
                    device_id,
                    evidence,
                    cohort,
                    attention,
                    policy.get("power", "unknown"),
                    self.monitor.redactor.text(
                        device.get("name_by_user") or device.get("name") or device_id, 160
                    ),
                    sorted({m["platform"] for m in members})[:8],
                    now,
                )
            for device_id in self.current.keys() - devices.keys():
                old = self.current[device_id]
                evidence = {**old["evidence"], "state": "unknown", "registry_complete": False}
                self.record(
                    device_id,
                    evidence,
                    old["cohort"],
                    old["attention"],
                    old["power"],
                    old["name"],
                    old["platforms"],
                    now,
                    "removed_from_registry",
                    present=False,
                    removed_at=old.get("removed_at") or now,
                )
            if not self.history_blocked:
                if self.store.rows("SELECT 1 FROM device_coverage WHERE ended IS NULL"):
                    self.store.execute(
                        "UPDATE device_coverage SET observed_until=max(observed_until"
                        ",?) WHERE ended IS NULL",
                        (now,),
                    )
                else:
                    self.store.execute(
                        "INSERT INTO device_coverage(started,observed_until,reason) VALUES "
                        "(?,?,'observed')",
                        (now, now),
                    )
        self.reliable, self.as_of = True, now
        self.request_cache(now)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self.build_cache(now)

    def observe(self, entity_id, now):
        if not self.reliable:
            return
        registered = self.monitor.registry.get(entity_id, {})
        device_id = registered.get("device_id")
        if device_id not in self.members or device_id not in self.current:
            return
        for member in self.members[device_id]:
            if member["entity_id"] == entity_id:
                member["availability"] = self.monitor.entities.get(entity_id, {}).get(
                    "availability", "not_loaded"
                )
                member["device_class"] = self.monitor.availability_metadata.get(entity_id, {}).get(
                    "device_class"
                )
                member["role"] = entity_role(
                    entity_id,
                    registered.get("entity_category"),
                    member["device_class"],
                    bool(registered.get("disabled_by")),
                )
        old = self.current[device_id]
        evidence = classify_device(
            self.members[device_id],
            registry_complete=old["evidence"].get("registry_complete", False),
            device_disabled=old["evidence"].get("device_disabled", False),
        )
        primary = [m for m in self.members[device_id] if m["role"] == "primary"]
        evidence.update(
            examples=primary[:12],
            examples_limited=len(primary) > 12,
        )
        cohort = fingerprint(
            [(m["entity_id"], m["role"], m["device_class"]) for m in self.members[device_id]]
            + [old["evidence"].get("device_disabled", False)]
        )
        if old["evidence"] == evidence and old["cohort"] == cohort:
            return
        with self.observation_transaction(device_id):
            self.record(
                device_id,
                evidence,
                cohort,
                old["attention"],
                old["power"],
                old["name"],
                old["platforms"],
                now,
            )
        self.request_cache(now, schedule=False)

    def snapshot(self, window="24h"):
        if window not in WINDOWS:
            raise ValueError("Unknown reliability window")
        if window in self.cache:
            value = self.cache[window]
        else:
            end = time.time()
            duration, buckets = WINDOWS[window]
            value = summarize_window([], [], end - duration, end, buckets)
            value["burden"]["total_devices"] = len(self.current)
            limit_summary(value, len(self.current))
            value.update(
                window=window,
                coverage_start=self.measurement_started,
                as_of=None,
                limited=True,
                evidence_limited=True,
                covered_hours=None,
                coverage_fraction=None,
            )
            for point in value["points"]:
                point["coverage"] = None
        counts = dict.fromkeys(STATES, 0)
        known = expected = 0
        for row in self.current.values():
            state = (
                row["state"]
                if isinstance(row.get("state"), str) and row["state"] in STATES and self.reliable
                else "unknown"
            )
            counts[state] += 1
            known += state == "offline" and row["attention"] == "known"
            expected += state == "offline" and row["attention"] == "expected"
        return {
            **value,
            "counts": counts,
            "known_offline": known,
            "expected_offline": expected,
            "inventory_coverage": self.inventory_coverage,
            "reliable_now": self.reliable,
            "current_as_of": self.as_of,
            "cache_state": self.cache_state,
            "cache_pending": self._dirty or bool(self._worker and not self._worker.done()),
            "cache_as_of": self.cache_as_of,
            "cache_error": self.cache_error,
            "cache_error_stage": self.cache_error_stage,
            "cache_failure_count": self.cache_failure_count,
            "storage": self.storage(),
            "priorities": self.priorities(),
            "integrations": self.heatmaps.get(window, {"total": 0, "items": [], "limited": False}),
            "read_only": True,
            "power_expectation": "Only explicit local power declarations; silence/battery value "
            "does not prove expected sleep.",
        }

    def heatmap(self, window):
        return self.heatmaps.get(window, {"total": 0, "items": [], "limited": False})

    def priorities(self):
        result = []
        now = time.time()
        attention = (
            "NOT EXISTS (SELECT 1 FROM case_annotations a WHERE a.key=i.key "
            "AND a.case_first_seen=i.first_seen AND a.status IN ('known','expected','snoozed') "
            "AND (a.expires IS NULL OR a.expires>?))"
        )
        critical = self.store.rows(
            "SELECT i.key,i.title,i.source FROM issues i WHERE i.active=1 "
            "AND i.severity='critical' AND " + attention + " ORDER BY i.first_seen,i.key LIMIT 1",
            (now,),
        )
        for row in critical:
            result.append(
                {
                    "key": row["key"],
                    "title": row["title"],
                    "kind": "health",
                    "impact": "Active critical source observation; inspect its retained facts.",
                    "manual_step": "Open the source case and perform its documented manual check.",
                    "validation": "Compare a later retained source observation; disappearance "
                    "alone does not prove recovery.",
                    "href": "#issues/" + quote(row["key"], safe=""),
                    "priority": 0,
                }
            )
        candidates = []
        for row in self.current.values():
            if not self.reliable:
                continue
            policy = self.policies.get(row["device_id"], {})
            worsened = row["attention"] == "known" and finite(policy.get("worsened_at"))
            if row["state"] in {"online", "excluded"} or (
                row["state"] == "unknown" and not worsened
            ):
                continue
            if row["attention"] != "review" and not worsened:
                continue
            new = (
                row.get("episode_kind") == "transition"
                and finite(row.get("episode_started"))
                and finite(self.as_of)
                and row["episode_started"] >= self.as_of - 86400
            )
            candidates.append((row, new, worsened))
        grouped = defaultdict(list)
        for row, new, worsened in candidates:
            platform = row["platforms"][0] if row["platforms"] else "unknown"
            grouped[platform].append((row, new, worsened))
        for platform, items in grouped.items():
            items.sort(key=lambda item: (item[0]["started"], item[0]["device_id"]))
            clusters = []
            for item in items:
                if (
                    platform != "unknown"
                    and clusters
                    and item[0]["started"] - clusters[-1][0][0]["started"] <= 300
                ):
                    clusters[-1].append(item)
                else:
                    clusters.append([item])
            for cluster in clusters:
                row = cluster[0][0]
                new = any(item[1] for item in cluster)
                worsened = any(item[2] for item in cluster)
                multiple = len(cluster) > 1 and platform != "unknown"
                offline_count = sum(item[0]["state"] == "offline" for item in cluster)
                partial_count = sum(item[0]["state"] == "partial" for item in cluster)
                unknown_count = sum(item[0]["state"] == "unknown" for item in cluster)
                result.append(
                    {
                        "key": ("cluster:" + platform + ":" if multiple else "device:")
                        + row["device_id"],
                        "device_id": row["device_id"],
                        "device_count": len(cluster) if multiple else 1,
                        "related_devices": [
                            {"device_id": item[0]["device_id"], "name": item[0]["name"]}
                            for item in cluster[:8]
                        ]
                        if multiple
                        else [],
                        "related_devices_limited": multiple and len(cluster) > 8,
                        "title": (
                            "Worsened evidence"
                            if worsened
                            else "New observations"
                            if new
                            else "Persistent backlog"
                        )
                        + (
                            f" · {len(cluster)} devices on {platform}"
                            if multiple
                            else " · " + row["name"]
                        ),
                        "evidence_since": min(
                            item[0]["episode_started"]
                            if finite(item[0].get("episode_started"))
                            else item[0]["started"]
                            for item in cluster
                        ),
                        "new_device_count": sum(item[1] for item in cluster),
                        "kind": "worsened_device"
                        if worsened
                        else "new_device"
                        if new
                        else "device_backlog",
                        "impact": f"{offline_count} unavailable · {partial_count} partial · "
                        f"{unknown_count} unknown. "
                        "Cause unknown.",
                        "scope_note": "Co-observed unavailable/partial devices; shared membership "
                        "is correlation, "
                        "not a proven simultaneous physical outage or cause. "
                        "The primary link opens "
                        "the first affected device; other retained members are linked separately.",
                        "manual_step": "Check this device's power and expected sleep manually, "
                        "then inspect its integration.",
                        "action_label": "Inspect first affected device"
                        if multiple
                        else "Inspect device evidence",
                        "validation": "Record a manual check and inspect later covered "
                        "device observations.",
                        "href": "#devices/reliability?device=" + quote(row["device_id"], safe=""),
                        "priority": 1 if new or worsened else 3 if row["state"] == "offline" else 4,
                    }
                )
        # Recency uses authoritative native run time, never issue.last_seen (which polls refresh).
        recent = self.store.rows(
            "SELECT r.entity_id,r.run_id,r.started FROM runs r JOIN run_timing t "
            "USING(entity_id,run_id) JOIN issues i ON i.key='automation:'||r.entity_id "
            "AND i.active=1 AND json_extract(i.detail,'$.run_id')=r.run_id "
            "WHERE r.started>=? AND r.outcome='failed' AND t.start_source='ha_trace' AND "
            + attention
            + " AND NOT EXISTS (SELECT 1 FROM runs later JOIN run_timing lt "
            "USING(entity_id,run_id) WHERE later.entity_id=r.entity_id "
            "AND lt.start_source IN ('ha_trace','event') AND later.run_id NOT LIKE 'event:%' "
            "AND (later.started>r.started OR (later.started=r.started AND later.run_id>r.run_id))) "
            "ORDER BY r.started DESC,r.entity_id,r.run_id LIMIT 3",
            ((self.as_of or time.time()) - 86400, now),
        )
        for row in recent:
            result.append(
                {
                    "key": "run:" + row["run_id"],
                    "title": row["entity_id"],
                    "kind": "recent_failure",
                    "impact": "A recent native trace reports failure.",
                    "manual_step": "Inspect the actual failing step and compare a covered run.",
                    "validation": "Inspect a later naturally retained run; Vision never "
                    "executes it.",
                    "href": "#automations/"
                    + quote(row["entity_id"], safe="")
                    + "?run_id="
                    + quote(row["run_id"], safe=""),
                    "priority": 2,
                }
            )
        return sorted(result, key=lambda row: (row["priority"], row["key"]))[:3]

    def list_devices(self, *, state="all", platform="", page=1, limit=25):
        if state not in STATES | {"all"} or not 1 <= limit <= 100 or not 1 <= page <= 10000:
            raise ValueError("Invalid device filter")
        rows = [
            r
            for r in self.current.values()
            if (state == "all" or (r["state"] if self.reliable else "unknown") == state)
            and (not platform or platform in r["platforms"])
        ]
        rows.sort(key=lambda r: (r["state"] != "offline", r["name"], r["device_id"]))
        start = (page - 1) * limit
        return {
            "items": [self.device_summary(r) for r in rows[start : start + limit]],
            "total": len(rows),
            "page": page,
            "limit": limit,
            "has_more": start + limit < len(rows),
            "reliable_now": self.reliable,
        }

    def device_summary(self, row):
        result = {
            key: row[key]
            for key in (
                "device_id",
                "name",
                "state",
                "attention",
                "power",
                "started",
                "platforms",
                "reason",
                "cohort",
                "evidence",
            )
        }
        state = (
            row["state"]
            if isinstance(row.get("state"), str) and row["state"] in STATES
            else "unknown"
        )
        result["evidence_at"] = row.get("evidence_at") if finite(row.get("evidence_at")) else None
        result["observed_state"] = state
        result["state"] = state if self.reliable else "unknown"
        return result

    def device(self, device_id):
        if device_id not in self.current:
            raise LookupError("Device is not in the retained observed cohort")
        row = self.current[device_id]
        history = self.store.rows(
            "SELECT state,started,ended,attention,reason FROM device_observations "
            "WHERE device_id=? ORDER BY id DESC LIMIT 30",
            (device_id,),
        )
        history_start = max(
            min((r["started"] for r in history), default=self.cache_as_of or 0),
            (self.cache_as_of or 0) - 30 * 86400,
        )
        history_end = max(self.cache_as_of or 0, history_start)
        known_coverage = union_intervals(self.coverage, history_start, history_end)
        gaps, cursor = [], history_start
        for a, b in known_coverage:
            if a > cursor:
                gaps.append({"started": cursor, "ended": a})
            cursor = b
        if cursor < history_end:
            gaps.append({"started": cursor, "ended": history_end})
        checks = self.store.rows(
            "SELECT * FROM device_checks WHERE device_id=? ORDER BY created DESC,id DESC LIMIT 20",
            (device_id,),
        )
        for check in checks:
            observed = (
                covered_intervals(
                    [(check["created"], self.cache_as_of)],
                    self.coverage,
                    check["created"],
                    self.cache_as_of,
                )
                if self.cache_as_of and self.cache_as_of > check["created"]
                else []
            )
            valid = (
                self.reliable
                and not self.intervals_limited
                and self.compiled_current.get(device_id) == (row["state"], row["cohort"])
                and self.cache_as_of
                and self.cache_as_of > check["created"]
                and seconds(observed) >= self.cache_as_of - check["created"] - 0.001
                and continuous_known(
                    self.intervals.get(device_id, []),
                    self.coverage,
                    check["created"],
                    self.cache_as_of,
                    check["cohort"],
                )
            )
            check["validation"] = "unknown"
            if (
                valid
                and row["state"] == "online"
                and check["before_state"] in {"offline", "partial"}
            ):
                check["validation"] = "observed_recovery"
            elif valid and row["state"] in {"offline", "partial"}:
                check["validation"] = "still_" + row["state"]
            check["meaning"] = "Later observations only; a manual check is not proof of causation."
        policy = self.store.rows("SELECT * FROM device_policies WHERE device_id=?", (device_id,))
        return {
            **self.device_summary(row),
            "reliable_now": self.reliable,
            "members": self.members.get(device_id, [])[:64],
            "member_count": len(self.members.get(device_id, [])),
            "history": history,
            "coverage_gaps": gaps[:30],
            "coverage_gaps_limited": len(gaps) > 30,
            "checks": checks,
            "policy": policy[0] if policy else None,
            "coverage_start": self.cache.get("30d", {}).get("coverage_start"),
            "cache_pending": self._dirty or bool(self._worker and not self._worker.done()),
        }

    def policy(self, device_id, attention, power, note, *, acknowledge_worsening=False):
        if device_id not in self.current:
            raise LookupError("Device is not in the retained observed cohort")
        if attention not in {"review", "known", "expected"} or power not in {
            "unknown",
            "battery",
            "mains",
        }:
            raise ValueError("Invalid local device policy")
        if acknowledge_worsening and (
            not self.reliable
            or self.current[device_id]["state"] not in {"online", "partial", "offline"}
        ):
            raise ValueError("Known current device evidence is required to acknowledge worsening")
        now = time.time()
        row = self.current[device_id]
        previous = self.store.rows("SELECT * FROM device_policies WHERE device_id=?", (device_id,))
        previous = previous[0] if previous else None
        baseline = (
            previous
            if previous and previous["attention"] == attention and not acknowledge_worsening
            else {
                "baseline_state": row["state"] if self.reliable else "unknown",
                "baseline_cohort": row["cohort"],
                "baseline_at": self.as_of,
                "worsened_at": None,
                "worsened_cohort": None,
            }
        )
        before_policy = self.policies.get(device_id)
        try:
            with self.observation_transaction(device_id):
                self.store.execute(
                    "INSERT INTO device_policies VALUES (?,?,?,?,?,?,?,?,?,?) ON "
                    "CONFLICT(device_id) DO UPDATE SET attention=excluded.attention,"
                    "power=excluded.power,note=excluded.note,updated=excluded.updated,"
                    "baseline_state=excluded.baseline_state,"
                    "baseline_cohort=excluded.baseline_cohort,"
                    "baseline_at=excluded.baseline_at,worsened_at=excluded.worsened_at,"
                    "worsened_cohort=excluded.worsened_cohort",
                    (
                        device_id,
                        attention,
                        power,
                        self.monitor.redactor.text(note, 300),
                        now,
                        baseline["baseline_state"],
                        baseline["baseline_cohort"],
                        baseline["baseline_at"],
                        baseline["worsened_at"],
                        baseline["worsened_cohort"],
                    ),
                )
                self.policies[device_id] = self.store.rows(
                    "SELECT * FROM device_policies WHERE device_id=?", (device_id,)
                )[0]
                self.record(
                    device_id,
                    row["evidence"],
                    row["cohort"],
                    attention,
                    power,
                    row["name"],
                    row["platforms"],
                    now,
                    "local_policy",
                    present=row.get("registry_present", True),
                    removed_at=row.get("removed_at"),
                )
        except BaseException:
            if before_policy is None:
                self.policies.pop(device_id, None)
            else:
                self.policies[device_id] = before_policy
            raise
        self.request_cache(now)
        return self.device(device_id)

    def check(self, device_id, kind, note):
        if device_id not in self.current:
            raise LookupError("Device is not in the retained observed cohort")
        if kind not in {"power", "integration", "connection", "other"}:
            raise ValueError("Invalid manual check kind")
        with self.store.transaction():
            if self.store.rows("SELECT count(*) n FROM device_checks")[0]["n"] >= MAX_CHECKS:
                raise ValueError(
                    "Local check history capacity reached; existing records are retained"
                )
            row = self.current[device_id]
            self.store.execute(
                "INSERT INTO device_checks(device_id,created,kind,note,before_state,cohort) "
                "VALUES (?,?,?,?,?,?)",
                (
                    device_id,
                    time.time(),
                    kind,
                    self.monitor.redactor.text(note, 400),
                    row["state"] if self.reliable else "unknown",
                    row["cohort"],
                ),
            )
        return self.device(device_id)
