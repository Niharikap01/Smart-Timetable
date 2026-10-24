from pydantic import BaseModel, Field
from typing import Optional, List
from app.models.course import CourseType, RoomType


class CourseBase(BaseModel):
    course_code: str = Field(..., min_length=1, max_length=50)
    course_name: str = Field(..., min_length=1, max_length=200)
    course_type: CourseType
    weekly_sessions: int = Field(..., gt=0)
    duration: int = Field(default=1, gt=0)
    section_id: int = Field(..., gt=0)
    teacher_id: int = Field(..., gt=0)
    required_room_type: RoomType
    priority: int = Field(default=5, ge=1, le=10)
    active: bool = True
    # Parallel alternatives/batches share a section slot but receive different
    # rooms.  These fields already exist in the model; exposing them here lets
    # imported reference data preserve that relationship through the API.
    link_group: Optional[str] = Field(None, max_length=50)
    batch_label: Optional[str] = Field(None, max_length=50)
    teacher_ids: Optional[List[int]] = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    course_code: Optional[str] = Field(None, min_length=1, max_length=50)
    course_name: Optional[str] = Field(None, min_length=1, max_length=200)
    course_type: Optional[CourseType] = None
    weekly_sessions: Optional[int] = Field(None, gt=0)
    duration: Optional[int] = Field(None, gt=0)
    section_id: Optional[int] = Field(None, gt=0)
    teacher_id: Optional[int] = Field(None, gt=0)
    required_room_type: Optional[RoomType] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    active: Optional[bool] = None
    link_group: Optional[str] = Field(None, max_length=50)
    batch_label: Optional[str] = Field(None, max_length=50)
    teacher_ids: Optional[List[int]] = None


class CourseResponse(CourseBase):
    id: int
    program_elective_group_id: Optional[int] = None
    model_config = {"from_attributes": True}
