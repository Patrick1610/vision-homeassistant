import asyncio
import json
from types import SimpleNamespace

import pytest
from aiohttp import web

from vision.config import Settings
from vision.monitor import Monitor
from vision.security import Redactor
from vision.store import Store


@pytest.mark.parametrize("supervisor_proxy", [False, True])
async def test_monitor_inventory_traces_issues_and_reconnect(
    tmp_path,
    unused_tcp_port,
    supervisor_proxy,
):
    sockets, reads, rest_methods = [], [], []
    synced, reconnected = asyncio.Event(), asyncio.Event()
    state = {"entity_id": "automation.example", "state": "on", "attributes": {"id": "123"}}

    async def websocket(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        sockets.append(ws)
        await ws.send_json({"type": "auth_required"})
        assert (await ws.receive_json())["access_token"] == "synthetic-ha-token"
        await ws.send_json({"type": "auth_ok"})
        if len(sockets) > 1:
            reconnected.set()
        async for frame in ws:
            data = json.loads(frame.data)
            command = data["type"]
            reads.append(command)
            values = {
                "get_states": [state, {"entity_id": "sensor.example", "state": "unknown"}],
                "config/device_registry/list": [{"id": "device-1", "name": "Synthetic"}],
                "config/entity_registry/list": [
                    {"entity_id": "sensor.example", "device_id": "device-1"},
                    {"entity_id": "sensor.disabled", "disabled_by": "user"},
                    {"entity_id": "automation.not_loaded", "disabled_by": None},
                ],
                "repairs/list_issues": {
                    "issues": [{"domain": "test", "issue_id": "synthetic", "severity": "warning"}]
                },
                "system_log/list": [
                    {
                        "level": "ERROR",
                        "name": "synthetic.test",
                        "count": 2,
                        "message": ["Timeout synthetic-ha-token"],
                    }
                ],
                "trace/list": [{"item_id": "123", "run_id": "run-1"}],
                "trace/get": {
                    "run_id": "run-1",
                    "context": {"id": "context-1"},
                    "state": "stopped",
                    "script_execution": "finished",
                },
                "subscribe_events": None,
            }
            assert command in values  # Any nonallowlisted operation fails the integration test.
            await ws.send_json(
                {"id": data["id"], "type": "result", "success": True, "result": values[command]}
            )
            if data.get("event_type") == "automation_triggered":
                await ws.send_json(
                    {
                        "id": data["id"],
                        "type": "event",
                        "event": {
                            "event_type": "automation_triggered",
                            "context": {"id": "context-1"},
                            "data": {"entity_id": "automation.example"},
                        },
                    }
                )
        return ws

    async def configuration(request):
        rest_methods.append(request.method)
        return web.json_response(
            {"triggers": [{"trigger": "state", "entity_id": "sensor.example"}], "actions": []}
        )

    server = web.Application()
    server.router.add_get("/core/websocket" if supervisor_proxy else "/api/websocket", websocket)
    prefix = "/core" if supervisor_proxy else ""
    server.router.add_get(prefix + "/api/config/automation/config/123", configuration)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    store = Store(tmp_path / "vision.db")
    runtime = SimpleNamespace(
        token="synthetic-ha-token",
        ha_url=f"http://127.0.0.1:{unused_tcp_port}" + prefix,
        websocket_url=f"http://127.0.0.1:{unused_tcp_port}"
        + ("/core/websocket" if supervisor_proxy else "/api/websocket"),
    )
    monitor = Monitor(store, Settings(), runtime, Redactor([runtime.token]))
    original_sync = monitor.sync

    async def observed_sync(ha):
        await original_sync(ha)
        synced.set()

    monitor.sync = observed_sync
    task = asyncio.create_task(monitor.run())
    try:
        async with asyncio.timeout(5):
            await synced.wait()
        assert len(monitor.entities) == 2 and len(monitor.devices) == 1
        assert len(monitor.inventory()) == 4
        assert monitor.entity_view("sensor.disabled")["availability"] == "disabled"
        assert monitor.entity_view("automation.not_loaded")["availability"] == "not_loaded"
        run = store.rows("SELECT * FROM runs")[0]
        assert run["outcome"] == "succeeded" and run["triggered"] == 1
        assert len(store.rows("SELECT * FROM issues WHERE active=1")) == 3
        assert "synthetic-ha-token" not in json.dumps(store.rows("SELECT * FROM issues"))
        assert rest_methods == ["GET"]
        await sockets[0].close()
        async with asyncio.timeout(5):
            await reconnected.wait()
        assert store.get_meta("last_gap")
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await runner.cleanup()
        store.close()
