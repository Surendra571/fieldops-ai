from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import get_work_order_service, require_roles
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserRole
from app.schemas.work_order import (
    WorkOrderCategory,
    WorkOrderCreate,
    WorkOrderPriority,
    WorkOrderResponse,
    WorkOrderStatus,
    WorkOrderStatusUpdate,
    WorkOrderUpdate,
)
from app.services.work_order_service import WorkOrderService

router = APIRouter(prefix="/work-orders", tags=["Work Orders"])


@router.post(
    "",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def create_work_order(
    wo_in: WorkOrderCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    wo_service: WorkOrderService = Depends(get_work_order_service),
):
    """Create a new service work order. Supports Idempotency-Key header."""
    if idempotency_key and not wo_in.idempotency_key:
        wo_in.idempotency_key = idempotency_key
    return await wo_service.create_work_order(wo_in)


@router.get(
    "",
    response_model=PaginatedResponse[WorkOrderResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def list_work_orders(
    status_filter: WorkOrderStatus | None = Query(None, alias="status"),
    priority: WorkOrderPriority | None = Query(None),
    category: WorkOrderCategory | None = Query(None),
    customer_id: str | None = Query(None),
    search: str | None = Query(
        None, description="Search by description, symptoms, address, or number"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    wo_service: WorkOrderService = Depends(get_work_order_service),
):
    """List work orders with filtering, search, and pagination."""
    return await wo_service.list_work_orders(
        status=status_filter,
        priority=priority,
        category=category,
        customer_id=customer_id,
        search=search,
        page=page,
        limit=limit,
    )


@router.get(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def get_work_order(
    work_order_id: str,
    wo_service: WorkOrderService = Depends(get_work_order_service),
):
    """Retrieve detailed work order information by ID."""
    return await wo_service.get_work_order(work_order_id)


@router.patch(
    "/{work_order_id}/status",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
@router.post(
    "/{work_order_id}/status",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def transition_work_order_status(
    work_order_id: str,
    status_in: WorkOrderStatusUpdate,
    wo_service: WorkOrderService = Depends(get_work_order_service),
):
    """Transition work order through domain state machine with audit logging."""
    return await wo_service.transition_status(work_order_id, status_in)


@router.patch(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER))],
)
async def update_work_order(
    work_order_id: str,
    wo_in: WorkOrderUpdate,
    wo_service: WorkOrderService = Depends(get_work_order_service),
):
    """Update work order fields."""
    return await wo_service.update_work_order(work_order_id, wo_in)
