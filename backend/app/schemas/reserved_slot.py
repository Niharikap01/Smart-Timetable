from pydantic import BaseModel, Field
from typing import Optional
from app.models.timeslot import DayOfWeek


class ReservedSlotBase(BaseModel):
    day: DayOfWeek
    slot_index: int = Field(..., ge=0)
    reason: str = Field(..., min_length=1, max_length=200)
    section_id: Optional[int] = None


class ReservedSlotCreate(ReservedSlotBase):
    pass


class ReservedSlotResponse(ReservedSlotBase):
    id: int
    model_config = {"from_attributes": True}
