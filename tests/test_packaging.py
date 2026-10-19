from pathlib import Path

import yaml

from vision import __version__
from vision.config import Settings

ROOT = Path(__file__).parents[1]


def test_supervisor_metadata_and_default_options():
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    assert config["version"] == __version__ == "0.1.0"
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
