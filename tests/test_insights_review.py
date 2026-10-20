"""Regression contracts from the independent phase-B review; synthetic data only."""

import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.evidence import fingerprint
from vision.insights import STATIC_PER_AUTOMATION, STATIC_TOTAL
from vision.monitor import Monitor
from vision.security import Redactor
from vision.store import CASE_NOTES_PER_CASE, MIGRATIONS, SCHEMA_VERSION, Store


@pytest.fixture
def local(tmp_path):
    store = Store(tmp_path / "vision.db")
    monitor = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor())
    yield monitor, monitor.insights
    store.close()


def offline(store, key="availability:sensor.example", now=None):
    store.issue(
        key,
        "availability",
        "warning",
        "Entity unavailable",
        {"entity_id": key.removeprefix("availability:")},
        now=now,
    )
    return key


def projection(count=1000):
    return {
        "nodes": [
            {"path": f"action/{index}", "kind": "action", "continue_on_error": True}
            for index in range(count)
        ],
        "references": [],
        "coverage": {"truncated": False},
    }


@pytest.mark.parametrize("status", ["known", "expected", "snoozed"])
def test_pruned_episode_cannot_reuse_attention_overlay(local, status):
    monitor, insights = local
    store = monitor.store
    old = time.time() - 100 * 86400
    key = offline(store, now=old)
    before = store.rows("SELECT * FROM issues WHERE key=?", (key,))[0]
    insights.annotate(key, status, "Old episode")
    assert store.rows("SELECT * FROM issues WHERE key=?", (key,))[0] == before
    store.execute("INSERT INTO exceptions VALUES ('sensor.independent','Operator exception',NULL)")
    store.execute("UPDATE issues SET active=0 WHERE key=?", (key,))
    store.prune(90)
    assert store.rows("SELECT * FROM case_annotations") == []
    assert store.rows("SELECT * FROM case_notes") == []
    offline(store)
    case = insights.dossier(key)["case"]
    assert case["status"] == "review" and case["source_active"]
    assert case["first_seen"] > old and case["occurrences"] == 1
    assert not store.expected("sensor.example")
    assert store.expected("sensor.independent")


def test_episode_binding_ignores_stale_overlay_before_cleanup(local):
    monitor, insights = local
    store = monitor.store
    key = offline(store, now=1)
    insights.annotate(key, "expected", "Old generation")
    store.execute("DELETE FROM issues WHERE key=?", (key,))
    offline(store, now=2)
    assert insights.cases()["items"][0]["status"] == "review"
    assert not store.expected("sensor.example")
    assert "sensor.example" not in store.expected_entities()
    assert not any(row["kind"] == "local_status" for row in insights.dossier(key)["timeline"])
    store.prune_case_history()
    assert not store.rows("SELECT * FROM case_annotations")
    assert not store.rows("SELECT * FROM case_notes")


def test_notes_are_bounded_stable_and_source_preserving_across_restart(local):
    monitor, insights = local
    store = monitor.store
    key = offline(store)
    source = store.rows("SELECT * FROM issues")[0]
    for index in range(101):
        insights.annotate(key, "known", f"Note {index}")
    notes = store.rows("SELECT * FROM case_notes ORDER BY id")
    assert len(notes) == CASE_NOTES_PER_CASE == 50
    assert notes[0]["note"] == "Note 51" and notes[-1]["note"] == "Note 100"
    assert store.rows("SELECT * FROM issues")[0] == source
    store.execute("UPDATE case_notes SET created=100")
    store.prune_case_history()
    assert [row["id"] for row in store.rows("SELECT id FROM case_notes ORDER BY id")] == [
        row["id"] for row in notes
    ]
    restarted = Monitor(store, Settings(), SimpleNamespace(token=""), Redactor()).insights
    assert restarted.dossier(key)["case"]["status"] == "known"
    assert len(store.rows("SELECT * FROM case_notes")) == 50
    store.prune_case_history(before=101)
    assert not store.rows("SELECT * FROM case_notes")
    assert store.rows("SELECT * FROM issues")[0] == source


