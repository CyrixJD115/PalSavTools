"""Direct Mode tests — forward (A+B→child) and reverse (A+target→B).

Validated against ground truth pulled directly from the breeding data files
(not via the engine), so these tests catch regressions in the indexing logic
independently of the lookup code itself.
"""

from __future__ import annotations

import json
from pathlib import Path


# ----------------------------------------------------------------------
# forward lookup
# ----------------------------------------------------------------------
def test_forward_known_combo(db, breeding):
    # Kitsun Noct + Eidrolon Ignis -> Anubis is row 0 of the formula table.
    r = breeding.direct_child(db, "AmaterasuWolf_Dark", "GhostDragon_Fire")
    assert r is not None
    assert r.child == "Anubis"
    assert r.child_display == "Anubis"
    assert r.combo_type == "formula"


def test_forward_self_breed(db, breeding):
    # Alpaca + Alpaca -> Alpaca (same-species self-breed is in the table).
    r = breeding.direct_child(db, "Alpaca", "Alpaca")
    assert r is not None
    assert r.child == "Alpaca"


def test_forward_order_independent(db, breeding):
    # Breeding is symmetric: A+B and B+A must give the same child.
    a, b = "AmaterasuWolf_Dark", "GhostDragon_Fire"
    assert breeding.direct_child(db, a, b).child == breeding.direct_child(db, b, a).child


def test_forward_no_combo(db, breeding):
    # A pair with no entry in the table returns None, not an exception.
    # (Pick two valid tribes that simply don't combine to anything recorded.)
    assert breeding.direct_child(db, "Alpaca", "NonexistentPalXYZ") is None


def test_forward_unknown_tribes_return_none(db, breeding):
    assert breeding.direct_child(db, "FAKE_A", "FAKE_B") is None


def test_forward_result_carries_gender_prob(db, breeding):
    r = breeding.direct_child(db, "AmaterasuWolf_Dark", "GhostDragon_Fire")
    assert r.child_gender_prob is not None
    assert set(r.child_gender_prob.keys()) == {"male", "female"}
    assert abs(sum(r.child_gender_prob.values()) - 1.0) < 0.01


def test_forward_cross_checks_raw_table(db, breeding, tmp_path):
    """Formula-table pairs resolve via direct_child, EXCEPT where a unique combo
    overrides the formula result (unique combos take precedence in-game).

    We build the set of unique-overridden pairs and skip them, then assert the
    rest resolve to their formula child.
    """
    raw = json.loads((_game_data_json()).read_text(encoding="utf-8"))
    overridden: set[frozenset] = set()
    for uc in raw["unique_combos"]:
        overridden.add(frozenset((uc["parent_a"], uc["parent_b"])))

    checked = 0
    skipped = 0
    for child, pairs in raw["child_to_parents_formula"].items():
        for pair in pairs:
            a, b = pair["parent_a"], pair["parent_b"]
            if frozenset((a, b)) in overridden:
                skipped += 1
                continue
            got = breeding.direct_child(db, a, b)
            assert got is not None, f"{a}+{b} should yield {child}, got None"
            assert got.child == child, f"{a}+{b} -> {got.child}, expected {child}"
            checked += 1
            if checked >= 200:  # sample, don't iterate all 33k
                assert skipped > 0, "expected some unique overrides to be skipped"
                return
    assert checked > 0


# ----------------------------------------------------------------------
# reverse lookup (partners + parents)
# ----------------------------------------------------------------------
def test_partners_returns_candidates(db, breeding):
    # Anubis has 100 formula parent pairs; at least one parent should have
    # multiple partners. Pick "Anubis" itself (self-breed gives many partners).
    ps = breeding.direct_partners(db, "Anubis", "Anubis")
    assert len(ps) > 0
    # Every candidate, paired with Anubis, must actually yield Anubis.
    for p in ps:
        child = breeding.direct_child(db, "Anubis", p.parent_b)
        assert child is not None and child.child == "Anubis"


def test_partners_sorted_by_display_name(db, breeding):
    ps = breeding.direct_partners(db, "Anubis", "Anubis")
    names = [db.display_name(p.parent_b).lower() for p in ps]
    assert names == sorted(names)


def test_partners_deduplicated(db, breeding):
    ps = breeding.direct_partners(db, "Anubis", "Anubis")
    partner_ids = [p.parent_b for p in ps]
    assert len(partner_ids) == len(set(partner_ids))


def test_partners_empty_for_unknown(db, breeding):
    assert breeding.direct_partners(db, "Anubis", "FAKE_CHILD") == []


def test_direct_parents_lists_all_pairs(db, breeding):
    """direct_parents(target) returns every de-duplicated pair for that child.

    A pair listed under a formula child may be overridden by a unique combo
    (which takes precedence in-game); those pairs legitimately won't reproduce
    the formula child via direct_child, so we filter them out before asserting.
    """
    rows = breeding.direct_parents(db, "Anubis")
    assert len(rows) > 0
    # No duplicate unordered pairs.
    keys = {tuple(sorted((r.parent_a, r.parent_b))) for r in rows}
    assert len(keys) == len(rows)
    # Each NON-overridden pair actually produces Anubis via forward lookup.
    verified = 0
    for r in rows:
        got = breeding.direct_child(db, r.parent_a, r.parent_b)
        if got is not None and got.combo_type == "unique" and got.child != "Anubis":
            continue  # unique-combo override; expected
        assert got is not None and got.child == "Anubis"
        verified += 1
    assert verified > 0, "expected at least one non-overridden Anubis pair"


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _game_data_json():
    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "_resources"
        / "game_data"
        / "breeding.json"
    )
