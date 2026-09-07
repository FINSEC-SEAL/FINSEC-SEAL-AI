from typing import Protocol
import json

from app.domain.agent import (
    ContractCandidateRequest,
    ContractCandidateResponse,
    AgentStepRequest,
    AgentStepResponse,
    FinalResponseAction,
    ToolProposalAction,
)


class AgentProvider(Protocol):
    def execute(self, request: AgentStepRequest) -> AgentStepResponse:
        ...

    def generate_contract_candidate(
        self,
        request: ContractCandidateRequest,
    ) -> ContractCandidateResponse:
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
                    arguments=dict(request.attackVariant.toolArguments),
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

    def generate_contract_candidate(
        self,
        request: ContractCandidateRequest,
    ) -> ContractCandidateResponse:
        payload = json.loads(request.inputJson)
        identity = payload.get("identity", {})
        template = dict(payload.get("financialTemplate", {}))
        template["contractId"] = identity.get("contractKey", "loan-review-default")
        template["version"] = identity.get("version", 1)
        return ContractCandidateResponse(
            provider=self.provider,
            model=self.model,
            content=json.dumps(template, ensure_ascii=False, sort_keys=True),
            latencyMs=0,
        )
