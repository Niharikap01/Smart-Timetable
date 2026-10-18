from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate, TeacherResponse

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


@router.get("/", response_model=List[TeacherResponse])
def list_teachers(active: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(Teacher)
    if active is not None:
        q = q.filter(Teacher.active == active)
    return q.all()


@router.get("/{teacher_id}", response_model=TeacherResponse)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    t = db.query(Teacher).get(teacher_id)
    if not t:
        raise HTTPException(404, "Teacher not found")
    return t


@router.post("/", response_model=TeacherResponse, status_code=201, dependencies=[Depends(require_coordinator)])
def create_teacher(data: TeacherCreate, db: Session = Depends(get_db)):
    if db.query(Teacher).filter(Teacher.employee_id == data.employee_id).first():
        raise HTTPException(409, "Employee ID already exists")
    if db.query(Teacher).filter(Teacher.email == data.email).first():
        raise HTTPException(409, "Email already exists")
    t = Teacher(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.put("/{teacher_id}", response_model=TeacherResponse, dependencies=[Depends(require_coordinator)])
def update_teacher(teacher_id: int, data: TeacherUpdate, db: Session = Depends(get_db)):
    t = db.query(Teacher).get(teacher_id)
    if not t:
        raise HTTPException(404, "Teacher not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{teacher_id}", dependencies=[Depends(require_coordinator)])
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    t = db.query(Teacher).get(teacher_id)
    if not t:
        raise HTTPException(404, "Teacher not found")
    t.active = False
    db.commit()
    return {"success": True, "message": "Teacher deactivated"}
