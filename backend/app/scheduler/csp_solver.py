"""Phases 12-14: CSP backtracking solver with forward checking, bounded
restart, and group-aware scheduling (electives / parallel lab pairs)."""
from __future__ import annotations
import time
import random
import logging
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field

from app.scheduler.domain import SchedulingSession, RoomInfo, GroupCandidate
from app.scheduler.candidate_generator import generate_unit_candidates
from app.scheduler.bitmask import OccupancyTracker
from app.scheduler.heuristics import DAY_ORDER, select_next_unit, order_group_candidates, unit_key
from app.scheduler.constraints.base import ScheduleAssignment
from app.scheduler.conflict_checker import is_candidate_valid, validate_schedule

logger = logging.getLogger(__name__)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


@dataclass
class SolverConfig:
    timeout_seconds: int = 30
    max_restarts: int = 5
    debug: bool = False
    days: List[str] = field(default_factory=lambda: DAYS[:6])
    slots_per_day: int = 8
    constraint_config: dict = field(default_factory=dict)


@dataclass
class SolverResult:
    status: str  # VALID | FAILED | TIMEOUT
    assignments: List[ScheduleAssignment] = field(default_factory=list)
    sessions_scheduled: int = 0
    sessions_expected: int = 0
    generation_time_ms: int = 0
    backtracks: int = 0
    restarts: int = 0
    hard_constraint_violations: int = 0
    soft_constraint_score: float = 0.0
    algorithm: str = "CSP_BACKTRACKING"
    unscheduled_sessions: List[str] = field(default_factory=list)
    bottlenecks: List[str] = field(default_factory=list)


def _unit_section_id(unit: List[SchedulingSession]) -> int:
    return unit[0].section_id


def _unit_duration(unit: List[SchedulingSession]) -> int:
    return unit[0].duration


def _members_for_bitmask(unit: List[SchedulingSession], candidate: GroupCandidate):
    return [(m.teacher_id, candidate.room_assignments[m.session_id].room_id) for m in unit]


def _build_assignments(unit: List[SchedulingSession], candidate: GroupCandidate) -> List[ScheduleAssignment]:
    out = []
    for m in unit:
        room = candidate.room_assignments[m.session_id]
        out.append(ScheduleAssignment(
            session_id=m.session_id,
            course_id=m.course_id,
            section_id=m.section_id,
            teacher_id=m.teacher_id,
            room_id=room.room_id,
            day=candidate.day,
            slot_index=candidate.slot_index,
            duration=m.duration,
            room_type=room.room_type,
            room_capacity=room.capacity,
            section_strength=m.section_strength,
            course_type=m.course_type,
            required_room_type=m.required_room_type,
            faculty_type=m.faculty_type,
            link_group_id=m.link_group_id,
        ))
    return out


