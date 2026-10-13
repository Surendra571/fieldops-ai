from app.core.exceptions import InvalidStateTransitionException
from app.schemas.appointment import AppointmentStatus
from app.schemas.work_order import WorkOrderStatus


class WorkOrderStateMachine:
    r"""
    Enforces the Work Order lifecycle state machine:
    DRAFT -> SUBMITTED -> TRIAGED -> SCHEDULED -> IN_PROGRESS -> COMPLETED
                                              \-> CANCELLED
                                              \-> FAILED -> TRIAGED
    """

    ALLOWED_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
        WorkOrderStatus.DRAFT: {WorkOrderStatus.SUBMITTED, WorkOrderStatus.CANCELLED},
        WorkOrderStatus.SUBMITTED: {WorkOrderStatus.TRIAGED, WorkOrderStatus.CANCELLED},
        WorkOrderStatus.TRIAGED: {WorkOrderStatus.SCHEDULED, WorkOrderStatus.CANCELLED},
        WorkOrderStatus.SCHEDULED: {
            WorkOrderStatus.IN_PROGRESS,
            WorkOrderStatus.COMPLETED,
            WorkOrderStatus.CANCELLED,
            WorkOrderStatus.SCHEDULED,  # allow rescheduling update
        },
        WorkOrderStatus.IN_PROGRESS: {
            WorkOrderStatus.COMPLETED,
            WorkOrderStatus.FAILED,
        },
        WorkOrderStatus.FAILED: {
            WorkOrderStatus.TRIAGED,
            WorkOrderStatus.CANCELLED,
        },
        WorkOrderStatus.COMPLETED: {
            WorkOrderStatus.COMPLETED,  # idempotent completion
        },
        WorkOrderStatus.CANCELLED: set(),  # terminal state
    }

    @classmethod
    def validate_transition(
        cls, current_state: WorkOrderStatus, next_state: WorkOrderStatus
    ) -> None:
        if current_state == next_state and current_state != WorkOrderStatus.SCHEDULED:
            return  # No-op transition
        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        if next_state not in allowed:
            raise InvalidStateTransitionException(
                current_state=current_state.value,
                attempted_state=next_state.value,
                entity_type="WorkOrder",
            )


class AppointmentStateMachine:
    r"""
    Enforces the Appointment lifecycle state machine:
    TENTATIVE_HOLD -> CONFIRMED -> EN_ROUTE -> ON_SITE -> COMPLETED
                   \-> CANCELLED
                   \-> RESCHEDULED
    """

    ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
        AppointmentStatus.TENTATIVE_HOLD: {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.CONFIRMED: {
            AppointmentStatus.EN_ROUTE,
            AppointmentStatus.ON_SITE,
            AppointmentStatus.IN_PROGRESS,
            AppointmentStatus.RESCHEDULED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        },
        AppointmentStatus.EN_ROUTE: {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.ON_SITE,
            AppointmentStatus.IN_PROGRESS,
            AppointmentStatus.RESCHEDULED,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.ON_SITE: {
            AppointmentStatus.EN_ROUTE,
            AppointmentStatus.IN_PROGRESS,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.RESCHEDULED,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.IN_PROGRESS: {
            AppointmentStatus.EN_ROUTE,
            AppointmentStatus.ON_SITE,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.RESCHEDULED,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.COMPLETED: set(),  # terminal state
        AppointmentStatus.CANCELLED: set(),  # terminal state
        AppointmentStatus.NO_SHOW: set(),  # terminal state
        AppointmentStatus.RESCHEDULED: set(),  # terminal state
    }

    @classmethod
    def validate_transition(
        cls, current_state: AppointmentStatus, next_state: AppointmentStatus
    ) -> None:
        if current_state == next_state:
            return
        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        if next_state not in allowed:
            raise InvalidStateTransitionException(
                current_state=current_state.value,
                attempted_state=next_state.value,
                entity_type="Appointment",
            )
