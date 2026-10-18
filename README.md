# Smart Department Timetable, Classroom Allotment & Real-Time Vacancy System

An automated scheduling platform that replaces manual timetable creation with a CSP-based engine, assigns classrooms jointly with timeslots, validates 20 hard constraints, and provides real-time vacancy tracking via WebSockets.

## Features

- **CSP Scheduling Engine** — backtracking solver with bitmask occupancy (O(1) conflict detection), MRV heuristic, forward checking, bounded restart, configurable timeout
- **20 Hard Constraints** — independently testable, modular constraint architecture
- **Soft Constraint Optimization** — 7 weighted quality metrics
- **Real-Time Vacancy** — in-memory occupancy cache + WebSocket broadcast
- **Admin Interface** — full CRUD plus transactional CSV/Excel imports for teachers, sections, courses, rooms, and timeslots
- **Timetable Views** — section, teacher, room views with print support
- **Vacancy Dashboard** — live room status cards with filters and search

## Architecture

```
React (Vite) → REST API / WebSocket → FastAPI → SQLite by default (MySQL optional)
                                        ├── CSP Solver (bitmask + MRV + forward checking)
                                        ├── 20 Constraint Modules
                                        ├── Soft Scorer / Optimizer
                                        └── Vacancy Cache + WebSocket Manager
```

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2
- **Frontend:** React, Vite, React Router, Axios, Recharts
- **Database:** SQLite for local use; MySQL can be configured for deployment
- **Real-time:** FastAPI WebSocket
- **Testing:** pytest

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- MySQL 8.0+

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
```

The default local database is `backend/smart_timetable.db`; no MySQL setup is
needed. To use MySQL in deployment, set `DATABASE_URL` in `backend/.env`.

### 2. Seed Database (verified CSE-V reference data)
```bash
python scripts/seed_database.py
```

The seed creates A1-A9 structurally. It assigns courses only to A2, A3, A5,
A7 and A9 because those are the sections present in the supplied workbook.
Room capacities and section strengths remain `0` until verified departmental
values are entered, so the system does not present invented values as official.

### Optional: load fictional demo data for testing
```bash
python scripts/seed_demo_data.py
```

This replaces the current local data with clearly labelled fictional CSE-V
records: 9 sections, classrooms/labs with capacities, a 09:00–17:00 academic
day, lunch reservations, fixed MDM periods, faculty availability, and 144
session records. Three-credit subjects are scheduled three times per week;
one-credit subjects once; paired practical batches use one contiguous two-hour
laboratory slot.
It is only for testing the generator before official college data is entered.
Use **Academic balance → Balanced week (recommended)** on the Generate page;
this spreads each section's workload across teaching days before filling extra
periods adjacent to existing classes.

### Importing official college data

Each of the **Faculty**, **Sections**, **Courses**, **Rooms**, and
**Timeslots** pages includes **Download CSV template** and **Import CSV /
Excel** controls. A file is checked completely before anything is saved, then
matching records are updated rather than duplicated. Import in this order:

1. Faculty, Sections, Rooms, Timeslots
2. Courses — use the section name and faculty `employee_id` from the earlier files

For courses, the `credits` column means the number of lectures required each
week. Recess/lunch blocks are added through Reserved Slots and appear as
visible RECESS cells in a section timetable.

### Importing the coordinator teaching-load workbook

The **Courses** page has an **Import coordinator workbook** control for the
three-sheet CSE teaching-load layout supplied by the department. It reads:

- `2026-27`: course codes, names, and weekly lecture/practical hours
- `FINAL_FacultyWise`: anonymized faculty roster and declared load records
- `FINAL_Subject wise`: semester/section counts plus explicit faculty-to-section assignments

The import creates CSE-I, CSE-III, CSE-V, and CSE-VII section records, faculty
records, and only course offerings whose faculty and section are explicitly
mapped in the source. It preserves existing verified section strengths and
faculty contact details.

The source workbook does **not** provide student strengths, room capacities,
timeslots, faculty availability, or a complete lab-batch-to-section map. The
system therefore reports those unresolved rows instead of inventing schedules.
After this import, complete the standard Sections, Rooms, Timeslots, and
Courses inputs for the reported rows before generating the departmental
timetable.

### 3. Start Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev:isolated
```

### 5. Access
- Frontend: http://localhost:5174
- API docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/vacancy

## Running Tests
```bash
cd backend
python -m pytest -v
```

## Running Benchmark
```bash
python scripts/benchmark_scheduler.py
```

## Constraint Documentation

| Code | Constraint | Status |
|------|-----------|--------|
| C01 | No teacher double-booking | Confirmed |
| C02 | No section double-booking | Confirmed |
| C03 | No room double-booking | Confirmed |
| C04 | Room capacity >= section strength | Confirmed |
| C05 | Room type matches course type | Confirmed |
| C06 | Weekly session count satisfied | Confirmed |
| C07 | Multi-period sessions contiguous | Confirmed |
| C08 | Teacher availability respected | Confirmed |
| C09 | Reserved slots blocked | Confirmed |
| C10 | Max lecture periods/day | PENDING CONFIRMATION — configurable |
| C11 | Max consecutive periods | Confirmed |
| C12 | Max section daily hours | Confirmed |
| C13 | Recess window | PENDING CONFIRMATION — configurable |
| C14 | Visiting faculty availability | Confirmed |
| C15 | Senior faculty preferences | Configurable: HARD/SOFT/DISABLED |
| C16 | Room inventory from database | PENDING CONFIRMATION — configurable |
| C17 | Max teacher daily hours | Confirmed |
| C18 | Honours reserved slot | PENDING CONFIRMATION — configurable |
| C19 | No unregistered or more-than-one-hour section gap | Confirmed |
| C20 | A section starts by 12:00 on an active day | Confirmed |

## Troubleshooting

- **MySQL connection fails:** Verify credentials in `.env`, ensure MySQL is running
- **Import errors:** Run from the `backend/` directory, ensure `pip install -r requirements.txt` completed
- **Frontend can't reach API:** Check CORS_ORIGINS in `.env`, ensure backend is on port 8000
- **Scheduler timeout:** Increase `SCHEDULER_TIMEOUT_SECONDS` in `.env`
- **No valid schedule:** Check if room capacities match section strengths, verify enough rooms/timeslots exist
- **Older timetable still appears:** Restart both backend and frontend, then generate again. The timetable view always shows the most recent valid schedule.
