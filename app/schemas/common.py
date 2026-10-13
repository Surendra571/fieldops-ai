from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: list[float] = Field(
        ...,
        description="Geographic coordinates in [longitude, latitude] format",
        min_length=2,
        max_length=2,
    )


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number starting from 1")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    total_pages: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None
    request_id: str | None = None
    timestamp: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
