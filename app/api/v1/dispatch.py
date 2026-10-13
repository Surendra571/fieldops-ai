from fastapi import APIRouter, Depends, status

from app.api.deps import get_dispatch_service, require_roles
from app.schemas.dispatch import MatchCandidatesRequest, MatchCandidatesResponse
from app.schemas.user import UserRole
from app.services.dispatch_service import DispatchService

router = APIRouter(prefix="/dispatch", tags=["Dispatch & Candidate Matching"])


@router.post(
    "/match-candidates",
    response_model=MatchCandidatesResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def match_candidates(
    request: MatchCandidatesRequest,
    dispatch_service: DispatchService = Depends(get_dispatch_service),
):
    """
    Match, evaluate hard constraints, and rank eligible technicians for a work order.
    Returns composite score and transparent breakdown explanation.
    """
    return await dispatch_service.match_candidates(request)
