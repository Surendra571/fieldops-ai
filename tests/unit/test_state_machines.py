import pytest

from app.core.exceptions import InvalidStateTransitionException
from app.domain.state_machine import AppointmentStateMachine, WorkOrderStateMachine
from app.schemas.appointment import AppointmentStatus
from app.schemas.work_order import WorkOrderStatus


def test_work_order_valid_transitions():
    # Valid forward flow
    WorkOrderStateMachine.validate_transition(WorkOrderStatus.DRAFT, WorkOrderStatus.SUBMITTED)
    WorkOrderStateMachine.validate_transition(WorkOrderStatus.SUBMITTED, WorkOrderStatus.TRIAGED)
    WorkOrderStateMachine.validate_transition(WorkOrderStatus.TRIAGED, WorkOrderStatus.SCHEDULED)
    WorkOrderStateMachine.validate_transition(
        WorkOrderStatus.SCHEDULED, WorkOrderStatus.IN_PROGRESS
    )
    WorkOrderStateMachine.validate_transition(
        WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED
    )

    # Valid failure recovery
    WorkOrderStateMachine.validate_transition(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.FAILED)
    WorkOrderStateMachine.validate_transition(WorkOrderStatus.FAILED, WorkOrderStatus.TRIAGED)


def test_work_order_invalid_transitions():
    # Terminal state transitions
    with pytest.raises(InvalidStateTransitionException) as exc_info:
        WorkOrderStateMachine.validate_transition(
            WorkOrderStatus.COMPLETED, WorkOrderStatus.IN_PROGRESS
        )
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"

    with pytest.raises(InvalidStateTransitionException):
        WorkOrderStateMachine.validate_transition(
            WorkOrderStatus.CANCELLED, WorkOrderStatus.SUBMITTED
        )

    # Illegal jump
    with pytest.raises(InvalidStateTransitionException):
        WorkOrderStateMachine.validate_transition(
            WorkOrderStatus.DRAFT, WorkOrderStatus.IN_PROGRESS
        )


def test_appointment_valid_transitions():
    AppointmentStateMachine.validate_transition(
        AppointmentStatus.TENTATIVE_HOLD, AppointmentStatus.CONFIRMED
    )
    AppointmentStateMachine.validate_transition(
        AppointmentStatus.CONFIRMED, AppointmentStatus.EN_ROUTE
    )
    AppointmentStateMachine.validate_transition(
        AppointmentStatus.EN_ROUTE, AppointmentStatus.ON_SITE
    )
    AppointmentStateMachine.validate_transition(
        AppointmentStatus.ON_SITE, AppointmentStatus.COMPLETED
    )


def test_appointment_invalid_transitions():
    with pytest.raises(InvalidStateTransitionException):
        AppointmentStateMachine.validate_transition(
            AppointmentStatus.COMPLETED, AppointmentStatus.EN_ROUTE
        )

    with pytest.raises(InvalidStateTransitionException):
        AppointmentStateMachine.validate_transition(
            AppointmentStatus.TENTATIVE_HOLD, AppointmentStatus.ON_SITE
        )
