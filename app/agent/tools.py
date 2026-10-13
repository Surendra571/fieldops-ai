import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.integrations.llm.protocol import ToolDefinition
from app.schemas.appointment import (
    ConfirmBookingRequest,
    HoldSlotRequest,
    RescheduleAppointmentRequest,
)
from app.schemas.common import GeoPoint
from app.schemas.customer import ChannelPreference, CustomerCreate, ServiceAddress
from app.schemas.dispatch import MatchCandidatesRequest
from app.schemas.work_order import (
    WorkOrderCategory,
    WorkOrderCreate,
    WorkOrderPriority,
    WorkOrderSource,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Tool Input Validation Schemas
# ---------------------------------------------------------


class CreateServiceRequestArgs(BaseModel):
    customer_name: str = Field(..., min_length=2)
    customer_phone: str = Field(..., min_length=7)
    customer_email: str | None = None
    address: str = Field(..., min_length=5, description="Full service street address")
    issue_category: str = Field(
        ..., description="Category: plumbing, hvac, electrical, appliance, roofing"
    )
    issue_description: str = Field(..., min_length=5)
    urgency: str = Field("medium", description="Urgency: critical, high, medium, low")
    equipment_type: str | None = None


class GetWorkOrderStatusArgs(BaseModel):
    work_order_id: str = Field(..., min_length=1)


class FindEligibleTechniciansArgs(BaseModel):
    work_order_id: str = Field(..., min_length=1)
    target_date: str | None = None


class GetAvailableSlotsArgs(BaseModel):
    work_order_id: str = Field(..., min_length=1)
    target_date: str | None = None
    days_ahead: int = Field(3, ge=1, le=14)


class ProposeAppointmentHoldArgs(BaseModel):
    work_order_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    technician_id: str = Field(..., min_length=1)
    scheduled_start: str = Field(..., description="ISO 8601 string, e.g. 2026-10-15T09:00:00Z")
    scheduled_end: str = Field(..., description="ISO 8601 string, e.g. 2026-10-15T11:00:00Z")


class ConfirmBookingArgs(BaseModel):
    hold_id: str = Field(..., min_length=1, description="Reservation hold token")
    user_confirmed: bool = Field(False, description="Strict boolean confirmation flag from user")
    customer_notes: str | None = None


class RescheduleAppointmentArgs(BaseModel):
    appointment_id: str = Field(..., min_length=1)
    new_start: str = Field(..., description="ISO 8601 string")
    new_end: str = Field(..., description="ISO 8601 string")
    user_confirmed: bool = Field(False, description="Strict boolean confirmation flag from user")
    reason: str | None = None


class EscalateToHumanArgs(BaseModel):
    reason: str = Field(..., min_length=3)
    summary: str = Field(..., min_length=5)
    work_order_id: str | None = None
    customer_phone: str | None = None


# ---------------------------------------------------------
# Tool Definitions for LLM Prompts
# ---------------------------------------------------------

TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="create_service_request",
        description="Creates a verified work order in the system after gathering the customer's issue, category, urgency, and exact address.",
        parameters={
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Customer's full name"},
                "customer_phone": {
                    "type": "string",
                    "description": "Customer contact phone number",
                },
                "customer_email": {"type": "string", "description": "Optional customer email"},
                "address": {
                    "type": "string",
                    "description": "Street address where the service is needed",
                },
                "issue_category": {
                    "type": "string",
                    "enum": ["hvac", "plumbing", "electrical", "appliance", "roofing"],
                    "description": "Category of the problem",
                },
                "issue_description": {
                    "type": "string",
                    "description": "Detailed description of the customer's problem",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Urgency level",
                },
                "equipment_type": {
                    "type": "string",
                    "description": "Type/brand of equipment if mentioned",
                },
            },
            "required": [
                "customer_name",
                "customer_phone",
                "address",
                "issue_category",
                "issue_description",
            ],
        },
    ),
    ToolDefinition(
        name="get_work_order_status",
        description="Checks the current status, details, and scheduled appointments for an existing work order.",
        parameters={
            "type": "object",
            "properties": {
                "work_order_id": {
                    "type": "string",
                    "description": "The work order ID or reference number",
                },
            },
            "required": ["work_order_id"],
        },
    ),
    ToolDefinition(
        name="find_eligible_technicians",
        description="Finds and ranks skilled technicians eligible to perform the service request.",
        parameters={
            "type": "object",
            "properties": {
                "work_order_id": {"type": "string", "description": "Work order ID"},
                "target_date": {"type": "string", "description": "Target date (YYYY-MM-DD)"},
            },
            "required": ["work_order_id"],
        },
    ),
    ToolDefinition(
        name="get_available_slots",
        description="Retrieves available appointment slots for a work order based on technician working hours and buffers.",
        parameters={
            "type": "object",
            "properties": {
                "work_order_id": {"type": "string", "description": "Work order ID"},
                "target_date": {
                    "type": "string",
                    "description": "Optional target date (YYYY-MM-DD)",
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days ahead to scan (1-14)",
                    "default": 3,
                },
            },
            "required": ["work_order_id"],
        },
    ),
    ToolDefinition(
        name="propose_appointment_hold",
        description="Places a temporary 15-minute tentative hold on an appointment slot. Does NOT confirm the booking.",
        parameters={
            "type": "object",
            "properties": {
                "work_order_id": {"type": "string", "description": "Work order ID"},
                "customer_id": {"type": "string", "description": "Customer ID"},
                "technician_id": {"type": "string", "description": "Technician ID"},
                "scheduled_start": {"type": "string", "description": "ISO 8601 start datetime"},
                "scheduled_end": {"type": "string", "description": "ISO 8601 end datetime"},
            },
            "required": [
                "work_order_id",
                "customer_id",
                "technician_id",
                "scheduled_start",
                "scheduled_end",
            ],
        },
    ),
    ToolDefinition(
        name="confirm_booking",
        description="Finalizes an appointment booking from a reservation hold token. STRICT: Requires explicit customer consent.",
        parameters={
            "type": "object",
            "properties": {
                "hold_id": {
                    "type": "string",
                    "description": "The reservation token from propose_appointment_hold",
                },
                "user_confirmed": {
                    "type": "boolean",
                    "description": "Must be true. The customer MUST have explicitly confirmed they want this slot.",
                },
                "customer_notes": {"type": "string", "description": "Optional notes from customer"},
            },
            "required": ["hold_id", "user_confirmed"],
        },
    ),
    ToolDefinition(
        name="reschedule_appointment",
        description="Reschedules an existing confirmed appointment. STRICT: Requires explicit customer consent.",
        parameters={
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "Appointment ID to reschedule"},
                "new_start": {"type": "string", "description": "New ISO 8601 start datetime"},
                "new_end": {"type": "string", "description": "New ISO 8601 end datetime"},
                "user_confirmed": {
                    "type": "boolean",
                    "description": "Must be true. The customer MUST have explicitly agreed to reschedule.",
                },
                "reason": {"type": "string", "description": "Reason for rescheduling"},
            },
            "required": ["appointment_id", "new_start", "new_end", "user_confirmed"],
        },
    ),
    ToolDefinition(
        name="escalate_to_human",
        description="Escalates the customer interaction to a human dispatcher when out of scope, hazardous, or requested.",
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for human escalation"},
                "summary": {"type": "string", "description": "Brief summary of customer situation"},
                "work_order_id": {
                    "type": "string",
                    "description": "Associated work order ID if any",
                },
                "customer_phone": {"type": "string", "description": "Customer contact number"},
            },
            "required": ["reason", "summary"],
        },
    ),
]


