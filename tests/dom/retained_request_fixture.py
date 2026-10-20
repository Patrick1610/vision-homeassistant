"""Emit actual synthetic ASGI previews/retained GETs for the whole-app DOM oracle."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from test_public_research import device_request  # noqa: E402

from vision.ai_contract import AnalysisInput  # noqa: E402
from vision.app import create_app  # noqa: E402
from vision.config import Settings  # noqa: E402


def main():
    settings = Settings(
        ai_enabled=True,
        anthropic_model="synthetic",
        anthropic_api_key=SecretStr("synthetic-dom-secret"),
        anthropic_input_usd_per_million=1,
        anthropic_output_usd_per_million=2,
    )
    with TemporaryDirectory() as folder:
        app = create_app(
            SimpleNamespace(supervised=False, data=Path(folder), token=""), settings, connect=False
        )
        with TestClient(
            app, client=("127.0.0.1", 123), headers={"x-vision-request": "1"}
        ) as client:

            async def prepare():
                return device_request(app.state.ai)

            device = client.portal.call(prepare)
            rows = []
            for request, expected in (
                (device, device.target),
                (
                    AnalysisInput(kind="availability", target="light.private_unavailable"),
                    "light.private_unavailable",
                ),
                (AnalysisInput(kind="audit"), "System"),
            ):
                response = client.post("/api/intelligence/preview", json=request.model_dump())
                assert response.status_code == 200
                post = response.json()
                retained = client.get("/api/intelligence/requests/" + post["request_id"]).json()
                rows.append({"expected": expected, "post": post, "retained": retained})
            assert not app.state.store.rows("SELECT * FROM usage")
            print(json.dumps(rows))


if __name__ == "__main__":
    main()
