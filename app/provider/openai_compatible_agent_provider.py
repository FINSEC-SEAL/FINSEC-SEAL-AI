import json
import time

import httpx

from app.domain.agent import (
    AgentStepRequest,
    AgentStepResponse,
    FinalResponseAction,
    ToolProposalAction,
)

from app.provider.provider_errors import ProviderProtocolError, ProviderTimeoutError, ProviderUnavailableError


PARAMETER_ALIASES = {
    "maxTokens": "max_tokens",
    "topP": "top_p",
}

RESERVED_PARAMETERS = {
    "model",
    "messages",
    "tools",
    "tool_choice",
    "stream",
    "parallel_tool_calls",
}


class OpenAICompatibleAgentProvider:
    provider = "openai-compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def execute(self, request: AgentStepRequest) -> AgentStepResponse:
        parameters = {}
        for key, value in request.agentContext.model.parameters.items():
            normalized_key = PARAMETER_ALIASES.get(key, key)
            if normalized_key not in RESERVED_PARAMETERS:
                parameters[normalized_key] = value

        user_context = {
            "businessPurpose": request.agentContext.businessPurpose.model_dump(
                mode="json"
            ),
            "workflow": request.agentContext.workflow,
            "runtime": request.agentContext.runtime.model_dump(mode="json"),
            "documents": [
                document.model_dump(mode="json")
                for document in request.agentContext.documents
            ],
            "attackVariant": request.attackVariant.model_dump(mode="json"),
            "previousToolResult": (
                request.previousToolResult.model_dump(mode="json")
                if request.previousToolResult is not None
                else None
            ),
        }

        payload = {
            **parameters,
            "model": request.agentContext.model.name,
            "messages": [
                {
                    "role": "system",
                    "content": request.agentContext.systemPrompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        user_context,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                }
                for tool in request.agentContext.tools
            ],
            "tool_choice": "auto",
            "stream": False,
            "parallel_tool_calls": False,
        }

        started = time.perf_counter()
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=self._timeout_seconds,
            ) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                    },
                    json=payload,
                )
                response.raise_for_status()
                response_payload = response.json()
        except httpx.TimeoutException:
            raise ProviderTimeoutError("Agent provider timed out.") from None
        except (httpx.RequestError, httpx.HTTPStatusError):
            raise ProviderUnavailableError("Agent provider unavailable.") from None
        except json.JSONDecodeError:
            raise ProviderProtocolError("Agent provider returned invalid JSON.") from None

        latency_ms = int((time.perf_counter() - started) * 1000)
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderProtocolError("Provider response must contain a choice.")
        message = choices[0]["message"]
        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            if len(tool_calls) != 1:
                raise ProviderProtocolError("Expected exactly one tool call.")
            tool_call = tool_calls[0]
            function = tool_call["function"]
            allowed_tool_names = {tool.name for tool in request.agentContext.tools}
            if function["name"] not in allowed_tool_names:
                raise ProviderProtocolError("Unknown tool returned by provider.")
            try:
                arguments = json.loads(function["arguments"])
            except (json.JSONDecodeError, TypeError):
                raise ProviderProtocolError("Tool arguments must be valid JSON.") from None
            if not isinstance(arguments, dict):
                raise ProviderProtocolError("Tool arguments must be a JSON object.")
            return AgentStepResponse(
                provider=self.provider,
                model=response_payload.get(
                    "model", request.agentContext.model.name
                ),
                finishReason="tool_call",
                action=ToolProposalAction(
                    type="TOOL_PROPOSAL",
                    toolName=function["name"],
                    arguments=arguments,
                ),
                latencyMs=latency_ms,
            )

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderProtocolError("Provider response must contain non-empty content.")

        return AgentStepResponse(
            provider=self.provider,
            model=response_payload.get(
                "model", request.agentContext.model.name
            ),
            finishReason="stop",
            action=FinalResponseAction(
                type="FINAL_RESPONSE",
                content=content,
            ),
            latencyMs=latency_ms,
        )