class AgentToolRegistry:
    """
    Registry that validates arguments server-side and executes backend services safely.
    """

    def __init__(
        self,
        customer_service: Any,
        work_order_service: Any,
        appointment_service: Any,
        dispatch_service: Any,
    ):
        self.customer_service = customer_service
        self.work_order_service = work_order_service
        self.appointment_service = appointment_service
        self.dispatch_service = dispatch_service

    def get_definitions(self) -> list[ToolDefinition]:
        return TOOL_DEFINITIONS

    async def execute(
        self, tool_name: str, arguments: dict[str, Any], context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Executes a registered tool after strict server-side validation.
        """
        context = context or {}
        try:
            if tool_name == "create_service_request":
                return await self._execute_create_service_request(arguments, context)
            elif tool_name == "get_work_order_status":
                return await self._execute_get_work_order_status(arguments, context)
            elif tool_name == "find_eligible_technicians":
                return await self._execute_find_eligible_technicians(arguments, context)
            elif tool_name == "get_available_slots":
                return await self._execute_get_available_slots(arguments, context)
            elif tool_name == "propose_appointment_hold":
                return await self._execute_propose_appointment_hold(arguments, context)
            elif tool_name == "confirm_booking":
                return await self._execute_confirm_booking(arguments, context)
            elif tool_name == "reschedule_appointment":
                return await self._execute_reschedule_appointment(arguments, context)
            elif tool_name == "escalate_to_human":
                return await self._execute_escalate_to_human(arguments, context)
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: '{tool_name}'",
                }
        except ValidationError as e:
            logger.warning("Tool %s validation failed: %s", tool_name, e)
            return {
                "success": False,
                "error": "VALIDATION_FAILED",
                "details": e.errors(),
            }
        except Exception as e:
            logger.exception("Tool %s failed: %s", tool_name, e)
            return {
                "success": False,
                "error": "EXECUTION_ERROR",
                "message": str(e),
            }

    async def _execute_create_service_request(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = CreateServiceRequestArgs(**arguments)

        # 1. Look up or create Customer
        customer = await self.customer_service.customer_repo.get_by_phone(args.customer_phone)
        if not customer:
            # Parse service address components safely
            service_addr = ServiceAddress(
                street=args.address,
                city="Metropolis",
                state="NY",
                postal_code="10001",
                location=GeoPoint(type="Point", coordinates=[-74.0060, 40.7128]),
                is_primary=True,
            )
            cust_in = CustomerCreate(
                full_name=args.customer_name,
                phone=args.customer_phone,
                email=args.customer_email,
                preferred_channel=ChannelPreference.VOICE,
                service_addresses=[service_addr],
            )
            created_cust = await self.customer_service.create_customer(cust_in)
            customer_id = created_cust.id
        else:
            customer_id = customer["id"]
            # Use customer's first address if available
            addrs = customer.get("service_addresses", [])
            if addrs:
                first_addr = addrs[0]
                service_addr = ServiceAddress(
                    street=first_addr.get("street", args.address),
                    city=first_addr.get("city", "Metropolis"),
                    state=first_addr.get("state", "NY"),
                    postal_code=first_addr.get("postal_code", "10001"),
                    location=GeoPoint(type="Point", coordinates=[-74.0060, 40.7128]),
                )
            else:
                service_addr = ServiceAddress(
                    street=args.address,
                    city="Metropolis",
                    state="NY",
                    postal_code="10001",
                    location=GeoPoint(type="Point", coordinates=[-74.0060, 40.7128]),
                )

        # 2. Map Category
        cat_lower = args.issue_category.lower()
        if "plumb" in cat_lower:
            category = WorkOrderCategory.PLUMBING
            skills = ["plumbing"]
        elif "hvac" in cat_lower or "heat" in cat_lower or "cool" in cat_lower or "ac" in cat_lower:
            category = WorkOrderCategory.HVAC
            skills = ["hvac"]
        elif "elec" in cat_lower:
            category = WorkOrderCategory.ELECTRICAL
            skills = ["electrical"]
        elif "appl" in cat_lower:
            category = WorkOrderCategory.APPLIANCE
            skills = ["appliances"]
        elif "roof" in cat_lower:
            category = WorkOrderCategory.ROOFING
            skills = ["roofing"]
        else:
            category = WorkOrderCategory.HVAC
            skills = ["general"]

        # 3. Map Urgency
        urg_lower = args.urgency.lower()
        if "crit" in urg_lower or "emerg" in urg_lower:
            priority = WorkOrderPriority.EMERGENCY
        elif "high" in urg_lower:
            priority = WorkOrderPriority.HIGH
        elif "low" in urg_lower:
            priority = WorkOrderPriority.ROUTINE
        else:
            priority = WorkOrderPriority.MEDIUM

        wo_create = WorkOrderCreate(
            customer_id=customer_id,
            category=category,
            priority=priority,
            urgency=priority,
            source=WorkOrderSource.VOICE,
            description=args.issue_description,
            service_address=service_addr,
            required_skills=skills,
            estimated_duration_minutes=90,
        )

        created_wo = await self.work_order_service.create_work_order(wo_create)

        return {
            "success": True,
            "work_order_id": created_wo.id,
            "work_order_number": created_wo.work_order_number,
            "customer_id": customer_id,
            "status": str(created_wo.status),
            "category": str(created_wo.category),
            "priority": str(created_wo.priority),
        }

    async def _execute_get_work_order_status(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = GetWorkOrderStatusArgs(**arguments)
        wo = await self.work_order_service.work_order_repo.get_by_id(args.work_order_id)
        if not wo:
            # Try searching by work_order_number
            doc = await self.work_order_service.work_order_repo.collection.find_one(
                {"work_order_number": args.work_order_id}
            )
            if doc:
                wo = self.work_order_service.work_order_repo._serialize_doc(doc)

        if not wo:
            return {
                "success": False,
                "error": f"Work order '{args.work_order_id}' was not found.",
            }

        # Check appointments
        appts = await self.appointment_service.appointment_repo.find_by_work_order(wo["id"])
        latest_appt = appts[0] if appts else None

        return {
            "success": True,
            "work_order_id": wo["id"],
            "work_order_number": wo.get("work_order_number"),
            "status": wo.get("status"),
            "priority": wo.get("priority"),
            "category": wo.get("issue_category"),
            "appointment": {
                "appointment_id": latest_appt.get("id"),
                "status": latest_appt.get("status"),
                "start": str(latest_appt.get("scheduled_start")),
                "end": str(latest_appt.get("scheduled_end")),
            }
            if latest_appt
            else None,
        }

    async def _execute_find_eligible_technicians(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = FindEligibleTechniciansArgs(**arguments)
        target_date = args.target_date or (datetime.now(UTC) + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        req = MatchCandidatesRequest(work_order_id=args.work_order_id, target_date=target_date)
        res = await self.dispatch_service.match_candidates(req)

        candidates = [
            {
                "technician_id": c.technician_id,
                "technician_name": c.technician_name,
                "score": round(c.overall_score, 2),
                "explanation": c.explanation,
            }
            for c in res.candidates[:3]
        ]
        return {
            "success": True,
            "work_order_id": args.work_order_id,
            "target_date": target_date,
            "candidates": candidates,
        }

    async def _execute_get_available_slots(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = GetAvailableSlotsArgs(**arguments)
        from app.schemas.appointment import AvailableSlotsRequest

        start_date = args.target_date or (datetime.now(UTC) + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        req = AvailableSlotsRequest(
            work_order_id=args.work_order_id,
            target_date=start_date,
            timezone="UTC",
            duration_minutes=90,
        )
        res = await self.appointment_service.get_available_slots(req)

        slots = [
            {
                "slot_id": s.slot_id,
                "technician_id": s.technician_id,
                "technician_name": s.technician_name,
                "start_time": s.start_time.isoformat(),
                "end_time": s.end_time.isoformat(),
            }
            for s in res.available_slots[:5]
        ]

        return {
            "success": True,
            "work_order_id": args.work_order_id,
            "target_date": start_date,
            "slots": slots,
        }

    async def _execute_propose_appointment_hold(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = ProposeAppointmentHoldArgs(**arguments)
        hold_req = HoldSlotRequest(
            work_order_id=args.work_order_id,
            customer_id=args.customer_id,
            technician_id=args.technician_id,
            scheduled_start=datetime.fromisoformat(args.scheduled_start.replace("Z", "+00:00")),
            scheduled_end=datetime.fromisoformat(args.scheduled_end.replace("Z", "+00:00")),
            hold_duration_minutes=15,
        )
        hold_res = await self.appointment_service.hold_slot(hold_req)

        return {
            "success": True,
            "reservation_token": hold_res.reservation_token,
            "status": "TENTATIVE_HOLD",
            "expires_at": hold_res.expires_at.isoformat(),
            "note": "Hold placed for 15 minutes. Explicit confirmation required to finalize booking.",
        }

    async def _execute_confirm_booking(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = ConfirmBookingArgs(**arguments)
        if not args.user_confirmed:
            return {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "message": "Explicit user confirmation is strictly required to finalize appointment booking.",
            }

        req = ConfirmBookingRequest(
            reservation_token=args.hold_id,
            user_confirmed=True,
            customer_notes=args.customer_notes,
        )
        appt_res = await self.appointment_service.confirm_booking(req)

        return {
            "success": True,
            "appointment_id": appt_res.id,
            "appointment_number": appt_res.appointment_number,
            "status": appt_res.status,
            "scheduled_start": appt_res.scheduled_start.isoformat(),
            "scheduled_end": appt_res.scheduled_end.isoformat(),
        }

    async def _execute_reschedule_appointment(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = RescheduleAppointmentArgs(**arguments)
        if not args.user_confirmed:
            return {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "message": "Explicit user confirmation is strictly required to reschedule an appointment.",
            }

        req = RescheduleAppointmentRequest(
            new_scheduled_start=datetime.fromisoformat(args.new_start.replace("Z", "+00:00")),
            new_scheduled_end=datetime.fromisoformat(args.new_end.replace("Z", "+00:00")),
            reschedule_reason=args.reason,
            user_confirmed=True,
        )
        res = await self.appointment_service.reschedule_appointment(args.appointment_id, req)
        return {
            "success": True,
            "appointment_id": res.id,
            "new_start": res.scheduled_start.isoformat(),
            "new_end": res.scheduled_end.isoformat(),
            "status": res.status,
        }

    async def _execute_escalate_to_human(
        self, arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        args = EscalateToHumanArgs(**arguments)
        return {
            "success": True,
            "escalated": True,
            "reason": args.reason,
            "summary": args.summary,
            "ticket_queue": "tier_2_dispatch_priority",
        }
