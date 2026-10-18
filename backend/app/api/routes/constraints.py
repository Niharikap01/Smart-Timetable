from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_coordinator
from app.database.session import get_db
from app.models.user import User
from app.schemas.constraint_profile import ConstraintProfileResponse, ConstraintProfileUpdate
from app.services.constraint_profiles import get_current_profile, save_profile

router = APIRouter(prefix="/api/constraints", tags=["constraints"])

EDITABLE_CONSTRAINTS = [
    {
        "key": "MAX_LECTURE_PERIODS_PER_DAY",
        "code": "C10",
        "label": "Maximum lecture periods per section per day",
        "minimum": 1,
        "maximum": 24,
        "unit": "periods",
    },
    {
        "key": "MAX_SECTION_DAILY_HOURS",
        "code": "C12",
        "label": "Maximum scheduled periods per section per day",
        "minimum": 1,
        "maximum": 24,
        "unit": "periods",
    },
    {
        "key": "MAX_CONSECUTIVE_PERIODS",
        "code": "C11",
        "label": "Maximum consecutive periods without a break",
        "minimum": 1,
        "maximum": 24,
        "unit": "periods",
    },
    {
        "key": "MAX_TEACHER_DAILY_HOURS",
        "code": "C17",
        "label": "Maximum teaching periods per teacher per day",
        "minimum": 1,
        "maximum": 24,
        "unit": "periods",
    },
    {
        "key": "LATEST_SECTION_START_TIME",
        "code": "C20",
        "label": "Latest allowed first-class start time",
        "unit": "time",
    },
]


def _serialize(profile) -> dict:
    return {
        "version": profile.version,
        "config": profile.config,
        "change_reason": profile.change_reason,
        "created_at": profile.created_at,
    }


@router.get("/config")
def read_constraint_config(
    db: Session = Depends(get_db),
    _coordinator: User = Depends(require_coordinator),
):
    profile = get_current_profile(db)
    return {**_serialize(profile), "editable_constraints": EDITABLE_CONSTRAINTS}


@router.put("/config", response_model=ConstraintProfileResponse)
def update_constraint_config(
    data: ConstraintProfileUpdate,
    db: Session = Depends(get_db),
    coordinator: User = Depends(require_coordinator),
):
    if data.MAX_LECTURE_PERIODS_PER_DAY > data.MAX_SECTION_DAILY_HOURS:
        raise HTTPException(
            status_code=422,
            detail="The daily lecture limit cannot exceed the section's total daily limit.",
        )
    if data.MAX_CONSECUTIVE_PERIODS > data.MAX_SECTION_DAILY_HOURS:
        raise HTTPException(
            status_code=422,
            detail="The consecutive-period limit cannot exceed the section's daily limit.",
        )

    config = data.model_dump(exclude={"change_reason"})
    profile = save_profile(db, config, data.change_reason, coordinator.id)
    return _serialize(profile)
