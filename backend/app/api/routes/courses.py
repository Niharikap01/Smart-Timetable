from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.course import Course
from app.models.teacher import Teacher
from app.models.section import Section
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse
from app.scheduler.batches import normalize_batch_label, teacher_ids

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _validated_teacher_ids(db: Session, primary_id: int, values: Optional[list[int]]) -> Optional[list[int]]:
    if values is None:
        return None
    ids = list(dict.fromkeys([primary_id, *(int(value) for value in values)]))
    missing = [teacher_id for teacher_id in ids if db.query(Teacher).get(teacher_id) is None]
    if missing:
        raise HTTPException(422, f"Teacher(s) do not exist: {', '.join(map(str, missing))}")
    return ids


def _validate_batch_course(course_type, batch_label):
    if normalize_batch_label(batch_label) and getattr(course_type, "value", course_type) != "lab":
        raise HTTPException(422, "Only lab courses can be assigned to B1/B2 or B3/B4 batches")


@router.get("/", response_model=List[CourseResponse])
def list_courses(section_id: Optional[int] = None, teacher_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Course)
    if section_id:
        q = q.filter(Course.section_id == section_id)
    courses = q.all()
    if teacher_id:
        courses = [
            course for course in courses
            if teacher_id in teacher_ids(course.teacher_id, course.teacher_ids)
        ]
    return courses


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
    payload = data.model_dump()
    payload["batch_label"] = payload.get("batch_label") or None
    _validate_batch_course(payload["course_type"], payload.get("batch_label"))
    payload["teacher_ids"] = _validated_teacher_ids(db, data.teacher_id, payload.get("teacher_ids"))
    c = Course(**payload)
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
    if "teacher_ids" in updates:
        primary_id = updates.get("teacher_id", c.teacher_id)
        updates["teacher_ids"] = _validated_teacher_ids(db, primary_id, updates["teacher_ids"])
    elif "teacher_id" in updates and c.teacher_ids:
        # A legacy single-teacher edit replaces the lead instructor while
        # retaining co-instructors already selected for the batch pair.
        updates["teacher_ids"] = list(dict.fromkeys([
            updates["teacher_id"], *[tid for tid in c.teacher_ids if tid != c.teacher_id]
        ]))
    _validate_batch_course(updates.get("course_type", c.course_type), updates.get("batch_label", c.batch_label))
    if "batch_label" in updates:
        updates["batch_label"] = updates["batch_label"] or None
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
