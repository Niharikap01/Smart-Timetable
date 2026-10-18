"""Translate the coordinator's teaching-load workbook into scheduler records.

The college workbook is deliberately not treated as a generic CSV.  Its three
sheets describe a curriculum, faculty loads, and subject-wise allocations in
separate layouts.  This module reads that structure without depending on
Excel/Pandas at runtime and returns only assignments that are explicit in the
source.  Ambiguous laboratory/batch rows are reported for review rather than
invented.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
import math
import re
from typing import Any
import zipfile
from xml.etree import ElementTree as ET


XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SEMESTERS = {"I": 1, "III": 3, "V": 5, "VII": 7}
FACULTY_PATTERN = re.compile(r"(?:DR\.?\s*)?(FACULTY_\d+)", re.IGNORECASE)
SECTION_PATTERN = re.compile(r"\b([A-Z])\s*[- ]?\s*(\d{1,2})\b", re.IGNORECASE)


@dataclass
class TeachingLoadPlan:
    teachers: dict[str, dict[str, str]] = field(default_factory=dict)
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    courses: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    curriculum_course_count: int = 0
    source_section_count: int = 0


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _column_index(cell_ref: str) -> int:
    match = re.match(r"[A-Z]+", cell_ref or "")
    if not match:
        return 0
    index = 0
    for char in match.group(0):
        index = index * 26 + ord(char) - 64
    return index - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.iter(f"{{{XLSX_NS}}}t")) for item in root]


def _xlsx_sheets(content: bytes) -> dict[str, list[tuple[int, list[str]]]]:
    """Read every worksheet as sparse-but-aligned row values."""
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            strings = _shared_strings(archive)
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            targets = {
                relation.attrib.get("Id"): relation.attrib.get("Target", "")
                for relation in relations.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
            }
            result: dict[str, list[tuple[int, list[str]]]] = {}
            for sheet in workbook.findall(f"{{{XLSX_NS}}}sheets/{{{XLSX_NS}}}sheet"):
                name = sheet.attrib.get("name", "")
                relationship_id = sheet.attrib.get(f"{{{DOC_REL_NS}}}id")
                target = targets.get(relationship_id, "")
                path = target.lstrip("/") if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
                root = ET.fromstring(archive.read(path))
                rows: list[tuple[int, list[str]]] = []
                for row in root.findall(f".//{{{XLSX_NS}}}sheetData/{{{XLSX_NS}}}row"):
                    cells: dict[int, str] = {}
                    for cell in row.findall(f"{{{XLSX_NS}}}c"):
                        cell_type = cell.attrib.get("t")
                        raw_value = cell.findtext(f"{{{XLSX_NS}}}v", default="")
                        if cell_type == "s" and raw_value:
                            value = strings[int(raw_value)] if int(raw_value) < len(strings) else ""
                        elif cell_type == "inlineStr":
                            value = "".join(node.text or "" for node in cell.iter(f"{{{XLSX_NS}}}t"))
                        else:
                            value = raw_value
                        cells[_column_index(cell.attrib.get("r", ""))] = value
                    if cells:
                        rows.append((int(row.attrib.get("r", len(rows) + 1)), [cells.get(i, "") for i in range(max(cells) + 1)]))
                result[name] = rows
            return result
    except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError, IndexError) as exc:
        raise ValueError(f"Unable to read the coordinator workbook: {exc}") from exc


def _cell(row: list[str], index: int) -> str:
    return _clean(row[index]) if index < len(row) else ""


def _integer(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _semester(value: str) -> int | None:
    normalized = _clean(value).upper().replace("SEMESTER", "").strip()
    if normalized.isdigit():
        return int(normalized)
    for roman, number in SEMESTERS.items():
        if re.search(rf"\b{roman}\b", normalized):
            return number
    return None


def _year_for_semester(semester: int) -> int:
    return (semester + 1) // 2


def _section_name(semester: int, label: str) -> str:
    return f"CSE-{semester}{label.upper()}"


def _faculty_key(value: str) -> str:
    return _clean(value).upper()


def _extract_faculty(value: str) -> list[str]:
    return [_faculty_key(match.group(1)) for match in FACULTY_PATTERN.finditer(value)]


def _extract_sections(value: str) -> list[str]:
    return [f"{match.group(1).upper()}{match.group(2)}" for match in SECTION_PATTERN.finditer(value)]


def parse_explicit_allocations(value: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """Return faculty-to-section assignments only where the source is clear.

    A typical coordinator cell is ``Faculty_068 (2) [A2, A7]``.  When one
    bracket group has two faculty labels (often theory faculty + TA), the file
    does not identify who owns the sections, so it is intentionally reported
    as unresolved.
    """
    text = _clean(value)
    assignments: list[tuple[str, list[str]]] = []
    problems: list[str] = []
    brackets = list(re.finditer(r"\[([^\]]+)\]", text))
    if not brackets:
        if _extract_faculty(text):
            problems.append("no explicit section list")
        return assignments, problems

    last_end = 0
    for bracket in brackets:
        segment = text[last_end:bracket.start()]
        faculty = _extract_faculty(segment)
        sections = _extract_sections(bracket.group(1))
        if len(faculty) != 1:
            problems.append("ambiguous faculty-to-section mapping")
        elif not sections:
            problems.append("section list could not be read")
        else:
            assignments.append((faculty[0], sections))
        last_end = bracket.end()
    return assignments, problems


def _find_header(rows: list[tuple[int, list[str]]], required: str) -> int:
    for index, (_, row) in enumerate(rows):
        if any(required in _clean(value).lower().replace("\n", " ") for value in row):
            return index
    raise ValueError(f"The workbook is missing a '{required}' header")


def _curriculum(rows: list[tuple[int, list[str]]]) -> dict[tuple[int, str], dict[str, Any]]:
    header = _find_header(rows, "course")
    current_semester: int | None = None
    catalogue: dict[tuple[int, str], dict[str, Any]] = {}
    for _, row in rows[header + 1:]:
        possible_semester = _semester(_cell(row, 0))
        if possible_semester:
            current_semester = possible_semester
        code = _cell(row, 1)
        name = _cell(row, 2)
        if not current_semester or not code or not name:
            continue
        catalogue[(current_semester, code.upper())] = {
            "name": name,
            "lecture_hours": _integer(_cell(row, 3)),
            "practical_hours": _integer(_cell(row, 4)),
        }
    return catalogue


def _add_section(plan: TeachingLoadPlan, semester: int, label: str) -> None:
    name = _section_name(semester, label)
    plan.sections.setdefault(name, {
        "name": name,
        "semester": semester,
        "year": _year_for_semester(semester),
        # The coordinator workbook does not include enrolment.  Zero makes
        # that missing prerequisite visible to preflight rather than guessing.
        "strength": 0,
        "program": "CSE",
    })


def _add_faculty(plan: TeachingLoadPlan, employee_id: str) -> None:
    employee_id = _faculty_key(employee_id)
    local_part = employee_id.lower()
    plan.teachers.setdefault(employee_id, {
        "employee_id": employee_id,
        "name": employee_id.replace("_", " ").title(),
        # The anonymized source has no official email address.  This local
        # placeholder lets the required field remain valid until admin update.
        "email": f"{local_part}@coordinator-import.local",
    })


def build_teaching_load_plan(content: bytes) -> TeachingLoadPlan:
    sheets = _xlsx_sheets(content)
    curriculum_sheet = next((name for name in sheets if name.strip() == "2026-27"), None)
    subject_sheet = next((name for name in sheets if "subject" in name.lower()), None)
    faculty_sheet = next((name for name in sheets if "faculty" in name.lower()), None)
    if not curriculum_sheet or not subject_sheet:
        raise ValueError("Expected curriculum and subject-wise worksheets were not found")

    catalogue = _curriculum(sheets[curriculum_sheet])
    plan = TeachingLoadPlan(curriculum_course_count=len(catalogue))

    # The faculty-wise sheet is useful for building the anonymized faculty
    # roster even where a teaching-load row lacks a section list.
    for rows in (sheets[subject_sheet], sheets[faculty_sheet] if faculty_sheet else []):
        for _, row in rows:
            for faculty in _extract_faculty(" ".join(row)):
                _add_faculty(plan, faculty)

    rows = sheets[subject_sheet]
    header = _find_header(rows, "course code")
    current: dict[str, Any] = {}
    sections_per_semester: dict[int, int] = defaultdict(int)

    for row_number, row in rows[header + 1:]:
        semester = _semester(_cell(row, 1)) or current.get("semester")
        section_count = _integer(_cell(row, 2))
        if semester and section_count:
            sections_per_semester[semester] = max(sections_per_semester[semester], section_count)

        code = _cell(row, 3)
        name = _cell(row, 4)
        teaching_mode = _cell(row, 5).upper()
        allocation = _cell(row, 6)
        if code or (name and teaching_mode):
            current = {
                "semester": semester,
                "code": code.upper() or current.get("code", ""),
                "name": name or current.get("name", ""),
                "mode": teaching_mode or current.get("mode", ""),
            }
        elif semester:
            current["semester"] = semester

        if not allocation or not current.get("semester") or not current.get("code"):
            continue

        explicit, problems = parse_explicit_allocations(allocation)
        if not explicit:
            if problems:
                plan.unresolved.append(
                    f"Row {row_number}: Semester {current['semester']} · {current['name'] or current['code']} — {', '.join(problems)}."
                )
            continue

        curriculum = catalogue.get((current["semester"], current["code"]))
        if not curriculum:
            plan.unresolved.append(
                f"Row {row_number}: {current['code']} has an explicit allocation but no matching curriculum course code."
            )
            continue

        is_lab = current.get("mode", "").startswith(("P", "L")) or "lab" in current.get("name", "").lower()
        weekly_hours = curriculum["practical_hours"] if is_lab else curriculum["lecture_hours"]
        if weekly_hours <= 0:
            plan.unresolved.append(
                f"Row {row_number}: {current['name'] or current['code']} has no {'practical' if is_lab else 'lecture'} hours in the curriculum."
            )
            continue
        duration = 2 if is_lab and weekly_hours >= 2 else 1
        weekly_sessions = math.ceil(weekly_hours / duration)
        for faculty, section_labels in explicit:
            _add_faculty(plan, faculty)
            for section_label in section_labels:
                _add_section(plan, current["semester"], section_label)
                section_name = _section_name(current["semester"], section_label)
                key = (current["code"], section_name, "lab" if is_lab else "lecture")
                offering = {
                    "course_code": current["code"],
                    "course_name": curriculum["name"],
                    "course_type": "lab" if is_lab else "lecture",
                    "weekly_sessions": weekly_sessions,
                    "duration": duration,
                    "section_name": section_name,
                    "teacher_employee_id": faculty,
                    "required_room_type": "lab" if is_lab else "lecture",
                    "priority": 8 if is_lab else 5,
                }
                existing = plan.courses.get(key)
                if existing and existing["teacher_employee_id"] != faculty:
                    plan.unresolved.append(
                        f"Row {row_number}: {current['code']} has more than one faculty allocation for {section_name}."
                    )
                else:
                    plan.courses[key] = offering

    for semester, count in sections_per_semester.items():
        for number in range(1, count + 1):
            _add_section(plan, semester, f"A{number}")
    plan.source_section_count = sum(sections_per_semester.values())
    return plan
