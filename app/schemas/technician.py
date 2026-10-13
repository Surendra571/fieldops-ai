from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import GeoPoint


class TechnicianStatus(str, Enum):
    ACTIVE = "ACTIVE"
    OFF_DUTY = "OFF_DUTY"
    ON_LEAVE = "ON_LEAVE"


class DayOfWeek(str, Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class ShiftWindow(BaseModel):
    day_of_week: DayOfWeek
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM format, e.g. 08:00")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM format, e.g. 17:00")


class TechnicianSchedule(BaseModel):
    timezone: str = "America/New_York"
    weekly_hours: list[ShiftWindow] = Field(default_factory=list)


class TechnicianBase(BaseModel):
    name: str
    phone: str
    email: EmailStr
    status: TechnicianStatus = TechnicianStatus.ACTIVE
    skills: list[str] = Field(
        default_factory=list, description="Skill tags e.g. HVAC_EPA_CERTIFIED"
    )
    home_base: GeoPoint | None = None
    max_travel_radius_km: float = Field(default=40.0, ge=1.0)
    shift_schedule: TechnicianSchedule | None = None


class TechnicianCreate(TechnicianBase):
    user_id: str | None = None


class TechnicianUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    status: TechnicianStatus | None = None
    skills: list[str] | None = None
    home_base: GeoPoint | None = None
    max_travel_radius_km: float | None = None
    shift_schedule: TechnicianSchedule | None = None


class TechnicianLocationUpdate(BaseModel):
    coordinates: list[float] = Field(..., min_length=2, max_length=2, description="[lon, lat]")
    heading: float | None = None
    speed_kph: float | None = None
    battery_level: float | None = None
    timestamp: datetime | None = None


class TechnicianResponse(TechnicianBase):
    id: str
    user_id: str | None = None
    current_location: GeoPoint | None = None
    rating: float = 5.0
    completed_jobs_count: int = 0
    created_at: datetime
    updated_at: datetime
