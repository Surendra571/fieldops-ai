from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import get_appointment_service, require_roles
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatus,
    AppointmentStatusUpdate,
    AppointmentUpdate,
    AvailableSlotsRequest,
    AvailableSlotsResponse,
    CancelAppointmentRequest,
    ConfirmBookingRequest,
    HoldSlotRequest,
    HoldSlotResponse,
    RescheduleAppointmentRequest,
)
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserRole
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


# --- Slot Discovery & Hold Flow ---


@router.post(
    "/available-slots",
    response_model=AvailableSlotsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.CUSTOMER))],
)
async def get_available_slots(
    req: AvailableSlotsRequest,
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """
    Discover conflict-free appointment slots based on technician shifts,
    buffers, existing bookings, and timezone.
    """
    return await appt_service.get_available_slots(req)


@router.post(
    "/hold",
    response_model=HoldSlotResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def hold_slot(
    req: HoldSlotRequest,
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """
    Place an ephemeral 10-minute hold on a candidate slot using an atomic database reservation.
    """
    return await appt_service.hold_slot(req)


@router.post(
    "/confirm",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def confirm_booking(
    req: ConfirmBookingRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """
    Finalize a held appointment. Requires explicit confirmation (user_confirmed: true).
    Supports Idempotency-Key header.
    """
    if idempotency_key and not req.idempotency_key:
        req.idempotency_key = idempotency_key
    return await appt_service.confirm_booking(req)


# --- Standard CRUD, Cancellation & Rescheduling ---


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def create_appointment(
    appt_in: AppointmentCreate,
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """Directly schedule an appointment (database-enforced conflict prevention)."""
    return await appt_service.create_appointment(appt_in)


@router.get(
    "",
    response_model=PaginatedResponse[AppointmentResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def list_appointments(
    technician_id: str | None = Query(None),
    customer_id: str | None = Query(None),
    status_filter: AppointmentStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """List appointments with filtering and chronological ordering."""
    return await appt_service.list_appointments(
        technician_id=technician_id,
        customer_id=customer_id,
        status=status_filter,
        page=page,
        limit=limit,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def get_appointment(
    appointment_id: str,
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """Retrieve appointment details by ID."""
    return await appt_service.get_appointment(appointment_id)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def cancel_appointment(
    appointment_id: str,
    req: CancelAppointmentRequest,
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """Cancel an appointment and atomically release the technician slot."""
    return await appt_service.cancel_appointment(appointment_id, req)


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN, UserRole.CUSTOMER
            )
        )
    ],
)
async def reschedule_appointment(
    appointment_id: str,
    req: RescheduleAppointmentRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """Reschedule an appointment to a new slot with atomic conflict prevention."""
    if idempotency_key and not req.idempotency_key:
        req.idempotency_key = idempotency_key
    return await appt_service.reschedule_appointment(appointment_id, req)


@router.patch(
    "/{appointment_id}/status",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
@router.post(
    "/{appointment_id}/status",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def transition_appointment_status(
    appointment_id: str,
    status_in: AppointmentStatusUpdate,
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """Transition appointment status through domain state machine with audit logging."""
    return await appt_service.transition_status(appointment_id, status_in)


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER))],
)
async def update_appointment(
    appointment_id: str,
    appt_in: AppointmentUpdate,
    appt_service: AppointmentService = Depends(get_appointment_service),
):
    """Reschedule or update appointment details."""
    return await appt_service.update_appointment(appointment_id, appt_in)
