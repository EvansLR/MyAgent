from types import SimpleNamespace
from pathlib import Path

import pytest

from myagent.config import Settings
from myagent.providers import EchoProvider, OpenAICompatibleProvider, create_provider


def test_settings_reads_myagent_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYAGENT_API_KEY", "myagent-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    settings = Settings.from_env()

    assert settings.api_key == "myagent-key"


def test_settings_falls_back_to_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MYAGENT_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    settings = Settings.from_env()

    assert settings.api_key == "openai-key"


def test_settings_reads_json_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MYAGENT_PROVIDER", raising=False)
    monkeypatch.delenv("MYAGENT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MYAGENT_BASE_URL", raising=False)
    monkeypatch.delenv("MYAGENT_MODEL", raising=False)
    monkeypatch.delenv("MYAGENT_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("MYAGENT_PROVIDER_RETRIES", raising=False)
    with_config_file(
        "settings_reads.json",
        "\n".join(
            [
                "{",
                '  "provider": {',
                '    "mode": "openai",',
                '    "apiKey": "file-key",',
                '    "baseUrl": "https://example.test/v1",',
                '    "model": "file-model",',
                '    "systemPrompt": "File prompt.",',
                '    "retries": 3',
                "  }",
                "}",
            ]
        ),
        lambda config: assert_settings_from_json(config),
    )


def test_environment_overrides_json_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYAGENT_PROVIDER", "openai")
    monkeypatch.setenv("MYAGENT_API_KEY", "env-key")
    monkeypatch.setenv("MYAGENT_MODEL", "env-model")

    with_config_file(
        "environment_overrides.json",
        "\n".join(
            [
                "{",
                '  "provider": {',
                '    "mode": "echo",',
                '    "apiKey": "file-key",',
                '    "model": "file-model"',
                "  }",
                "}",
            ]
        ),
        lambda config: assert_environment_overrides(config),
    )


def with_config_file(name: str, content: str, check) -> None:
    path = Path(".test-workspaces") / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        check(path)
    finally:
        path.unlink(missing_ok=True)


def assert_settings_from_json(config: Path) -> None:
    settings = Settings.from_sources(config)

    assert settings.provider == "openai"
    assert settings.api_key == "file-key"
    assert settings.base_url == "https://example.test/v1"
    assert settings.model == "file-model"
    assert settings.system_prompt == "File prompt."
    assert settings.provider_retries == 3


def assert_environment_overrides(config: Path) -> None:
    settings = Settings.from_sources(config)

    assert settings.provider == "openai"
    assert settings.api_key == "env-key"
    assert settings.model == "env-model"


def test_create_provider_auto_without_key_returns_echo() -> None:
    provider = create_provider(Settings(provider="auto", api_key=None))

    assert isinstance(provider, EchoProvider)


def test_create_provider_auto_with_key_returns_openai_provider() -> None:
    provider = create_provider(Settings(provider="auto", api_key="test-key"))

    assert isinstance(provider, OpenAICompatibleProvider)


def test_create_provider_openai_without_key_raises() -> None:
    with pytest.raises(ValueError, match="requires an API key"):
        create_provider(Settings(provider="openai", api_key=None))


def test_create_provider_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported provider mode"):
        create_provider(Settings(provider="missing", api_key=None))


class FakeCompletions:
    def __init__(self, failures_before_success: int = 0) -> None:
        self.calls = 0
        self.failures_before_success = failures_before_success

    async def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise RuntimeError("temporary failure")
        assert kwargs["model"] == "fake-model"
        assert kwargs["messages"][-1] == {"role": "user", "content": "hello"}
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="real reply"),
                )
            ]
        )


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


async def test_openai_provider_generates_text_from_fake_client() -> None:
    completions = FakeCompletions()
    provider = OpenAICompatibleProvider(
        Settings(api_key="test-key", model="fake-model"),
        client=FakeClient(completions),
    )

    result = await provider.generate([{"role": "user", "content": "hello"}])

    assert result == "real reply"
    assert completions.calls == 1


async def test_openai_provider_retries_then_succeeds() -> None:
    completions = FakeCompletions(failures_before_success=1)
    provider = OpenAICompatibleProvider(
        Settings(api_key="test-key", model="fake-model", provider_retries=2),
        client=FakeClient(completions),
    )

    result = await provider.generate([{"role": "user", "content": "hello"}])

    assert result == "real reply"
    assert completions.calls == 2
