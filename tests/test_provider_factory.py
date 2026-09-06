def test_provider_factory_defaults_to_deterministic():
    from app.provider.agent_provider import DeterministicAgentProvider
    from app.provider.provider_factory import build_agent_provider

    provider = build_agent_provider({})

    assert isinstance(provider, DeterministicAgentProvider)


def test_provider_factory_builds_openai_compatible_provider():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_factory import build_agent_provider

    provider = build_agent_provider({
        "AGENT_PROVIDER": "openai-compatible",
        "OPENAI_API_KEY": "test-secret",
        "OPENAI_BASE_URL": "https://llm.example/v1",
        "OPENAI_TIMEOUT_SECONDS": "12.5",
    })

    assert isinstance(provider, OpenAICompatibleAgentProvider)


def test_provider_factory_requires_api_key_for_openai_compatible():
    import pytest
    from app.provider.provider_factory import build_agent_provider

    with pytest.raises(RuntimeError):
        build_agent_provider({"AGENT_PROVIDER": "openai-compatible"})


def test_provider_factory_reads_os_environ_when_not_explicitly_provided(monkeypatch):
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_factory import build_agent_provider

    monkeypatch.setenv("AGENT_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")

    provider = build_agent_provider()

    assert isinstance(provider, OpenAICompatibleAgentProvider)
