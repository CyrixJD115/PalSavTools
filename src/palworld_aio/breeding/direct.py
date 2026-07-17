"""Direct Mode — the PySide6 breeding tab, ported to pure functions.

Two operations, matching the legacy tool's two sub-modes:

* **Forward** — Parent A + Parent B → resulting child. One lookup.
* **Reverse** — Parent A + target child → all candidate Parent B pals.

Gender is *not* a filter here (the combo table is gender-agnostic, as in the
legacy tool); we surface the child's gender probability for display only. The
gender-aware logic lives in the chain solver, where it gates feasibility.
"""

from __future__ import annotations

from typing import Optional

from .data import BreedingDB
from .model import DirectResult


def direct_child(db: BreedingDB, parent_a: str, parent_b: str) -> Optional[DirectResult]:
    """A + B → child. Returns ``None`` if the pair has no known child.

    This is the single forward lookup the legacy "Children" sub-mode effectively
    resolved to, plus the gender-probability enrichment the old tool lacked.
    """
    child = db.forward(parent_a, parent_b)
    if child is None:
        return None
    combo_type = "unique" if _is_unique_combo(db, parent_a, parent_b, child) else "formula"
    return db.direct_result(parent_a, parent_b, child, combo_type=combo_type)


def direct_partners(
    db: BreedingDB, parent_a: str, target_child: str
) -> list[DirectResult]:
    """A + target → candidate B pals, sorted by partner display name.

    Mirrors the legacy "Parents" sub-mode restricted to a known Parent A: take
    every parent pair that produces ``target_child``, keep those where one side
    is ``parent_a``, project the other side. De-duplicated and sorted.
    """
    partners: list[DirectResult] = []
    seen: set[str] = set()
    for b in db.reverse(parent_a, target_child):
        if b in seen:
            continue
        seen.add(b)
        combo_type = "unique" if _is_unique_combo(db, parent_a, b, target_child) else "formula"
        partners.append(db.direct_result(parent_a, b, target_child, combo_type=combo_type))
    partners.sort(key=lambda r: db.display_name(r.parent_b).lower())
    return partners


def direct_parents(db: BreedingDB, target_child: str) -> list[DirectResult]:
    """target → ALL parent pairs (no Parent A pinned).

    This is the full reverse view the legacy "Parents" sub-mode showed when no
    parent was selected: every (A, B) pair that yields ``target_child``, unique
    combos first then formula, de-duplicated symmetrically.
    """
    out: list[DirectResult] = []
    seen: set[tuple[str, str]] = set()
    for a, b in db.child_to_parents(target_child):
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        combo_type = "unique" if _is_unique_combo(db, a, b, target_child) else "formula"
        out.append(db.direct_result(a, b, target_child, combo_type=combo_type))
    return out


def _is_unique_combo(
    db: BreedingDB, parent_a: str, parent_b: str, child: str
) -> bool:
    """A pair is a "unique" combo if it appears in the unique-combos list.

    Checked by membership in ``child_to_parents_unique`` rather than re-scanning
    the flat list — same data, indexed form.
    """
    unique_pairs = db.child_to_parents_unique.get(child)
    if not unique_pairs:
        return False
    key = frozenset((parent_a, parent_b))
    return any(frozenset((p["parent_a"], p["parent_b"])) == key for p in unique_pairs)