def schema_four(path):
    db = sqlite3.connect(path)
    for version in range(1, 5):
        for statement in MIGRATIONS[version]:
            db.execute(statement)
    db.execute("PRAGMA user_version=4")
    db.execute(
        "INSERT INTO issues VALUES ('availability:sensor.example','availability','warning',"
        "'Unavailable','{\"entity_id\":\"sensor.example\"}',123,456,7,1)"
    )
    db.execute(
        "INSERT INTO case_annotations VALUES "
        "('availability:sensor.example','expected','Retained note',500,NULL)"
    )
    db.execute(
        "INSERT INTO case_notes VALUES (1,'availability:sensor.example',500,'expected',"
        "'Retained note',NULL)"
    )
    db.commit()
    db.close()


def test_schema_four_upgrade_backfills_episodes_without_rewriting_source(tmp_path):
    path = tmp_path / "vision.db"
    schema_four(path)
    with sqlite3.connect(path) as old:
        source = old.execute("SELECT * FROM issues").fetchall()
    store = Store(path)
    try:
        assert store.rows("PRAGMA user_version")[0]["user_version"] == SCHEMA_VERSION
        assert [tuple(row) for row in store.db.execute("SELECT * FROM issues")] == source
        assert (
            store.rows("SELECT case_first_seen FROM case_annotations")[0]["case_first_seen"] == 123
        )
        assert store.rows("SELECT case_first_seen FROM case_notes")[0]["case_first_seen"] == 123
        assert store.expected("sensor.example")
        with sqlite3.connect(tmp_path / "vision.db.v4.bak") as backup:
            assert backup.execute("PRAGMA user_version").fetchone()[0] == 4
            assert backup.execute("SELECT * FROM issues").fetchall() == source
            assert len(backup.execute("SELECT * FROM case_annotations").fetchone()) == 5
    finally:
        store.close()


def test_migration_backup_never_clobbers_operator_collision(tmp_path):
    path = tmp_path / "vision.db"
    schema_four(path)
    collision = tmp_path / "vision.db.v4.bak"
    collision.write_bytes(b"Operator-owned snapshot: preserve exactly")
    original = collision.read_bytes()
    store = Store(path)
    store.close()
    assert collision.read_bytes() == original
    backups = list(tmp_path.glob("vision.db.v4-*.bak"))
    assert len(backups) == 1
    assert backups[0].stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(backups[0]) as saved:
        assert saved.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert saved.execute("PRAGMA user_version").fetchone()[0] == 4
        assert saved.execute("SELECT occurrences FROM issues").fetchone()[0] == 7
    assert (tmp_path / "vision.db.pre-migration.bak").read_bytes() == backups[0].read_bytes()


def test_static_fanout_is_bounded_explicit_batched_and_below_availability(local):
    monitor, insights = local
    store = monitor.store
    for index in range(80):
        store.save_structure(f"automation.example_{index:03}", projection(), "current_config")
    offline(store)
    queries = []
    store.db.set_trace_callback(queries.append)
    try:
        insights.refresh()
    finally:
        store.db.set_trace_callback(None)
    coverage = store.get_meta("local_rules_coverage")
    assert coverage["observed"] == 80000
    assert coverage["retained"] == STATIC_TOTAL == 500
    assert coverage["omitted"] == 79500 and coverage["truncated"]
    assert coverage["automations_limited_count"] == 80
    assert "automations_limited" not in coverage
    assert (
        max(
            store.get_meta(f"local_rule_coverage:automation.example_{index:03}")["retained"]
            for index in range(80)
        )
        <= 20
    )
    counts = store.rows(
        "SELECT json_extract(detail,'$.entity_id') entity,count(*) n FROM issues "
        "WHERE source='static' GROUP BY entity"
    )
    assert all(row["n"] <= STATIC_PER_AUTOMATION for row in counts)
    assert sum(row["n"] for row in counts) == 500
    reads = [query for query in queries if query.startswith("SELECT") and "FROM issues" in query]
    assert len(reads) == 1 and "WHERE key=" not in reads[0]
    assert insights.overview()["cases"]["items"][0]["source"] == "availability"
    changes = store.db.total_changes
    queries.clear()
    store.db.set_trace_callback(queries.append)
    try:
        insights.refresh()
    finally:
        store.db.set_trace_callback(None)
    assert store.db.total_changes == changes
    assert not any("s.projection" in query or "row_number()" in query for query in queries)


