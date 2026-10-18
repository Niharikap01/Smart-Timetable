from fastapi import APIRouter
from app.api.routes import (
    auth, teachers, sections, courses, rooms,
    timeslots, availability, reserved_slots, timetable, imports, constraints,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(teachers.router)
api_router.include_router(sections.router)
api_router.include_router(courses.router)
api_router.include_router(rooms.router)
api_router.include_router(timeslots.router)
api_router.include_router(availability.router)
api_router.include_router(reserved_slots.router)
api_router.include_router(timetable.router)
api_router.include_router(imports.router)
api_router.include_router(constraints.router)
