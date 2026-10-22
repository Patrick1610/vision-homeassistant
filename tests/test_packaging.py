import tomllib
from pathlib import Path
from types import SimpleNamespace

import yaml
from fastapi.testclient import TestClient

from vision import __version__
from vision.app import create_app
from vision.config import Settings

ROOT = Path(__file__).parents[1]


def test_supervisor_metadata_and_default_options():
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    assert config["version"] == __version__ == "0.3.0-dev.2"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["version"] == __version__
    assert f'io.hass.version="{__version__}"' in (ROOT / "Dockerfile").read_text()
    assert f"vision:{__version__}" in (ROOT / "scripts/container_smoke.py").read_text()
    assert config["slug"] == "vision"
    assert config["url"] == "https://github.com/Patrick1610/vision-homeassistant"
    assert config["homeassistant_api"] is True
    assert config["hassio_api"] is False
    assert config["ingress"] and config["panel_admin"]
    assert not any(
        config.get(key)
        for key in ["ports", "map", "privileged", "host_network", "docker_api", "full_access"]
    )
    assert set(config["arch"]) == {"amd64", "aarch64"}
    settings = Settings.model_validate(config["options"])
    assert not settings.ai_enabled and not settings.allowed_user_ids
    assert not settings.daily_audit
    assert settings.ai_privacy == config["options"]["ai_privacy"] == "compact"
    assert config["schema"]["anthropic_api_key"] == "password?"
    assert (ROOT / "Dockerfile").is_file()


def test_supervisor_discovery_algorithm_includes_root():
    # Official Supervisor StoreData._find_app_configs uses this recursive glob.
    configs = [
        p
        for p in ROOT.glob("**/config.*")
        if p.suffix in {".yaml", ".yml", ".json"}
        and not any(part.startswith(".") or part == "rootfs" for part in p.parts)
        and "work" not in p.relative_to(ROOT).parts
    ]
    assert configs == [ROOT / "config.yaml"]


def test_static_assets_use_ingress_relative_paths():
    html = (ROOT / "vision/static/index.html").read_text()
    assert 'href="static/style.css"' in html
    assert 'src="static/app.js"' in html
    assert 'src="/static' not in html


def test_visible_http_version_uses_runtime_metadata(tmp_path, monkeypatch):
    # A changed runtime value must reach the visible wordmark without editing HTML.
    monkeypatch.setattr("vision.app.__version__", "0.2.0-visible-probe")
    runtime = SimpleNamespace(supervised=False, data=tmp_path, token="")
    with TestClient(
        create_app(runtime, Settings(), connect=False), client=("127.0.0.1", 123)
    ) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert '<small id="app-version">0.2.0-visible-probe</small>' in response.text
        assert "{{VISION_VERSION}}" not in response.text
        assert client.get("/api/health").json()["version"] == "0.2.0-visible-probe"
