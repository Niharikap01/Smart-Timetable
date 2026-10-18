from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.section import Section
from app.schemas.section import SectionCreate, SectionUpdate, SectionResponse

router = APIRouter(prefix="/api/sections", tags=["sections"])


@router.get("/", response_model=List[SectionResponse])
def list_sections(semester: Optional[int] = None, program: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Section)
    if semester:
        q = q.filter(Section.semester == semester)
    if program:
        q = q.filter(Section.program == program)
    return q.all()


@router.get("/{section_id}", response_model=SectionResponse)
def get_section(section_id: int, db: Session = Depends(get_db)):
    s = db.query(Section).get(section_id)
    if not s:
        raise HTTPException(404, "Section not found")
    return s


@router.post("/", response_model=SectionResponse, status_code=201, dependencies=[Depends(require_coordinator)])
def create_section(data: SectionCreate, db: Session = Depends(get_db)):
    if db.query(Section).filter(Section.name == data.name).first():
        raise HTTPException(409, "Section name already exists")
    s = Section(**data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/{section_id}", response_model=SectionResponse, dependencies=[Depends(require_coordinator)])
def update_section(section_id: int, data: SectionUpdate, db: Session = Depends(get_db)):
    s = db.query(Section).get(section_id)
    if not s:
        raise HTTPException(404, "Section not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{section_id}", dependencies=[Depends(require_coordinator)])
def delete_section(section_id: int, db: Session = Depends(get_db)):
    s = db.query(Section).get(section_id)
    if not s:
        raise HTTPException(404, "Section not found")
    s.active = False
    db.commit()
    return {"success": True, "message": "Section deactivated"}
