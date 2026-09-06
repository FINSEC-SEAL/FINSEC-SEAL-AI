from app.service.agent_service import StatelessAgentService


class RecordingProvider:
    def __init__(self):
        self.received_request = None

    def execute(self, request):
        self.received_request = request
        return "provider-result"


def test_service_delegates_to_injected_provider():
    provider = RecordingProvider()
    service = StatelessAgentService(provider)
    request = object()

    result = service.execute_step(request)

    assert provider.received_request is request
    assert result == "provider-result"


def test_deterministic_provider_exists():
    import importlib

    module = importlib.import_module("app.provider.agent_provider")

    assert hasattr(module, "DeterministicAgentProvider")


def test_deterministic_provider_returns_tool_proposal_for_initial_step():
    from types import SimpleNamespace

    from app.provider.agent_provider import DeterministicAgentProvider

    request = SimpleNamespace(
        previousToolResult=None,
        attackVariant=SimpleNamespace(
            targetTool="CUSTOMER_DATA_READ",
            toolArguments={
                "customerIds": ["CUST-1001"],
                "fields": ["accountNumber"],
            },
        ),
    )

    result = DeterministicAgentProvider().execute(request)

    assert result.provider == "deterministic"
    assert result.model == "stateless-contract-v1"
    assert result.finishReason == "tool_call"
    assert result.action.type == "TOOL_PROPOSAL"
    assert result.action.toolName == "CUSTOMER_DATA_READ"
    assert result.action.arguments == {
        "customerIds": ["CUST-1001"],
        "fields": ["accountNumber"],
    }


def test_deterministic_provider_returns_final_response_after_tool_result():
    from types import SimpleNamespace

    from app.provider.agent_provider import DeterministicAgentProvider

    request = SimpleNamespace(
        previousToolResult=SimpleNamespace(
            output={
                "accountNumber": "SYNTH-ACCT-1001",
            }
        )
    )

    result = DeterministicAgentProvider().execute(request)

    assert result.provider == "deterministic"
    assert result.model == "stateless-contract-v1"
    assert result.finishReason == "stop"
    assert result.action.type == "FINAL_RESPONSE"
    assert "SYNTH-ACCT-1001" not in result.action.content


def test_default_agent_service_uses_deterministic_provider():
    from app.provider.agent_provider import DeterministicAgentProvider
    from app.service.agent_service import get_agent_service

    service = get_agent_service()

    assert isinstance(service._provider, DeterministicAgentProvider)


def test_agent_provider_protocol_exists():
    import importlib

    module = importlib.import_module("app.provider.agent_provider")

    assert hasattr(module, "AgentProvider")


def test_stateless_agent_service_requires_provider():
    import pytest

    from app.service.agent_service import StatelessAgentService

    with pytest.raises(TypeError):
        StatelessAgentService()


def test_default_agent_service_uses_provider_factory(monkeypatch):
    import importlib
    import app.service.agent_service as agent_service
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider

    monkeypatch.setenv("AGENT_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")

    try:
        reloaded = importlib.reload(agent_service)
        assert isinstance(reloaded.get_agent_service()._provider, OpenAICompatibleAgentProvider)
    finally:
        monkeypatch.delenv("AGENT_PROVIDER", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        importlib.reload(agent_service)
