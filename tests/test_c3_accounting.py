"""C3 regression contracts, entirely local/synthetic and with no provider access."""

import copy
import json
import sqlite3
import time
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError
from test_ai_lifecycle import configured
from test_ai_pipeline import SyntheticProvider, consent
from test_ai_pipeline import ai as ai

from vision.ai import AIConflict, AIError
from vision.ai_contract import AnalysisInput, Diagnosis, provider_schema
from vision.app import create_app
from vision.config import Settings
from vision.store import MIGRATIONS, SCHEMA_VERSION, Store


def insert_pair(db, ident, created, body="🟢", status="completed"):
    analysis = db.execute(
        "INSERT INTO analyses(created,kind,target,provider,model,result,evidence) "
        "VALUES (?,'audit',NULL,'synthetic','synthetic',?,?) RETURNING id",
        (created, json.dumps({"summary": body}, ensure_ascii=False), body),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO ai_requests VALUES (?,?,?,?,'conversation',1,'audit',NULL,'compact',"
        "NULL,NULL,'binding','digest',?,?,?,NULL)",
        (ident, created, created + 3600, status, body, body, analysis),
    )
    return analysis


def exact_sizes(store):
    requests = store.rows("SELECT id,payload,local_evidence FROM ai_requests")
    analyses = store.rows("SELECT id,result,evidence FROM analyses")
    return sorted(
        [
            {
                "kind": kind,
                "record_id": str(row["id"]),
                "stored_bytes": sum(len(row[k].encode()) for k in fields),
            }
            for kind, rows, fields in (
                ("request", requests, ("payload", "local_evidence")),
                ("analysis", analyses, ("result", "evidence")),
            )
            for row in rows
        ],
        key=lambda row: (row["kind"], row["record_id"]),
    )


def assert_sizes(store):
    expected = exact_sizes(store)
    assert store.rows("SELECT * FROM ai_storage_sizes ORDER BY kind,record_id") == expected
    assert store.ai_storage()["stored_bytes"] == sum(row["stored_bytes"] for row in expected)


def test_schema_eight_preserves_original_rows_and_backfills_utf8_sizes(tmp_path):
    path = tmp_path / "vision.db"
    with sqlite3.connect(path) as db:
        for version in range(1, 8):
            for statement in MIGRATIONS[version]:
                db.execute(statement)
        insert_pair(db, "old", time.time())
        db.execute("PRAGMA user_version=7")
        old = {
            table: db.execute("SELECT * FROM " + table).fetchall()
            for table in ("analyses", "ai_requests")
        }
    store = Store(path)
    assert store.db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    for table, rows in old.items():
        assert [tuple(row) for row in store.db.execute("SELECT * FROM " + table)] == rows
    assert_sizes(store)
    assert (
        len(
            store.rows(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%_storage_%'"
            )
        )
        == 6
    )
    store.close()
    reopened = Store(path)
    assert_sizes(reopened)
    reopened.close()


def test_size_triggers_follow_updates_deletes_rollback_prune_and_status_only_metadata(tmp_path):
    store = Store(tmp_path / "vision.db")
    with store.transaction():
        analysis = insert_pair(store.db, "recent", time.time())
        insert_pair(store.db, "old", time.time() - 100 * 86400)
    assert_sizes(store)
    store.execute(
        "UPDATE ai_requests SET payload=?,local_evidence=? WHERE id='recent'", ("é" * 23, "漢字")
    )
    store.execute("UPDATE analyses SET result=?,evidence=? WHERE id=?", ("🚦" * 7, "🟢", analysis))
    assert_sizes(store)
    before = store.rows("SELECT * FROM ai_storage_sizes ORDER BY kind,record_id")
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.db.execute("UPDATE ai_requests SET payload='rolled-back'")
            insert_pair(store.db, "rolled-back", time.time())
            raise RuntimeError("synthetic rollback")
    assert store.rows("SELECT * FROM ai_storage_sizes ORDER BY kind,record_id") == before
    # Authorizer rejects any body-column read, including one hidden in a trigger.
    bodies = {
        ("ai_requests", "payload"),
        ("ai_requests", "local_evidence"),
        ("analyses", "result"),
        ("analyses", "evidence"),
    }

    def authorize(action, table, column, _db, _trigger):
        return (
            sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and (table, column) in bodies
            else sqlite3.SQLITE_OK
        )

    store.db.set_authorizer(authorize)
    try:
        store.execute("UPDATE ai_requests SET status='revoked',error='safe' WHERE id='recent'")
        assert store.ai_storage()["stored_bytes"] == sum(row["stored_bytes"] for row in before)
    finally:
        store.db.set_authorizer(None)
    store.prune(90)
    assert not store.rows("SELECT * FROM ai_requests WHERE id='old'")
    assert_sizes(store)
    store.execute("DELETE FROM ai_requests WHERE id='recent'")
    store.execute("DELETE FROM analyses WHERE id=?", (analysis,))
    assert not store.rows("SELECT * FROM ai_storage_sizes")
    store.close()


async def test_near_cap_http_preview_and_headroom_do_not_rescan_retained_bodies(
    tmp_path, monkeypatch
):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), configured(), connect=False
    )
    async with app.router.lifespan_context(app):
        store = app.state.store
        app.state.ai.providers = {
            provider: SyntheticProvider() for provider in ("anthropic", "openai")
        }
        with store.transaction():
            for number in range(480):
                insert_pair(store.db, str(number), time.time(), "x" * 32768)
        size = store.ai_storage()
        assert 60 * 1048576 <= size["stored_bytes"] < 61 * 1048576
        statements = []
        store.db.set_trace_callback(statements.append)
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://vision", headers={"x-vision-request": "1"}
        ) as client:
            started = time.monotonic()
            preview = await client.post("/api/intelligence/preview", json={})
            elapsed = time.monotonic() - started
            assert preview.status_code == 200
            assert elapsed < 2, f"Bounded local preview took {elapsed:.3f}s"
            current = store.ai_storage()
            assert current["request_count"] == 481
            assert current["available_request_slots"] == 31
            assert (
                current["available_payload_bytes"]
                == current["max_storage_bytes"]
                - current["stored_bytes"]
                - current["promised_result_bytes"]
            )
            # A stricter admission cap must not remove existing exact history.
            monkeypatch.setattr("vision.ai.AI_MAX_STORAGE_BYTES", current["stored_bytes"])
            rejected = await client.post("/api/intelligence/preview", json={})
            assert rejected.status_code == 400 and "storage admission" in rejected.json()["detail"]
            assert len(store.rows("SELECT id FROM analyses")) == 480
            assert store.ai_storage()["request_count"] == 481
            assert not store.rows("SELECT * FROM usage")
        store.db.set_trace_callback(None)
        reads = [sql.lower() for sql in statements if sql.lstrip().lower().startswith("select")]
        assert reads and not any("length(cast(" in sql for sql in reads)
        assert not any("sum(length" in sql for sql in reads)
        assert not any(
            "from ai_requests" in sql and ("payload" in sql or "local_evidence" in sql)
            for sql in reads
        )
        assert any("stored_bytes" in sql and "ai_storage_sizes" in sql for sql in reads)
        assert not any(provider.calls for provider in app.state.ai.providers.values())


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_ref_schema_copies_shared_input_and_isolates_rounds_fields_and_providers(
    monkeypatch, provider
):
    shared = Diagnosis.model_json_schema()
    original = copy.deepcopy(shared)
    monkeypatch.setattr(Diagnosis, "model_json_schema", lambda: shared)
    first = provider_schema(provider, ("round1_E1", "round1_E2"))
    assert shared == original
    fields = first["$defs"]["Finding"]["properties"]
    fields["evidence"]["items"]["enum"].append("mutation")
    assert "mutation" not in fields["counter_evidence"]["items"]["enum"]
    second = provider_schema("openai", ("round2_E1",))
    assert second["$defs"]["Finding"]["properties"]["evidence"]["items"]["enum"] == ["round2_E1"]
    plain = provider_schema(provider)
    assert "enum" not in plain["$defs"]["Finding"]["properties"]["evidence"]["items"]
    assert shared == original


