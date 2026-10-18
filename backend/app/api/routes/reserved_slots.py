from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.reserved_slot import ReservedSlot
from app.schemas.reserved_slot import ReservedSlotCreate, ReservedSlotResponse

router = APIRouter(prefix="/api/reserved-slots", tags=["reserved-slots"])


@router.get("/", response_model=List[ReservedSlotResponse])
def list_reserved_slots(db: Session = Depends(get_db)):
    return db.query(ReservedSlot).all()


@router.post("/", response_model=ReservedSlotResponse, status_code=201, dependencies=[Depends(require_coordinator)])
def create_reserved_slot(data: ReservedSlotCreate, db: Session = Depends(get_db)):
    r = ReservedSlot(**data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{slot_id}", dependencies=[Depends(require_coordinator)])
def delete_reserved_slot(slot_id: int, db: Session = Depends(get_db)):
    r = db.query(ReservedSlot).get(slot_id)
    if not r:
        raise HTTPException(404, "Reserved slot not found")
    db.delete(r)
    db.commit()
    return {"success": True, "message": "Reserved slot deleted"}
