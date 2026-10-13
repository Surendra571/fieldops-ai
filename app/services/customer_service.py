from app.core.exceptions import ConflictException, EntityNotFoundException
from app.repositories.customer_repo import CustomerRepository
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate


class CustomerService:
    def __init__(self, customer_repo: CustomerRepository):
        self.customer_repo = customer_repo

    async def create_customer(self, customer_in: CustomerCreate) -> CustomerResponse:
        existing = await self.customer_repo.get_by_phone(customer_in.phone)
        if existing:
            raise ConflictException(
                f"Customer with phone number '{customer_in.phone}' already exists."
            )

        doc_data = customer_in.model_dump()
        doc_data["total_completed_jobs"] = 0
        doc_data["no_show_history_count"] = 0

        created = await self.customer_repo.create(doc_data)
        return CustomerResponse(**created)

    async def get_customer(self, customer_id: str) -> CustomerResponse:
        doc = await self.customer_repo.get_by_id(customer_id)
        if not doc:
            raise EntityNotFoundException("Customer", customer_id)
        return CustomerResponse(**doc)

    async def list_customers(
        self, search: str | None = None, page: int = 1, limit: int = 20
    ) -> PaginatedResponse[CustomerResponse]:
        skip = (page - 1) * limit
        if search:
            items, total = await self.customer_repo.search(search, skip=skip, limit=limit)
        else:
            items, total = await self.customer_repo.get_many(skip=skip, limit=limit)

        total_pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[CustomerResponse(**item) for item in items],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def update_customer(
        self, customer_id: str, customer_in: CustomerUpdate
    ) -> CustomerResponse:
        await self.get_customer(customer_id)  # verifies existence
        update_data = customer_in.model_dump(exclude_unset=True)
        updated = await self.customer_repo.update(customer_id, update_data)
        return CustomerResponse(**updated)  # type: ignore
