from datetime import datetime

from pydantic import BaseModel, Field


class ConstraintProfileUpdate(BaseModel):
    MAX_LECTURE_PERIODS_PER_DAY: int = Field(ge=1, le=24)
    MAX_SECTION_DAILY_HOURS: int = Field(ge=1, le=24)
    MAX_CONSECUTIVE_PERIODS: int = Field(ge=1, le=24)
    MAX_TEACHER_DAILY_HOURS: int = Field(ge=1, le=24)
    LATEST_SECTION_START_TIME: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    change_reason: str = Field(min_length=3, max_length=500)


class ConstraintProfileResponse(BaseModel):
    version: int
    config: dict
    change_reason: str
    created_at: datetime

    model_config = {"from_attributes": True}
