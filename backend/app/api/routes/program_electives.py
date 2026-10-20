from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_coordinator
from app.database.session import get_db
from app.models import Course, ProgramElective, ProgramElectiveGroup, Section, Teacher, TimetableSession
from app.models.course import CourseType, RoomType
from app.schemas.program_elective import ProgramElectiveCreate
from app.services.program_elective_sync import deactivate_legacy_elective_offerings


router = APIRouter(prefix="/api/program-electives", tags=["program-electives"])
LARGE_ELECTIVE_ROOMS = {"DT-301", "DT-701", "DT-702"}


def _elective_response(elective: ProgramElective) -> dict:
    return {
        "id": elective.id,
        "semester": elective.semester,
        "course_code": elective.course_code,
        "course_name": elective.course_name,
        "weekly_sessions": elective.weekly_sessions,
        "duration": elective.duration,
        "groups": [
            {
                "id": group.id,
                "group_name": group.group_name,
                "teacher_id": group.teacher_id,
                "teacher_name": group.teacher.name,
                "student_count": group.student_count,
                "room_policy": "large-only" if group.student_count > 70 else "standard-only",
                "section_ids": [section.id for section in group.sections],
                "section_names": sorted(section.name for section in group.sections),
            }
            for group in elective.groups if group.active
        ],
    }


@router.get("/")
def list_program_electives(
    semester: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
    _coordinator=Depends(require_coordinator),
):
    electives = (
        db.query(ProgramElective)
        .filter(ProgramElective.semester == semester, ProgramElective.active.is_(True))
        .order_by(ProgramElective.course_code)
        .all()
    )
    return [_elective_response(elective) for elective in electives]


@router.post("/", status_code=201, dependencies=[Depends(require_coordinator)])
def create_program_elective(data: ProgramElectiveCreate, db: Session = Depends(get_db)):
    code = data.course_code.strip().upper()
    existing = db.query(ProgramElective).filter(
        ProgramElective.semester == data.semester,
        ProgramElective.course_code == code,
        ProgramElective.active.is_(True),
    ).first()
    if existing:
        raise HTTPException(409, f"{code} already exists as a program elective in Semester {data.semester}")

    requested_section_ids = {section_id for group in data.groups for section_id in group.section_ids}
    sections = db.query(Section).filter(
        Section.id.in_(requested_section_ids),
        Section.semester == data.semester,
        Section.program.ilike("CSE"),
        Section.active.is_(True),
    ).all()
    section_by_id = {section.id: section for section in sections}
    missing_sections = requested_section_ids - set(section_by_id)
    if missing_sections:
        raise HTTPException(422, "Every selected section must be an active CSE section in the chosen semester")

    requested_teacher_ids = {group.teacher_id for group in data.groups}
    teachers = db.query(Teacher).filter(
        Teacher.id.in_(requested_teacher_ids), Teacher.active.is_(True),
    ).all()
    if len(teachers) != len(requested_teacher_ids):
        raise HTTPException(422, "Choose an active faculty member for each program-elective group")

    elective = ProgramElective(
        semester=data.semester,
        course_code=code,
        course_name=data.course_name.strip(),
        weekly_sessions=data.weekly_sessions,
        duration=data.duration,
        active=True,
    )
    db.add(elective)
    db.flush()

    try:
        for group_data in data.groups:
            group = ProgramElectiveGroup(
                program_elective_id=elective.id,
                group_name=group_data.group_name.strip(),
                teacher_id=group_data.teacher_id,
                student_count=group_data.student_count,
                active=True,
            )
            group.sections = [section_by_id[section_id] for section_id in group_data.section_ids]
            db.add(group)
            db.flush()

            for section in group.sections:
                active_matches = db.query(Course).filter(
                    Course.course_code == code,
                    Course.section_id == section.id,
                    Course.active.is_(True),
                ).all()
                if len(active_matches) > 1:
                    raise HTTPException(
                        409,
                        f"{section.name} has multiple active offerings for {code}; resolve the duplicate in Courses first",
                    )

                reusable = active_matches[0] if active_matches else None
                if reusable and reusable.program_elective_group_id is not None:
                    # Keep old generated timetables' course references immutable.
                    reusable.active = False
                    reusable = None
                elif reusable:
                    has_history = db.query(TimetableSession.id).filter(
                        TimetableSession.course_id == reusable.id,
                    ).first() is not None
                    if has_history:
                        reusable.active = False
                        reusable = None

                fields = {
                    "course_code": code,
                    "course_name": elective.course_name,
                    "course_type": CourseType.LECTURE,
                    "weekly_sessions": elective.weekly_sessions,
                    "duration": elective.duration,
                    "section_id": section.id,
                    "teacher_id": group.teacher_id,
                    "required_room_type": RoomType.LECTURE,
                    "priority": 5,
                    "active": True,
                    "link_group": None,
                    "batch_label": group.group_name,
                    "program_elective_group_id": group.id,
                }
                if reusable is None:
                    db.add(Course(**fields))
                else:
                    for key, value in fields.items():
                        setattr(reusable, key, value)

        # Older workbook/demo imports may contain an independent PEI-* row
        # for every section. The configured groups replace those offerings.
        deactivate_legacy_elective_offerings(db, semester=data.semester)
        db.commit()
        db.refresh(elective)
        return _elective_response(elective)
    except Exception as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(422, f"Program elective could not be saved: {exc}") from exc


@router.delete("/{elective_id}", dependencies=[Depends(require_coordinator)])
def deactivate_program_elective(elective_id: int, db: Session = Depends(get_db)):
    elective = db.query(ProgramElective).filter(ProgramElective.id == elective_id).first()
    if elective is None or not elective.active:
        raise HTTPException(404, "Program elective not found")

    group_ids = [group.id for group in elective.groups]
    elective.active = False
    for group in elective.groups:
        group.active = False
    if group_ids:
        db.query(Course).filter(Course.program_elective_group_id.in_(group_ids)).update(
            {Course.active: False}, synchronize_session=False,
        )
    db.commit()
    return {"success": True, "message": "Program elective removed from future timetables"}
