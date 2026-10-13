from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_customer_service, require_roles
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.schemas.user import UserRole
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.CUSTOMER))],
)
async def create_customer(
    customer_in: CustomerCreate,
    customer_service: CustomerService = Depends(get_customer_service),
):
    """Create a new customer profile with service address."""
    return await customer_service.create_customer(customer_in)


@router.get(
    "",
    response_model=PaginatedResponse[CustomerResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def list_customers(
    search: str | None = Query(None, description="Search by name, phone, or email"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    customer_service: CustomerService = Depends(get_customer_service),
):
    """List and search customer profiles."""
    return await customer_service.list_customers(search=search, page=page, limit=limit)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def get_customer(
    customer_id: str,
    customer_service: CustomerService = Depends(get_customer_service),
):
    """Retrieve customer details by ID."""
    return await customer_service.get_customer(customer_id)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.CUSTOMER))],
)
async def update_customer(
    customer_id: str,
    customer_in: CustomerUpdate,
    customer_service: CustomerService = Depends(get_customer_service),
):
    """Update customer profile information."""
    return await customer_service.update_customer(customer_id, customer_in)
