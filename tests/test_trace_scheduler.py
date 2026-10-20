"""Newest evidence must progress independently of historical failed-run backfill."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from vision.config import Settings
from vision.evidence import trace_summary
from vision.monitor import Monitor
from vision.security import Redactor
from vision.store import Store


async def test_165_latest_successes_with_error_backlog_are_inspected_within_15_cycles(tmp_path):
    store = Store(tmp_path / "vision.db")
    monitor = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor())
    traces = []
    with store.transaction():
        for entity_index in range(165):
            item = f"example_{entity_index:03}"
            entity = "automation." + item
            monitor.entities[entity] = {"entity_id": entity, "automation_id": item}
            for run_index in range(22):
                fresh = run_index == 21
                run = "fresh" if fresh else f"old_{run_index:02}"
                started = 1800000000 + run_index
                trace = {
                    "item_id": item,
                    "run_id": run,
                    "script_execution": "finished" if fresh else "error",
                    "timestamp": {"start": datetime.fromtimestamp(started, UTC).isoformat()},
                }
                traces.append(trace)
                monitor.save_trace(entity, trace)
                if not fresh:
                    # A compacted short trace is still missing detail; successful
                    # full traces compacted later must not be fetched again.
                    summary = Store.compact_summary(trace_summary(trace, Redactor(), "failed"))
                    raw = json.dumps(summary)
                    store.execute(
                        "UPDATE run_evidence SET summary=?,stored_bytes=?,compacted=1 "
                        "WHERE entity_id=? AND run_id=?",
                        (raw, len(raw.encode()), entity, run),
                    )
    calls = []

    class HA:
        async def read(self, command, **params):
            assert command == "trace/get"
            calls.append((params["item_id"], params["run_id"]))
            return {
                "run_id": params["run_id"],
                "script_execution": "finished",
                "trace": {"action/0": [{"result": {"done": True}}]},
            }

    for _ in range(15):
        before = len(calls)
        await monitor.sync_traces(HA(), traces)
        assert len(calls) - before <= 12
    assert len({item for item, run in calls if run == "fresh"}) == 165
    assert sum(run != "fresh" for _, run in calls) == 15
    assert len(set(calls)) == len(calls)
    # With newest evidence covered, all remaining slots become backfill; the
    # already completed newest runs never re-enter either read lane.
    before = len(calls)
    await monitor.sync_traces(HA(), traces)
    assert len(calls) - before == 12
    assert all(run != "fresh" for _, run in calls[before:])
    assert len(set(calls)) == len(calls)
    store.close()
