"""Runtime settings loaded from JSON plus environment overrides."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from myagent.mcp import McpServerConfig, parse_mcp_servers


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_SYSTEM_PROMPT = "You are MyAgent, a concise and helpful assistant."
DEFAULT_CONFIG_PATH = Path("myagent.json")


@dataclass(frozen=True, slots=True)
class Settings:
    """Small settings object for the first-stage runtime."""

    provider: str = "auto"
    api_key: str | None = None
    base_url: str | None = None
    model: str = DEFAULT_MODEL
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    provider_retries: int = 2
    mcp_servers: list[McpServerConfig] = field(default_factory=list)

    @classmethod
    def from_sources(cls, config_path: str | Path | None = None) -> "Settings":
        """Load settings from config file, then apply environment overrides."""
        file_values = _load_config_values(_resolve_config_path(config_path))
        return cls(
            provider=(
                os.getenv("MYAGENT_PROVIDER")
                or file_values.get("provider")
                or "auto"
            ).strip().lower()
            or "auto",
            api_key=(
                os.getenv("MYAGENT_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or _none_if_blank(file_values.get("api_key"))
            ),
            base_url=os.getenv("MYAGENT_BASE_URL") or _none_if_blank(file_values.get("base_url")),
            model=(os.getenv("MYAGENT_MODEL") or file_values.get("model") or DEFAULT_MODEL).strip()
            or DEFAULT_MODEL,
            system_prompt=(
                os.getenv("MYAGENT_SYSTEM_PROMPT")
                or file_values.get("system_prompt")
                or DEFAULT_SYSTEM_PROMPT
            ).strip()
            or DEFAULT_SYSTEM_PROMPT,
            provider_retries=_read_int(
                "MYAGENT_PROVIDER_RETRIES",
                default=_int_from_value(file_values.get("provider_retries"), default=2),
                minimum=1,
            ),
            mcp_servers=file_values.get("mcp_servers", []),
        )

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from default sources.

        Kept for compatibility with the first implementation; this now also
        reads ``myagent.json`` when present.
        """
        return cls.from_sources()

    @property
    def has_api_key(self) -> bool:
        """Return whether a real provider can be configured."""
        return bool(self.api_key)


def _read_int(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _resolve_config_path(config_path: str | Path | None) -> Path:
    if config_path is not None:
        return Path(config_path)
    env_path = os.getenv("MYAGENT_CONFIG")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_PATH


def _load_config_values(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    provider = data.get("provider", {})
    if not isinstance(provider, dict):
        return {}
    return {
        "provider": _string_value(provider.get("mode")),
        "api_key": _string_value(_pick(provider, "apiKey", "api_key")),
        "base_url": _string_value(_pick(provider, "baseUrl", "base_url", "apiBase", "api_base")),
        "model": _string_value(provider.get("model")),
        "system_prompt": _string_value(_pick(provider, "systemPrompt", "system_prompt")),
        "provider_retries": provider.get("retries"),
        "mcp_servers": parse_mcp_servers(data),
    }


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _none_if_blank(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_from_value(value: Any, *, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
