"""Closed read gateway. This module contains the ONLY HA network transport."""

import asyncio
import json
import re
import time
from contextlib import suppress

import aiohttp

# Values are exact permitted parameter names. No raw path or command comes from AI/UI.
READS = {
    "get_states": set(),
    "config/device_registry/list": set(),
    "config/entity_registry/list": set(),
    "repairs/list_issues": set(),
    "system_log/list": set(),
    "trace/list": {"domain", "item_id"},
    "trace/get": {"domain", "item_id", "run_id"},
    "subscribe_events": {"event_type"},
}
EVENTS = {"state_changed", "automation_triggered"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")
VERSION = re.compile(r"20[0-9]{2}\.(?:[1-9]|1[0-2])\.(?:0|[1-9][0-9]{0,3})(?:b[1-9][0-9]{0,2})?")


def core_version(value):
    return value if isinstance(value, str) and VERSION.fullmatch(value) else None


class HAError(Exception):
    """Safe code only; never store remote error messages or credentials."""


def validate_read(command, params):
    if command not in READS or set(params) - READS[command]:
        raise HAError("read_policy_denied")
    if command.startswith("trace/"):
        if params.get("domain") != "automation":
            raise HAError("read_policy_denied")
        for name in ("item_id", "run_id"):
            if name in params and not IDENTIFIER.fullmatch(str(params[name])):
                raise HAError("read_policy_denied")
        if command == "trace/get" and not {"item_id", "run_id"} <= params.keys():
            raise HAError("read_policy_denied")
    if command == "subscribe_events" and params.get("event_type") not in EVENTS:
        raise HAError("read_policy_denied")


class HAClient:
    def __init__(self, base_url, token, on_event, *, websocket_url=None):
        self.base_url = base_url
        self.websocket_url = websocket_url or base_url + "/api/websocket"
        self.token = token
        self.on_event = on_event
        self.pending = {}
        self.counter = 0
        self.reader = None
        self.server_version, self.version_observed_at = None, None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            trust_env=False,
        )
        try:
            self.ws = await self.session.ws_connect(
                self.websocket_url,
                heartbeat=30,
                max_msg_size=16 * 1024 * 1024,
            )
            async with asyncio.timeout(15):
                hello = await self.ws.receive_json()
                if hello.get("type") != "auth_required":
                    raise HAError("unexpected_auth_protocol")
                await self.ws.send_json({"type": "auth", "access_token": self.token})
                auth = await self.ws.receive_json()
                if auth.get("type") != "auth_ok":
                    raise HAError("authentication_failed")
                self.server_version = core_version(auth.get("ha_version"))
                self.version_observed_at = time.time() if self.server_version else None
            self.reader = asyncio.create_task(self._read())
            return self
        except BaseException:
            await self.session.close()
            raise

    async def __aexit__(self, *args):
        if self.reader:
            self.reader.cancel()
            with suppress(asyncio.CancelledError, HAError, aiohttp.ClientError):
                await self.reader
        await self.session.close()

    async def _read(self):
        try:
            async for frame in self.ws:
                if frame.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = frame.json()
                if data.get("type") == "event":
                    self.on_event(data.get("event", {}))
                elif data.get("type") == "result":
                    future = self.pending.get(data.get("id"))
                    if future and not future.done():
                        if data.get("success"):
                            future.set_result(data.get("result"))
                        else:
                            error = data.get("error")
                            code = error.get("code") if isinstance(error, dict) else None
                            safe_code = "read_unavailable"
                            if code == "not_found":
                                safe_code = "read_not_found"
                            elif isinstance(code, str) and code in {
                                "unauthorized",
                                "unauthenticated",
                                "unknown_command",
                                "not_supported",
                            }:
                                safe_code = "capability_unavailable"
                            future.set_exception(HAError(safe_code))
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(HAError("connection_lost"))
        raise HAError("connection_lost")

    async def read(self, command, **params):
        validate_read(command, params)
        self.counter += 1
        request_id = self.counter
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            await self.ws.send_json({"id": request_id, "type": command, **params})
            async with asyncio.timeout(20):
                return await future
        finally:
            self.pending.pop(request_id, None)

    async def automation_config(self, automation_id):
        # Admin-only YAML automation config lookup; unavailable entries may 404.
        if not IDENTIFIER.fullmatch(automation_id):
            raise HAError("read_policy_denied")
        async with self.session.get(
            self.base_url + "/api/config/automation/config/" + automation_id,
            headers={"Authorization": "Bearer " + self.token},
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise HAError("config_unavailable")
            chunks = []
            size = 0
            async for chunk in response.content.iter_chunked(64 * 1024):
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    raise HAError("config_too_large")
                chunks.append(chunk)
            try:
                config = json.loads(b"".join(chunks))
            except ValueError:
                raise HAError("config_invalid_response") from None
            if not isinstance(config, dict):
                raise HAError("config_invalid_response")
            return config
