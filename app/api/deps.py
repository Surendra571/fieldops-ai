from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agent.tools import AgentToolRegistry
from app.core.database import get_database
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import decode_access_token
from app.integrations.llm import get_llm_adapter
from app.integrations.maps.mock_maps import MockMapsAdapter
from app.integrations.maps.protocol import MapsProviderProtocol
from app.integrations.voice import get_stt_adapter, get_tts_adapter
from app.ml.service import MLPredictionService, get_ml_service
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.idempotency_repo import IdempotencyRepository
from app.repositories.outbox_repo import OutboxRepository
from app.repositories.technician_repo import TechnicianRepository
from app.repositories.user_repo import UserRepository
from app.repositories.work_order_repo import WorkOrderRepository
from app.schemas.user import UserResponse, UserRole
from app.services.agent_service import AgentService
from app.services.appointment_service import AppointmentService
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.dispatch_service import DispatchService
from app.services.technician_service import TechnicianService
from app.services.work_order_service import WorkOrderService

security = HTTPBearer(auto_error=False)


# --- Repository Dependencies ---
def get_user_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> UserRepository:
    return UserRepository(db)


def get_customer_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> CustomerRepository:
    return CustomerRepository(db)


def get_technician_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> TechnicianRepository:
    return TechnicianRepository(db)


def get_work_order_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> WorkOrderRepository:
    return WorkOrderRepository(db)


def get_appointment_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> AppointmentRepository:
    return AppointmentRepository(db)


def get_audit_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> AuditRepository:
    return AuditRepository(db)


def get_idempotency_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> IdempotencyRepository:
    return IdempotencyRepository(db)


def get_outbox_repo(db: AsyncIOMotorDatabase = Depends(get_database)) -> OutboxRepository:
    return OutboxRepository(db)


def get_conversation_repo(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ConversationRepository:
    return ConversationRepository(db)


# --- Integration Adapters ---
def get_maps_adapter() -> MapsProviderProtocol:
    return MockMapsAdapter()


# --- Service Dependencies ---
def get_auth_service(user_repo: UserRepository = Depends(get_user_repo)) -> AuthService:
    return AuthService(user_repo)


def get_customer_service(
    customer_repo: CustomerRepository = Depends(get_customer_repo),
) -> CustomerService:
    return CustomerService(customer_repo)


def get_technician_service(
    technician_repo: TechnicianRepository = Depends(get_technician_repo),
) -> TechnicianService:
    return TechnicianService(technician_repo)


def get_work_order_service(
    work_order_repo: WorkOrderRepository = Depends(get_work_order_repo),
    customer_repo: CustomerRepository = Depends(get_customer_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    idempotency_repo: IdempotencyRepository = Depends(get_idempotency_repo),
    outbox_repo: OutboxRepository = Depends(get_outbox_repo),
) -> WorkOrderService:
    return WorkOrderService(
        work_order_repo, customer_repo, audit_repo, idempotency_repo, outbox_repo
    )


def get_appointment_service(
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
    technician_repo: TechnicianRepository = Depends(get_technician_repo),
    work_order_repo: WorkOrderRepository = Depends(get_work_order_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    idempotency_repo: IdempotencyRepository = Depends(get_idempotency_repo),
    outbox_repo: OutboxRepository = Depends(get_outbox_repo),
) -> AppointmentService:
    return AppointmentService(
        appointment_repo,
        technician_repo,
        work_order_repo,
        audit_repo,
        idempotency_repo,
        outbox_repo,
    )


def get_dispatch_service(
    technician_repo: TechnicianRepository = Depends(get_technician_repo),
    work_order_repo: WorkOrderRepository = Depends(get_work_order_repo),
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
    maps_adapter: MapsProviderProtocol = Depends(get_maps_adapter),
    ml_service: MLPredictionService = Depends(get_ml_service),
) -> DispatchService:
    return DispatchService(
        technician_repo, work_order_repo, appointment_repo, maps_adapter, ml_service
    )


def get_agent_tool_registry(
    customer_service: CustomerService = Depends(get_customer_service),
    work_order_service: WorkOrderService = Depends(get_work_order_service),
    appointment_service: AppointmentService = Depends(get_appointment_service),
    dispatch_service: DispatchService = Depends(get_dispatch_service),
) -> AgentToolRegistry:
    return AgentToolRegistry(
        customer_service=customer_service,
        work_order_service=work_order_service,
        appointment_service=appointment_service,
        dispatch_service=dispatch_service,
    )


def get_agent_service(
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    tool_registry: AgentToolRegistry = Depends(get_agent_tool_registry),
) -> AgentService:
    return AgentService(
        conversation_repo=conversation_repo,
        tool_registry=tool_registry,
        llm_adapter=get_llm_adapter(),
        stt_adapter=get_stt_adapter(),
        tts_adapter=get_tts_adapter(),
    )


# --- Authentication & RBAC Dependencies ---
async def get_current_user(
    auth_header: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    if not auth_header:
        raise AuthenticationException("Authorization header is required.")

    token = auth_header.credentials
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationException("Token payload missing subject.")
    except Exception as e:
        raise AuthenticationException(f"Invalid or expired token: {str(e)}") from e

    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise AuthenticationException("Authenticated user no longer exists.")
    if not user.is_active:
        raise AuthenticationException("User account is inactive.")

    return user


async def get_current_user_optional(
    auth_header: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse | None:
    """Returns authenticated user if a valid bearer token is provided; otherwise returns None without error."""
    if not auth_header:
        return None
    token = auth_header.credentials
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = await auth_service.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


def require_roles(*allowed_roles: UserRole) -> Callable:
    """Dependency factory checking if current user holds one of the required roles."""

    async def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in allowed_roles:
            raise AuthorizationException(
                f"Role '{current_user.role.value}' is not authorized. Required: {[r.value for r in allowed_roles]}."
            )
        return current_user

    return role_checker


# Compatibility aliases
get_db = get_database
get_current_active_user = get_current_user
