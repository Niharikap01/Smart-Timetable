from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import time
from app.models.timeslot import DayOfWeek


class TimeslotBase(BaseModel):
    day: DayOfWeek
    start_time: time
    end_time: time
    slot_index: int = Field(..., ge=0)
    is_reserved: bool = False
    reservation_reason: Optional[str] = None

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: time, info) -> time:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class TimeslotCreate(TimeslotBase):
    pass


class TimeslotUpdate(BaseModel):
    is_reserved: Optional[bool] = None
    reservation_reason: Optional[str] = None


class TimeslotResponse(TimeslotBase):
    id: int
    model_config = {"from_attributes": True}