async def test_empty_projected_evidence_is_clear_local_failure_without_request_or_usage(
    ai, monkeypatch
):
    from vision.ai import project

    def empty(*args, **kwargs):
        bundle, mapping, aliases = project(*args, **kwargs)
        bundle["evidence"] = {}
        return bundle, mapping, aliases

    monkeypatch.setattr("vision.ai.project", empty)
    with pytest.raises(AIError, match="No bounded local evidence"):
        ai.preview(AnalysisInput())
    assert not ai.store.rows("SELECT * FROM ai_requests")
    assert not ai.store.rows("SELECT * FROM usage")
    assert not any(provider.calls for provider in ai.providers.values())
    await ai.close()


async def test_withdrawn_received_followup_is_in_audit_and_cannot_be_continued(ai):
    first = ai.preview(AnalysisInput())
    await ai.send(consent(first))
    followup = AnalysisInput(conversation_id=first["conversation_id"])
    second = ai.preview(followup)
    # A stale third-round preview prepared before withdrawal must also fail.
    await ai.send(consent(second))
    third = ai.preview(followup)
    ai.store.execute("UPDATE ai_requests SET status='revoked' WHERE id=?", (second["request_id"],))
    with pytest.raises(AIError, match="Withdrawn conversation"):
        ai.preview(followup)
    with pytest.raises(AIConflict, match="Conversation changed|withdrawn result"):
        await ai.send(consent(third))
    assert len(ai.store.rows("SELECT * FROM usage")) == 2
    assert ai.withdrawn_conversation(first["conversation_id"])
    await ai.close()


async def test_withdrawn_analysis_round_is_visible_in_http_conversation_audit(tmp_path):
    app = create_app(
        SimpleNamespace(supervised=False, data=tmp_path, token=""), configured(), connect=False
    )
    async with app.router.lifespan_context(app):
        store = app.state.store
        with store.transaction():
            first = insert_pair(store.db, "a" * 32, time.time(), "retained")
            second = insert_pair(store.db, "b" * 32, time.time(), "retained", "revoked")
            store.db.execute("UPDATE ai_requests SET round=2 WHERE id=?", ("b" * 32,))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://vision"
        ) as client:
            audit = (await client.get("/api/intelligence/conversations/conversation")).json()
            assert [row["status"] for row in audit["rounds"]] == ["completed", "revoked"]
            assert [row["analysis_id"] for row in audit["rounds"]] == [first, second]
            for ident in (first, second):
                assert not (await client.get(f"/api/intelligence/analyses/{ident}")).json()[
                    "can_continue"
                ]
            assert all(
                not row["can_continue"]
                for row in (await client.get("/api/intelligence")).json()["analyses"]
            )


def test_failed_after_validator_assignment_keeps_fields_set_and_exclude_unset_atomic():
    settings = Settings(ai_enabled=True, daily_audit=True)
    before = settings.model_dump(exclude_unset=True)
    fields = settings.model_fields_set.copy()
    with pytest.raises(ValidationError):
        settings.ai_enabled = False
    assert settings.model_dump(exclude_unset=True) == before
    assert settings.model_fields_set == fields
    untouched = Settings()
    with pytest.raises(ValidationError):
        untouched.daily_audit = True
    assert untouched.model_fields_set == set()
    assert untouched.model_dump(exclude_unset=True) == {}
