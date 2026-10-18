from pydantic import BaseModel, Field, field_validator
from typing import Optional
from app.models.teacher import FacultyType


class TeacherBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    employee_id: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., min_length=1, max_length=200)
    max_daily_hours: int = Field(default=7, gt=0, le=12)
    faculty_type: FacultyType = FacultyType.REGULAR
    preferences: Optional[str] = None
    active: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = Field(None, min_length=1, max_length=200)
    max_daily_hours: Optional[int] = Field(None, gt=0, le=12)
    faculty_type: Optional[FacultyType] = None
    preferences: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v and ("@" not in v or "." not in v.split("@")[-1]):
            raise ValueError("Invalid email format")
        return v


class TeacherResponse(TeacherBase):
    id: int
    model_config = {"from_attributes": True}
