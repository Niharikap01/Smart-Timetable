"""Reconcile legacy elective course rows with configured program electives."""
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Course, ProgramElective, Section


def _normalized(value: str) -> str:
    """Compare course titles/codes while ignoring case, spaces, and punctuation."""
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def deactivate_legacy_elective_offerings(
    db: Session, semester: Optional[int] = None,
) -> list[str]:
    """Deactivate old PEI-* per-section rows replaced by configured groups.

    Older imports stored electives as ordinary independent courses (for
    example, PEI-DPD once per section). Once a coordinator configures the same
    elective with shared section groups, those old rows must not also be
    scheduled independently. Keep historical timetable rows intact; only
    remove the legacy course offerings from future generations.
    """
    elective_query = db.query(ProgramElective).filter(ProgramElective.active.is_(True))
    if semester is not None:
        elective_query = elective_query.filter(ProgramElective.semester == semester)
    electives = elective_query.all()
    if not electives:
        return []

    legacy_query = (
        db.query(Course)
        .join(Section, Section.id == Course.section_id)
        .filter(
            Course.active.is_(True),
            Course.program_elective_group_id.is_(None),
            Course.course_code.ilike("PEI-%"),
        )
    )
    if semester is not None:
        legacy_query = legacy_query.filter(Section.semester == semester)
    legacy_courses = legacy_query.all()

    deactivated = []
    for elective in electives:
        # Only replace legacy rows once the coordinator has actually configured
        # at least one active shared group for this elective.
        if not any(group.active for group in elective.groups):
            continue

        elective_name = _normalized(elective.course_name)
        elective_code = _normalized(elective.course_code)
        for course in legacy_courses:
            if not course.active or course.section.semester != elective.semester:
                continue
            legacy_code = (course.course_code or "").strip().upper()
            legacy_suffix = _normalized(legacy_code[4:]) if legacy_code.startswith("PEI-") else ""
            if (
                _normalized(course.course_name) == elective_name
                or (legacy_suffix and legacy_suffix == elective_code)
            ):
                course.active = False
                deactivated.append(f"{course.course_code} / {course.section.name}")

    if deactivated:
        db.flush()
    return deactivated
