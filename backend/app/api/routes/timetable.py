from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
from app.database.session import get_db
from app.core.security import require_coordinator
from app.models.timetable import GeneratedSchedule, TimetableSession
from app.schemas.timetable import (
    GeneratedScheduleResponse, GeneratedScheduleDetailResponse,
    TimetableSessionResponse, GenerateRequest, GenerateResultResponse,
)

router = APIRouter(prefix="/api/timetable", tags=["timetable"])


class PreviewMoveRequest(BaseModel):
    session_id: int
    day: str
    slot_index: int
    room_id: Optional[int] = None
    teacher_id: Optional[int] = None


class ApplyMoveRequest(BaseModel):
    session_id: int
    day: str
    slot_index: int
    room_id: Optional[int] = None
    teacher_id: Optional[int] = None


class PreviewSwapRequest(BaseModel):
    a_session_id: int
    b_session_id: int


class ApplySwapRequest(BaseModel):
    a_session_id: int
    b_session_id: int


@router.get("/", response_model=List[GeneratedScheduleResponse])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(GeneratedSchedule).order_by(GeneratedSchedule.generated_at.desc()).all()


@router.get("/{schedule_id}", response_model=GeneratedScheduleDetailResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(GeneratedSchedule).get(schedule_id)
    if not s:
        raise HTTPException(404, "Schedule not found")
    return s


@router.post("/generate", response_model=GenerateResultResponse, dependencies=[Depends(require_coordinator)])
def generate_timetable(req: GenerateRequest, db: Session = Depends(get_db)):
    from app.services.scheduler_service import run_scheduler
    result = run_scheduler(
        db, timeout=req.timeout_seconds, enable_optimization=req.enable_optimization,
        semester=req.semester,
    )
    return result


@router.get("/section/{section_id}", response_model=List[TimetableSessionResponse])
def get_section_timetable(section_id: int, db: Session = Depends(get_db)):
    latest = db.query(GeneratedSchedule).filter(
        GeneratedSchedule.status == "VALID",
        GeneratedSchedule.is_stale.is_(False),
    ).order_by(GeneratedSchedule.generated_at.desc()).first()
    if not latest:
        raise HTTPException(404, "No valid schedule found")
    return db.query(TimetableSession).filter(
        TimetableSession.generated_schedule_id == latest.id,
        TimetableSession.section_id == section_id,
    ).all()


@router.get("/teacher/{teacher_id}", response_model=List[TimetableSessionResponse])
def get_teacher_timetable(teacher_id: int, db: Session = Depends(get_db)):
    latest = db.query(GeneratedSchedule).filter(
        GeneratedSchedule.status == "VALID",
        GeneratedSchedule.is_stale.is_(False),
    ).order_by(GeneratedSchedule.generated_at.desc()).first()
    if not latest:
        raise HTTPException(404, "No valid schedule found")
    rows = db.query(TimetableSession).options(joinedload(TimetableSession.course)).filter(
        TimetableSession.generated_schedule_id == latest.id,
    ).all()
    return [session for session in rows if teacher_id in session.teacher_ids]


@router.get("/room/{room_id}", response_model=List[TimetableSessionResponse])
def get_room_timetable(room_id: int, db: Session = Depends(get_db)):
    latest = db.query(GeneratedSchedule).filter(
        GeneratedSchedule.status == "VALID",
        GeneratedSchedule.is_stale.is_(False),
    ).order_by(GeneratedSchedule.generated_at.desc()).first()
    if not latest:
        raise HTTPException(404, "No valid schedule found")
    return db.query(TimetableSession).filter(
        TimetableSession.generated_schedule_id == latest.id,
        TimetableSession.room_id == room_id,
    ).all()


# ── Coordinator inline editing (constraint-checked, vacancy-synced) ──────────

@router.get("/latest/id")
def get_latest_schedule_id(db: Session = Depends(get_db)):
    latest = db.query(GeneratedSchedule).filter(
        GeneratedSchedule.status == "VALID",
        GeneratedSchedule.is_stale.is_(False),
    ).order_by(GeneratedSchedule.generated_at.desc()).first()
    if not latest:
        raise HTTPException(404, "No valid schedule found")
    return {"schedule_id": latest.id}


@router.post("/latest/preview-move")
def preview_move(req: PreviewMoveRequest, db: Session = Depends(get_db)):
    from app.services.timetable_editor import preview_move as do_preview, latest_valid_schedule
    schedule = latest_valid_schedule(db)
    if not schedule:
        raise HTTPException(404, "No valid schedule to edit")
    return do_preview(db, schedule, req.session_id, req.day, req.slot_index, req.room_id, req.teacher_id)


@router.post("/latest/move", dependencies=[Depends(require_coordinator)])
def apply_move(req: ApplyMoveRequest, db: Session = Depends(get_db)):
    from app.services.timetable_editor import apply_move as do_move, latest_valid_schedule
    schedule = latest_valid_schedule(db)
    if not schedule:
        raise HTTPException(404, "No valid schedule to edit")
    result = do_move(db, schedule, req.session_id, req.day, req.slot_index, req.room_id, req.teacher_id)
    if not result.get("valid"):
        raise HTTPException(422, detail=result)
    return result


@router.post("/latest/preview-swap")
def preview_swap(req: PreviewSwapRequest, db: Session = Depends(get_db)):
    from app.services.timetable_editor import preview_swap as do_preview, latest_valid_schedule
    schedule = latest_valid_schedule(db)
    if not schedule:
        raise HTTPException(404, "No valid schedule to edit")
    return do_preview(db, schedule, req.a_session_id, req.b_session_id)


@router.post("/latest/swap", dependencies=[Depends(require_coordinator)])
def apply_swap(req: ApplySwapRequest, db: Session = Depends(get_db)):
    from app.services.timetable_editor import apply_swap as do_swap, latest_valid_schedule
    schedule = latest_valid_schedule(db)
    if not schedule:
        raise HTTPException(404, "No valid schedule to edit")
    result = do_swap(db, schedule, req.a_session_id, req.b_session_id)
    if not result.get("valid"):
        raise HTTPException(422, detail=result)
    return result


@router.get("/latest/sessions", response_model=List[TimetableSessionResponse])
def get_latest_sessions(db: Session = Depends(get_db)):
    from app.services.timetable_editor import latest_valid_schedule
    schedule = latest_valid_schedule(db)
    if not schedule:
        raise HTTPException(404, "No valid schedule found")
    return db.query(TimetableSession).filter(
        TimetableSession.generated_schedule_id == schedule.id
    ).all()


@router.post("/latest/undo", dependencies=[Depends(require_coordinator)])
def undo_last_edit(db: Session = Depends(get_db)):
    """Undo by snapshot? Minimal: coordinator can regenerate. This endpoint
    exists as a fast 'revert last move/swap' is not auto-tracked server-side;
    frontend keeps its own undo stack. Returns latest sessions for refresh."""
    from app.services.timetable_editor import latest_valid_schedule
    schedule = latest_valid_schedule(db)
    if not schedule:
        raise HTTPException(404, "No valid schedule found")
    sessions = db.query(TimetableSession).filter(
        TimetableSession.generated_schedule_id == schedule.id
    ).all()
    return {"schedule_id": schedule.id, "sessions": [TimetableSessionResponse.model_validate(s).model_dump() for s in sessions]}
