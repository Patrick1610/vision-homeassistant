import asyncio
import json

import aiohttp
import pytest
from aiohttp import web

from vision.ha import HAClient, HAError


@pytest.mark.parametrize(
    "body,error_code",
    [
        (b'{"triggers":[{"trigger":"state"}],"actions":[]}', None),
        (b'{"triggers":', "config_invalid_response"),
        (b"[]", "config_invalid_response"),
        (b'{"padding":"' + b"x" * (2 * 1024 * 1024) + b'"}', "config_too_large"),
    ],
    ids=["fragmented-json", "malformed-json", "nonobject-json", "oversized-stream"],
)
async def test_streamed_automation_configuration(unused_tcp_port, body, error_code):
    requests = []

    async def handler(request):
        requests.append((request.method, request.path, request.headers.get("Authorization")))
        response = web.StreamResponse(headers={"Content-Type": "application/json"})
        await response.prepare(request)
        await response.write(body[:4])
        await asyncio.sleep(0.02)  # Force a partial network read before the rest arrives.
        try:
            await response.write(body[4:])
            await response.write_eof()
        except ConnectionResetError:
            pass  # A size-limit rejection may close the response before the writer finishes.
        return response

    server = web.Application()
    server.router.add_get("/api/config/automation/config/123", handler)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    try:
        async with aiohttp.ClientSession() as session:
            client = HAClient(
                f"http://127.0.0.1:{unused_tcp_port}", "synthetic-token", lambda _: None
            )
            client.session = session
            if error_code:
                with pytest.raises(HAError, match=error_code):
                    await client.automation_config("123")
            else:
                assert await client.automation_config("123") == json.loads(body)
        assert requests == [("GET", "/api/config/automation/config/123", "Bearer synthetic-token")]
    finally:
        await runner.cleanup()
