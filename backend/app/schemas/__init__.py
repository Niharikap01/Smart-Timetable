from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.teacher import TeacherCreate, TeacherUpdate, TeacherResponse
from app.schemas.section import SectionCreate, SectionUpdate, SectionResponse
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse
from app.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from app.schemas.timeslot import TimeslotCreate, TimeslotUpdate, TimeslotResponse
from app.schemas.teacher_availability import TeacherAvailabilityCreate, TeacherAvailabilityResponse
from app.schemas.reserved_slot import ReservedSlotCreate, ReservedSlotResponse
from app.schemas.timetable import (
    TimetableSessionResponse, GeneratedScheduleResponse,
    GeneratedScheduleDetailResponse, GenerateRequest, GenerateResultResponse,
)
from app.schemas.user import UserCreate, UserResponse, Token, TokenData
