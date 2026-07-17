"""Solver tests — chain correctness, passive inheritance, gender feasibility.

Covers the three source adapters (the palcalc unification: Save/Selection/Wild
all flow through one solver), passive carry-through across generations, gender
feasibility filtering, reachability pruning, and result ranking/dedup.
"""

from __future__ import annotations

import time

import pytest


# ----------------------------------------------------------------------
# basic reachability — what CAN'T be reached
# ----------------------------------------------------------------------
def test_unreachable_target_returns_empty(db, breeding):
    # A tiny pool with no path to Anubis within budget, no wilds.
    src = breeding.SelectedSource(
        [{"species": "Alpaca"}, {"species": "ChickenPal"}, {"species": "PinkCat"}]
    )
    spec = breeding.BreedingSpec(target_pal="Anubis", max_generations=2)
    assert breeding.solve(db, src, spec) == []


def test_unreachable_with_more_budget_but_no_intermediates(db, breeding):
    # Even with a high gen cap, the same 3-pal pool can't reach Anubis because
    # breeding only those 3 never produces an Anubis ancestor line.
    src = breeding.SelectedSource(
        [{"species": "Alpaca"}, {"species": "ChickenPal"}, {"species": "PinkCat"}]
    )
    spec = breeding.BreedingSpec(target_pal="Anubis", max_generations=6)
    assert breeding.solve(db, src, spec) == []


# ----------------------------------------------------------------------
# 0-gen: target already owned
# ----------------------------------------------------------------------
def test_owned_target_returns_zero_gen_chain(db, breeding):
    src = breeding.SelectedSource([{"species": "Anubis"}])
    chains = breeding.solve(db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=3))
    assert len(chains) == 1
    assert chains[0].generations == 0
    assert chains[0].steps == []
    assert chains[0].sources[0]["type"] == "selected"
    assert chains[0].sources[0]["pal"] == "Anubis"


# ----------------------------------------------------------------------
# 1-gen: two direct parents
# ----------------------------------------------------------------------
def test_direct_parents_form_one_step_chain(db, breeding):
    # AmaterasuWolf_Dark + GhostDragon_Fire -> Anubis (verified in test_direct).
    src = breeding.SelectedSource(
        [{"species": "AmaterasuWolf_Dark"}, {"species": "GhostDragon_Fire"}]
    )
    chains = breeding.solve(db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=2))
    assert len(chains) >= 1
    one_step = [c for c in chains if c.generations == 1]
    assert one_step, "expected at least one 1-generation chain"
    c = one_step[0]
    assert len(c.steps) == 1
    s = c.steps[0]
    assert s.child == "Anubis"
    assert {s.parent_a, s.parent_b} == {"AmaterasuWolf_Dark", "GhostDragon_Fire"}


# ----------------------------------------------------------------------
# multi-gen with wilds
# ----------------------------------------------------------------------
def test_multi_gen_chain_with_wilds(db, breeding):
    pool = ["Alpaca", "ChickenPal", "PinkCat", "Carbunclo", "Kitsunebi", "Blueplatypus"]
    selected = breeding.SelectedSource([{"species": t} for t in pool])
    # Exclude the target from wilds so the solver must build a real chain
    # (otherwise it returns a 0-gen "catch a wild Anubis" answer, which is valid
    # but not what this test exercises — see test_wild_target_is_zero_gen).
    src = breeding.CompositeSource(selected, breeding.WildSource(exclude={"Anubis"}))
    chains = breeding.solve(
        db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=4, max_results=3)
    )
    assert len(chains) >= 1
    for c in chains:
        assert c.generations >= 1
        # Every step's child must be reachable from its parents in the table.
        for s in c.steps:
            assert breeding.direct_child(db, s.parent_a, s.parent_b) is not None
        # Final step produces Anubis.
        assert c.steps[-1].child == "Anubis"
        # Sources are a mix that includes the user's selected pals or wilds.
        assert all(s["type"] in ("selected", "wild") for s in c.sources)


def test_wild_target_is_zero_gen(db, breeding):
    """If wilds include the target, the solver correctly returns a 0-gen
    'just catch one' answer — the simplest valid plan."""
    src = breeding.WildSource()
    chains = breeding.solve(
        db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=3)
    )
    assert len(chains) >= 1
    assert chains[0].generations == 0
    assert chains[0].sources[0]["type"] == "wild"


