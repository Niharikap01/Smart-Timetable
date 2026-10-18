from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String

from app.database.session import Base


class ConstraintProfile(Base):
    """Immutable history of coordinator-approved solver settings."""

    __tablename__ = "constraint_profiles"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, nullable=False, unique=True, index=True)
    config = Column(JSON, nullable=False)
    change_reason = Column(String(500), nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
