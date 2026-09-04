from app.domain.agent import (
    AgentStepRequest,
    AgentStepResponse,
    FinalResponseAction,
    ToolProposalAction,
)


class StatelessAgentService:
    """
    Contract-first stateless agent.

    This first slice intentionally does not call an external LLM yet.
    Each request contains all state needed for one step. The deterministic
    behavior lets Spring/Python integration be verified before a provider
    adapter is introduced.
    """

    provider = "deterministic"
    model = "stateless-contract-v1"

    def execute_step(self, request: AgentStepRequest) -> AgentStepResponse:
        if request.previousToolResult is None:
            return AgentStepResponse(
                provider=self.provider,
                model=self.model,
                finishReason="tool_call",
                action=ToolProposalAction(
                    type="TOOL_PROPOSAL",
                    toolName=request.attackVariant.targetTool,
                    arguments=dict(request.attackVariant.toolArguments),
                ),
                latencyMs=0,
            )

        # The tool output was delivered to the agent boundary. Do not echo it
        # into the final response: persisted evidence remains Spring-owned.
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


_service = StatelessAgentService()


def get_agent_service() -> StatelessAgentService:
    return _service
