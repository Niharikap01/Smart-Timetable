"""Tests for validated master-data spreadsheet/CSV imports."""
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.models import Course, Section, Teacher
from app.api.routes.imports import (
    _link_parallel_batch_labs, _parse_csv, _parse_xlsx, _prepare_rows, _time, _upsert,
)
from app.services.teaching_load_import import _xlsx_sheets


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return session, engine


def test_import_csv_upserts_master_data_and_resolves_course_references():
    db, engine = _db_session()
    try:
        teacher_rows = _parse_csv(b"name,employee_id,email,faculty_type,max_daily_hours\nDr. Priya Sharma,CSE101,priya@college.edu,regular,7\n")
        records, errors = _prepare_rows("teachers", teacher_rows, db)
        assert not errors
        assert _upsert("teachers", records, db) == (1, 0)
        db.commit()

        section_rows = _parse_csv(b"name,semester,strength,program,year\nCSE-5A1,5,60,CSE,3\n")
        records, errors = _prepare_rows("sections", section_rows, db)
        assert not errors
        assert _upsert("sections", records, db) == (1, 0)
        db.commit()

        course_rows = _parse_csv(
            b"course_code,course_name,course_type,credits,duration,section,teacher_employee_id,required_room_type,priority\n"
            b"24CS01TH0501,Machine Learning,lecture,3,1,CSE-5A1,CSE101,lecture,5\n"
        )
        records, errors = _prepare_rows("courses", course_rows, db)
        assert not errors
        assert _upsert("courses", records, db) == (1, 0)
        db.commit()

        course = db.query(Course).one()
        assert course.weekly_sessions == 3
        assert course.section.name == "CSE-5A1"
        assert course.teacher.employee_id == "CSE101"

        # Uploading the same natural key updates rather than duplicates it.
        updated_rows = _parse_csv(b"name,employee_id,email,faculty_type,max_daily_hours\nDr. Priya Sharma,CSE101,priya@college.edu,senior,6\n")
        records, errors = _prepare_rows("teachers", updated_rows, db)
        assert not errors
        assert _upsert("teachers", records, db) == (0, 1)
        db.commit()
        assert db.query(Teacher).one().max_daily_hours == 6
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_import_reports_invalid_rows_before_anything_is_saved():
    db, engine = _db_session()
    try:
        rows = _parse_csv(b"name,semester,strength,program,year\nCSE-5A1,5,60,CSE,3\nCSE-5A2,5,not-a-number,CSE,3\n")
        records, errors = _prepare_rows("sections", rows, db)
        assert len(records) == 1
        assert errors == ["Row 3: Strength must be a whole number"]
        # The route does not call _upsert when errors exist, so this empty
        # database remains untouched by the rejected file.
        assert db.query(Section).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_import_reads_the_first_excel_worksheet():
    """A real .xlsx is a ZIP of XML files; exercise that parser without files."""
    workbook = BytesIO()
    with ZipFile(workbook, "w") as archive:
        archive.writestr("xl/workbook.xml", '''<?xml version="1.0"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Sections" sheetId="1" r:id="rId1"/></sheets>
            </workbook>''')
        archive.writestr("xl/_rels/workbook.xml.rels", '''<?xml version="1.0"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Target="/xl/worksheets/sections.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
            </Relationships>''')
        archive.writestr("xl/worksheets/sections.xml", '''<?xml version="1.0"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
              <row r="1"><c r="A1" t="inlineStr"><is><t>name</t></is></c><c r="B1" t="inlineStr"><is><t>semester</t></is></c></row>
              <row r="2"><c r="A2" t="inlineStr"><is><t>CSE-5A1</t></is></c><c r="B2"><v>5</v></c></row>
            </sheetData></worksheet>''')

    assert _parse_xlsx(workbook.getvalue()) == [(2, {"name": "CSE-5A1", "semester": "5"})]
    assert _xlsx_sheets(workbook.getvalue())["Sections"] == [
        (1, ["name", "semester"]),
        (2, ["CSE-5A1", "5"]),
    ]


def test_import_accepts_excel_serial_time_values():
    assert _time("0.375", "Start time") == "09:00:00"


def test_parallel_batch_labs_pair_different_subjects_when_same_subject_faculty_overlap():
    offerings = [
        SimpleNamespace(id=1, section_id=5, course_code="LAB-A", batch_label="B1/B2", link_group=None,
                        weekly_sessions=1, duration=2, teacher_id=1, teacher_ids=[1]),
        SimpleNamespace(id=2, section_id=5, course_code="LAB-B", batch_label="B1/B2", link_group=None,
                        weekly_sessions=1, duration=2, teacher_id=2, teacher_ids=[2]),
        SimpleNamespace(id=3, section_id=5, course_code="LAB-A", batch_label="B3/B4", link_group=None,
                        weekly_sessions=1, duration=2, teacher_id=1, teacher_ids=[1]),
        SimpleNamespace(id=4, section_id=5, course_code="LAB-B", batch_label="B3/B4", link_group=None,
                        weekly_sessions=1, duration=2, teacher_id=2, teacher_ids=[2]),
    ]

    _link_parallel_batch_labs({5: offerings})

    groups = {}
    for course in offerings:
        groups.setdefault(course.link_group, []).append(course)
    assert len(groups) == 2
    assert all({course.batch_label for course in group} == {"B1/B2", "B3/B4"} for group in groups.values())
    assert all(set(group[0].teacher_ids).isdisjoint(group[1].teacher_ids) for group in groups.values())
    assert all(len({course.course_code for course in group}) == 2 for group in groups.values())


def test_parallel_batch_lab_import_rejects_unavoidable_faculty_overlap():
    offerings = [
        SimpleNamespace(id=1, section_id=5, course_code="LAB-A", batch_label="B1/B2", link_group=None,
                        weekly_sessions=1, duration=2, teacher_id=7, teacher_ids=[7]),
        SimpleNamespace(id=2, section_id=5, course_code="LAB-A", batch_label="B3/B4", link_group=None,
                        weekly_sessions=1, duration=2, teacher_id=7, teacher_ids=[7]),
    ]

    with pytest.raises(ValueError, match="faculty clash"):
        _link_parallel_batch_labs({5: offerings})