def test_static_budget_omission_preserves_older_source_and_marks_unknown(local):
    monitor, insights = local
    store = monitor.store
    ast = projection(30)
    store.save_structure("automation.example", ast, "current_config")
    digest = fingerprint(ast)
    key = (
        "rule:"
        + fingerprint(["automation.example", digest, "continued_errors", "action/29", None])[:32]
    )
    store.issue(
        key,
        "static",
        "info",
        "Existing advice",
        {
            "entity_id": "automation.example",
            "configuration_digest": digest,
            "rule": "continued_errors",
            "path": "action/29",
            "coverage": {},
        },
        now=123,
        occurrences=4,
    )
    before = store.rows("SELECT * FROM issues WHERE key=?", (key,))[0]
    insights.refresh()
    after = store.rows("SELECT * FROM issues WHERE key=?", (key,))[0]
    assert after["active"] == 1
    for field in ("first_seen", "last_seen", "occurrences", "source", "title"):
        assert after[field] == before[field]
    assert json.loads(after["detail"])["coverage"]["static_selection_limited"]
    assert insights.dossier(key)["case"]["status"] == "limited"
    assert insights.cases(status="limited")["total"] == 1
    assert insights.cases()["total"] == 20


def seed_run(store, run_id="example", outcome="succeeded", started=123):
    store.execute(
        "INSERT INTO runs VALUES ('automation.example',?,NULL,?,?,0,'{}')",
        (run_id, started, outcome),
    )
    store.execute(
        "INSERT INTO run_timing VALUES ('automation.example',?,?,'ha_trace')", (run_id, started)
    )


def test_run_revision_detects_existing_outcome_update_without_count_change(local):
    monitor, insights = local
    store = monitor.store
    seed_run(store)
    insights.refresh()
    assert not insights.cases(source="automation")["items"]
    store.execute("UPDATE runs SET outcome='blocked'")
    insights.refresh()
    assert insights.cases(source="automation")["items"][0]["detail"]["rule"] == "mode_conflict"
    assert store.rows("SELECT count(*) n FROM runs")[0]["n"] == 1
    store.execute("UPDATE runs SET outcome='succeeded'")
    insights.refresh()
    assert insights.cases(source="automation")["total"] == 0


async def test_completed_monitor_sync_materializes_findings_without_a_get(local):
    monitor, insights = local
    monitor.store.save_structure("automation.example", projection(1), "current_config")

    class SyntheticHA:
        async def read(self, command, **params):
            if command == "get_states":
                return [{"entity_id": "automation.example", "state": "on", "attributes": {}}]
            return {"issues": []} if command == "repairs/list_issues" else []

    assert not monitor.store.rows("SELECT * FROM issues WHERE source='static'")
    await monitor.sync(SyntheticHA())
    assert monitor.store.rows("SELECT * FROM issues WHERE source='static'")
    assert insights.cases()["total"] == 1


def test_real_landing_reads_are_bounded_and_never_refresh_or_write(tmp_path):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    app = create_app(runtime, Settings(), connect=False)
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        monitor, store = app.state.monitor, app.state.store
        with store.transaction():
            for index in range(200):
                entity = f"automation.example_{index:03}"
                store.save_structure(entity, projection(), "current_config")
            store.db.executemany(
                "INSERT INTO runs VALUES (?,?,NULL,?,'succeeded',0,'{}')",
                [(f"automation.example_{i % 200:03}", f"r{i}", i) for i in range(4000)],
            )
            store.db.execute(
                "INSERT INTO run_timing SELECT entity_id,run_id,started,'ha_trace' FROM runs"
            )
            store.issue(
                "automation:automation.example_000",
                "automation",
                "error",
                "Retained failure",
                {"entity_id": "automation.example_000", "run_id": "r0"},
            )
        monitor.entities = {
            f"sensor.example_{i}": {
                "entity_id": f"sensor.example_{i}",
                "name": "Example",
                "availability": "available",
                "updated": 1,
                "device_id": None,
            }
            for i in range(5000)
        }
        monitor.entities.update(
            {
                f"automation.example_{i:03}": {
                    "entity_id": f"automation.example_{i:03}",
                    "name": "Example automation",
                    "availability": "available",
                    "updated": 1,
                    "device_id": None,
                }
                for i in range(200)
            }
        )
        monitor.insights.refresh()
        before = store.db.total_changes
        queries = []
        store.db.set_trace_callback(queries.append)
        durations = []
        try:
            for _ in range(3):
                for route, budget in (("/api/overview", 20), ("/api/cases", 5)):
                    queries.clear()
                    start = time.monotonic()
                    response = client.get(route)
                    durations.append(time.monotonic() - start)
                    assert response.status_code == 200
                    assert len(response.content) < 250_000
                    assert len(queries) <= budget, queries
                    assert not any(
                        "projection" in query
                        or "row_number()" in query
                        or query.startswith(("INSERT", "UPDATE", "DELETE", "BEGIN"))
                        for query in queries
                    ), queries
            assert max(durations) < 2  # Generous local regression guard, no HA hardware claim.
            assert store.db.total_changes == before
        finally:
            store.db.set_trace_callback(None)
        # Readers must also progress while an independent WAL writer holds its lock.
        with sqlite3.connect(tmp_path / "vision.db", timeout=0.1) as writer:
            writer.execute("BEGIN IMMEDIATE")
            start = time.monotonic()
            assert client.get("/api/overview").status_code == 200
            assert client.get("/api/cases").status_code == 200
            assert time.monotonic() - start < 2
            writer.rollback()


