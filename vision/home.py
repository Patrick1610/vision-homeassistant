"""Bounded local presentation. Names, preferences and subjective reports never enter AI."""

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from .reliability import finite, union_intervals

MAX_PROBLEMS = 10000
MAX_FEEDBACK = 20000
MAX_DEVICE_PREFERENCES = 6000
MAX_SNAPSHOT_BYTES = 4096
MIN_REFRESH_SECONDS = 2.0


class FeedbackError(ValueError):
    """Only fixed local guidance may cross the API boundary."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:32]


def problem_id(kind, target):
    return kind + "-" + digest(target)


class Personalization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=256)
    importance: Literal["low", "normal", "high"] | None = None
    known_issue: bool | None = None
    usual_behavior: bool | None = None
    acknowledge_worsening: bool = False


class PreferencesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    locale: Literal["auto", "nl", "en"] | None = None
    intake: Literal["draft", "complete", "skipped"] | None = None
    devices: list[Personalization] = Field(default_factory=list, max_length=100)


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")
    episode: str = Field(pattern=r"^[a-f0-9]{32}$")
    kind: Literal["checked", "no_change", "seems_recovered", "later"]
    check_kind: Literal["power", "integration", "connection", "other"] = "other"
    note: str = Field(default="", max_length=400)


class HomeExperience:
    def __init__(self, monitor):
        self.monitor, self.store = monitor, monitor.store
        self.cache, self.pending, self.timer = [], True, None
        self.syncing = False
        self.as_of, self.limited = None, False
        self.last_refresh = 0.0
        self.last_retention = 0.0
        self.snapshot_hashes = {}
        self.cache_ids = set()
        self.coverage_limited, self.continuous_since = True, None
        self.current_coverage = []
        self.personal = {
            row["device_id"]: row
            for row in self.store.rows("SELECT * FROM home_device_preferences LIMIT 6000")
        }
        self.refresh()

    def invalidate(self):
        self.pending = True
        if self.syncing:
            return
        if self.timer is None:
            try:
                delay = max(0.25, MIN_REFRESH_SECONDS - (time.monotonic() - self.last_refresh))
                self.timer = asyncio.get_running_loop().call_later(delay, self.refresh)
            except RuntimeError:
                pass

    def close(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def device_name(self, device_id):
        value = self.monitor.reliability.current.get(device_id, {}).get("name")
        return value[:120] if isinstance(value, str) and value != device_id else None

    def room(self, device_id):
        devices = self.monitor.local_device_locations
        entry = devices.get(device_id, {})
        if entry.get("area_id") is not None:
            return self.monitor.local_areas.get(entry["area_id"])
        parent_id = entry.get("parent_device_id")
        parent = devices.get(parent_id, {}) if parent_id != device_id else {}
        # HA child entries inherit from a main device, not an arbitrary chain.
        if not parent.get("parent_device_id"):
            return self.monitor.local_areas.get(parent.get("area_id"))
        return None

    def preference(self, row):
        pref = self.personal.get(row["device_id"], {})
        old = self.monitor.reliability.policies.get(row["device_id"], {})
        known = pref.get("known_issue")
        usual = pref.get("usual_behavior")
        known = row.get("attention") == "known" if known is None else bool(known)
        usual = row.get("attention") == "expected" if usual is None else bool(usual)
        effective = "expected" if usual else "known" if known else "review"
        ack = pref.get("acknowledged_at") or 0
        worsened = finite(old.get("worsened_at")) and old["worsened_at"] > ack
        worsened = worsened or (finite(pref.get("worsened_at")) and pref["worsened_at"] > ack)
        return {
            "importance": pref.get("importance", "normal"),
            "known_issue": known,
            "usual_behavior": usual,
            "effective_context": effective,
            "worsened": bool(worsened),
        }

    def transition(self, row):
        at, rel = row.get("episode_started"), self.monitor.reliability
        return (
            rel.reliable
            and not rel.history_blocked
            and row.get("episode_kind") == "transition"
            and finite(at)
            and finite(rel.as_of)
            and 0 <= rel.as_of - at <= 86400
            and not self.coverage_limited
            and finite(self.continuous_since)
            and at >= self.continuous_since - 0.001
        )

    def device_problem(self, row):
        pref = self.preference(row)
        state = row.get("state") if self.monitor.reliability.reliable else "unknown"
        changed = bool(self.transition(row))
        active = state in {"offline", "partial"} and row.get("registry_present", True)
        actionable = active and (pref["effective_context"] == "review" or pref["worsened"])
        return {
            "problem_id": problem_id("device", row["device_id"]),
            "kind": "device",
            "target": row["device_id"],
            "episode": digest([row["cohort"], row.get("episode_started"), state]),
            "name": self.device_name(row["device_id"]),
            "room": self.room(row["device_id"]),
            "state": state,
            "source_active": bool(active),
            "actionable": bool(actionable),
            "changed": changed,
            "tier": 1 if changed or pref["worsened"] else 2,
            "observed_since": row.get("episode_started") or row.get("started"),
            "as_of": self.monitor.reliability.as_of,
            "preference": pref,
            "cohort": row["cohort"],
            "platforms": row.get("platforms", [])[:8],
            "members": [],
            "selection": {"kind": "device", "device_id": row["device_id"]},
        }

    def refresh(self):
        if self.syncing:
            self.pending = True
            return
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.last_refresh = time.monotonic()
        if not self.monitor.reliability.reliable:
            # A gap does not invalidate the earlier proof or manufacture recovery.
            self.pending = True
            return
        self.prune()
        self.personal = {
            row["device_id"]: row
            for row in self.store.rows("SELECT * FROM home_device_preferences LIMIT 6000")
        }
        coverage = self.store.rows(
            "SELECT started,observed_until FROM device_coverage WHERE observed_until>=? "
            "ORDER BY id DESC LIMIT 1025",
            ((self.monitor.reliability.as_of or time.time()) - 86400,),
        )
        self.coverage_limited = len(coverage) > 1024
        self.current_coverage = [
            (r["started"], r["observed_until"])
            for r in coverage[:1024]
            if finite(r["started"])
            and finite(r["observed_until"])
            and r["started"] <= r["observed_until"]
        ]
        end = self.monitor.reliability.as_of
        merged = union_intervals(self.current_coverage, end - 86400, end) if finite(end) else []
        self.continuous_since = merged[-1][0] if merged and merged[-1][1] >= end - 0.001 else None
        newly_worsened = []
        for key, pref in self.personal.items():
            row = self.monitor.reliability.current.get(key)
            if (
                row
                and pref["baseline_state"] == "partial"
                and row["state"] == "offline"
                and pref["baseline_cohort"] == row["cohort"]
                and self.transition(row)
                and not finite(pref.get("worsened_at"))
            ):
                pref.update(worsened_at=row["episode_started"], worsened_cohort=row["cohort"])
                newly_worsened.append(pref)
        if newly_worsened:
            with self.store.transaction():
                for pref in newly_worsened:
                    self.store.execute(
                        "UPDATE home_device_preferences SET worsened_at=?,"
                        "worsened_cohort=? WHERE device_id=?",
                        (pref["worsened_at"], pref["worsened_cohort"], pref["device_id"]),
                    )
        rows = []
        for row in self.monitor.reliability.current.values():
            if row.get("state") in {"offline", "partial"}:
                rows.append(self.device_problem(row))
        # Independent source admission happens BEFORE any three-card limit.
        # Poll-refreshed issue.last_seen is never evidence of a recent failure.
        now = time.time()
        attention = (
            "NOT EXISTS (SELECT 1 FROM case_annotations a WHERE a.key=i.key "
            "AND a.case_first_seen=i.first_seen AND a.status IN ('known','expected','snoozed') "
            "AND (a.expires IS NULL OR a.expires>?))"
        )
        critical = self.store.rows(
            "SELECT i.key,i.title,i.first_seen,NULL entity_id,NULL run_id FROM issues i "
            "WHERE i.active=1 AND i.severity='critical' AND "
            + attention
            + " ORDER BY i.first_seen,i.key LIMIT 21",
            (now,),
        )
        recent = self.store.rows(
            "SELECT i.key,i.title,i.first_seen,r.entity_id,r.run_id FROM runs r JOIN "
            "run_timing t USING(entity_id,run_id) JOIN issues i "
            "ON i.key IN ('automation:'||r.entity_id,'automation_step:'||r.entity_id) "
            "AND i.active=1 AND json_valid(i.detail) "
            "AND json_extract(i.detail,'$.run_id')=r.run_id "
            "WHERE r.started>=? AND (r.outcome='failed' OR i.source='automation_step') "
            "AND t.start_source='ha_trace' AND "
            + attention
            + " AND NOT EXISTS (SELECT 1 FROM runs later JOIN run_timing lt "
            "USING(entity_id,run_id) WHERE later.entity_id=r.entity_id "
            "AND lt.start_source IN ('ha_trace','event') AND later.run_id NOT LIKE 'event:%' "
            "AND (later.started>r.started OR (later.started=r.started AND later.run_id>r.run_id))) "
            "ORDER BY r.started DESC,r.entity_id,r.run_id,"
            "CASE i.source WHEN 'automation' THEN 0 ELSE 1 END,i.key LIMIT 51",
            (now - 86400, now),
        )
        sources_limited = len(critical) > 20 or len(recent) > 50
        seen_sources = set()
        seen_runs = set()
        for item in critical[:20] + recent[:50]:
            key = item["key"]
            if (key, item["first_seen"]) in seen_sources:
                continue
            seen_sources.add((key, item["first_seen"]))
            is_run = item["run_id"] is not None
            run_identity = (item["entity_id"], item["run_id"])
            if is_run and run_identity in seen_runs:
                continue
            if is_run:
                seen_runs.add(run_identity)
            href = (
                "#automations/"
                + quote(item["entity_id"], safe="")
                + "?run_id="
                + quote(item["run_id"], safe="")
                if is_run
                else "#issues/" + quote(key, safe="")
            )
            rows.append(
                {
                    "problem_id": problem_id("source", [key, item["first_seen"]]),
                    "kind": "source",
                    "target": key,
                    "episode": digest([key, item["first_seen"], item["run_id"]]),
                    "name": (
                        self.monitor.entities.get(item["entity_id"], {}).get("name")
                        or item["title"]
                    )[:120],
                    "room": None,
                    "state": "step_errors"
                    if key.startswith("automation_step:")
                    else "source_failure",
                    "source_active": True,
                    "actionable": True,
                    "changed": is_run,
                    "tier": 3 if is_run else 0,
                    "observed_since": item["first_seen"],
                    "as_of": self.monitor.last_sync,
                    "preference": {"importance": "normal", "effective_context": "review"},
                    "expert_href": href,
                    "selection": {
                        "kind": "automation_run",
                        "entity_id": item["entity_id"],
                        "run_id": item["run_id"],
                        "case_key": key,
                        "case_first_seen": item["first_seen"],
                    }
                    if is_run
                    else {
                        "kind": "source_case",
                        "case_key": key,
                        "case_first_seen": item["first_seen"],
                    },
                    "members": [],
                }
            )
        # Only covered *transition* observations can form a group. A first
        # imported inventory, same platform alone, or an observation gap cannot.
        groups = defaultdict(list)
        for row in rows:
            if row["kind"] == "device" and row["actionable"] and row["changed"]:
                platforms = row["platforms"]
                if len(platforms) == 1 and platforms[0] != "unknown":
                    groups[(platforms[0], self.monitor.local_upstream.get(row["target"]))].append(
                        row
                    )
        grouped = set()
        for (platform, _upstream), items in groups.items():
            clusters = []
            for item in sorted(items, key=lambda r: (r["observed_since"], r["problem_id"])):
                if clusters and item["observed_since"] - clusters[-1][0]["observed_since"] <= 300:
                    clusters[-1].append(item)
                else:
                    clusters.append([item])
            for cluster in clusters:
                if len(cluster) < 2:
                    continue
                members = sorted(r["problem_id"] for r in cluster)
                identity = [[r["problem_id"], r["episode"]] for r in cluster]
                group = {
                    **cluster[0],
                    "problem_id": problem_id(
                        "group", [platform, sorted([r["problem_id"], r["cohort"]] for r in cluster)]
                    ),
                    "kind": "group",
                    "target": platform,
                    "name": None,
                    "room": None,
                    "episode": digest(sorted(identity)),
                    "members": members[:32],
                    "member_count": len(members),
                    "members_omitted": max(0, len(members) - 32),
                    "correlation": "covered_transitions_same_integration",
                    "preference": {
                        "importance": "high"
                        if any(r["preference"]["importance"] == "high" for r in cluster)
                        else "normal",
                        "effective_context": "review",
                    },
                }
                rows.append(group)
                group["selection"] = {
                    "kind": "device_group",
                    "problem_id": group["problem_id"],
                    "episode": group["episode"],
                    "omitted": group["members_omitted"],
                }
                group["member_labels"] = [
                    {"name": r["name"], "room": r["room"]} for r in cluster[:2]
                ]
                upstream = {self.monitor.local_upstream.get(r["target"]) for r in cluster}
                group["declared_shared_upstream"] = len(upstream) == 1 and None not in upstream
                grouped.update(members)
        for row in rows:
            row["grouped"] = row["problem_id"] in grouped
        # New presentation history has explicit admission, never an eviction of
        # existing source history, preferences, checks or billing.
        existing = {
            r["problem_id"]: r
            for r in self.store.rows(
                "SELECT problem_id,present FROM home_problems LIMIT ?", (MAX_PROBLEMS,)
            )
        }
        self.limited = sources_limited or self.coverage_limited
        admitted = set()
        changed = []
        hashes = {}
        now = time.time()
        for row in rows:
            # A later unchanged sync is not a new presentation-history boundary.
            body = json.dumps({**row, "as_of": None}, ensure_ascii=False, separators=(",", ":"))
            if len(body.encode()) > MAX_SNAPSHOT_BYTES:
                self.limited = True
                continue
            old = existing.get(row["problem_id"])
            if not old and len(existing) >= MAX_PROBLEMS:
                self.limited = True
                continue
            body_hash = hashlib.sha256(body.encode()).hexdigest()
            hashes[row["problem_id"]] = body_hash
            if (
                not old
                or self.snapshot_hashes.get(row["problem_id"]) != body_hash
                or not old["present"]
            ):
                changed.append((row, body))
            if not old:
                existing[row["problem_id"]] = {"present": 0}
            admitted.add(row["problem_id"])
        present = admitted
        retired = [key for key, r in existing.items() if r["present"] and key not in present]
        if changed or retired:
            with self.store.transaction():
                self.store.db.executemany(
                    "INSERT INTO home_problems VALUES (?,?,?,?,?,?,?,1) ON "
                    "CONFLICT(problem_id) DO UPDATE SET episode=excluded.episode,"
                    "snapshot=excluded.snapshot,updated=excluded.updated,present=1 "
                    "WHERE home_problems.snapshot<>excluded.snapshot "
                    "OR home_problems.present=0",
                    [
                        (
                            row["problem_id"],
                            row["kind"],
                            row["target"],
                            row["episode"],
                            body,
                            now,
                            now,
                        )
                        for row, body in changed
                    ],
                )
                self.store.db.executemany(
                    "UPDATE home_problems SET present=0,updated=? WHERE problem_id=?",
                    [(now, key) for key in retired],
                )
        admitted_groups = {
            key
            for r in rows
            if r["kind"] == "group" and r["problem_id"] in admitted
            for key in r["members"]
        }
        for row in rows:
            row["grouped"] = row["problem_id"] in admitted_groups
        self.cache = sorted(
            [r for r in rows if r["problem_id"] in admitted],
            key=lambda r: (
                r["tier"],
                {"high": 0, "normal": 1, "low": 2}[r["preference"]["importance"]],
                r["problem_id"],
            ),
        )
        self.as_of, self.pending = self.monitor.reliability.as_of, False
        self.cache_ids = {r["problem_id"] for r in self.cache}
        self.snapshot_hashes = hashes

    def prune(self):
        now = time.time()
        if now - self.last_retention < 60:
            return
        # Only disposable presentation snapshots expire. Owner reports and every
        # earlier source/AI/policy/check/billing table are outside this cleanup.
        before = now - self.monitor.settings.retention_days * 86400
        eligible = self.store.rows(
            "SELECT p.problem_id FROM home_problems p WHERE p.present=0 AND p.updated<? "
            "AND NOT EXISTS (SELECT 1 FROM home_feedback f WHERE f.problem_id=p.problem_id) "
            "ORDER BY p.updated,p.problem_id LIMIT 1000",
            (before,),
        )
        if eligible:
            with self.store.transaction():
                self.store.db.executemany(
                    "DELETE FROM home_problems WHERE problem_id=? AND present=0 "
                    "AND NOT EXISTS (SELECT 1 FROM home_feedback f "
                    "WHERE f.problem_id=home_problems.problem_id)",
                    [(r["problem_id"],) for r in eligible],
                )
        self.last_retention = now

    def preferences(self):
        value = self.store.rows("SELECT locale,intake,updated FROM home_preferences WHERE id=1")[0]
        value["configured_devices"] = len(self.personal)
        return value

    def devices(self, page=1, limit=25, q=""):
        values = []
        for row in self.monitor.reliability.current.values():
            if not row.get("registry_present", True):
                continue
            name, room = self.device_name(row["device_id"]), self.room(row["device_id"])
            if q and q.casefold() not in ((name or "") + " " + (room or "")).casefold():
                continue
            values.append(
                {
                    "device_id": row["device_id"],
                    "name": name,
                    "room": room,
                    "state": row["state"] if self.monitor.reliability.reliable else "unknown",
                    "preference": self.preference(row),
                    "problem_id": problem_id("device", row["device_id"]),
                    "problem_available": problem_id("device", row["device_id"]) in self.cache_ids,
                }
            )
        values.sort(key=lambda r: ((r["name"] or "").casefold(), r["device_id"]))
        start = (page - 1) * limit
        return {
            "items": values[start : start + limit],
            "total": len(values),
            "page": page,
            "has_more": start + limit < len(values),
            "rooms": self.monitor.local_area_status,
        }

    def save_preferences(self, value):
        if value.intake is not None and any(d.acknowledge_worsening for d in value.devices):
            raise ValueError("Intake cannot acknowledge worsening")
        ids = [d.device_id for d in value.devices]
        if len(ids) != len(set(ids)) or any(
            key not in self.monitor.reliability.current for key in ids
        ):
            raise ValueError("Unknown or duplicate registered device")
        for item in value.devices:
            row = self.monitor.reliability.current[item.device_id]
            if item.acknowledge_worsening and (
                not self.monitor.reliability.reliable
                or row["state"] not in {"online", "partial", "offline"}
            ):
                raise ValueError("Covered current evidence required for acknowledgement")
        now = time.time()
        with self.store.transaction():
            count = self.store.rows("SELECT count(*) n FROM home_device_preferences")[0]["n"]
            if count + sum(key not in self.personal for key in ids) > MAX_DEVICE_PREFERENCES:
                raise ValueError("Local preference capacity reached")
            for item in value.devices:
                row, old = (
                    self.monitor.reliability.current[item.device_id],
                    self.personal.get(item.device_id),
                )
                importance = item.importance or (old["importance"] if old else "normal")
                known = (
                    item.known_issue
                    if "known_issue" in item.model_fields_set
                    else old["known_issue"]
                    if old
                    else None
                )
                usual = (
                    item.usual_behavior
                    if "usual_behavior" in item.model_fields_set
                    else old["usual_behavior"]
                    if old
                    else None
                )
                inherited = self.monitor.reliability.policies.get(item.device_id)
                baseline = (
                    old
                    if old and not item.acknowledge_worsening
                    else {
                        "baseline_state": inherited["baseline_state"]
                        if inherited and not item.acknowledge_worsening
                        else row["state"],
                        "baseline_cohort": inherited["baseline_cohort"]
                        if inherited and not item.acknowledge_worsening
                        else row["cohort"],
                        "acknowledged_at": now if item.acknowledge_worsening else None,
                        "worsened_at": None,
                        "worsened_cohort": None,
                    }
                )
                self.store.execute(
                    "INSERT INTO home_device_preferences VALUES (?,?,?,?,?,?,?,?,?,?) ON "
                    "CONFLICT(device_id) DO UPDATE SET importance=excluded.importance,"
                    "known_issue=excluded.known_issue,usual_behavior=excluded.usual_behavior,"
                    "baseline_state=excluded.baseline_state,"
                    "baseline_cohort=excluded.baseline_cohort,"
                    "acknowledged_at=excluded.acknowledged_at,worsened_at=excluded.worsened_at,"
                    "worsened_cohort=excluded.worsened_cohort,updated=excluded.updated",
                    (
                        item.device_id,
                        importance,
                        known,
                        usual,
                        baseline["baseline_state"],
                        baseline["baseline_cohort"],
                        baseline["acknowledged_at"],
                        baseline["worsened_at"],
                        baseline["worsened_cohort"],
                        now,
                    ),
                )
            if value.locale is not None:
                self.store.execute(
                    "UPDATE home_preferences SET locale=?,updated=? WHERE id=1", (value.locale, now)
                )
            if value.intake is not None:
                self.store.execute(
                    "UPDATE home_preferences SET intake=?,updated=? WHERE id=1", (value.intake, now)
                )
        self.personal = {
            r["device_id"]: r
            for r in self.store.rows("SELECT * FROM home_device_preferences LIMIT 6000")
        }
        self.refresh()
        return self.preferences()

    def overview(self, window="24h"):
        rel = self.monitor.reliability
        items = [r for r in self.cache if r["actionable"] and not r["grouped"]]
        visible = finite(self.as_of)
        current = self.monitor.connected and rel.reliable
        assessed = any(
            r.get("state") in {"online", "offline", "partial"} for r in rel.current.values()
        )
        return {
            "status": "attention"
            if visible and current and items
            else "quiet"
            if visible and current and assessed and not self.pending and not self.limited
            else "limited",
            "as_of": self.as_of,
            "pending": self.pending,
            "priorities": [self.presentation(r) for r in items[:3]] if visible else [],
            "actionable_total": len(items)
            if visible and current and not self.pending and not self.limited
            else None,
            "backlog_total": sum(r["source_active"] and not r["actionable"] for r in self.cache),
            "read_only": True,
            "limited": self.limited,
            "coverage": {
                "connected": self.monitor.connected,
                "reliable_now": rel.reliable,
                "cache_state": rel.cache_state,
                "history_blocked": rel.history_blocked,
                "inventory": rel.inventory_coverage,
            },
            "rooms": self.monitor.local_area_status,
            "metrics": rel.snapshot(window),
            "preferences": self.preferences(),
        }

    def problems(self, page=1, limit=25, mode="attention"):
        if not finite(self.as_of) and mode == "attention":
            return {
                "items": [],
                "total": None,
                "page": page,
                "has_more": False,
                "as_of": self.as_of,
                "pending": True,
                "limited": self.limited,
            }
        if mode == "all":
            current = {r["problem_id"]: r for r in self.cache}
            saved = self.store.rows(
                "SELECT problem_id,snapshot,present FROM home_problems "
                "ORDER BY updated DESC,problem_id LIMIT ? OFFSET ?",
                (limit + 1, (page - 1) * limit),
            )
            items = [
                self.presentation(
                    current.get(
                        r["problem_id"],
                        {
                            **json.loads(r["snapshot"]),
                            "retained_only": True,
                            "actionable": False,
                            "state": "unknown",
                        },
                    )
                )
                for r in saved[:limit]
            ]
            return {
                "items": items,
                "page": page,
                "has_more": len(saved) > limit,
                "as_of": self.as_of,
                "pending": self.pending,
                "limited": self.limited,
            }
        rows = [
            r
            for r in self.cache
            if not r["grouped"]
            and (mode == "all" or (r["actionable"] if mode == "attention" else not r["actionable"]))
        ]
        start = (page - 1) * limit
        return {
            "items": [self.presentation(r) for r in rows[start : start + limit]],
            "total": len(rows),
            "page": page,
            "has_more": start + limit < len(rows),
            "as_of": self.as_of,
            "pending": self.pending,
            "limited": self.limited,
        }

    def presentation(self, row):
        if not self.monitor.connected or not self.monitor.reliability.reliable:
            return {**row, "state": "unknown", "stale": True}
        return row

    def dossier(self, key):
        saved = self.store.rows("SELECT * FROM home_problems WHERE problem_id=?", (key,))
        if not saved:
            raise LookupError("Unknown local problem")
        stored = saved[0]
        row = next(
            (r for r in self.cache if r["problem_id"] == key), json.loads(stored["snapshot"])
        )
        result = {
            "problem": self.presentation(row),
            "current": bool(stored["present"]),
            "pending": self.pending,
            "facts": [],
            "unknowns": ["cause_unknown"],
            "members": [],
            "members_omitted": 0,
            "feedback": self.store.rows(
                "SELECT * FROM home_feedback WHERE problem_id=? "
                "ORDER BY created DESC,id DESC LIMIT 50",
                (key,),
            ),
        }
        for item in result["feedback"]:
            item["check_unavailable"] = json.loads(item["basis"]).get("check_unavailable")
        result["earlier_feedback"] = [
            item for item in result["feedback"] if item["episode"] != row["episode"]
        ]
        result["feedback"] = [
            item for item in result["feedback"] if item["episode"] == row["episode"]
        ]
        if row["kind"] == "device" and row["target"] in self.monitor.reliability.current:
            device = self.monitor.reliability.device(row["target"])
            after = row.get("observed_since")
            ids = [c["id"] for c in device["checks"]]
            bindings = (
                self.store.rows(
                    "SELECT check_id,episode FROM home_feedback "
                    "WHERE problem_id=? AND check_id IN (" + ",".join("?" for _ in ids) + ")",
                    (key, *ids),
                )
                if ids
                else []
            )
            earlier_owned = {r["check_id"] for r in bindings if r["episode"] != row["episode"]}
            device["earlier_checks"] = [
                c
                for c in device["checks"]
                if c["id"] in earlier_owned
                or not finite(after)
                or c["created"] < after
                or c["cohort"] != row.get("cohort")
            ]
            earlier_ids = {c["id"] for c in device["earlier_checks"]}
            device["checks"] = [c for c in device["checks"] if c["id"] not in earlier_ids]
            result.update(
                device=device,
                preference=self.preference(self.monitor.reliability.current[row["target"]]),
            )
            result["facts"] = [{"kind": "availability", "value": device["state"]}]
            for member in device["members"]:
                entity = self.monitor.entities.get(member["entity_id"], {})
                explicit = self.monitor.local_entity_areas.get(member["entity_id"])
                room = (
                    self.monitor.local_areas.get(explicit)
                    if explicit is not None
                    else self.room(row["target"])
                )
                result["members"].append({**member, "name": entity.get("name"), "room": room})
            result["members_omitted"] = max(0, device["member_count"] - len(result["members"]))
            result["dependencies"] = self.monitor.insights.impact(row["target"], "device")
            for relation in result["dependencies"]["affected_automations"]:
                identifier = relation["source"].removeprefix("automation:")
                relation["display_name"] = self.monitor.entities.get(identifier, {}).get("name")
                relation["href"] = "#automations/" + quote(identifier, safe="")
            if not device["reliable_now"] or device.get("cache_pending") is not False:
                result["unknowns"].append("coverage_limited")
        elif row["kind"] == "group":
            live = {r["problem_id"]: r for r in self.cache}
            retained = (
                self.store.rows(
                    "SELECT snapshot FROM home_problems WHERE problem_id IN ("
                    + ",".join("?" for _ in row["members"])
                    + ")",
                    row["members"],
                )
                if row["members"]
                else []
            )
            retained = {r["problem_id"]: r for r in (json.loads(r["snapshot"]) for r in retained)}
            for member in row["members"]:
                if member in live:
                    result["members"].append(self.presentation(live[member]))
                elif member in retained:
                    result["members"].append(
                        {**retained[member], "state": "unknown", "retained_only": True}
                    )
            result["members_omitted"] = row["member_count"] - len(result["members"])
            result["member_detail_unknown"] = len(result["members"]) < len(row["members"])
            result["unknowns"].append("correlation_not_cause")
            peers = [
                r
                for r in self.monitor.reliability.current.values()
                if self.monitor.reliability.reliable
                and r["state"] == "online"
                and row["target"] in r.get("platforms", [])
            ]
            result["healthy_counterevidence"] = [
                {"name": self.device_name(r["device_id"]), "device_id": r["device_id"]}
                for r in peers[:8]
            ]
            result["healthy_omitted"] = max(0, len(peers) - 8)
        elif row.get("expert_href"):
            result["expert_href"] = row["expert_href"]
        return result

    def feedback(self, key, value):
        dossier = self.dossier(key)
        row = dossier["problem"]
        note = self.monitor.redactor.text(value.note, 400)
        basis = {
            key: row.get(key)
            for key in ("selection", "state", "cohort", "observed_since", "as_of", "members")
        }
        basis["check_kind"] = value.check_kind
        with self.store.transaction():
            prior = self.store.rows(
                "SELECT * FROM home_feedback WHERE request_id=?", (value.request_id,)
            )
            if prior:
                if (
                    prior[0]["problem_id"],
                    prior[0]["episode"],
                    prior[0]["kind"],
                    prior[0]["note"],
                    json.loads(prior[0]["basis"]).get("check_kind", "other"),
                ) != (key, value.episode, value.kind, note, value.check_kind):
                    raise FeedbackError("Feedback identifier already used; reopen the report")
                return self.dossier(key)
            if row["episode"] != value.episode:
                raise FeedbackError("Problem episode changed; reopen the current evidence")
            if self.store.rows("SELECT count(*) n FROM home_feedback")[0]["n"] >= MAX_FEEDBACK:
                raise FeedbackError("Local feedback capacity reached; prior reports are retained")
            check_id = None
            if value.kind == "checked" and row["kind"] == "device":
                try:
                    self.monitor.reliability.check(row["target"], value.check_kind, note)
                    check_id = self.store.rows("SELECT max(id) id FROM device_checks")[0]["id"]
                except LookupError:
                    basis["check_unavailable"] = "device_not_retained"
                except ValueError as error:
                    if (
                        str(error)
                        != "Local check history capacity reached; existing records are retained"
                    ):
                        raise RuntimeError("Local check recording failed") from None
                    basis["check_unavailable"] = "check_capacity"
            basis = json.dumps(basis, ensure_ascii=False, separators=(",", ":"))
            if len(basis.encode()) > 4096:
                raise FeedbackError("Feedback evidence bound reached; prior reports are retained")
            self.store.execute(
                "INSERT INTO home_feedback(request_id,problem_id,episode,created,"
                "kind,note,basis,check_id) VALUES (?,?,?,?,?,?,?,?)",
                (
                    value.request_id,
                    key,
                    value.episode,
                    time.time(),
                    value.kind,
                    note,
                    basis,
                    check_id,
                ),
            )
        return self.dossier(key)
