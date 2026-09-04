from fastapi import APIRouter, Depends

from app.domain.agent import AgentStepRequest, AgentStepResponse
from app.service.agent_service import StatelessAgentService, get_agent_service

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post("/steps", response_model=AgentStepResponse)
def execute_step(
    request: AgentStepRequest,
    service: StatelessAgentService = Depends(get_agent_service),
) -> AgentStepResponse:
    return service.execute_step(request)
