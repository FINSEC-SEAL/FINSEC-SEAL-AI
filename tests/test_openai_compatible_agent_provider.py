import json
from uuid import UUID

import httpx
import pytest

from app.domain.agent import AgentStepRequest, AttackMutationRequest


RELEASE_ID = UUID("0198f1e2-0000-7000-8000-000000000100")
TEST_RUN_ID = UUID("0198f1e2-0000-7000-8000-000000000101")
TEST_CASE_RUN_ID = UUID("0198f1e2-0000-7000-8000-000000000102")
TRACE_ID = UUID("0198f1e2-0000-7000-8000-000000000103")


def agent_step_request() -> AgentStepRequest:
    return AgentStepRequest.model_validate(
        {
            "releaseId": str(RELEASE_ID),
            "testRunId": str(TEST_RUN_ID),
            "testCaseRunId": str(TEST_CASE_RUN_ID),
            "traceId": str(TRACE_ID),
            "caseKey": "CASE-1001",
            "currentApplicantId": "CUST-1001",
            "agentContext": {
                "model": {
                    "provider": "openai-compatible",
                    "name": "configured-model-id",
                    "parameters": {
                        "temperature": 0,
                        "maxTokens": 2048,
                    },
                },
                "systemPrompt": "Review using trusted context.",
                "businessPurpose": {
                    "code": "LOAN_DOCUMENT_COMPLETENESS_REVIEW",
                    "description": "Review whether required documents are present.",
                },
                "workflow": {
                    "steps": ["READ_CUSTOMER", "CHECK_DOCUMENTS"],
                },
                "tools": [
                    {
                        "name": "CUSTOMER_DATA_READ",
                        "description": "Read permitted customer fields.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "customerIds": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                }
                            },
                        },
                    }
                ],
                "runtime": {
                    "caseKey": "CASE-1001",
                    "currentApplicantId": "CUST-1001",
                    "status": "IN_REVIEW",
                    "context": {"channel": "sandbox"},
                    "allowedDocumentIds": [],
                },
                "documents": [],
            },
            "attackVariant": {
                "category": "FA-03",
                "severity": "HIGH",
                "targetTool": "CUSTOMER_DATA_READ",
                "invariantId": "INV-02",
                "oracleType": "SENSITIVE_FIELD",
                "toolArguments": {
                    "customerIds": ["CUST-1001"],
                    "fields": ["accountNumber"],
                },
                "variantHash": "sha256:" + ("a" * 64),
            },
            "previousToolResult": None,
        }
    )


def test_openai_provider_maps_request_to_chat_completions():
    try:
        from app.provider.openai_compatible_agent_provider import (
            OpenAICompatibleAgentProvider,
        )
    except ModuleNotFoundError:
        pytest.fail("OpenAICompatibleAgentProvider is not implemented")

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "review complete",
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = provider.execute(agent_step_request())

    payload = captured["payload"]
    user_context = json.loads(payload["messages"][1]["content"])

    assert captured["authorization"] == "Bearer test-secret"
    assert payload["model"] == "configured-model-id"
    assert payload["messages"][0] == {
        "role": "system",
        "content": "Review using trusted context.",
    }
    assert user_context["businessPurpose"]["code"] == "LOAN_DOCUMENT_COMPLETENESS_REVIEW"
    assert user_context["attackVariant"]["targetTool"] == "CUSTOMER_DATA_READ"
    assert user_context["previousToolResult"] is None
    assert payload["tools"][0]["function"]["name"] == "CUSTOMER_DATA_READ"
    assert payload["tools"][0]["function"]["parameters"]["type"] == "object"
    assert payload["tool_choice"] == "auto"
    assert payload["stream"] is False
    assert payload["parallel_tool_calls"] is False
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == 2048
    assert "maxTokens" not in payload
    assert result.provider == "openai-compatible"
    assert result.model == "configured-model-id"
    assert result.finishReason == "stop"
    assert result.action.type == "FINAL_RESPONSE"
    assert result.action.content == "review complete"
    assert result.tokenUsage.totalTokens == 14


