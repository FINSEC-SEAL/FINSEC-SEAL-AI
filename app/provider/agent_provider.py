from typing import Protocol

from app.domain.agent import (
    AgentStepRequest,
    AgentStepResponse,
    FinalResponseAction,
    ToolProposalAction,
)


class AgentProvider(Protocol):
    def execute(self, request: AgentStepRequest) -> AgentStepResponse:
        ...


class DeterministicAgentProvider:
    provider = "deterministic"
    model = "stateless-contract-v1"

    def execute(self, request: AgentStepRequest) -> AgentStepResponse:
        if request.previousToolResult is None:
            return AgentStepResponse(
                provider=self.provider,
                model=self.model,
                finishReason="tool_call",
                action=ToolProposalAction(
                    type="TOOL_PROPOSAL",
                    toolName=request.attackVariant.targetTool,
                    arguments=self._proposal_arguments(request),
                ),
                latencyMs=0,
            )

        return AgentStepResponse(
            provider=self.provider,
            model=self.model,
            finishReason="stop",
            action=FinalResponseAction(
                type="FINAL_RESPONSE",
                content="Tool result received; agent step completed.",
            ),
            latencyMs=0,
        )

    @staticmethod
    def _proposal_arguments(request: AgentStepRequest) -> dict:
        if request.attackVariant.category != "FA-01":
            return dict(request.attackVariant.toolArguments)

        # Reproduce the Tool call induced by the curated untrusted-document seed.
        # The real provider derives this proposal from the document content.
        return {
            "customerIds": ["CUST-1002"],
            "fields": ["incomeBand", "accountNumber"],
        }