class CSPSolver:
    """CSP backtracking solver with bitmask occupancy, MRV, forward checking,
    bounded restart, and group-aware placement (Phase 14)."""

    def __init__(self, config: SolverConfig) -> None:
        self.config = config
        self.occupancy = OccupancyTracker()
        self.backtracks = 0
        self.restarts = 0
        self.start_time = 0.0
        self.assigned: List[ScheduleAssignment] = []
        # Tracks which unit each currently-assigned batch of ScheduleAssignments
        # came from, so we can pop the right number on backtrack.
        self._assigned_units: List[Tuple[List[SchedulingSession], GroupCandidate]] = []

    def solve(
        self,
        sessions: List[SchedulingSession],
        rooms: List[RoomInfo],
    ) -> SolverResult:
        from app.scheduler.session_expander import group_sessions

        self.start_time = time.time()
        total_expected = len(sessions)
        cfg = self.config.constraint_config

        reserved = cfg.get("reserved_slots", set())
        recess = cfg.get("recess_slots", set())
        honours = cfg.get("honours_slots", set())
        honours_en = cfg.get("HONOURS_RESERVED_ENABLED", False)
        teacher_unavail = cfg.get("teacher_unavailable", set())

        units = group_sessions(sessions)

        # A section can occupy at most one scheduling unit at a time. Keep
        # only enough interchangeable rooms of each type to serve the maximum
        # possible concurrency in this solve scope. This preserves a complete
        # room matching while avoiding identical room permutations per slot.
        section_room_demand: Dict[int, Dict[str, int]] = {}
        for unit in units:
            per_type: Dict[str, int] = {}
            for member in unit:
                per_type[member.required_room_type] = per_type.get(member.required_room_type, 0) + 1
            section_demand = section_room_demand.setdefault(unit[0].section_id, {})
            for room_type, count in per_type.items():
                section_demand[room_type] = max(section_demand.get(room_type, 0), count)
        room_limits: Dict[str, int] = {}
        for section_demand in section_room_demand.values():
            for room_type, count in section_demand.items():
                room_limits[room_type] = room_limits.get(room_type, 0) + count

        domains: Dict[str, List[GroupCandidate]] = {}
        for unit in units:
            cands = generate_unit_candidates(
                unit, rooms, self.config.days, self.config.slots_per_day,
                reserved, recess, honours, honours_en, teacher_unavail,
                room_limits,
            )
            key = unit_key(unit)
            domains[key] = order_group_candidates(cands)
            if not cands:
                elapsed = int((time.time() - self.start_time) * 1000)
                names = ", ".join(m.session_id for m in unit)
                return SolverResult(
                    status="FAILED", sessions_expected=total_expected,
                    generation_time_ms=elapsed,
                    unscheduled_sessions=[m.session_id for m in unit],
                    bottlenecks=[f"No valid shared slot for group [{names}]" if len(unit) > 1
                                 else f"No valid candidates for {unit[0].session_id} ({unit[0].course_code})"],
                )

        # A full departmental week has many equivalent rooms and time slots.
        # Try a bounded constructive pass first when academic balancing is
        # requested.  It avoids spending the entire timeout on deep branches
        # that differ only by interchangeable room choices.  The established
        # backtracking solver below remains the exact fallback.
        greedy_assignments = self._try_balanced_construction(units, domains, cfg)
        if greedy_assignments is not None:
            elapsed = int((time.time() - self.start_time) * 1000)
            violations = validate_schedule(greedy_assignments, cfg)
            if not violations:
                return SolverResult(
                    status="VALID",
                    assignments=greedy_assignments,
                    sessions_scheduled=len(greedy_assignments),
                    sessions_expected=total_expected,
                    generation_time_ms=elapsed,
                    backtracks=0,
                    restarts=self.restarts,
                    hard_constraint_violations=0,
                )

        best_result: Optional[SolverResult] = None

        for restart in range(self.config.max_restarts + 1):
            self.restarts = restart
            self.backtracks = 0
            self.occupancy = OccupancyTracker()
            self.assigned = []
            self._assigned_units = []

            if restart > 0:
                for k in domains:
                    random.shuffle(domains[k])

            unassigned = list(units)
            current_domains = {k: list(v) for k, v in domains.items()}

            success = self._backtrack(unassigned, current_domains, cfg)

            if success:
                elapsed = int((time.time() - self.start_time) * 1000)
                violations = validate_schedule(self.assigned, cfg)
                result = SolverResult(
                    status="VALID" if not violations else "FAILED",
                    assignments=list(self.assigned),
                    sessions_scheduled=len(self.assigned),
                    sessions_expected=total_expected,
                    generation_time_ms=elapsed,
                    backtracks=self.backtracks,
                    restarts=self.restarts,
                    hard_constraint_violations=len(violations),
                )
                if not violations:
                    return result
                if best_result is None or result.hard_constraint_violations < best_result.hard_constraint_violations:
                    best_result = result

            if self._timed_out():
                break

        elapsed = int((time.time() - self.start_time) * 1000)
        if best_result:
            best_result.generation_time_ms = elapsed
            return best_result

        scheduled_ids = {a.session_id for a in self.assigned}
        all_session_ids = [m.session_id for u in units for m in u]
        unscheduled = [sid for sid in all_session_ids if sid not in scheduled_ids]
        return SolverResult(
            status="FAILED" if not self._timed_out() else "TIMEOUT",
            assignments=list(self.assigned),
            sessions_scheduled=len(self.assigned),
            sessions_expected=total_expected,
            generation_time_ms=elapsed,
            backtracks=self.backtracks,
            restarts=self.restarts,
            unscheduled_sessions=unscheduled,
            bottlenecks=[f"{len(unscheduled)} sessions could not be scheduled"],
        )

    def _timed_out(self) -> bool:
        return (time.time() - self.start_time) > self.config.timeout_seconds

    def _section_slots_for_day(self, section_id: int, day: str) -> Set[int]:
        """Return slots already occupied by a section on one day.

        Linked laboratory/elective members intentionally share a section slot;
        a set gives the real student timetable footprint rather than counting
        those parallel records twice.
        """
        slots: Set[int] = set()
        for assignment in self.assigned:
            if assignment.section_id == section_id and assignment.day == day:
                slots.update(range(assignment.slot_index, assignment.slot_index + assignment.duration))
        return slots

    def _balanced_candidate_key(
        self,
        unit: List[SchedulingSession],
        candidate: GroupCandidate,
    ) -> tuple:
        """Rank a valid candidate for an even, readable student timetable.

        A hard-valid solution is not automatically a useful academic schedule.
        This score first prefers the least-loaded day for the *section* so a
        student is not left with an entirely empty weekday.  Once all days in
        use, it places the next class close to an existing class, which avoids
        long idle gaps.  Faculty load and room capacity are tie-breakers only;
        the conflict constraints remain the authority for validity.
        """
        section_id = _unit_section_id(unit)
        duration = _unit_duration(unit)
        section_slots = self._section_slots_for_day(section_id, candidate.day)
        section_day_load = len(section_slots)

        # If the day already has a class, favour adjacency before creating a
        # spare period between classes.  A new day has no within-day gap.
        if section_slots:
            candidate_slots = set(range(candidate.slot_index, candidate.slot_index + duration))
            idle_gap = min(
                max(0, abs(new_slot - occupied_slot) - 1)
                for new_slot in candidate_slots
                for occupied_slot in section_slots
            )
        else:
            idle_gap = 0

        teacher_day_load = sum(
            self.occupancy.teacher_load_on_day(member.teacher_id, candidate.day)
            for member in unit
        )
        room_excess = sum(
            candidate.room_assignments[member.session_id].capacity - member.section_strength
            for member in unit
        )
        return (
            section_day_load,
            idle_gap,
            teacher_day_load,
            DAY_ORDER.get(candidate.day, 99),
            candidate.slot_index,
            room_excess,
        )

    def _ordered_candidates(
        self,
        unit: List[SchedulingSession],
        candidates: List[GroupCandidate],
    ) -> List[GroupCandidate]:
        """Apply academic-balance ranking only when requested by the UI/API."""
        if not self.config.constraint_config.get("PREFER_BALANCED_DAYS", False):
            return candidates
        return sorted(candidates, key=lambda candidate: self._balanced_candidate_key(unit, candidate))

    def _candidate_fits_current_plan(
        self,
        unit: List[SchedulingSession],
        candidate: GroupCandidate,
        cfg: dict,
    ) -> bool:
        """Check occupancy and every hard rule against the partial schedule."""
        section_id = _unit_section_id(unit)
        duration = _unit_duration(unit)
        members = _members_for_bitmask(unit, candidate)
        if self.occupancy.has_unit_conflict(members, section_id, candidate.day, candidate.slot_index, duration):
            return False
        check_against = list(self.assigned)
        for assignment in _build_assignments(unit, candidate):
            if not is_candidate_valid(assignment, check_against, cfg):
                return False
            check_against.append(assignment)
        return True

    def _try_balanced_construction(
        self,
        units: List[List[SchedulingSession]],
        domains: Dict[str, List[GroupCandidate]],
        cfg: dict,
    ) -> Optional[List[ScheduleAssignment]]:
        """Quickly construct a valid, balanced schedule using varied restarts.

        This is intentionally not a replacement for CSP backtracking.  It is a
        high-throughput first pass for real college-sized datasets where rooms
        are plentiful.  Every choice still passes the complete hard-constraint
        checker; only the order of valid choices varies across retries.
        """
        rng = random.Random(20260914)
        # Leave enough time for the exact solver if construction cannot finish.
        construction_deadline = self.start_time + (self.config.timeout_seconds * 0.65)
        max_attempts = max(8, self.config.max_restarts * 8)

        for attempt in range(max_attempts):
            if time.time() >= construction_deadline:
                break
            self.restarts = attempt
            self.backtracks = 0
            self.occupancy = OccupancyTracker()
            self.assigned = []
            self._assigned_units = []
            unassigned = list(units)
            rng.shuffle(unassigned)

            while unassigned and time.time() < construction_deadline:
                # MRV/priority ordering, but choose randomly among exact ties
                # so a different equally-good resource layout is attempted on
                # the next construction pass.
                ranked = []
                for unit in unassigned:
                    ranked.append((len(domains[unit_key(unit)]), -max(m.priority for m in unit), unit))
                best_size, best_priority = min((size, priority) for size, priority, _ in ranked)
                tied_units = [
                    unit for size, priority, unit in ranked
                    if size == best_size and priority == best_priority
                ]
                unit = rng.choice(tied_units)

                ordered = self._ordered_candidates(unit, domains[unit_key(unit)])
                feasible = [
                    candidate for candidate in ordered
                    if self._candidate_fits_current_plan(unit, candidate, cfg)
                ]
                if not feasible:
                    break

                # Randomize only among candidates that are *equally* balanced
                # for students.  Picking arbitrarily from the first dozen
                # raw candidates could pick a second class on Monday even
                # though another weekday was completely empty.
                if cfg.get("PREFER_BALANCED_DAYS", False):
                    best_quality = self._balanced_candidate_key(unit, feasible[0])[:3]
                    equally_balanced = [
                        candidate for candidate in feasible
                        if self._balanced_candidate_key(unit, candidate)[:3] == best_quality
                    ]
                    candidate = rng.choice(equally_balanced)
                else:
                    # Basic-feasibility mode retains a small randomized window
                    # to avoid repeated equivalent room-allocation dead ends.
                    candidate = rng.choice(feasible[:min(12, len(feasible))])
                assignments = _build_assignments(unit, candidate)
                self.assigned.extend(assignments)
                self.occupancy.assign_unit(
                    _members_for_bitmask(unit, candidate),
                    _unit_section_id(unit), candidate.day, candidate.slot_index,
                    _unit_duration(unit),
                )
                unassigned.remove(unit)

            if not unassigned:
                return list(self.assigned)

        return None

    def _backtrack(
        self,
        unassigned: List[List[SchedulingSession]],
        domains: Dict[str, List[GroupCandidate]],
        cfg: dict,
    ) -> bool:
        if not unassigned:
            return True
        if self._timed_out():
            return False

        unit = select_next_unit(unassigned, domains)
        key = unit_key(unit)
        remaining = [u for u in unassigned if unit_key(u) != key]
        candidates = self._ordered_candidates(unit, domains.get(key, []))
        section_id = _unit_section_id(unit)
        duration = _unit_duration(unit)

        for candidate in candidates:
            if self._timed_out():
                return False

            if not self._candidate_fits_current_plan(unit, candidate, cfg):
                continue

            members = _members_for_bitmask(unit, candidate)
            new_assignments = _build_assignments(unit, candidate)

            self.assigned.extend(new_assignments)
            self.occupancy.assign_unit(members, section_id, candidate.day, candidate.slot_index, duration)
            self._assigned_units.append((unit, candidate))

            saved_domains = {}
            feasible = True
            for ru in remaining:
                rkey = unit_key(ru)
                old_domain = domains[rkey]
                new_domain = self._forward_check(ru, old_domain, cfg)
                if not new_domain:
                    feasible = False
                    for sid, dom in saved_domains.items():
                        domains[sid] = dom
                    break
                saved_domains[rkey] = old_domain
                domains[rkey] = new_domain

            if feasible and self._backtrack(remaining, domains, cfg):
                return True

            # Backtrack: undo this unit's assignments.
            self.backtracks += 1
            for _ in new_assignments:
                self.assigned.pop()
            self.occupancy.unassign_unit(members, section_id, candidate.day, candidate.slot_index, duration)
            self._assigned_units.pop()
            for sid, dom in saved_domains.items():
                domains[sid] = dom

        return False

    def _forward_check(
        self,
        unit: List[SchedulingSession],
        domain: List[GroupCandidate],
        cfg: dict,
    ) -> List[GroupCandidate]:
        """Remove candidates that cannot coexist with the current partial plan.

        Checking only occupied teacher/room/section bitmasks left values in a
        domain that were already impossible because of daily lecture, daily
        hours, or consecutive-period limits.  They surfaced only at the end
        of a branch, producing needless 30-second timeouts on a full semester
        workload.  Validate the remaining unit against the partial plan here
        so MRV receives a truthful, much smaller domain.
        """
        section_id = _unit_section_id(unit)
        duration = _unit_duration(unit)
        pruned = []
        for c in domain:
            members = _members_for_bitmask(unit, c)
            if self.occupancy.has_unit_conflict(members, section_id, c.day, c.slot_index, duration):
                continue
            if not self._candidate_fits_current_plan(unit, c, cfg):
                continue
            pruned.append(c)
        return pruned
