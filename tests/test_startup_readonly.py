"""A preliminary read-only schema check must not prevent writable crash recovery."""

import json
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest

from vision.store import MIGRATIONS, SCHEMA_VERSION, Store


def schema_eight(path):
    with closing(sqlite3.connect(path)) as db:
        for version in range(1, 9):
            for statement in MIGRATIONS[version]:
                db.execute(statement)
        db.execute("PRAGMA user_version=8")
        db.execute("INSERT INTO availability VALUES (1,'light.synthetic','unavailable',10,20,0)")
        db.execute("INSERT INTO meta VALUES ('retained',?)", (json.dumps("original"),))
        db.commit()


@pytest.mark.parametrize("failure", ["connect", "read"])
def test_readonly_precheck_failure_still_allows_authoritative_writable_upgrade(
    tmp_path, monkeypatch, failure
):
    path = tmp_path / "vision.db"
    schema_eight(path)
    original_connect = sqlite3.connect
    uri = path.resolve().as_uri() + "?mode=ro"
    attempts, closed = [], []

    class UnreadableConnection(sqlite3.Connection):
        def execute(self, statement, *args, **kwargs):
            if statement == "PRAGMA user_version":
                raise sqlite3.OperationalError("Synthetic read-only pager failure")
            return super().execute(statement, *args, **kwargs)

        def close(self):
            closed.append(True)
            return super().close()

    def unavailable_precheck(database, *args, **kwargs):
        # Only the first preliminary open fails; snapshot opens retain the real API.
        if database == uri and not attempts:
            attempts.append(failure)
            if failure == "connect":
                raise sqlite3.OperationalError("Synthetic read-only open failure")
            return original_connect(database, *args, **kwargs, factory=UnreadableConnection)
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", unavailable_precheck)
    store = Store(path)
    try:
        assert attempts == [failure]
        assert closed == ([True] if failure == "read" else [])
        assert store.rows("PRAGMA user_version")[0]["user_version"] == SCHEMA_VERSION
        assert store.get_meta("retained") == "original"
        assert store.rows("SELECT * FROM availability") == [
            {
                "id": 1,
                "entity_id": "light.synthetic",
                "state": "unavailable",
                "started": 10,
                "ended": 20,
                "uncertain": 0,
            }
        ]
        with closing(original_connect(tmp_path / "vision.db.v8.bak")) as saved:
            assert saved.execute("PRAGMA user_version").fetchone()[0] == 8
            assert saved.execute("SELECT value FROM meta WHERE key='retained'").fetchone() == (
                json.dumps("original"),
            )
    finally:
        store.close()


def test_actual_hot_delete_journal_recovers_before_schema_upgrade(tmp_path):
    path = tmp_path / "vision.db"
    schema_eight(path)
    # Enough pages to force uncommitted writes to spill from the child pager cache.
    retained = [(f"crash-{index}", json.dumps("original-" + "A" * 4096)) for index in range(256)]
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        db.executemany("INSERT INTO meta VALUES (?,?)", retained)
        db.commit()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os,sqlite3,sys; db=sqlite3.connect(sys.argv[1]); "
            "db.execute('PRAGMA cache_size=2'); db.execute('PRAGMA synchronous=FULL'); "
            "db.execute('BEGIN IMMEDIATE'); "
            "db.execute(\"UPDATE meta SET value=? WHERE key LIKE 'crash-%'\", ('B'*4096,)); "
            "os._exit(0)",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    journal = path.with_name(path.name + "-journal")
    assert journal.exists() and journal.stat().st_size > 512
    assert journal.read_bytes()[:8] == bytes.fromhex("d9d505f920a163d7")
    # Prove this fixture needs writable rollback, rather than merely leaving a file.
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as readonly:
        with pytest.raises(sqlite3.OperationalError) as failure:
            readonly.execute("PRAGMA user_version").fetchone()
        assert failure.value.sqlite_errorcode == sqlite3.SQLITE_READONLY_ROLLBACK
    store = Store(path)
    try:
        assert store.rows("PRAGMA user_version")[0]["user_version"] == SCHEMA_VERSION
        assert store.rows("PRAGMA quick_check")[0]["quick_check"] == "ok"
        assert store.rows("SELECT key,value FROM meta WHERE key LIKE 'crash-%' ORDER BY key") == [
            {"key": key, "value": value} for key, value in sorted(retained)
        ]
        assert store.get_meta("retained") == "original"
        with closing(sqlite3.connect(tmp_path / "vision.db.v8.bak")) as backup:
            assert backup.execute("PRAGMA user_version").fetchone()[0] == 8
            assert backup.execute(
                "SELECT key,value FROM meta WHERE key LIKE 'crash-%' ORDER BY key"
            ).fetchall() == sorted(retained)
        assert not journal.exists()
    finally:
        store.close()
