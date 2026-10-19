import asyncio
import io
import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vision.app import create_app
from vision.config import Settings
from vision.security import RedactingFormatter, Redactor, protect_logging
from vision.store import Store


def test_invalid_options_are_safe_and_visible(tmp_path):
    options = tmp_path / "private-options.json"
    options.write_text('{"daily_audit":true,"anthropic_model":"private-model-value"}')
    runtime = SimpleNamespace(supervised=False, data=tmp_path, options=options, token="")
    with TestClient(create_app(runtime, connect=False), client=("127.0.0.1", 123)) as client:
        response = client.get("/api/health")
        assert "Invalid app options" in response.json()["configuration_error"]
        assert "private-model-value" not in response.text
        assert client.get("/api/settings").json()["ai_enabled"] is False


def test_supervised_default_denies_user_data(tmp_path):
    runtime = SimpleNamespace(supervised=True, data=tmp_path, token="test-token")
    with TestClient(
        create_app(runtime, Settings(), connect=False), client=("172.30.32.2", 123)
    ) as client:
        assert client.get("/api/devices").status_code == 403
        locked = client.get("/", headers={"x-remote-user-id": "setup-user-id"})
        assert "setup-user-id" in locked.text and "access is locked" in locked.text


def test_log_redaction_including_exception():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        RedactingFormatter(logging.Formatter("%(message)s"), Redactor(["private-test-secret"]))
    )
    logger = logging.getLogger("vision-test-private")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    try:
        try:
            raise ValueError("private-test-secret")
        except ValueError:
            logger.exception("private-test-secret")
        assert "private-test-secret" not in stream.getvalue()
        assert "REDACTED" in stream.getvalue()
    finally:
        logger.removeHandler(handler)


def test_store_serializes_threads_and_wal_is_private(tmp_path):
    path = tmp_path / "vision.db"
    store = Store(path)

    def increment(_):
        with store.transaction():
            value = store.get_meta("counter", 0)
            store.set_meta("counter", value + 1)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(increment, range(100)))
    assert store.get_meta("counter") == 100
    for name in ("vision.db", "vision.db-wal", "vision.db-shm"):
        assert (tmp_path / name).stat().st_mode & 0o777 == 0o600
    store.close()


def test_retention_preserves_open_intervals_and_billing(tmp_path):
    store = Store(tmp_path / "vision.db")
    old = time.time() - 100 * 86400
    store.execute("INSERT INTO availability VALUES (1,'sensor.a','unknown',?,NULL,0)", (old,))
    store.execute("INSERT INTO availability VALUES (2,'sensor.b','unknown',?,?,0)", (old, old + 1))
    store.execute(
        "INSERT INTO usage VALUES (1,?,'openai','model',1,1,.1,'response_received')", (old,)
    )
    store.prune(7)
    assert len(store.rows("SELECT * FROM availability")) == 1
    assert len(store.rows("SELECT * FROM usage")) == 1
    store.close()


def test_newer_schema_is_refused(tmp_path):
    path = tmp_path / "vision.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version=99")
    connection.close()
    with pytest.raises(RuntimeError, match="newer Vision"):
        Store(path)


def test_redactor_deep_and_bytes():
    value = b"private-test-secret"
    for _ in range(20):
        value = [value]
    redactor = Redactor(["private-test-secret"])
    assert "DEPTH LIMIT" in str(redactor.clean(value))
    assert redactor.clean(b"private-test-secret") == "[REDACTED]"


async def test_transactions_deny_cross_task_nesting(tmp_path):
    store = Store(tmp_path / "vision.db")
    entered, finished = asyncio.Event(), asyncio.Event()

    async def owner():
        with store.transaction():
            store.set_meta("owner", True)
            entered.set()
            await finished.wait()  # Deliberate misuse must not corrupt a second task.

    task = asyncio.create_task(owner())
    await entered.wait()
    try:
        with pytest.raises(RuntimeError, match="Cross-task"):
            store.set_meta("intruder", True)
        with pytest.raises(RuntimeError, match="Cross-task"):
            store.get_meta("owner")
    finally:
        finished.set()
        await task
    assert store.get_meta("owner") is True and store.get_meta("intruder") is None
    store.close()


def test_logging_wiring_covers_handlerless_root(monkeypatch, capsys):
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    protect_logging(Redactor(["private-asyncio-secret"]))
    logging.getLogger("asyncio").error("private-asyncio-secret")
    output = capsys.readouterr().err
    assert "private-asyncio-secret" not in output and "[REDACTED]" in output


def test_invalid_supervised_options_preserve_valid_access(tmp_path):
    path = tmp_path / "options-private.json"
    path.write_text('{"allowed_user_ids":["tester"],"daily_audit":true}')
    runtime = SimpleNamespace(supervised=True, data=tmp_path, options=path, token="synthetic")
    with TestClient(create_app(runtime, connect=False), client=("172.30.32.2", 123)) as client:
        locked = client.get("/")
        assert locked.status_code == 403 and "Invalid app options" in locked.text
        client.headers["x-remote-user-id"] = "tester"
        assert "Invalid app options" in client.get("/api/health").text
        settings = client.get("/api/settings").json()
        assert not settings["ai_enabled"] and settings["allowed_user_count"] == 1
        assert "allowed_user_ids" not in settings


def test_generic_500_has_security_headers(tmp_path):
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="synthetic")
    app = create_app(runtime, Settings(), connect=False)

    @app.get("/api/test-crash")
    async def crash():
        raise RuntimeError("private-test-secret")

    with TestClient(app, client=("127.0.0.1", 123), raise_server_exceptions=False) as client:
        response = client.get("/api/test-crash")
        assert response.status_code == 500
        assert "private-test-secret" not in response.text
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Cache-Control"] == "no-store"
