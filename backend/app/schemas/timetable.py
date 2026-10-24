from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime, time
from app.models.timeslot import DayOfWeek
from app.models.timetable import ScheduleStatus


class TimetableSessionResponse(BaseModel):
    id: int
    course_id: int
    section_id: int
    teacher_id: int
    room_id: int
    timeslot_id: int
    day: DayOfWeek
    start_time: time
    end_time: time
    session_number: int
    generated_schedule_id: int
    batch_label: Optional[str] = None
    teacher_ids: List[int] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class GeneratedScheduleResponse(BaseModel):
    id: int
    generated_at: datetime
    status: ScheduleStatus
    hard_constraint_violations: int
    soft_constraint_score: Optional[float]
    generation_time_ms: Optional[int]
    algorithm: str
    version: Optional[str]
    backtracks: Optional[int]
    restarts: Optional[int]
    constraint_profile_version: Optional[int] = None
    constraint_config_snapshot: Optional[dict] = None
    is_stale: bool = False
    model_config = {"from_attributes": True}


class GeneratedScheduleDetailResponse(GeneratedScheduleResponse):
    sessions: List[TimetableSessionResponse] = []


class GenerateRequest(BaseModel):
    timeout_seconds: int = Field(default=30, gt=0, le=300)
    enable_optimization: bool = False
    algorithm: str = "GOOGLE_OR_TOOLS_CP_SAT"
    # The coordinator source is complete enough to schedule some semesters
    # before others. `None` remains the explicit full-department option.
    semester: Optional[int] = Field(default=None, ge=1, le=12)


class GenerateResultResponse(BaseModel):
    status: str
    message: Optional[str] = None
    generation_time_ms: Optional[int] = None
    hard_constraint_violations: int = 0
    soft_constraint_score: Optional[float] = None
    sessions_scheduled: int = 0
    sessions_expected: int = 0
    backtracks: Optional[int] = None
    restarts: Optional[int] = None
    algorithm: str = "GOOGLE_OR_TOOLS_CP_SAT"
    schedule_id: Optional[int] = None
    unscheduled_sessions: Optional[List[Any]] = None
    bottlenecks: Optional[List[str]] = None