def test_solver_performance_under_500ms(db, breeding):
    """A 4-gen search with wilds (304 species) must stay well under 500ms."""
    src = breeding.CompositeSource(
        breeding.SelectedSource([{"species": "Alpaca"}]), breeding.WildSource()
    )
    t0 = time.time()
    breeding.solve(db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=4))
    elapsed_ms = (time.time() - t0) * 1000
    assert elapsed_ms < 500, f"solver took {elapsed_ms:.0f}ms (budget 500ms)"


# ----------------------------------------------------------------------
# passive inheritance
# ----------------------------------------------------------------------
def test_passive_carries_through_chain(db, breeding):
    # Give the only pool pal a passive; require it on the target.
    src = breeding.CompositeSource(
        breeding.SelectedSource([{"species": "Alpaca", "passives": ["Legend"]}]),
        breeding.WildSource(),
    )
    chains = breeding.solve(
        db,
        src,
        breeding.BreedingSpec(
            target_pal="Anubis", required_passives=("Legend",), max_generations=4
        ),
    )
    assert len(chains) >= 1, "expected at least one chain carrying Legend"
    for c in chains:
        assert "Legend" in c.final_passives
        assert "Legend" in c.matched_passives
        # The passive must be present on every step from the carrying parent onward.
        # (At minimum, the final step inherits it.)
        assert "Legend" in c.steps[-1].inherited_passives


def test_required_passive_not_in_pool_yields_nothing(db, breeding):
    # Pool has no Legend anywhere; requiring it is impossible.
    src = breeding.CompositeSource(
        breeding.SelectedSource([{"species": "Alpaca"}]),  # no passives
        breeding.WildSource(),  # wilds have no passives
    )
    chains = breeding.solve(
        db,
        src,
        breeding.BreedingSpec(
            target_pal="Anubis", required_passives=("Legend",), max_generations=4
        ),
    )
    assert chains == []


def test_passive_inheritance_capped_at_four(db, breeding):
    # Two parents with 3 distinct passives each (6 total) -> child capped at 4.
    src = breeding.SelectedSource(
        [
            {"species": "AmaterasuWolf_Dark", "passives": ["A", "B", "C"]},
            {"species": "GhostDragon_Fire", "passives": ["D", "E", "F"]},
        ]
    )
    chains = breeding.solve(
        db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=2)
    )
    assert chains
    # The final child's passive count never exceeds the game cap of 4.
    for c in chains:
        assert len(c.final_passives) <= 4


# ----------------------------------------------------------------------
# gender
# ----------------------------------------------------------------------
def test_gender_feasible_when_species_supports_it(db, breeding):
    # Anubis is BOTH gender (per palcalc data); target_gender Female is feasible.
    src = breeding.SelectedSource(
        [{"species": "AmaterasuWolf_Dark"}, {"species": "GhostDragon_Fire"}]
    )
    chains = breeding.solve(
        db,
        src,
        breeding.BreedingSpec(
            target_pal="Anubis", target_gender=breeding.Gender.FEMALE, max_generations=2
        ),
    )
    assert len(chains) >= 1
    assert all(c.gender_feasible for c in chains)


def test_gender_infeasible_filters_results(db, breeding):
    # Find a MALE_ONLY species in the data and target it as FEMALE -> no chains.
    male_only = [t for t, g in db.breedable_genders.items() if g == "MALE_ONLY"]
    if not male_only:
        pytest.skip("no MALE_ONLY species in this data snapshot")
    target = male_only[0]
    # Provide a parent pool that can reach the target (use wilds).
    src = breeding.CompositeSource(
        breeding.SelectedSource([]), breeding.WildSource()
    )
    chains = breeding.solve(
        db,
        src,
        breeding.BreedingSpec(
            target_pal=target,
            target_gender=breeding.Gender.FEMALE,  # impossible for MALE_ONLY
            max_generations=3,
        ),
    )
    assert chains == [], f"{target} is MALE_ONLY; FEMALE target should yield no chains"


