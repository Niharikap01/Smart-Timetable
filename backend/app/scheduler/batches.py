"""Shared batch-pair and multi-faculty helpers for lab scheduling."""
from __future__ import annotations

import math
import re
from typing import Iterable


_PAIR_MEMBERS = {
    "B1/B2": frozenset({1, 2}),
    "B3/B4": frozenset({3, 4}),
}


def normalize_batch_label(value: object | None) -> str | None:
    """Return a supported pair label; unknown labels mean whole-section scope."""
    if value is None:
        return None
    tokens = tuple(int(number) for number in re.findall(r"B\s*([1-4])", str(value).upper()))
    if len(tokens) == 2 and frozenset(tokens) in _PAIR_MEMBERS.values():
        return "B1/B2" if frozenset(tokens) == _PAIR_MEMBERS["B1/B2"] else "B3/B4"
    return None


def batch_indices(value: object | None) -> tuple[int, ...]:
    """Student-batch indices occupied by a course (1-based)."""
    normalized = normalize_batch_label(value)
    if normalized is None:
        return (1, 2, 3, 4)
    return tuple(sorted(_PAIR_MEMBERS[normalized]))


def assignments_share_students(first: object, second: object) -> bool:
    """Whether two assignments in the same section have any students in common."""
    if getattr(first, "section_id", None) != getattr(second, "section_id", None):
        return False
    return not set(batch_indices(getattr(first, "batch_label", None))).isdisjoint(
        batch_indices(getattr(second, "batch_label", None))
    )


def assignment_batch_keys(assignment: object) -> tuple[tuple[int, int], ...]:
    """Return per-section student cohorts occupied by one assignment."""
    section_id = getattr(assignment, "section_id", None)
    if section_id is None:
        return ()
    return tuple((section_id, batch) for batch in batch_indices(getattr(assignment, "batch_label", None)))


def teacher_ids(primary_id: int | None, additional_ids: Iterable[int] | None = None) -> tuple[int, ...]:
    """Stable unique faculty list that keeps legacy ``teacher_id`` records valid."""
    values = ([primary_id] if primary_id is not None else []) + list(additional_ids or [])
    return tuple(dict.fromkeys(int(value) for value in values if value is not None))


def group_capacity(section_strength: int, batch_label: object | None) -> int:
    """Use half the section headcount for a two-batch lab pair."""
    if normalize_batch_label(batch_label) is None:
        return max(0, int(section_strength or 0))
    return math.ceil(max(0, int(section_strength or 0)) / 2)

