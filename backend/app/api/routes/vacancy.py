from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import Room
from app.models.timetable import GeneratedSchedule, ScheduleStatus
from app.vacancy.cache import occupancy_cache

router = APIRouter(prefix="/api/vacancy", tags=["vacancy"])


def refresh_cache_from_database(db: Session) -> None:
    latest_schedule = db.query(GeneratedSchedule).filter(
        GeneratedSchedule.status == ScheduleStatus.VALID,
        GeneratedSchedule.is_stale.is_(False),
    ).order_by(GeneratedSchedule.generated_at.desc(), GeneratedSchedule.id.desc()).first()

    if latest_schedule:
        from app.services.timetable_editor import refresh_vacancy_cache
        refresh_vacancy_cache(db, latest_schedule, broadcast=False)
    else:
        rooms = db.query(Room).filter(Room.active.is_(True)).all()
        occupancy_cache.load_rooms([
            {
                "room_id": room.id,
                "room_number": room.room_number,
                "room_type": room.room_type.value if hasattr(room.room_type, "value") else room.room_type,
                "capacity": room.capacity,
            }
            for room in rooms
        ])
        occupancy_cache.load_schedule([])
        occupancy_cache.update_current()


@router.get("/rooms")
def get_all_rooms(db: Session = Depends(get_db)):
    refresh_cache_from_database(db)
    return occupancy_cache.get_all()


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    refresh_cache_from_database(db)
    return occupancy_cache.get_summary()


@router.get("/{room_id}")
def get_room_status(room_id: int, db: Session = Depends(get_db)):
    refresh_cache_from_database(db)
    r = occupancy_cache.get_room(room_id)
    if not r:
        return {"error": "Room not found"}
    return r
