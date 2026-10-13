from app.core.exceptions import EntityNotFoundException
from app.repositories.technician_repo import TechnicianRepository
from app.schemas.common import PaginatedResponse
from app.schemas.technician import (
    TechnicianCreate,
    TechnicianLocationUpdate,
    TechnicianResponse,
    TechnicianStatus,
    TechnicianUpdate,
)


class TechnicianService:
    def __init__(self, technician_repo: TechnicianRepository):
        self.technician_repo = technician_repo

    async def create_technician(self, tech_in: TechnicianCreate) -> TechnicianResponse:
        doc_data = tech_in.model_dump()
        doc_data["rating"] = 5.0
        doc_data["completed_jobs_count"] = 0
        created = await self.technician_repo.create(doc_data)
        return TechnicianResponse(**created)

    async def get_technician(self, technician_id: str) -> TechnicianResponse:
        doc = await self.technician_repo.get_by_id(technician_id)
        if not doc:
            raise EntityNotFoundException("Technician", technician_id)
        return TechnicianResponse(**doc)

    async def list_technicians(
        self,
        status: TechnicianStatus | None = None,
        skills: list[str] | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedResponse[TechnicianResponse]:
        skip = (page - 1) * limit
        filter_query = {}
        if status:
            filter_query["status"] = status.value
        if skills:
            filter_query["skills"] = {"$all": skills}

        items, total = await self.technician_repo.get_many(filter_query, skip=skip, limit=limit)
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[TechnicianResponse(**item) for item in items],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def update_technician(
        self, technician_id: str, tech_in: TechnicianUpdate
    ) -> TechnicianResponse:
        await self.get_technician(technician_id)
        update_data = tech_in.model_dump(exclude_unset=True)
        updated = await self.technician_repo.update(technician_id, update_data)
        return TechnicianResponse(**updated)  # type: ignore

    async def update_location(
        self, technician_id: str, location_in: TechnicianLocationUpdate
    ) -> TechnicianResponse:
        await self.get_technician(technician_id)
        updated = await self.technician_repo.update_location(
            technician_id=technician_id,
            coordinates=location_in.coordinates,
            heading=location_in.heading,
            speed_kph=location_in.speed_kph,
            battery_level=location_in.battery_level,
        )
        return TechnicianResponse(**updated)  # type: ignore
