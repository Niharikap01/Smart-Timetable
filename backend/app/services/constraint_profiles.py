"""Load and version the coordinator-managed solver settings."""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.constraint_profile import ConstraintProfile


def default_constraint_values() -> dict:
    return {
        "MAX_LECTURE_PERIODS_PER_DAY": settings.MAX_LECTURE_PERIODS_PER_DAY,
        "MAX_SECTION_DAILY_HOURS": settings.MAX_SECTION_DAILY_HOURS,
        "MAX_CONSECUTIVE_PERIODS": settings.MAX_CONSECUTIVE_PERIODS,
        "MAX_TEACHER_DAILY_HOURS": settings.MAX_TEACHER_DAILY_HOURS,
        "LATEST_SECTION_START_TIME": settings.MAX_SECTION_START_TIME,
    }


def get_current_profile(db: Session, create_if_missing: bool = True) -> ConstraintProfile:
    profile = db.query(ConstraintProfile).order_by(ConstraintProfile.version.desc()).first()
    if profile is not None or not create_if_missing:
        return profile

    profile = ConstraintProfile(
        version=1,
        config=default_constraint_values(),
        change_reason="Initial system defaults",
        changed_by_user_id=None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def save_profile(db: Session, config: dict, reason: str, changed_by_user_id: int) -> ConstraintProfile:
    current = get_current_profile(db)
    profile = ConstraintProfile(
        version=current.version + 1,
        config=config,
        change_reason=reason,
        changed_by_user_id=changed_by_user_id,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
