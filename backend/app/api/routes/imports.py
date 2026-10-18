"""Validated CSV/XLSX imports for the department master-data pages.

The endpoint deliberately treats an upload as a single transaction.  A row
with an invalid reference or malformed value rejects the complete file, so a
partially imported department dataset can never be used for scheduling.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Any, Callable
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import require_coordinator
from app.models import (
    Course, Room, Section, Teacher, Timeslot,
)
from app.models.course import CourseType, RoomType
from app.models.teacher import FacultyType
from app.models.timeslot import DayOfWeek
from app.schemas.course import CourseCreate
from app.schemas.room import RoomCreate
from app.schemas.section import SectionCreate
from app.schemas.teacher import TeacherCreate
from app.schemas.timeslot import TimeslotCreate


router = APIRouter(prefix="/api/import", tags=["imports"])

MAX_IMPORT_BYTES = 10 * 1024 * 1024
SUPPORTED_ENTITIES = {"teachers", "sections", "courses", "rooms", "timeslots"}
DAYS = {day.value.lower(): day.value for day in DayOfWeek}
XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
def _header_key(value: Any) -> str:
    """Convert human-friendly column headings to predictable lookup keys."""
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    value = _text(value)
    return value or None


def _column_index(cell_ref: str) -> int:
    """Return zero-based column position for an XLSX reference such as B12."""
    letters = re.match(r"[A-Z]+", cell_ref or "")
    if not letters:
        return 0
    result = 0
    for letter in letters.group(0):
        result = result * 26 + ord(letter) - 64
    return result - 1


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.iter(f"{{{XLSX_NS}}}t")) for item in root]


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    """Resolve the first worksheet rather than assuming it is named sheet1."""
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheet = workbook.find(f"{{{XLSX_NS}}}sheets/{{{XLSX_NS}}}sheet")
    if sheet is None:
        raise ValueError("The workbook does not contain a worksheet")
    relationship_id = sheet.attrib.get(f"{{{DOC_REL_NS}}}id")
    relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relation in relations.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        if relation.attrib.get("Id") == relationship_id:
            target = relation.attrib.get("Target", "")
            return target.lstrip("/") if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
    raise ValueError("The workbook's first worksheet could not be read")


def _parse_xlsx(content: bytes) -> list[tuple[int, dict[str, str]]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            root = ET.fromstring(archive.read(_first_sheet_path(archive)))
    except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError) as exc:
        raise ValueError(f"Unable to read this Excel workbook: {exc}") from exc

    parsed_rows: list[tuple[int, list[str]]] = []
    for row in root.findall(f".//{{{XLSX_NS}}}sheetData/{{{XLSX_NS}}}row"):
        cells: dict[int, str] = {}
        for cell in row.findall(f"{{{XLSX_NS}}}c"):
            cell_type = cell.attrib.get("t")
            raw_value = cell.findtext(f"{{{XLSX_NS}}}v", default="")
            if cell_type == "s" and raw_value:
                try:
                    value = shared_strings[int(raw_value)]
                except (IndexError, ValueError):
                    value = ""
            elif cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.iter(f"{{{XLSX_NS}}}t"))
            else:
                value = raw_value
            cells[_column_index(cell.attrib.get("r", ""))] = value
        if cells:
            parsed_rows.append((int(row.attrib.get("r", len(parsed_rows) + 1)), [cells.get(i, "") for i in range(max(cells) + 1)]))

    return _rows_from_values(parsed_rows)


def _rows_from_values(values: list[tuple[int, list[str]]]) -> list[tuple[int, dict[str, str]]]:
    if not values:
        raise ValueError("The file is empty")
    _, headings = values[0]
    headers = [_header_key(value) for value in headings]
    if not any(headers):
        raise ValueError("The first row must contain column headings")
    non_empty_headers = [header for header in headers if header]
    if len(non_empty_headers) != len(set(non_empty_headers)):
        raise ValueError("Column headings must be unique")

    rows: list[tuple[int, dict[str, str]]] = []
    for row_number, values_row in values[1:]:
        row = {header: _text(values_row[index]) if index < len(values_row) else "" for index, header in enumerate(headers) if header}
        if any(row.values()):
            rows.append((row_number, row))
    if not rows:
        raise ValueError("The file contains headings but no data rows")
    return rows


def _parse_csv(content: bytes) -> list[tuple[int, dict[str, str]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV files must be saved using UTF-8 encoding") from exc
    values = [(line_number, row) for line_number, row in enumerate(csv.reader(io.StringIO(text)), start=1) if any(_text(value) for value in row)]
    return _rows_from_values(values)


def _parse_file(filename: str, content: bytes) -> list[tuple[int, dict[str, str]]]:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "csv":
        return _parse_csv(content)
    if extension == "xlsx":
        return _parse_xlsx(content)
    raise ValueError("Choose a .csv or .xlsx file")


def _pick(row: dict[str, str], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and _text(row[name]):
            return row[name]
    return default


def _required(row: dict[str, str], label: str, *names: str) -> str:
    value = _pick(row, *names)
    if value is None:
        raise ValueError(f"{label} is required")
    return _text(value)


def _integer(value: Any, label: str, default: int | None = None) -> int:
    if value is None or _text(value) == "":
        if default is not None:
            return default
        raise ValueError(f"{label} is required")
    try:
        number = float(_text(value))
    except ValueError as exc:
        raise ValueError(f"{label} must be a whole number") from exc
    if not number.is_integer():
        raise ValueError(f"{label} must be a whole number")
    return int(number)


def _boolean(value: Any, label: str, default: bool = True) -> bool:
    if value is None or _text(value) == "":
        return default
    normalized = _text(value).lower()
    if normalized in {"1", "true", "yes", "y", "active", "reserved"}:
        return True
    if normalized in {"0", "false", "no", "n", "inactive", "unreserved"}:
        return False
    raise ValueError(f"{label} must be Yes/No or True/False")


def _one_of(value: Any, label: str, allowed: set[str], aliases: dict[str, str] | None = None, default: str | None = None) -> str:
    result = _text(value).lower() if value is not None else ""
    if not result and default is not None:
        return default
    result = (aliases or {}).get(result, result)
    if result not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(sorted(allowed))}")
    return result


def _day(value: Any) -> str:
    normalized = _text(value).lower()
    if normalized not in DAYS:
        raise ValueError("Day must be Monday through Saturday")
    return DAYS[normalized]


def _time(value: Any, label: str) -> str:
    result = _required({"value": _text(value)}, label, "value")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", result)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
    else:
        # Excel stores a formatted time such as 09:00 as the fractional part
        # of a day (09:00 = 0.375).  XLSX XML keeps that raw number, so accept
        # it as well as the more readable text form used by CSV templates.
        try:
            excel_value = float(result)
        except ValueError as exc:
            raise ValueError(f"{label} must look like 09:00") from exc
        if "." not in result or excel_value < 0:
            raise ValueError(f"{label} must look like 09:00")
        minutes_in_day = round((excel_value % 1) * 24 * 60)
        hour, minute = divmod(minutes_in_day, 60)
        hour %= 24
    if hour > 23 or minute > 59:
        raise ValueError(f"{label} is not a valid time")
    return f"{hour:02d}:{minute:02d}:00"


def _pydantic_payload(model: Any, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return model.model_validate(payload).model_dump()
    except ValidationError as exc:
        message = "; ".join(f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors())
        raise ValueError(message) from exc


def _reference_by_id_or_name(value: str, values_by_id: dict[int, Any], values_by_name: dict[str, list[Any]], label: str) -> Any:
    try:
        numeric_id = int(value)
    except ValueError:
        numeric_id = None
    if numeric_id is not None and numeric_id in values_by_id:
        return values_by_id[numeric_id]
    matches = values_by_name.get(value.strip().lower(), [])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"{label} '{value}' is ambiguous; use its ID")
    raise ValueError(f"{label} '{value}' was not found")


def _make_name_index(items: list[Any], attr: str) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    for item in items:
        result.setdefault(_text(getattr(item, attr)).lower(), []).append(item)
    return result


def _normalise_teacher(row: dict[str, str]) -> dict[str, Any]:
    return _pydantic_payload(TeacherCreate, {
        "name": _required(row, "Name", "name", "teacher_name"),
        "employee_id": _required(row, "Employee ID", "employee_id", "emp_id", "faculty_id"),
        "email": _required(row, "Email", "email", "email_address"),
        "faculty_type": _one_of(_pick(row, "faculty_type", "type"), "Faculty type", {item.value for item in FacultyType}, default="regular"),
        "max_daily_hours": _integer(_pick(row, "max_daily_hours", "max_hours"), "Max daily hours", 7),
        "preferences": _optional_text(_pick(row, "preferences", "preference")),
        "active": _boolean(_pick(row, "active", "status"), "Active", True),
    })


def _normalise_section(row: dict[str, str]) -> dict[str, Any]:
    return _pydantic_payload(SectionCreate, {
        "name": _required(row, "Section name", "name", "section", "section_name"),
        "semester": _integer(_pick(row, "semester", "sem"), "Semester"),
        "strength": _integer(_pick(row, "strength", "students", "student_strength"), "Strength"),
        "program": _text(_pick(row, "program", "department", default="CSE")),
        "year": _integer(_pick(row, "year"), "Year"),
        "active": _boolean(_pick(row, "active", "status"), "Active", True),
    })


def _normalise_room(row: dict[str, str]) -> dict[str, Any]:
    return _pydantic_payload(RoomCreate, {
        "room_number": _required(row, "Room number", "room_number", "room", "room_no"),
        "room_type": _one_of(_pick(row, "room_type", "type"), "Room type", {item.value for item in RoomType}, {"classroom": "lecture", "theory": "lecture", "practical": "lab"}, "lecture"),
        "capacity": _integer(_pick(row, "capacity", "strength"), "Capacity"),
        "building": _optional_text(_pick(row, "building", "block")),
        "floor": _integer(_pick(row, "floor"), "Floor") if _pick(row, "floor") is not None else None,
        "active": _boolean(_pick(row, "active", "status"), "Active", True),
    })


def _normalise_timeslot(row: dict[str, str]) -> dict[str, Any]:
    return _pydantic_payload(TimeslotCreate, {
        "day": _day(_required(row, "Day", "day")),
        "slot_index": _integer(_pick(row, "slot_index", "slot", "period"), "Slot index"),
        "start_time": _time(_pick(row, "start_time", "start"), "Start time"),
        "end_time": _time(_pick(row, "end_time", "end"), "End time"),
        "is_reserved": _boolean(_pick(row, "is_reserved", "reserved"), "Reserved", False),
        "reservation_reason": _optional_text(_pick(row, "reservation_reason", "reason", "reservation")),
    })


def _normalise_course(row: dict[str, str], sections: list[Section], teachers: list[Teacher]) -> dict[str, Any]:
    sections_by_id = {section.id: section for section in sections}
    teachers_by_id = {teacher.id: teacher for teacher in teachers}
    section_ref = _required(row, "Section", "section", "section_name", "section_id")
    teacher_ref = _required(row, "Teacher employee ID", "teacher_employee_id", "teacher_emp_id", "faculty_id", "teacher_id", "teacher")
    section = _reference_by_id_or_name(section_ref, sections_by_id, _make_name_index(sections, "name"), "Section")
    teacher = _reference_by_id_or_name(teacher_ref, teachers_by_id, _make_name_index(teachers, "employee_id"), "Teacher employee ID")
    if teacher.id not in teachers_by_id:
        raise ValueError("Teacher was not found")
    course_type = _one_of(_pick(row, "course_type", "type"), "Course type", {item.value for item in CourseType}, {"theory": "lecture", "practical": "lab"}, "lecture")
    room_type = _one_of(_pick(row, "required_room_type", "room_type"), "Required room type", {item.value for item in RoomType}, {"classroom": "lecture", "theory": "lecture", "practical": "lab"}, "lab" if course_type == "lab" else "lecture")
    return _pydantic_payload(CourseCreate, {
        "course_code": _required(row, "Course code", "course_code", "code", "subject_code"),
        "course_name": _required(row, "Course name", "course_name", "name", "subject_name"),
        "course_type": course_type,
        # Credits are intentionally an alias for the existing weekly_sessions
        # field: one credit represents one scheduled lecture each week.
        "weekly_sessions": _integer(_pick(row, "credits", "weekly_sessions", "lectures_per_week", "sessions_per_week"), "Credits / weekly sessions"),
        "duration": _integer(_pick(row, "duration", "duration_periods", "periods"), "Duration", 1),
        "section_id": section.id,
        "teacher_id": teacher.id,
        "required_room_type": room_type,
        "priority": _integer(_pick(row, "priority"), "Priority", 5),
        "active": _boolean(_pick(row, "active", "status"), "Active", True),
        "link_group": _optional_text(_pick(row, "link_group", "parallel_group")),
        "batch_label": _optional_text(_pick(row, "batch_label", "batch", "batches")),
    })


def _prepare_rows(entity: str, rows: list[tuple[int, dict[str, str]]], db: Session) -> tuple[list[dict[str, Any]], list[str]]:
    normalisers: dict[str, Callable[[dict[str, str]], dict[str, Any]]] = {
        "teachers": _normalise_teacher,
        "sections": _normalise_section,
        "rooms": _normalise_room,
        "timeslots": _normalise_timeslot,
    }
    sections = db.query(Section).all() if entity == "courses" else []
    teachers = db.query(Teacher).all() if entity == "courses" else []
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_keys: set[tuple[Any, ...]] = set()

    for row_number, row in rows:
        try:
            payload = _normalise_course(row, sections, teachers) if entity == "courses" else normalisers[entity](row)
            if entity == "teachers":
                key = (payload["employee_id"].lower(),)
            elif entity == "sections":
                key = (payload["name"].lower(),)
            elif entity == "courses":
                key = (payload["course_code"].lower(), payload["section_id"], payload.get("batch_label") or "")
            elif entity == "rooms":
                key = (payload["room_number"].lower(),)
            else:
                key = (payload["day"].value if hasattr(payload["day"], "value") else payload["day"], payload["slot_index"])
            if key in seen_keys:
                raise ValueError("This file contains another row for the same record")
            seen_keys.add(key)
            records.append(payload)
        except ValueError as exc:
            errors.append(f"Row {row_number}: {exc}")
    return records, errors


def _upsert(entity: str, records: list[dict[str, Any]], db: Session) -> tuple[int, int]:
    created = updated = 0
    for data in records:
        if entity == "teachers":
            item = db.query(Teacher).filter(Teacher.employee_id == data["employee_id"]).first()
        elif entity == "sections":
            item = db.query(Section).filter(Section.name == data["name"]).first()
        elif entity == "courses":
            query = db.query(Course).filter(
                Course.course_code == data["course_code"],
                Course.section_id == data["section_id"],
                Course.course_type == data["course_type"],
            )
            item = query.filter(Course.batch_label.is_(None) if data.get("batch_label") is None else Course.batch_label == data["batch_label"]).first()
        elif entity == "rooms":
            item = db.query(Room).filter(Room.room_number == data["room_number"]).first()
        else:
            item = db.query(Timeslot).filter(Timeslot.day == data["day"], Timeslot.slot_index == data["slot_index"]).first()
        if item is None:
            model = {"teachers": Teacher, "sections": Section, "courses": Course, "rooms": Room, "timeslots": Timeslot}[entity]
            db.add(model(**data))
            created += 1
        else:
            for key, value in data.items():
                setattr(item, key, value)
            updated += 1
    return created, updated


@router.post("/estimate-section-strengths", dependencies=[Depends(require_coordinator)])
def apply_estimated_section_strengths(db: Session = Depends(get_db)):
    """Apply the user-approved 60–65 planning estimate to CSE sections.

    This is labelled as an estimate in the API/UI. Official enrolment values
    entered later through Sections always replace it.
    """
    strengths = [60, 61, 62, 63, 64, 65]
    sections = (
        db.query(Section)
        .filter(Section.active == True, Section.program == "CSE")
        .order_by(Section.semester, Section.name)
        .all()
    )
    if not sections:
        raise HTTPException(422, "No active CSE sections are available to update")
    for index, section in enumerate(sections):
        section.strength = strengths[index % len(strengths)]
    db.commit()
    return {
        "message": "Estimated planning strengths of 60–65 were applied to all active CSE sections.",
        "updated": len(sections),
        "range": "60–65",
        "note": "Replace these estimates with official enrolment once available.",
    }


@router.post("/{entity}", dependencies=[Depends(require_coordinator)])
async def import_records(entity: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Create/update master data from a CSV or first worksheet of an XLSX file."""
    if entity not in SUPPORTED_ENTITIES:
        raise HTTPException(404, "This type of data cannot be imported")
    filename = file.filename or "upload"
    content = await file.read()
    if not content:
        raise HTTPException(422, "Choose a file that contains data")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "The import file is larger than 10 MB")
    try:
        rows = _parse_file(filename, content)
        records, errors = _prepare_rows(entity, rows, db)
    except ValueError as exc:
        raise HTTPException(422, {"message": "Import rejected. No data was saved.", "errors": [str(exc)]}) from exc
    if errors:
        raise HTTPException(422, {"message": "Import rejected. No data was saved.", "errors": errors[:25]})

    try:
        created, updated = _upsert(entity, records, db)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(422, {"message": "Import could not be saved. No data was changed.", "errors": [str(exc)]}) from exc
    return {
        "entity": entity,
        "created": created,
        "updated": updated,
        "total": len(records),
        "message": f"{len(records)} {entity} imported: {created} added, {updated} updated.",
    }
