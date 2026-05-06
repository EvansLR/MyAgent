"""Provider implementations."""

from myagent.config import Settings
from myagent.providers.base import BaseProvider
from myagent.providers.echo import EchoProvider
from myagent.providers.openai_compatible import OpenAICompatibleProvider


def create_provider(settings: Settings | None = None) -> BaseProvider:
    """Create the provider selected by settings."""
    settings = settings or Settings.from_env()

    if settings.provider == "echo":
        return EchoProvider()
    if settings.provider == "openai":
        return OpenAICompatibleProvider(settings)
    if settings.provider == "auto":
        if settings.has_api_key:
            return OpenAICompatibleProvider(settings)
        return EchoProvider()

    raise ValueError(f"Unsupported provider mode: {settings.provider}")


__all__ = ["BaseProvider", "EchoProvider", "OpenAICompatibleProvider", "create_provider"]
