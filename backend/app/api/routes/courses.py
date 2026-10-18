from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.course import Course
from app.models.teacher import Teacher
from app.models.section import Section
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("/", response_model=List[CourseResponse])
def list_courses(section_id: Optional[int] = None, teacher_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Course)
    if section_id:
        q = q.filter(Course.section_id == section_id)
    if teacher_id:
        q = q.filter(Course.teacher_id == teacher_id)
    return q.all()


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    c = db.query(Course).get(course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    return c


@router.post("/", response_model=CourseResponse, status_code=201, dependencies=[Depends(require_coordinator)])
def create_course(data: CourseCreate, db: Session = Depends(get_db)):
    if not db.query(Teacher).get(data.teacher_id):
        raise HTTPException(422, "Teacher does not exist")
    if not db.query(Section).get(data.section_id):
        raise HTTPException(422, "Section does not exist")
    c = Course(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{course_id}", response_model=CourseResponse, dependencies=[Depends(require_coordinator)])
def update_course(course_id: int, data: CourseUpdate, db: Session = Depends(get_db)):
    c = db.query(Course).get(course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    updates = data.model_dump(exclude_unset=True)
    if "teacher_id" in updates and not db.query(Teacher).get(updates["teacher_id"]):
        raise HTTPException(422, "Teacher does not exist")
    if "section_id" in updates and not db.query(Section).get(updates["section_id"]):
        raise HTTPException(422, "Section does not exist")
    for k, v in updates.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{course_id}", dependencies=[Depends(require_coordinator)])
def delete_course(course_id: int, db: Session = Depends(get_db)):
    c = db.query(Course).get(course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    c.active = False
    db.commit()
    return {"success": True, "message": "Course deactivated"}
