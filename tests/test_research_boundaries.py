"""Narrow current-auth version, existing v2 bytes and own SQLite sidecar contracts."""

import hashlib

import pytest
from aiohttp import web
from test_public_research import ai as ai
from test_public_research import device_request

from vision.ai_provider import request_body
from vision.ha import HAClient, core_version
from vision.store import Store


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "version",
    [
        "2026.10.2",
        "2026.11.0b2",
        None,
        "2026.13.0",
        "custom-secret-canary",
        "2026.10.2/../../",
        True,
    ],
)
async def test_only_current_authenticated_ha_version_is_available(
    tmp_path, unused_tcp_port, version
):
    async def websocket(request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        await socket.send_json({"type": "auth_required", "ha_version": "2025.1.1"})
        assert (await socket.receive_json()) == {"type": "auth", "access_token": "synthetic"}
        await socket.send_json({"type": "auth_ok", "ha_version": version})
        async for _ in socket:
            pytest.fail("Version capture must issue no HA read")
        return socket

    app = web.Application()
    app.router.add_get("/api/websocket", websocket)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    try:
        async with HAClient(
            f"http://127.0.0.1:{unused_tcp_port}", "synthetic", lambda event: None
        ) as ha:
            assert ha.server_version == core_version(version)
            assert (ha.version_observed_at is not None) == (core_version(version) is not None)
    finally:
        await runner.cleanup()


def test_own_actual_wal_sidecars_are_private_after_authoritative_validation(tmp_path):
    path = tmp_path / "vision.db"
    first = Store(path)
    second = None
    try:
        first.set_meta("retained", "same")
        sidecars = [path.with_name(path.name + suffix) for suffix in ("-wal", "-shm")]
        assert all(item.exists() for item in sidecars)
        for item in sidecars:
            item.chmod(0o640)
        second = Store(path)
        assert all(item.stat().st_mode & 0o777 == 0o600 for item in sidecars)
        assert second.get_meta("retained") == "same"
    finally:
        if second:
            second.close()
        first.close()


@pytest.mark.parametrize(
    "provider,expected",
    [
        ("anthropic", "6bf81ff65c78bbf3ccdafc97e54e011932b56f29f802d22479c501536363b36e"),
        ("openai", "d51ea34495fe396de337de7ea475435a4969cd0e25e39327dd6f6a7459ce666f"),
    ],
)
def test_original_v2_provider_wire_contract_is_byte_identical(provider, expected):
    # Golden hashes generated from accepted 83355b6, with fixed synthetic arguments.
    body = request_body(
        provider,
        "synthetic-model",
        "Fixed system",
        '{"bundle":{"evidence":{"Rold:E1":{"type":"coverage"}}}}',
        8192,
        evidence_refs=["Rold:E1"],
    )
    assert hashlib.sha256(body.encode()).hexdigest() == expected


def test_disconnected_or_unvalidated_current_version_is_not_replaced_by_historical_context(ai):
    from vision.ai_contract import SendInput

    device_request(ai)
    ai.monitor.connected = False
    ai.monitor.ha_version = "2026.10.2"
    preview = ai.preview(device_request(ai))
    ai.monitor.connected = False
    plan = ai.research.plan(SendInput(request_id=preview["request_id"], digest=preview["digest"]))
    assert plan["plan"]["technical_context"]["core_version"] is None
    assert not any(item["kind"] == "core_manifest" for item in plan["plan"]["requests"])
