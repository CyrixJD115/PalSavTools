"""Graph reachability tests — min_steps + can_reach + the distance map.

The distance map is palcalc's precomputed Floyd-Warshall result; these tests
verify the engine reads it correctly and falls back sensibly for pals it
doesn't cover.
"""

from __future__ import annotations


def test_min_steps_same_pal_is_zero(db, breeding):
    assert breeding.min_steps(db, "Anubis", "Anubis") == 0
    assert breeding.min_steps(db, "Alpaca", "Alpaca") == 0


def test_min_steps_known_path(db, breeding):
    # Frostallion (IceHorse) is a 1-step Anubis ancestor per the data.
    assert breeding.min_steps(db, "IceHorse", "Anubis") == 1


def test_min_steps_symmetric_shape(db, breeding):
    # The map is keyed source->target; we don't assume symmetry, but the value
    # type must be a non-negative int when present.
    s = breeding.min_steps(db, "Alpaca", "Anubis")
    assert s is None or (isinstance(s, int) and s >= 0)


def test_min_steps_unknown_pal_returns_none_or_one(db, breeding):
    # A pal absent from the distance map: None unless it directly breeds into
    # the target (1-step fallback).
    s = breeding.min_steps(db, "BlackFurDragon", "Anubis")
    assert s is None or s == 1


def test_min_steps_truly_fake_pal(db, breeding):
    assert breeding.min_steps(db, "FAKE_PAL", "Anubis") is None


def test_can_reach_within_budget(db, breeding):
    # IceHorse -> Anubis is 1 step.
    assert breeding.can_reach(db, "IceHorse", "Anubis", 1) is True
    assert breeding.can_reach(db, "IceHorse", "Anubis", 0) is False
    assert breeding.can_reach(db, "IceHorse", "Anubis", 5) is True


def test_can_reach_same_pal(db, breeding):
    assert breeding.can_reach(db, "Anubis", "Anubis", 0) is True


def test_db_reachable_matches_graph(db, breeding):
    # db.reachable and graph.can_reach should agree on covered pals.
    for a, b, budget in [("IceHorse", "Anubis", 1), ("Alpaca", "Anubis", 2)]:
        assert db.reachable(a, b, budget) == breeding.can_reach(db, a, b, budget)


def test_distance_map_consistency(db):
    # Every entry in the distance map is a non-negative int, and every pal is
    # 0 steps from itself.
    for src, row in db.min_steps.items():
        assert row.get(src) == 0, f"{src} should be 0 steps from itself"
        for target, steps in row.items():
            assert isinstance(steps, int) and steps >= 0
