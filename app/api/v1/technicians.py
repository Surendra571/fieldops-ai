from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_technician_service, require_roles
from app.schemas.common import PaginatedResponse
from app.schemas.technician import (
    TechnicianCreate,
    TechnicianLocationUpdate,
    TechnicianResponse,
    TechnicianStatus,
    TechnicianUpdate,
)
from app.schemas.user import UserRole
from app.services.technician_service import TechnicianService

router = APIRouter(prefix="/technicians", tags=["Technicians"])


@router.post(
    "",
    response_model=TechnicianResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER))],
)
async def create_technician(
    tech_in: TechnicianCreate,
    tech_service: TechnicianService = Depends(get_technician_service),
):
    """Register a new field technician in the system."""
    return await tech_service.create_technician(tech_in)


@router.get(
    "",
    response_model=PaginatedResponse[TechnicianResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def list_technicians(
    status_filter: TechnicianStatus | None = Query(None, alias="status"),
    skills: list[str] | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tech_service: TechnicianService = Depends(get_technician_service),
):
    """List technicians filtered by status or required skills."""
    return await tech_service.list_technicians(
        status=status_filter, skills=skills, page=page, limit=limit
    )


@router.get(
    "/{technician_id}",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def get_technician(
    technician_id: str,
    tech_service: TechnicianService = Depends(get_technician_service),
):
    """Retrieve technician details by ID."""
    return await tech_service.get_technician(technician_id)


@router.patch(
    "/{technician_id}",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def update_technician(
    technician_id: str,
    tech_in: TechnicianUpdate,
    tech_service: TechnicianService = Depends(get_technician_service),
):
    """Update technician profile, certifications, or working shifts."""
    return await tech_service.update_technician(technician_id, tech_in)


@router.post(
    "/{technician_id}/location",
    response_model=TechnicianResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def update_technician_location(
    technician_id: str,
    location_in: TechnicianLocationUpdate,
    tech_service: TechnicianService = Depends(get_technician_service),
):
    """Update technician live GPS coordinates from mobile application."""
    return await tech_service.update_location(technician_id, location_in)
