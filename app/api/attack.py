from fastapi import APIRouter, Depends

from app.domain.agent import AttackMutationRequest, AttackMutationResponse
from app.service.agent_service import StatelessAgentService, get_agent_service

router = APIRouter(prefix="/v1/attacks", tags=["attacks"])


@router.post("/mutations", response_model=AttackMutationResponse)
def generate_mutations(
    request: AttackMutationRequest,
    service: StatelessAgentService = Depends(get_agent_service),
) -> AttackMutationResponse:
    return service.generate_mutations(request)
