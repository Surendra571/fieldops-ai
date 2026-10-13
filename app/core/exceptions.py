import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class FieldOpsException(Exception):
    """Base class for all domain exceptions in FieldOps AI."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class EntityNotFoundException(FieldOpsException):
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' was not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"entity": entity_name, "id": entity_id},
        )


class ConflictException(FieldOpsException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class SlotConflictException(ConflictException):
    def __init__(self, technician_id: str, scheduled_start: str):
        super().__init__(
            message="The requested technician time slot conflicts with an existing booking or is unavailable.",
            details={"technician_id": technician_id, "scheduled_start": scheduled_start},
        )


class ConcurrencyException(ConflictException):
    def __init__(self, message: str = "The resource was modified concurrently by another process."):
        super().__init__(
            message=message,
            details={"reason": "CONCURRENT_UPDATE_CONFLICT"},
        )


class IdempotencyPayloadMismatchException(FieldOpsException):
    def __init__(self, key: str):
        super().__init__(
            message=f"Idempotency-Key '{key}' was already used with a different request payload.",
            code="IDEMPOTENCY_PAYLOAD_MISMATCH",
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details={"idempotency_key": key},
        )


class IdempotencyConflictException(FieldOpsException):
    def __init__(self, key: str):
        super().__init__(
            message=f"A request with Idempotency-Key '{key}' is currently in progress. Please retry shortly.",
            code="IDEMPOTENCY_IN_PROGRESS",
            status_code=status.HTTP_409_CONFLICT,
            details={"idempotency_key": key},
        )


class InvalidStateTransitionException(FieldOpsException):
    def __init__(self, current_state: str, attempted_state: str, entity_type: str = "Entity"):
        super().__init__(
            message=f"Cannot transition {entity_type} from '{current_state}' to '{attempted_state}'.",
            code="INVALID_STATE_TRANSITION",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "entity_type": entity_type,
                "current_state": current_state,
                "attempted_state": attempted_state,
            },
        )


class AuthenticationException(FieldOpsException):
    def __init__(self, message: str = "Could not validate authentication credentials."):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationException(FieldOpsException):
    def __init__(self, message: str = "Insufficient permissions to perform this operation."):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationException(FieldOpsException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FieldOpsException)
    async def fieldops_exception_handler(request: Request, exc: FieldOpsException):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        formatted_errors = []
        for err in exc.errors():
            formatted_errors.append(
                {
                    "loc": [str(loc) for loc in err.get("loc", [])],
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "Input validation failed on request body or parameters.",
                    "details": {"errors": formatted_errors},
                    "request_id": request_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            },
        )
