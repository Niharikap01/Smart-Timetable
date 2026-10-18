from fastapi import APIRouter
from app.vacancy.cache import occupancy_cache

router = APIRouter(prefix="/api/vacancy", tags=["vacancy"])


@router.get("/rooms")
def get_all_rooms():
    return occupancy_cache.get_all()


@router.get("/summary")
def get_summary():
    return occupancy_cache.get_summary()


@router.get("/{room_id}")
def get_room_status(room_id: int):
    r = occupancy_cache.get_room(room_id)
    if not r:
        return {"error": "Room not found"}
    return r
