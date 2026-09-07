from app.domain.agent import (
    AgentStepRequest,
    AgentStepResponse,
    ContractCandidateRequest,
    ContractCandidateResponse,
)
from app.provider.agent_provider import AgentProvider
from app.provider.provider_factory import build_agent_provider


class StatelessAgentService:
    def __init__(self, provider: AgentProvider):
        self._provider = provider

    def execute_step(self, request: AgentStepRequest) -> AgentStepResponse:
        return self._provider.execute(request)

    def generate_contract_candidate(
        self,
        request: ContractCandidateRequest,
    ) -> ContractCandidateResponse:
        return self._provider.generate_contract_candidate(request)


_service = StatelessAgentService(build_agent_provider())


def get_agent_service() -> StatelessAgentService:
    return _service
