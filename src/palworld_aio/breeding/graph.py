"""Breeding-graph reachability helpers.

The precomputed ``MinBreedingSteps`` map (built by palcalc via Floyd-Warshall
and shipped in ``breeding_distance.json``) already answers shortest-path
queries in O(1). This module just exposes a thin query layer over it plus a
fallback for pairs the map doesn't cover (newer pals absent from the
palcalc snapshot) — a one-step direct-breed check against the combo table.
"""

from __future__ import annotations

from .data import BreedingDB


def min_steps(db: BreedingDB, start: str, target: str) -> int | None:
    """Fewest breeding steps from ``start`` to ``target``.

    Same pal → 0. Unknown (not in the distance map) → ``None``, **unless** the
    pair is directly breedable (one step), which we detect via the combo table
    so newer pals without a distance row aren't falsely reported unreachable.
    """
    if start == target:
        return 0
    row = db.min_steps.get(start)
    if row is not None and target in row:
        return row[target]
    # Fallback: maybe start can breed *directly* into target even though it has
    # no distance row (e.g. it's a pal added after palcalc's snapshot). This
    # only resolves the 1-step case; multi-step paths through such pals stay
    # unknown (None) rather than guessed.
    if _directly_breeds_into(db, start, target):
        return 1
    return None


def _directly_breeds_into(db: BreedingDB, parent: str, target: str) -> bool:
    """True if some pairing of ``parent`` yields ``target`` in one breed."""
    for a, _b in db.child_to_parents(target):
        if a == parent:
            return True
    return False


def can_reach(db: BreedingDB, start: str, target: str, max_steps: int) -> bool:
    """Convenience: is ``min_steps(start, target)`` within ``max_steps``?"""
    steps = min_steps(db, start, target)
    return steps is not None and steps <= max_steps
