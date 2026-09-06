from app.domain.agent import AgentStepRequest, AgentStepResponse
from app.provider.agent_provider import AgentProvider, DeterministicAgentProvider


class StatelessAgentService:
    def __init__(self, provider: AgentProvider):
        self._provider = provider

    def execute_step(self, request: AgentStepRequest) -> AgentStepResponse:
        return self._provider.execute(request)


_service = StatelessAgentService(DeterministicAgentProvider())


def get_agent_service() -> StatelessAgentService:
    return _service
