from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.teacher_availability import TeacherAvailability
from app.models.teacher import Teacher
from app.schemas.teacher_availability import TeacherAvailabilityCreate, TeacherAvailabilityResponse

router = APIRouter(prefix="/api/availability", tags=["availability"])


@router.get("/teacher/{teacher_id}", response_model=List[TeacherAvailabilityResponse])
def get_teacher_availability(teacher_id: int, db: Session = Depends(get_db)):
    if not db.query(Teacher).get(teacher_id):
        raise HTTPException(404, "Teacher not found")
    return db.query(TeacherAvailability).filter(
        TeacherAvailability.teacher_id == teacher_id
    ).all()


@router.post("/", response_model=TeacherAvailabilityResponse, status_code=201, dependencies=[Depends(require_coordinator)])
def create_availability(data: TeacherAvailabilityCreate, db: Session = Depends(get_db)):
    if not db.query(Teacher).get(data.teacher_id):
        raise HTTPException(422, "Teacher does not exist")
    a = TeacherAvailability(**data.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{avail_id}", dependencies=[Depends(require_coordinator)])
def delete_availability(avail_id: int, db: Session = Depends(get_db)):
    a = db.query(TeacherAvailability).get(avail_id)
    if not a:
        raise HTTPException(404, "Availability record not found")
    db.delete(a)
    db.commit()
    return {"success": True, "message": "Availability deleted"}