# ----------------------------------------------------------------------
# ranking + dedup
# ----------------------------------------------------------------------
def test_chains_ranked_by_fewest_generations(db, breeding):
    src = breeding.CompositeSource(
        breeding.SelectedSource(
            [{"species": "AmaterasuWolf_Dark"}, {"species": "GhostDragon_Fire"}]
        ),
        breeding.WildSource(),
    )
    chains = breeding.solve(
        db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=3, max_results=5)
    )
    if len(chains) >= 2:
        gens = [c.generations for c in chains]
        assert gens == sorted(gens), "chains must be ordered by generation count"


def test_no_duplicate_chain_signatures(db, breeding):
    src = breeding.CompositeSource(
        breeding.SelectedSource([{"species": "Alpaca"}]), breeding.WildSource()
    )
    chains = breeding.solve(
        db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=4, max_results=5)
    )
    sigs = [
        (c.target, frozenset((s.parent_a, s.parent_b, s.child) for s in c.steps))
        for c in chains
    ]
    assert len(sigs) == len(set(sigs)), "duplicate chain signatures in results"


def test_max_results_respected(db, breeding):
    src = breeding.CompositeSource(
        breeding.SelectedSource([{"species": "Alpaca"}]), breeding.WildSource()
    )
    chains = breeding.solve(
        db, src, breeding.BreedingSpec(target_pal="Anubis", max_generations=4, max_results=2)
    )
    assert len(chains) <= 2


# ----------------------------------------------------------------------
# source adapters
# ----------------------------------------------------------------------
def test_owned_source_normalizes_boss_prefix(db, breeding):
    # Save CharacterIDs carry BOSS_ prefixes; OwnedSource must strip them.
    pals = [
        {"character_id": "BOSS_Anubis", "gender": "Male", "passive_skills": []},
    ]
    src = breeding.OwnedSource(pals)
    refs = src.initial_refs(db)
    assert len(refs) == 1
    assert refs[0].species == "Anubis"
    assert refs[0].gender == breeding.Gender.MALE


def test_owned_source_skips_unbreedable(db, breeding):
    pals = [
        {"character_id": "Anubis", "gender": "Male", "passive_skills": []},
        {"character_id": "SOME_RAID_BOSS_NOT_IN_TABLE", "gender": "Female", "passive_skills": []},
    ]
    refs = breeding.OwnedSource(pals).initial_refs(db)
    assert [r.species for r in refs] == ["Anubis"]


def test_owned_source_carries_provenance(db, breeding):
    pals = [
        {
            "character_id": "Anubis", "gender": "Female", "passive_skills": ["Legend"],
            "instance_id": "abc-123", "nickname": "Buddy", "level": 50, "owner_uid": "player1",
        }
    ]
    refs = breeding.OwnedSource(pals).initial_refs(db)
    assert refs[0].provenance["instance_id"] == "abc-123"
    assert refs[0].provenance["nickname"] == "Buddy"
    assert "Legend" in refs[0].passives


def test_selected_source_gender_defaults_wildcard(db, breeding):
    refs = breeding.SelectedSource([{"species": "Anubis"}]).initial_refs(db)
    assert refs[0].gender == breeding.Gender.WILDCARD


def test_selected_source_warns_on_unbreedable(db, breeding):
    src = breeding.SelectedSource([{"species": "Anubis"}, {"species": "FAKE_PAL"}])
    refs = src.initial_refs(db)
    assert len(refs) == 1
    assert any("FAKE_PAL" in w for w in src.warnings)


def test_wild_source_covers_all_tribes_except_excluded(db, breeding):
    src = breeding.WildSource(exclude={"Anubis"})
    refs = src.initial_refs(db)
    species = {r.species for r in refs}
    assert "Anubis" not in species
    assert len(species) == len(db.breedable_tribes()) - 1
    assert all(r.gender == breeding.Gender.WILDCARD for r in refs)
    assert all(r.origin == "wild" for r in refs)


def test_composite_source_dedups_group_keys(db, breeding):
    # Same species from two adapters -> one ref.
    src = breeding.CompositeSource(
        breeding.SelectedSource([{"species": "Anubis"}]),
        breeding.WildSource(),
    )
    refs = src.initial_refs(db)
    anubis_refs = [r for r in refs if r.species == "Anubis"]
    assert len(anubis_refs) == 1
