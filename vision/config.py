"""Private configuration. No arbitrary provider endpoints or HA operations."""

import json
import os
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SecretStr, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)
    _consent_generation: int = PrivateAttr(default=0)

    def __setattr__(self, name, value):
        previous = self.__dict__.copy()
        fields_set = self.__pydantic_fields_set__.copy()
        try:
            super().__setattr__(name, value)
        except ValueError:
            # Pydantic after-validators can fail after assigning a field. Restore
            # the complete validated configuration before exposing that failure.
            self.__dict__.clear()
            self.__dict__.update(previous)
            object.__setattr__(self, "__pydantic_fields_set__", fields_set)
            raise
        if (
            name in {"ai_enabled", "ai_privacy"}
            and name in previous
            and previous[name] != getattr(self, name)
        ):
            self._consent_generation += 1

    allowed_user_ids: list[
        Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
    ] = Field(
        default_factory=list,
        max_length=100,
    )

    poll_seconds: int = Field(default=60, ge=15, le=3600)
    retention_days: int = Field(default=90, ge=7, le=730)
    ai_enabled: bool = False
    ai_privacy: Literal["local_only", "compact", "diagnostic"] = "compact"
    daily_audit: bool = False
    audit_hour_utc: int = Field(default=4, ge=0, le=23)
    primary_provider: Literal["anthropic", "openai"] = "anthropic"
    allow_budget_failover: bool = False
    monthly_budget_usd: float = Field(default=5, ge=0, le=10000)
    max_output_tokens: int = Field(default=2048, ge=512, le=65536)
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = Field(default="", max_length=100, pattern=r"^[\w.:-]*$")
    anthropic_daily_budget_usd: float = Field(default=1, ge=0, le=1000)
    anthropic_input_usd_per_million: float = Field(default=0, ge=0, le=10000)
    anthropic_output_usd_per_million: float = Field(default=0, ge=0, le=10000)
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = Field(default="", max_length=100, pattern=r"^[\w.:-]*$")
    openai_daily_budget_usd: float = Field(default=1, ge=0, le=1000)
    openai_input_usd_per_million: float = Field(default=0, ge=0, le=10000)
    openai_output_usd_per_million: float = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def daily_needs_consent(self):
        if self.daily_audit and not self.ai_enabled:
            raise ValueError("Daily audits require AI opt-in")
        return self

    def public(self) -> dict:
        result = self.model_dump(
            exclude={"anthropic_api_key", "openai_api_key", "allowed_user_ids"}
        )
        result["allowed_user_count"] = len(self.allowed_user_ids)
        for provider in ("anthropic", "openai"):
            result[f"{provider}_key_configured"] = bool(self.key(provider))
        return result

    def key(self, provider: str) -> str:
        return getattr(self, f"{provider}_api_key").get_secret_value()

    @classmethod
    def load(cls, path: Path):
        return cls.model_validate(json.loads(path.read_text()) if path.exists() else {})


class Runtime:
    """Host-specific connection details, deliberately absent from public settings."""

    def __init__(self):
        self.supervised = bool(os.environ.get("SUPERVISOR_TOKEN"))
        self.data = Path(os.environ.get("VISION_DATA", "/data" if self.supervised else "data"))
        self.options = Path(os.environ.get("VISION_OPTIONS", str(self.data / "options.json")))
        self.token = os.environ.get("SUPERVISOR_TOKEN", os.environ.get("HA_TOKEN", ""))
        self.ha_url = (
            "http://supervisor/core"
            if self.supervised
            else os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
        )
        self.websocket_url = (
            "http://supervisor/core/websocket"
            if self.supervised
            else self.ha_url + "/api/websocket"
        )
