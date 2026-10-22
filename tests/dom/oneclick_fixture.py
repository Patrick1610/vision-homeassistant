"""Real synthetic ASGI/native-mock lifecycle projected for whole-app DOM tests."""

import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root), str(root / "tests")]

import httpx  # noqa: E402
from pydantic import SecretStr  # noqa: E402
from test_home_experience import seed  # noqa: E402
from test_oneclick import human_result  # noqa: E402
from test_public_research import PublicMock  # noqa: E402

from vision.ai_provider import HTTPProvider  # noqa: E402
from vision.app import create_app  # noqa: E402
from vision.config import Settings  # noqa: E402
from vision.oneclick import VERSION  # noqa: E402


async def main(directory):
    app = create_app(
        SimpleNamespace(supervised=False, data=Path(directory), token=""),
        Settings(
            ai_enabled=True,
            anthropic_api_key=SecretStr("synthetic-key"),
            anthropic_model="synthetic",
            anthropic_input_usd_per_million=1,
            anthropic_output_usd_per_million=2,
        ),
        connect=False,
    )
    async with app.router.lifespan_context(app):
        ai, m = app.state.ai, app.state.monitor
        seed(m)
        await m.reliability.wait_cache()
        m.home.refresh()
        entered, release = asyncio.Event(), asyncio.Event()
        await ai.research.client.aclose()
        ai.research.client = httpx.AsyncClient(transport=httpx.MockTransport(PublicMock()))

        async def provider(request):
            entered.set()
            await release.wait()
            body = json.loads(request.content)
            result = human_result(json.loads(body["messages"][0]["content"]))
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as native:
            ai.providers["anthropic"] = HTTPProvider("anthropic", native)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)),
                base_url="http://vision",
                headers={"x-vision-request": "1"},
            ) as client:
                paths = [
                    "health",
                    "settings",
                    "devices",
                    "exceptions",
                    "home/preferences",
                    "today?window=24h",
                    "home/devices?page=1&q=",
                    "problems?mode=attention&page=1",
                    "home/investigation-consent",
                ]
                values = {p: (await client.get("/api/" + p)).json() for p in paths}
                key = values["problems?mode=attention&page=1"]["items"][0]["problem_id"]
                values["problems/" + key] = (await client.get("/api/problems/" + key)).json()
                await client.post(
                    "/api/home/investigation-consent", json={"version": VERSION, "enabled": True}
                )
                context = (await client.get(f"/api/problems/{key}/investigation-context")).json()
                values[f"problems/{key}/investigation-context"] = context
                for item in values["problems?mode=attention&page=1"]["items"]:
                    path = "problems/" + item["problem_id"]
                    values[path] = (await client.get("/api/" + path)).json()
                    values[path + "/investigation-context"] = (
                        await client.get("/api/" + path + "/investigation-context")
                    ).json()
                token = {
                    "operation_id": f"op1_{context['slot']}_" + "a" * 32,
                    "revision": context["revision"],
                    "language": "en",
                }
                response = await client.post(f"/api/problems/{key}/investigate", json=token)
                assert response.status_code == 202, response.text
                await entered.wait()
                values["qa/running"] = (
                    await client.get("/" + response.json()["status_url"])
                ).json()
                values["qa/running-context"] = (
                    await client.get(f"/api/problems/{key}/investigation-context")
                ).json()
                release.set()
                await ai.oneclick.task
                values["qa/completed"] = (
                    await client.get("/" + response.json()["status_url"])
                ).json()
                values["qa/completed-context"] = (
                    await client.get(f"/api/problems/{key}/investigation-context")
                ).json()
                values["intelligence"] = (await client.get("/api/intelligence")).json()
                values["qa/request"] = (
                    await client.get(
                        "/api/intelligence/requests/" + values["qa/completed"]["final_request_id"]
                    )
                ).json()
                values["qa/conversation"] = (
                    await client.get(
                        "/api/intelligence/conversations/" + values["qa/request"]["conversation_id"]
                    )
                ).json()
                values["qa/audit"] = (
                    await client.get("/" + response.json()["status_url"] + "/audit")
                ).json()
                values["qa/analysis"] = (
                    await client.get(
                        "/api/intelligence/analyses/" + str(values["qa/completed"]["analysis_id"])
                    )
                ).json()
                other = next(
                    item["problem_id"]
                    for item in values["problems?mode=attention&page=1"]["items"]
                    if item["problem_id"] != key
                )
                other_context = values[f"problems/{other}/investigation-context"]
                second = {
                    "operation_id": f"op1_{other_context['slot']}_" + "b" * 32,
                    "revision": other_context["revision"],
                    "language": "en",
                }
                second_response = await client.post(
                    f"/api/problems/{other}/investigate", json=second
                )
                assert second_response.status_code == 202, second_response.text
                await ai.oneclick.task
                values["qa/other-completed"] = (
                    await client.get("/" + second_response.json()["status_url"])
                ).json()
                values["qa/revoked"] = (
                    await client.post("/" + response.json()["status_url"] + "/revoke")
                ).json()
                print(json.dumps(values))


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        asyncio.run(main(directory))