@pytest.mark.parametrize(
    "summary",
    [
        None,
        [],
        42,
        {},
        {"coverage": None, "steps": [], "errors": []},
        {"coverage": {}, "steps": [], "errors": [None]},
        {"coverage": {}, "steps": [], "errors": [{}]},
        {"coverage": {}, "steps": [], "errors": [{"path": "action/0"}]},
        {"coverage": {}, "steps": [None], "errors": []},
    ],
)
def test_malformed_retained_evidence_is_explicit_unknown_not_http_500(tmp_path, summary):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    app = create_app(runtime, Settings(), connect=False)
    with TestClient(app, client=("127.0.0.1", 123)) as client:
        store, monitor = app.state.store, app.state.monitor
        monitor.observe_state({"entity_id": "automation.example", "state": "on", "attributes": {}})
        seed_run(store, outcome="failed")
        raw = json.dumps(summary)
        store.execute(
            "INSERT INTO run_evidence VALUES ('automation.example','example',?,?,0)",
            (raw, len(raw.encode())),
        )
        key = "automation:automation.example"
        store.issue(
            key,
            "automation",
            "error",
            "Run failed",
            {
                "entity_id": "automation.example",
                "run_id": "example",
            },
        )
        before = store.rows("SELECT * FROM issues WHERE key=?", (key,))[0]
        for route in ("/api/overview", "/api/cases", f"/api/cases/{key}"):
            response = client.get(route)
            assert response.status_code == 200, response.text
            assert "unknown" in response.text.lower() or "no step evidence" in response.text.lower()
            assert "linked run no longer retained" not in response.text
        response = client.get(
            "/api/investigation/automation.example?run_id=example&compare=example"
        )
        assert response.status_code == 200
        assert response.json()["run"]["evidence"] is None
        assert response.json()["run"]["evidence_unknown_reason"]
        assert response.json()["comparison"]["coverage_limited"]
        assert store.rows("SELECT * FROM issues WHERE key=?", (key,))[0] == before
        assert not store.rows("SELECT * FROM usage")


def test_availability_only_overview_keeps_concrete_case_links():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for this frontend contract")
    source = (Path(__file__).parents[1] / "vision/static/app.js").read_text()
    selector = source.split("function overviewCases(", 1)[1].split("async function overview(", 1)[0]
    availability = [
        {"key": f"availability:sensor.example_{i}", "source": "availability", "severity": "warning"}
        for i in range(1200)
    ]
    info = {"key": "static", "source": "static", "severity": "info"}
    fault = {"key": "failure", "source": "automation", "severity": "error"}
    script = (
        "function overviewCases("
        + selector
        + "\n"
        + (
            "const a="
            + json.dumps(availability)
            + "; const info="
            + json.dumps(info)
            + "; const fault="
            + json.dumps(fault)
            + "; console.log(JSON.stringify(["
            "overviewCases(a),overviewCases([info,...a]),overviewCases([fault,...a])]))"
        )
    )
    result = json.loads(subprocess.check_output([node, "-e", script]))
    assert [row["key"] for row in result[0]] == [row["key"] for row in availability[:3]]
    assert result[1] == availability[:3]
    assert result[2] == [fault]
