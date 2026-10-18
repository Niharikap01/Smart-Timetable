from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.timeslot import Timeslot
from app.schemas.timeslot import TimeslotCreate, TimeslotUpdate, TimeslotResponse

router = APIRouter(prefix="/api/timeslots", tags=["timeslots"])


@router.get("/", response_model=List[TimeslotResponse])
def list_timeslots(day: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Timeslot)
    if day:
        q = q.filter(Timeslot.day == day)
    return q.order_by(Timeslot.day, Timeslot.slot_index).all()


@router.get("/{timeslot_id}", response_model=TimeslotResponse)
def get_timeslot(timeslot_id: int, db: Session = Depends(get_db)):
    t = db.query(Timeslot).get(timeslot_id)
    if not t:
        raise HTTPException(404, "Timeslot not found")
    return t


@router.post("/", response_model=TimeslotResponse, status_code=201, dependencies=[Depends(require_coordinator)])
def create_timeslot(data: TimeslotCreate, db: Session = Depends(get_db)):
    t = Timeslot(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.put("/{timeslot_id}", response_model=TimeslotResponse, dependencies=[Depends(require_coordinator)])
def update_timeslot(timeslot_id: int, data: TimeslotUpdate, db: Session = Depends(get_db)):
    t = db.query(Timeslot).get(timeslot_id)
    if not t:
        raise HTTPException(404, "Timeslot not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{timeslot_id}", dependencies=[Depends(require_coordinator)])
def delete_timeslot(timeslot_id: int, db: Session = Depends(get_db)):
    t = db.query(Timeslot).get(timeslot_id)
    if not t:
        raise HTTPException(404, "Timeslot not found")
    db.delete(t)
    db.commit()
    return {"success": True, "message": "Timeslot deleted"}
