from pydantic import BaseModel, Field
from app.models.timeslot import DayOfWeek


class TeacherAvailabilityBase(BaseModel):
    teacher_id: int = Field(..., gt=0)
    day: DayOfWeek
    slot_index: int = Field(..., ge=0)
    is_available: bool = True


class TeacherAvailabilityCreate(TeacherAvailabilityBase):
    pass


class TeacherAvailabilityResponse(TeacherAvailabilityBase):
    id: int
    model_config = {"from_attributes": True}
