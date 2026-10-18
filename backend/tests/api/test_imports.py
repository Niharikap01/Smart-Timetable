"""Tests for validated master-data spreadsheet/CSV imports."""
from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.models import Course, Section, Teacher
from app.api.routes.imports import _parse_csv, _parse_xlsx, _prepare_rows, _time, _upsert


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
              <Relationship Id="rId1" Target="worksheets/sections.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
            </Relationships>''')
        archive.writestr("xl/worksheets/sections.xml", '''<?xml version="1.0"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
              <row r="1"><c r="A1" t="inlineStr"><is><t>name</t></is></c><c r="B1" t="inlineStr"><is><t>semester</t></is></c></row>
              <row r="2"><c r="A2" t="inlineStr"><is><t>CSE-5A1</t></is></c><c r="B2"><v>5</v></c></row>
            </sheetData></worksheet>''')

    assert _parse_xlsx(workbook.getvalue()) == [(2, {"name": "CSE-5A1", "semester": "5"})]


def test_import_accepts_excel_serial_time_values():
    assert _time("0.375", "Start time") == "09:00:00"
