from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import GeoPoint


class ChannelPreference(str, Enum):
    VOICE = "VOICE"
    SMS = "SMS"
    EMAIL = "EMAIL"


class ServiceAddress(BaseModel):
    street: str
    unit: str | None = None
    city: str
    state: str
    postal_code: str
    location: GeoPoint | None = None
    access_instructions: str | None = None
    is_primary: bool = True


class CustomerBase(BaseModel):
    full_name: str
    phone: str
    email: EmailStr | None = None
    preferred_channel: ChannelPreference = ChannelPreference.VOICE
    service_addresses: list[ServiceAddress] = Field(default_factory=list)


class CustomerCreate(CustomerBase):
    user_id: str | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    preferred_channel: ChannelPreference | None = None
    service_addresses: list[ServiceAddress] | None = None


class CustomerResponse(CustomerBase):
    id: str
    user_id: str | None = None
    total_completed_jobs: int = 0
    no_show_history_count: int = 0
    created_at: datetime
    updated_at: datetime
