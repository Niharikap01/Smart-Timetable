from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate, RoomResponse

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.get("/", response_model=List[RoomResponse])
def list_rooms(room_type: Optional[str] = None, building: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Room)
    if room_type:
        q = q.filter(Room.room_type == room_type)
    if building:
        q = q.filter(Room.building == building)
    return q.all()


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(room_id: int, db: Session = Depends(get_db)):
    r = db.query(Room).get(room_id)
    if not r:
        raise HTTPException(404, "Room not found")
    return r


@router.post("/", response_model=RoomResponse, status_code=201, dependencies=[Depends(require_coordinator)])
def create_room(data: RoomCreate, db: Session = Depends(get_db)):
    if db.query(Room).filter(Room.room_number == data.room_number).first():
        raise HTTPException(409, "Room number already exists")
    r = Room(**data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.put("/{room_id}", response_model=RoomResponse, dependencies=[Depends(require_coordinator)])
def update_room(room_id: int, data: RoomUpdate, db: Session = Depends(get_db)):
    r = db.query(Room).get(room_id)
    if not r:
        raise HTTPException(404, "Room not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{room_id}", dependencies=[Depends(require_coordinator)])
def delete_room(room_id: int, db: Session = Depends(get_db)):
    r = db.query(Room).get(room_id)
    if not r:
        raise HTTPException(404, "Room not found")
    r.active = False
    db.commit()
    return {"success": True, "message": "Room deactivated"}
