import pytest

from scripts import container_smoke


def test_readiness_waits_for_application_storage(monkeypatch):
    responses = iter([{}, {"read_only": True}, {"read_only": True, "storage": "ready"}])
    waits = []
    monkeypatch.setattr(container_smoke, "http_json", lambda *_: next(responses))
    monkeypatch.setattr(container_smoke.time, "sleep", waits.append)
    container_smoke.wait_ready("synthetic-container")
    assert waits == [1, 1]


def test_readiness_never_accepts_writable_application(monkeypatch):
    monkeypatch.setattr(
        container_smoke, "http_json", lambda *_: {"read_only": False, "storage": "ready"}
    )
    monkeypatch.setattr(container_smoke.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="did not become ready"):
        container_smoke.wait_ready("synthetic-container")
