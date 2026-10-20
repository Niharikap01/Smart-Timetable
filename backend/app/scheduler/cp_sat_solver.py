"""Google OR-Tools CP-SAT implementation for the timetable engine.

The rest of the application still supplies the same expanded sessions, room
inventory, candidate generator and post-generation constraint validator used
by the original CSP backtracking solver.  This module only changes *how* a
valid timetable is searched for, keeping the import/UI/database contract
stable and leaving ``CSPSolver`` available as a fallback.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

from app.scheduler.candidate_generator import generate_unit_candidates
from app.scheduler.conflict_checker import validate_schedule
from app.scheduler.constraints.base import ScheduleAssignment
from app.scheduler.csp_solver import SolverConfig, SolverResult
from app.scheduler.domain import GroupCandidate, RoomInfo, SchedulingSession
from app.scheduler.session_expander import group_sessions

try:  # Import lazily/defensively so the fallback still works before install.
    from ortools.sat.python import cp_model
except ImportError:  # pragma: no cover - exercised only on a missing install
    cp_model = None


@dataclass(frozen=True)
class _Choice:
    """One binary CP-SAT decision: place a whole scheduling unit here."""

    unit_index: int
    unit: Tuple[SchedulingSession, ...]
    candidate: GroupCandidate
    variable: object


class CPSATSolver:
    """Find a valid timetable with Google OR-Tools CP-SAT.

    A decision variable represents a pre-validated placement for either one
    session or a linked parallel group.  Candidate generation already removes
    invalid room types/capacities, unavailable faculty, recesses, reserved
    slots and non-contiguous lab placements.  CP-SAT then chooses exactly one
    candidate for every unit while enforcing all cross-session rules.
    """

    algorithm = "GOOGLE_OR_TOOLS_CP_SAT"

    def __init__(self, config: SolverConfig) -> None:
        self.config = config

    def solve(
        self,
        sessions: List[SchedulingSession],
        rooms: List[RoomInfo],
    ) -> SolverResult:
        started = time.monotonic()
        expected = len(sessions)

        if cp_model is None:
            return SolverResult(
                status="UNAVAILABLE",
                sessions_expected=expected,
                algorithm=self.algorithm,
                bottlenecks=["Google OR-Tools is not installed. Install the backend requirements."],
            )

        cfg = self.config.constraint_config
        model = cp_model.CpModel()
        units = group_sessions(sessions)
        choices: List[_Choice] = []
        by_unit: DefaultDict[int, List[object]] = defaultdict(list)

        reserved = cfg.get("reserved_slots", set())
        recess = cfg.get("recess_slots", set())
        honours = cfg.get("honours_slots", set())
        honours_enabled = cfg.get("HONOURS_RESERVED_ENABLED", False)
        unavailable = cfg.get("teacher_unavailable", set())

        for unit_index, raw_unit in enumerate(units):
            unit = tuple(raw_unit)
            candidates = generate_unit_candidates(
                list(unit), rooms, self.config.days, self.config.slots_per_day,
                reserved, recess, honours, honours_enabled, unavailable,
            )
            candidates = [candidate for candidate in candidates if self._senior_preference_allows(unit, candidate, cfg)]
            # Room choice is independent of a unit's time choice until two
            # sessions overlap. Keep one placement per time and match rooms
            # after CP-SAT has found the timetable; room permutations otherwise
            # multiply the Boolean model without adding scheduling information.
            unique_times: Dict[Tuple[str, int], GroupCandidate] = {}
            for candidate in candidates:
                unique_times.setdefault((candidate.day, candidate.slot_index), candidate)
            candidates = list(unique_times.values())
            if not candidates:
                names = ", ".join(member.session_id for member in unit)
                return self._failed(
                    expected,
                    started,
                    [member.session_id for member in unit],
                    [f"No valid CP-SAT candidates for [{names}]"],
                )

            for candidate_index, candidate in enumerate(candidates):
                variable = model.NewBoolVar(f"u{unit_index}_c{candidate_index}")
                choice = _Choice(unit_index, unit, candidate, variable)
                choices.append(choice)
                by_unit[unit_index].append(variable)
            # C06: every expanded session/course occurrence is placed once.
            model.AddExactlyOne(by_unit[unit_index])

        self._add_resource_constraints(model, choices)
        self._add_daily_load_constraints(model, choices, cfg)
        section_occupancy = self._section_occupancy(model, choices)
        self._add_compact_day_constraints(model, section_occupancy, cfg)
        self._add_start_time_constraints(model, section_occupancy, cfg)

        deadline = started + max(0.0, float(self.config.timeout_seconds))

        last_bottlenecks: List[str] = []
        solver = None
        assignments: List[ScheduleAssignment] = []
        warm_choices = self._warm_start_choices(choices, units, cfg.get("warm_start_slots", {}))
        warm_seeded = False

        # First try to complete the previous valid timetable while keeping its
        # matching placements fixed in a temporary model copy. For imports
        # that add only a few sessions, this turns the old schedule into a
        # near-complete solution instead of asking CP-SAT to rediscover it.
        remaining = deadline - time.monotonic()
        seed_budget = min(5.0, max(0.0, remaining * 0.35))
        if warm_choices and seed_budget > 0.25:
            seed_model = model.clone()
            for choice in warm_choices.values():
                seed_variable = seed_model.get_bool_var_from_proto_index(choice.variable.index)
                seed_model.Add(seed_variable == 1)
            seed_solver = self._new_solver(seed_budget)
            seed_status = seed_solver.Solve(seed_model)
            if seed_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                selected = [
                    choice for choice in choices
                    if seed_solver.BooleanValue(
                        seed_model.get_bool_var_from_proto_index(choice.variable.index)
                    )
                ]
                seed_assignments = [
                    assignment
                    for choice in selected
                    for assignment in self._build_assignments(choice.unit, choice.candidate)
                ]
                if self._allocate_rooms(seed_assignments, rooms) and not validate_schedule(seed_assignments, cfg):
                    solver = seed_solver
                    assignments = seed_assignments
                    warm_seeded = True
                    # The completed seed is also a complete hint for the
                    # unconstrained model used for any optional optimization.
                    selected_ids = {id(choice) for choice in selected}
                    for choice in choices:
                        model.AddHint(choice.variable, int(id(choice) in selected_ids))

        if not warm_seeded:
            self._add_warm_start_hints(model, choices, warm_choices)
            if warm_choices:
                # Preserve previous course times where possible, moving only
                # the units needed to place the new or changed offerings.
                # This gives CP-SAT a useful direction when a timetable is
                # almost valid but additions require a small neighbourhood of
                # existing classes to move.
                model.Maximize(sum(choice.variable for choice in warm_choices.values()))

        while not warm_seeded:
            remaining = deadline - time.monotonic()
            if remaining <= 0.01:
                return SolverResult(
                    status="TIMEOUT",
                    sessions_expected=expected,
                    generation_time_ms=int((time.monotonic() - started) * 1000),
                    algorithm=self.algorithm,
                    bottlenecks=last_bottlenecks or [
                        "CP-SAT reached the time limit before finding a complete timetable."
                    ],
                )

            solver = self._new_solver(remaining)
            status = solver.Solve(model)
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                timed_out = status == cp_model.UNKNOWN
                return SolverResult(
                    status="TIMEOUT" if timed_out else "FAILED",
                    sessions_expected=expected,
                    generation_time_ms=int((time.monotonic() - started) * 1000),
                    algorithm=self.algorithm,
                    bottlenecks=last_bottlenecks or [
                        "CP-SAT reached the time limit before finding a complete timetable."
                        if timed_out else
                        "CP-SAT found the supplied rooms, faculty availability, and timetable rules infeasible."
                    ],
                )

            selected = [choice for choice in choices if solver.Value(choice.variable)]
            assignments = [
                assignment
                for choice in selected
                for assignment in self._build_assignments(choice.unit, choice.candidate)
            ]
            if self._allocate_rooms(assignments, rooms):
                violations = validate_schedule(assignments, cfg)
                if not violations:
                    break
                last_bottlenecks = [violation.message for violation in violations[:5]]
            else:
                last_bottlenecks = [
                    "The selected times could not be matched to distinct compatible rooms."
                ]

            # Room matching is a separate step because it is independent of
            # time choice in most cases. If a chosen pattern cannot be matched,
            # exclude just that combination and let CP-SAT try another one.
            model.Add(sum(choice.variable for choice in selected) <= len(selected) - 1)

        best_solver = solver
        best_assignments = assignments

        # Hard feasibility comes first. Only spend leftover time on the
        # optional balance objective after a fully validated timetable exists.
        self._add_optional_balance_objective(model, choices, cfg, warm_choices.values())
        remaining = deadline - time.monotonic()
        optimization_budget = min(5.0, max(0.0, remaining * 0.25))
        if cfg.get("PREFER_BALANCED_DAYS", False) and optimization_budget > 0.25:
            optimizer = self._new_solver(optimization_budget)
            optimized_status = optimizer.Solve(model)
            if optimized_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                optimized_choices = [choice for choice in choices if optimizer.Value(choice.variable)]
                optimized_assignments = [
                    assignment
                    for choice in optimized_choices
                    for assignment in self._build_assignments(choice.unit, choice.candidate)
                ]
                if self._allocate_rooms(optimized_assignments, rooms) and not validate_schedule(optimized_assignments, cfg):
                    best_solver = optimizer
                    best_assignments = optimized_assignments

        return SolverResult(
            status="VALID",
            assignments=best_assignments,
            sessions_scheduled=len(best_assignments),
            sessions_expected=expected,
            generation_time_ms=int((time.monotonic() - started) * 1000),
            hard_constraint_violations=0,
            algorithm=self.algorithm,
            # CP-SAT does not use chronological backtracking.  Conflicts are
            # the closest useful diagnostic exposed by OR-Tools.
            backtracks=int(best_solver.NumConflicts()),
            restarts=0,
        )

    @staticmethod
    def _new_solver(remaining_seconds: float):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.01, remaining_seconds)
        solver.parameters.num_search_workers = 8
        solver.parameters.random_seed = 20261008
        return solver

    @staticmethod
    def _warm_start_choices(choices, units, warm_start_slots: dict) -> dict:
        choices_by_unit: DefaultDict[int, List[_Choice]] = defaultdict(list)
        for choice in choices:
            choices_by_unit[choice.unit_index].append(choice)

        selected_by_unit = {}
        for unit_index, unit in enumerate(units):
            prior_slots = [
                warm_start_slots.get((member.course_id, member.section_id, member.session_number))
                for member in unit
            ]
            if not prior_slots or any(slot is None for slot in prior_slots):
                continue
            if len(set(prior_slots)) != 1:
                continue
            prior_day, prior_slot = prior_slots[0]
            unit_choices = choices_by_unit[unit_index]
            matching = next((
                choice for choice in unit_choices
                if choice.candidate.day == prior_day and choice.candidate.slot_index == prior_slot
            ), None)
            if matching is not None:
                selected_by_unit[unit_index] = matching
        return selected_by_unit

    @staticmethod
    def _add_warm_start_hints(model, choices, selected_by_unit: dict) -> None:
        choices_by_unit: DefaultDict[int, List[_Choice]] = defaultdict(list)
        for choice in choices:
            choices_by_unit[choice.unit_index].append(choice)
        for unit_index, matching in selected_by_unit.items():
            for choice in choices_by_unit[unit_index]:
                model.AddHint(choice.variable, int(choice is matching))

    def _failed(
        self, expected: int, started: float, unscheduled: List[str], bottlenecks: List[str],
    ) -> SolverResult:
        return SolverResult(
            status="FAILED",
            sessions_expected=expected,
            generation_time_ms=int((time.monotonic() - started) * 1000),
            algorithm=self.algorithm,
            unscheduled_sessions=unscheduled,
            bottlenecks=bottlenecks,
        )

    @staticmethod
    def _build_assignments(
        unit: Iterable[SchedulingSession], candidate: GroupCandidate,
    ) -> List[ScheduleAssignment]:
        assignments = []
        for member in unit:
            room = candidate.room_assignments[member.session_id]
            assignments.append(ScheduleAssignment(
                session_id=member.session_id,
                course_id=member.course_id,
                section_id=member.section_id,
                teacher_id=member.teacher_id,
                room_id=room.room_id,
                day=candidate.day,
                slot_index=candidate.slot_index,
                duration=member.duration,
                room_type=room.room_type,
                room_capacity=room.capacity,
                section_strength=member.section_strength,
                course_type=member.course_type,
                required_room_type=member.required_room_type,
                faculty_type=member.faculty_type,
                link_group_id=member.link_group_id,
                shared_room_group_id=member.shared_room_group_id,
                required_capacity=max(member.section_strength, member.program_elective_student_count),
                program_elective_group_id=member.program_elective_group_id,
                program_elective_student_count=member.program_elective_student_count,
                room_number=room.room_number,
            ))
        return assignments

    @staticmethod
    def _senior_preference_allows(
        unit: Tuple[SchedulingSession, ...], candidate: GroupCandidate, cfg: dict,
    ) -> bool:
        """Only enforce C15 when the administrator configures it as HARD."""
        if cfg.get("SENIOR_FACULTY_CONSTRAINT_MODE", "SOFT") != "HARD":
            return True
        preferences = cfg.get("senior_preferred_slots", set())
        for member in unit:
            if member.faculty_type != "senior":
                continue
            teacher_preferences = {
                (day, slot) for teacher_id, day, slot in preferences
                if teacher_id == member.teacher_id
            }
            if teacher_preferences and any(
                (candidate.day, slot) not in teacher_preferences
                for slot in range(candidate.slot_index, candidate.slot_index + member.duration)
            ):
                return False
        return True

    @staticmethod
    def _add_at_most_one(model, indexed_variables: Dict[tuple, List[object]]) -> None:
        for variables in indexed_variables.values():
            if len(variables) > 1:
                # A malformed linked group could contain the same teacher
                # twice.  Keeping duplicate literals in this linear form
                # correctly makes that placement impossible; some CP-SAT
                # versions reject duplicates passed to AddAtMostOne.
                model.Add(sum(variables) <= 1)

    def _add_resource_constraints(self, model, choices: List[_Choice]) -> None:
        """C01/C02: teachers and sections never overlap.

        A linked elective/lab group shares a section slot deliberately.  It is
        represented by one choice variable, so section occupancy is added once
        per group. Compatible rooms are assigned after time placement.
        """
        teacher_slots: DefaultDict[tuple, List[object]] = defaultdict(list)
        section_slots: DefaultDict[tuple, List[object]] = defaultdict(list)

        for choice in choices:
            for section_id in {member.section_id for member in choice.unit}:
                for slot in range(choice.candidate.slot_index, choice.candidate.slot_index + choice.unit[0].duration):
                    section_slots[(section_id, choice.candidate.day, slot)].append(choice.variable)
            for teacher_id in {member.teacher_id for member in choice.unit}:
                for slot in range(choice.candidate.slot_index, choice.candidate.slot_index + choice.unit[0].duration):
                    teacher_slots[(teacher_id, choice.candidate.day, slot)].append(choice.variable)

        self._add_at_most_one(model, teacher_slots)
        self._add_at_most_one(model, section_slots)

    @staticmethod
    def _allocate_rooms(assignments: List[ScheduleAssignment], rooms: List[RoomInfo]) -> bool:
        """Match room units, keeping cross-section electives in one room."""
        units_by_key = defaultdict(list)
        for assignment in assignments:
            key = ("shared", assignment.shared_room_group_id) if assignment.shared_room_group_id else ("session", assignment.session_id)
            units_by_key[key].append(assignment)

        room_units = []
        large_room_numbers = {"DT-301", "DT-701", "DT-702"}
        for unit in units_by_key.values():
            shared = bool(unit[0].shared_room_group_id)
            options = [
                room for room in rooms
                if all(
                    room.room_type == assignment.required_room_type
                    and room.capacity >= (assignment.required_capacity or assignment.section_strength)
                    and (
                        not shared
                        or ((room.room_number or "").replace(" ", "").upper() in large_room_numbers)
                        == (assignment.program_elective_student_count > 70)
                    )
                    for assignment in unit
                )
            ]
            options.sort(key=lambda room: (
                room.capacity - max(a.required_capacity or a.section_strength for a in unit),
                room.room_id,
            ))
            if not options:
                return False
            room_units.append((unit, options))

        room_units_by_day: DefaultDict[str, list] = defaultdict(list)
        for unit, options in room_units:
            room_units_by_day[unit[0].day].append((unit, options))

        for day_units in room_units_by_day.values():
            ordered = sorted(day_units, key=lambda item: (len(item[1]), -item[0][0].duration, item[0][0].slot_index))
            room_slots: Dict[int, set] = defaultdict(set)

            def assign(index: int) -> bool:
                if index == len(ordered):
                    return True
                unit, options = ordered[index]
                assignment = unit[0]
                occupied_slots = set(range(assignment.slot_index, assignment.slot_index + assignment.duration))
                for room in options:
                    if room_slots[room.room_id].isdisjoint(occupied_slots):
                        room_slots[room.room_id].update(occupied_slots)
                        for member in unit:
                            member.room_id = room.room_id
                            member.room_type = room.room_type
                            member.room_capacity = room.capacity
                            member.room_number = room.room_number
                        if assign(index + 1):
                            return True
                        room_slots[room.room_id].difference_update(occupied_slots)
                return False

            if not assign(0):
                return False

        return True

    def _add_daily_load_constraints(self, model, choices: List[_Choice], cfg: dict) -> None:
        """C10/C12/C17: section lecture load, total load and faculty load."""
        lecture_loads: DefaultDict[tuple, List[object]] = defaultdict(list)
        section_loads: DefaultDict[tuple, List[object]] = defaultdict(list)
        teacher_loads: DefaultDict[tuple, List[object]] = defaultdict(list)

        for choice in choices:
            by_section = defaultdict(list)
            for member in choice.unit:
                by_section[member.section_id].append(member)
            for section_id, members in by_section.items():
                key = (section_id, choice.candidate.day)
                section_loads[key].append(choice.unit[0].duration * choice.variable)
                if any(member.course_type == "lecture" for member in members):
                    lecture_loads[key].append(choice.unit[0].duration * choice.variable)
            for teacher_id in {member.teacher_id for member in choice.unit}:
                teacher_loads[(teacher_id, choice.candidate.day)].append(choice.unit[0].duration * choice.variable)

        for terms in lecture_loads.values():
            model.Add(sum(terms) <= cfg.get("MAX_LECTURE_PERIODS_PER_DAY", 5))
        for terms in section_loads.values():
            model.Add(sum(terms) <= cfg.get("MAX_SECTION_DAILY_HOURS", 6))
        for terms in teacher_loads.values():
            model.Add(sum(terms) <= cfg.get("MAX_TEACHER_DAILY_HOURS", 7))

    def _section_occupancy(self, model, choices: List[_Choice]) -> Dict[tuple, object]:
        """Create one Boolean occupancy variable per section/day/period.

        Do not carry every room alternative into the compactness rules.  A
        section being occupied is a single fact regardless of whether one of
        16 equivalent DT classrooms was selected.  This symmetry reduction is
        what keeps CP-SAT responsive on a full departmental inventory.
        """
        choices_by_slot: DefaultDict[tuple, List[object]] = defaultdict(list)
        for choice in choices:
            duration = choice.unit[0].duration
            for section_id in {member.section_id for member in choice.unit}:
                for slot in range(choice.candidate.slot_index, choice.candidate.slot_index + duration):
                    choices_by_slot[(section_id, choice.candidate.day, slot)].append(choice.variable)

        occupancy: Dict[tuple, object] = {}
        for (section_id, day, slot), variables in choices_by_slot.items():
            occupied = model.NewBoolVar(f"occupied_s{section_id}_{day}_{slot}")
            # C02 makes the sum at most one.  Equality also gives CP-SAT a
            # useful exact definition of the occupancy Boolean.
            model.Add(sum(variables) == occupied)
            occupancy[(section_id, day, slot)] = occupied
        return occupancy

    def _add_compact_day_constraints(self, model, occupancy: Dict[tuple, object], cfg: dict) -> None:
        """C11/C19: cap continuous classes and forbid non-recess gaps."""
        consecutive_limit = cfg.get("MAX_CONSECUTIVE_PERIODS", 3)
        allowed_breaks = cfg.get("allowed_break_slots", set())

        sections_days = {(section_id, day) for section_id, day, _ in occupancy}
        for section_id, day in sections_days:
            # C11: every run of limit + 1 slots must contain at least one gap.
            for start in range(self.config.slots_per_day - consecutive_limit):
                terms = [
                    occupancy[(section_id, day, slot)]
                    for slot in range(start, start + consecutive_limit + 1)
                    if (section_id, day, slot) in occupancy
                ]
                if terms:
                    model.Add(sum(terms) <= consecutive_limit)

            # C19: a day may be continuous, except for an explicitly
            # registered one-period recess/lunch gap.  For every non-break
            # slot, a class before and a class after it require occupation of
            # that middle slot.
            for gap_slot in range(1, self.config.slots_per_day - 1):
                if (section_id, day, gap_slot) in allowed_breaks:
                    continue
                before = [occupancy[(section_id, day, slot)] for slot in range(gap_slot) if (section_id, day, slot) in occupancy]
                after = [occupancy[(section_id, day, slot)] for slot in range(gap_slot + 1, self.config.slots_per_day) if (section_id, day, slot) in occupancy]
                at_gap = occupancy.get((section_id, day, gap_slot), 0)
                if not before or not after:
                    continue
                for earlier in before:
                    for later in after:
                        model.Add(earlier + later <= 1 + at_gap)

            # C19 also explicitly rejects a two-hour "break", even if both
            # adjacent slots were accidentally registered as recess.  Classes
            # may not appear on both sides of such a run.
            break_slots = sorted(
                slot for slot in range(self.config.slots_per_day)
                if (section_id, day, slot) in allowed_breaks
            )
            run_start: Optional[int] = None
            previous: Optional[int] = None
            for slot in [*break_slots, None]:
                if slot is not None and (previous is None or slot == previous + 1):
                    run_start = slot if run_start is None else run_start
                    previous = slot
                    continue
                if run_start is not None and previous is not None and previous > run_start:
                    before_run = [
                        occupancy[(section_id, day, index)]
                        for index in range(run_start)
                        if (section_id, day, index) in occupancy
                    ]
                    after_run = [
                        occupancy[(section_id, day, index)]
                        for index in range(previous + 1, self.config.slots_per_day)
                        if (section_id, day, index) in occupancy
                    ]
                    for earlier in before_run:
                        for later in after_run:
                            model.Add(earlier + later <= 1)
                run_start = slot
                previous = slot

    def _add_start_time_constraints(self, model, occupancy: Dict[tuple, object], cfg: dict) -> None:
        """C20: a section that teaches that day must begin no later than noon."""
        latest_by_day = cfg.get("MAX_SECTION_START_SLOT_BY_DAY", {})
        default_latest = cfg.get("MAX_SECTION_START_SLOT", 3)
        sections_days = {(section_id, day) for section_id, day, _ in occupancy}

        for section_id, day in sections_days:
            latest = latest_by_day.get(day, default_latest)
            early = [
                occupancy[(section_id, day, slot)]
                for slot in range(0, min(latest + 1, self.config.slots_per_day))
                if (section_id, day, slot) in occupancy
            ]
            late = [
                occupancy[(section_id, day, slot)]
                for slot in range(latest + 1, self.config.slots_per_day)
                if (section_id, day, slot) in occupancy
            ]
            for variable in late:
                if early:
                    model.Add(variable <= sum(early))
                else:
                    model.Add(variable == 0)

    def _add_optional_balance_objective(
        self, model, choices: List[_Choice], cfg: dict, warm_choices: Iterable[_Choice] = (),
    ) -> None:
        """Prefer a spread, readable week without weakening hard rules."""
        if not cfg.get("PREFER_BALANCED_DAYS", False):
            return

        section_day_choices: DefaultDict[tuple, List[object]] = defaultdict(list)
        course_day_choices: DefaultDict[tuple, List[object]] = defaultdict(list)
        room_waste_terms: List[object] = []
        for choice in choices:
            for section_id in {member.section_id for member in choice.unit}:
                section_day_choices[(section_id, choice.candidate.day)].append(choice.variable)
            for member in choice.unit:
                course_day_choices[(member.course_id, choice.candidate.day)].append(choice.variable)
                room = choice.candidate.room_assignments[member.session_id]
                room_waste_terms.append(max(0, room.capacity - member.section_strength) * choice.variable)

        active_days: List[object] = []
        for key, variables in section_day_choices.items():
            active = model.NewBoolVar(f"section_day_{key[0]}_{key[1]}")
            for variable in variables:
                model.Add(variable <= active)
            model.Add(active <= sum(variables))
            active_days.append(active)

        course_days: List[object] = []
        for key, variables in course_day_choices.items():
            active = model.NewBoolVar(f"course_day_{key[0]}_{key[1]}")
            for variable in variables:
                model.Add(variable <= active)
            model.Add(active <= sum(variables))
            course_days.append(active)

        # Primary: use as many working days as the weekly workload permits.
        # Secondary: spread each course across days.  Room-capacity excess is
        # only a tie-breaker, so it never creates an unbalanced timetable.
        model.Maximize(
            1000 * sum(active_days)
            + 100 * sum(course_days)
            + 1000 * sum(choice.variable for choice in warm_choices)
            - sum(room_waste_terms)
        )