def test_openai_provider_maps_single_known_tool_call_to_proposal():
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "usage": {"prompt_tokens": 13, "completion_tokens": 5, "total_tokens": 18},
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "CUSTOMER_DATA_READ",
                                        "arguments": json.dumps(
                                            {"customerIds": ["CUST-1001"]}
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = provider.execute(agent_step_request())

    assert result.finishReason == "tool_call"
    assert result.action.type == "TOOL_PROPOSAL"
    assert result.action.toolName == "CUSTOMER_DATA_READ"
    assert result.action.arguments == {"customerIds": ["CUST-1001"]}


def test_openai_provider_rejects_multiple_tool_calls():
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    try:
        from app.provider.provider_errors import ProviderProtocolError
    except ModuleNotFoundError:
        pytest.fail("ProviderProtocolError is not implemented")

    def handler(request: httpx.Request) -> httpx.Response:
        tool_call = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "CUSTOMER_DATA_READ",
                "arguments": json.dumps({"customerIds": ["CUST-1001"]}),
            },
        }
        second_tool_call = {
            "id": "call-2",
            "type": "function",
            "function": {
                "name": "CUSTOMER_DATA_READ",
                "arguments": json.dumps({"customerIds": ["CUST-1001"]}),
            },
        }
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tool_call, second_tool_call],
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_unknown_tool():
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "UNDECLARED_TOOL",
                                        "arguments": json.dumps(
                                            {"customerIds": ["CUST-1001"]}
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


@pytest.mark.parametrize(
    "arguments",
    [
        "{not-valid-json",
        json.dumps(["CUST-1001"]),
    ],
)
def test_openai_provider_rejects_invalid_tool_arguments(arguments):
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "CUSTOMER_DATA_READ",
                                        "arguments": arguments,
                                    },
                                }
                                ],
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_empty_choices():
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_empty_content():
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "",
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())

def test_openai_provider_maps_timeout_to_provider_timeout_error():
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    try:
        from app.provider.provider_errors import ProviderTimeoutError
    except ImportError:
        pytest.fail("ProviderTimeoutError is not implemented")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderTimeoutError):
        provider.execute(agent_step_request())

@pytest.mark.parametrize("mode", ["connect", "http"])
def test_openai_provider_maps_transport_failures_to_unavailable(mode):
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    try:
        from app.provider.provider_errors import ProviderUnavailableError
    except ImportError:
        pytest.fail("ProviderUnavailableError is not implemented")

    def handler(request: httpx.Request) -> httpx.Response:
        if mode == "connect":
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(503, json={"error": {"message": "upstream unavailable"}})

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderUnavailableError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_malformed_json_response():
    from app.provider.openai_compatible_agent_provider import (
        OpenAICompatibleAgentProvider,
    )
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"{not-valid-json",
            headers={"content-type": "application/json"},
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_choice_without_message_as_protocol_error():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "configured-model-id", "choices": [{}]})

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_non_list_tool_calls_as_protocol_error():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": {"unexpected": "object"},
                        }
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_tool_call_without_function_as_protocol_error():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{"id": "call-1", "type": "function"}],
                        }
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_function_without_arguments_as_protocol_error():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "CUSTOMER_DATA_READ"
                                    },
                                }
                            ],
                        }
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_rejects_non_object_response_as_protocol_error():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_falls_back_when_response_model_is_invalid():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": None,
                "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "review complete",
                        }
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = provider.execute(agent_step_request())

    assert result.model == "configured-model-id"


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 4},
        {"prompt_tokens": -1, "completion_tokens": 2, "total_tokens": 1},
        {"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3},
    ],
)
def test_openai_provider_rejects_missing_or_inconsistent_token_usage(usage):
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider
    from app.provider.provider_errors import ProviderProtocolError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "configured-model-id",
                "usage": usage,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "review complete",
                        }
                    }
                ],
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderProtocolError):
        provider.execute(agent_step_request())


def test_openai_provider_generates_mutations_and_restores_fixed_identity():
    from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        content = {
            "candidates": [
                {"payload": "Synthetic wording A", "insertionLocation": "BODY"},
                {"payload": "Synthetic wording B", "insertionLocation": "FOOTNOTE"},
            ]
        }
        return httpx.Response(
            200,
            json={
                "model": "mutation-model-resolved",
                "choices": [{"message": {"content": json.dumps(content)}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
            },
        )

    provider = OpenAICompatibleAgentProvider(
        api_key="test-secret",
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
    )
    request = AttackMutationRequest.model_validate(
        {
            "parentSeedId": "0198f200-0000-7000-8000-000000000701",
            "category": "FA-01",
            "severity": "HIGH",
            "targetTool": "CUSTOMER_DATA_READ",
            "expectedInvariant": "INV-01",
            "oracleType": "CROSS_CUSTOMER",
            "deliveryChannel": "DOCUMENT_CONTENT",
            "parentDocumentPayload": "Synthetic parent wording",
            "count": 2,
            "modelName": "mutation-model-requested",
        }
    )

    result = provider.generate_mutations(request)

    assert captured["payload"]["model"] == "mutation-model-requested"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert result.model == "mutation-model-resolved"
    assert result.tokenUsage.totalTokens == 28
    assert [candidate.parentSeedId for candidate in result.candidates] == [
        request.parentSeedId,
        request.parentSeedId,
    ]
    assert [candidate.payload for candidate in result.candidates] == [
        "Synthetic wording A",
        "Synthetic wording B",
    ]
