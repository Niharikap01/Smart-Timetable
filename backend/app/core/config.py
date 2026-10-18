from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# Anchor paths to this file's location (backend/app/core/config.py -> backend/),
# not to the current working directory. Without this, running
# `python scripts/seed_database.py` from the project root and
# `uvicorn app.main:app` from backend/ silently create/read TWO DIFFERENT
# SQLite files (each relative to wherever the process happened to be
# launched from), which looks exactly like "no such table" errors even
# though seeding succeeded.
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Database – defaults to SQLite for zero-config local dev, always at
    # backend/smart_timetable.db regardless of the process's CWD.
    # Set DATABASE_URL in .env to use MySQL/PostgreSQL instead.
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'smart_timetable.db'}"

    # Auth
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Scheduler
    SCHEDULER_TIMEOUT_SECONDS: int = 30
    SCHEDULER_MAX_RESTARTS: int = 5
    SCHEDULER_DEBUG: bool = False

    # Constraint Configuration (configurable / pending confirmation)
    MAX_LECTURE_PERIODS_PER_DAY: int = 5
    MAX_SECTION_DAILY_HOURS: int = 6
    # The supplied CSE-V reference timetable uses compact three-period theory
    # runs (for example, Wednesday DP → SE → CC).  Allowing three periods
    # follows that departmental pattern while still preventing long stacks.
    MAX_CONSECUTIVE_PERIODS: int = 3
    RECESS_START: str = "11:00"
    RECESS_END: str = "13:00"
    # Slot 4 is 12:00–13:00 when the normal 08:00 master pattern is used.
    # A section may have later classes, but its first class on an active day
    # cannot begin at 13:00 or later.
    MAX_SECTION_START_SLOT: int = 4
    MAX_SECTION_START_TIME: str = "12:00"
    MAX_TEACHER_DAILY_HOURS: int = 7
    HONOURS_RESERVED_ENABLED: bool = False
    SENIOR_FACULTY_CONSTRAINT_MODE: str = "SOFT"  # HARD | SOFT | DISABLED

    # CORS
    # 5174 is the isolated development frontend for this project. Keeping
    # 5173 preserves compatibility if no other Vite project is running.
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:5174"]

    model_config = {
        "env_file": str(BACKEND_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
