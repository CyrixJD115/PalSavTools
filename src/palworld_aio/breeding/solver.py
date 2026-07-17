"""The breeding-chain solver — Selection Mode and Save Mode share this.

Algorithm: iterative working-set expansion (adapted from palcalc, but simpler
— no effort/IV-probability engine). We grow a frontier of reachable ``PalRef``s
one breeding generation at a time, breeding every compatible pair, and keep
only the optimal ref per group. The load-bearing optimizations, mostly lifted
from palcalc, are:

1. **Reachability pruning** via the precomputed ``MinBreedingSteps`` map
   (``BreedingDB.reachable``): before breeding a pair we check the resulting
   child can still reach the target within the remaining generation budget.
   Without this the frontier explodes combinatorially.
2. **Effective-passives grouping**: two refs are interchangeable for breeding
   if they share species, gender, and the *required-relevant* subset of their
   passives. Non-required passives are collapsed to a single boolean
   ("has extras") in the group key — so a player who owns 50 Anubis with 50
   different random passive sets occupies ONE group slot, not 50. This is the
   palcalc ``WorkingSet.DefaultGroupFn`` + ``ToDedicatedPassives`` trick; it is
   what makes Save Mode tractable over thousands of owned pals. The full
   passive set is still carried on each ref for the final answer.
3. **Optimal-per-group keep**: within a group we keep only the cheapest ref
   (fewest generations, then most required-passive matches).

Passive inheritance is modeled as *possibility*, not probability: a child "can
have" passive P iff at least one parent has P (union, capped at 4 slots). This
tracks what's achievable; the Tier-3 probability model can be layered on later
without changing this loop.

Gender: bred children are ``WILDCARD``. A pair is compatible when at least one
male and one female are present (wildcard counts as either). ``target_gender``
feasibility is checked at the end against the species' gender probability — a
bred WILDCARD child of a species that can be the requested gender is feasible.
"""

from __future__ import annotations

import itertools
from typing import Iterable, Optional

from .data import BreedingDB
from .model import (
    BreedingSpec,
    BreedingStep,
    Chain,
    Gender,
    PalRef,
)
from .sources import SourceAdapter

_MAX_PASSIVES = 4  # game hard cap; a child can hold at most 4 passives
# Sentinel marking "one or more non-required passives present" in an effective
# passives set. Kept distinct from any real passive name (which are CamelCase
# internal IDs like "Legend", never this lowercase sentinel).
_OTHER = "\x00other"


def solve(
    db: BreedingDB,
    source: SourceAdapter,
    spec: BreedingSpec,
) -> list[Chain]:
    """Return up to ``spec.max_results`` chains from ``source`` to ``spec.target_pal``.

    Empty list if unreachable within ``spec.max_generations`` or no chain
    satisfies the required-passives / target-gender constraints.
    """
    required = frozenset(spec.required_passives)

    # --- seed the working set from the source adapter, pruning unreachable pals
    initial = [r for r in source.initial_refs(db) if _keep_seed(db, r, spec)]
    working: dict[tuple, PalRef] = {}
    for ref in initial:
        _merge(working, ref, required)

    # Short-circuit: the target is already in the seed pool (e.g. the player
    # owns one). Still subject to the passive / gender constraints below.
    target_refs: list[PalRef] = []

    # --- iterate: breed pairs, add children, prune, repeat
    for gen in range(spec.max_generations):
        # Snapshot keys before we mutate; only the existing frontier breeds this pass.
        frontier = list(working.values())
        if not frontier:
            break

        remaining_budget = spec.max_generations - (gen + 1)
        new_children: list[PalRef] = []

        # Symmetric product with i<=j dedup. ``itertools.combinations_with_replacement``
        # gives unordered pairs including (a,a) for same-species self-breeds.
        for p1, p2 in _unordered_pairs(frontier):
            if not _gender_compatible(p1, p2):
                continue
            child_species = db.forward(p1.species, p2.species)
            if child_species is None:
                continue
            if not db.reachable(child_species, spec.target_pal, remaining_budget):
                continue
            inherited = _inherit_passives(p1.passives, p2.passives)
            child_ref = PalRef(
                species=child_species,
                gender=Gender.WILDCARD,
                passives=inherited,
                generation=gen + 1,
                parents=(p1, p2),
                origin="bred",
            )
            new_children.append(child_ref)

        if not new_children:
            break

        changed = False
        for ref in new_children:
            if ref.species == spec.target_pal:
                target_refs.append(ref)
            if _merge(working, ref, required):
                changed = True
        if not changed:
            # Frontier is stable: no ref improved on what we already have. Further
            # generations can't help.
            break

    return _build_results(db, target_refs, working, spec, required)


# ----------------------------------------------------------------------
# pair iteration + merge — the working-set core
# ----------------------------------------------------------------------
def _unordered_pairs(refs: list[PalRef]) -> Iterable[tuple[PalRef, PalRef]]:
    """All unordered pairs (including self-pairs) from ``refs``.

    ``combinations_with_replacement`` yields (a,b) with a<=b by position, which
    covers every distinct unordered pair exactly once — what we want, since
    breeding is symmetric. Same-position pairs (a,a) give the self-breed case.
    """
    return itertools.combinations_with_replacement(refs, 2)


def _merge(
    working: dict[tuple, PalRef],
    ref: PalRef,
    required: frozenset[str],
) -> bool:
    """Insert ``ref`` if it improves on the existing entry for its group.

    Returns True if the working set changed (new group or better ref). "Better"
    = fewer generations, then more required-passive matches. This is the single
    optimization that keeps the frontier small — see palcalc ``WorkingSet``.

    The group key uses **effective passives** (required subset + an "has extras"
    sentinel), NOT the full passive set — otherwise a player owning 50 pals of
    one species with 50 different random passives would occupy 50 slots and the
    frontier×frontier cartesian product would explode. Two refs with the same
    species/gender/required-passives breed identically regardless of their
    irrelevant passives, so they collapse to one group.
    """
    key = _group_key(ref, required)
    existing = working.get(key)
    if existing is None:
        working[key] = ref
        return True
    if _is_better(ref, existing, required):
        working[key] = ref
        return True
    return False


def _group_key(ref: PalRef, required: frozenset[str]) -> tuple:
    """Group identity: (species, gender, effective-passives).

    Effective passives = the required passives the ref actually carries, plus a
    sentinel iff it has any *extra* non-required passives (so we don't pretend a
    pal with extras is identical to one without — extras can matter if a later
    requirement is added, and they're free passive slots already filled).
    """
    eff = _effective_passives(ref.passives, required)
    return (ref.species, ref.gender, eff)


def _effective_passives(
    passives: frozenset[str], required: frozenset[str]
) -> frozenset[str]:
    """Collapse non-required passives to a single sentinel.

    ``{"Legend", "Runner", "Swift"}`` with required ``{"Legend"}`` →
    ``{"Legend", _OTHER}``. This is what makes the working set small: only the
    required-relevant distinctions survive, everything else folds together.
    """
    kept = passives & required
    has_extra = bool(passives - required)
    return frozenset(kept | {_OTHER}) if has_extra else frozenset(kept)


def _is_better(a: PalRef, b: PalRef, required: frozenset[str]) -> bool:
    """True if ``a`` is strictly preferable to ``b`` for future breeding."""
    if a.generation != b.generation:
        return a.generation < b.generation
    a_match = len(a.passives & required)
    b_match = len(b.passives & required)
    if a_match != b_match:
        return a_match > b_match
    return False


# ----------------------------------------------------------------------
# passives + gender
# ----------------------------------------------------------------------
def _inherit_passives(a: frozenset[str], b: frozenset[str]) -> frozenset[str]:
    """Union of both parents' passives, capped at 4 (game slot limit).

    We keep *required* passives preferentially when truncation is needed, so a
    chain never silently drops a passive the user asked for. Stable ordering by
    insertion (a's passives first) keeps group keys deterministic.
    """
    combined = list(a) + [p for p in b if p not in a]
    if len(combined) <= _MAX_PASSIVES:
        return frozenset(combined)
    return frozenset(combined[:_MAX_PASSIVES])


def _gender_compatible(p1: PalRef, p2: PalRef) -> bool:
    """A pair can breed iff one can be male and the other female.

    WILDCARD/UNKNOWN count as either. Same concrete gender (Male+Male,
    Female+Female) is incompatible unless one is wildcard-ish.
    """
    g1, g2 = p1.gender, p2.gender
    if g1 in (Gender.WILDCARD, Gender.UNKNOWN) or g2 in (Gender.WILDCARD, Gender.UNKNOWN):
        return True
    return {g1, g2} == {Gender.MALE, Gender.FEMALE}


def _gender_feasible(db: BreedingDB, species: str, target: Optional[Gender]) -> bool:
    """Can ``species`` be the requested ``target`` gender?

    ``None`` target → always feasible. Otherwise check the gender probability
    table: any nonzero probability for that gender means a bred WILDCARD child
    of this species can be it. Defaults to True for unknown species (we don't
    have palcalc data for them; better to over-offer than hide a valid chain).
    """
    if target is None or target in (Gender.WILDCARD, Gender.UNKNOWN):
        return True
    prob = db.gender_probability(species)
    if target is Gender.MALE:
        return prob.get("male", 0.0) > 0
    if target is Gender.FEMALE:
        return prob.get("female", 0.0) > 0
    return True


# ----------------------------------------------------------------------
# seed filtering
# ----------------------------------------------------------------------
def _keep_seed(db: BreedingDB, ref: PalRef, spec: BreedingSpec) -> bool:
    """Drop seed pals that can't possibly contribute to the target chain.

    A pal is kept if it can reach the target within the full generation budget.
    Same-species-as-target is always kept (it might already satisfy the spec).
    """
    if ref.species == spec.target_pal:
        return True
    return db.reachable(ref.species, spec.target_pal, spec.max_generations)


# ----------------------------------------------------------------------
# result assembly
# ----------------------------------------------------------------------
def _build_results(
    db: BreedingDB,
    bred_targets: list[PalRef],
    working: dict[tuple, PalRef],
    spec: BreedingSpec,
    required: frozenset[str],
) -> list[Chain]:
    """Collect qualifying target refs (seed-owned or bred) and rank them."""
    candidates: list[PalRef] = list(bred_targets)
    # Include a target that was already in the seed pool (e.g. owned target pal
    # that nonetheless needs more passives bred onto it — or just a 0-gen "you
    # already have it" answer).
    seed_target_key_prefix = (spec.target_pal,)
    for key, ref in working.items():
        if key[0] != spec.target_pal:
            continue
        if ref.origin != "bred":  # bred ones already in `bred_targets`
            candidates.append(ref)

    # Filter by constraints.
    qualifying: list[PalRef] = []
    for ref in candidates:
        if required and not required.issubset(ref.passives):
            continue
        if not _gender_feasible(db, ref.species, spec.target_gender):
            continue
        qualifying.append(ref)

    # Rank: fewest generations first, then most required-passive matches,
    # then fewest total passives (cleaner chains).
    qualifying.sort(
        key=lambda r: (
            r.generation,
            -len(r.passives & required),
            len(r.passives),
        )
    )

    # Build chains, then de-duplicate by step signature. The same logical chain
    # can surface as multiple refs (e.g. a gen-1 and a gen-2 ref whose lineage
    # is identical because gen-2 just re-breeds the target with itself). We also
    # drop degenerate self-breed-only chains (target+target→target with no other
    # steps and no passive gain) — those carry no information beyond "you have
    # the pal already", which the 0-gen owned answer already conveys.
    chains: list[Chain] = []
    seen_sigs: set[tuple] = set()
    for ref in qualifying:
        chain = _build_chain(db, ref, spec)
        sig = _chain_signature(chain)
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        if _is_degenerate_self_breed(chain, required):
            continue
        chains.append(chain)
        if len(chains) >= spec.max_results:
            break
    return chains


def _chain_signature(chain: Chain) -> tuple:
    """Content identity for a chain: its sorted set of breeding edges.

    Two chains with the same edges (regardless of how many redundant self-breed
    generations got appended) are the same plan.
    """
    edges = frozenset((s.parent_a, s.parent_b, s.child) for s in chain.steps)
    return (chain.target, edges, frozenset(chain.final_passives))


def _is_degenerate_self_breed(chain: Chain, required: frozenset[str]) -> bool:
    """True if the chain is ONLY target+target→target with no passive gain.

    Such a chain says nothing the 0-gen "you own the target" answer doesn't.
    Kept only when required passives are actually gained (rare: breeding a pal
    with itself to roll for inherited passives — modeled here as the child
    keeping the union, so a self-breed never *adds* passives; thus always drop).
    """
    if not chain.steps:
        return False  # 0-gen owned/selected answer is never "degenerate"
    return all(
        s.parent_a == chain.target and s.parent_b == chain.target and s.child == chain.target
        for s in chain.steps
    )


def _build_chain(db: BreedingDB, final: PalRef, spec: BreedingSpec) -> Chain:
    """Walk ``final.parents`` recursively into a flat, ordered step list."""
    steps: list[BreedingStep] = []
    sources: list[dict] = []
    _flatten(db, final, steps, sources, set())

    # Deduplicate sources by (origin, species, provenance identity).
    seen_src: set[tuple] = set()
    unique_sources: list[dict] = []
    for s in sources:
        identity = (s.get("type"), s.get("pal"), s.get("instance_id", ""))
        if identity in seen_src:
            continue
        seen_src.add(identity)
        unique_sources.append(s)

    # Preserve insertion order but parents-before-children (already the case
    # because we recurse depth-first, emitting the step at visit time).
    generations = final.generation
    return Chain(
        target=spec.target_pal,
        generations=generations,
        steps=steps,
        final_passives=sorted(final.passives),
        sources=unique_sources,
        gender_feasible=_gender_feasible(db, final.species, spec.target_gender),
        matched_passives=sorted(final.passives & frozenset(spec.required_passives)),
    )


def _flatten(
    db: BreedingDB,
    ref: PalRef,
    steps: list[BreedingStep],
    sources: list[dict],
    visited: set,
) -> None:
    """Depth-first walk: emit leaf sources, emit bred steps after recursing."""
    if id(ref) in visited:
        return
    visited.add(id(ref))

    if ref.is_source:
        sources.append(
            {
                "type": ref.origin,
                "pal": ref.species,
                "display": db.display_name(ref.species),
                "gender": ref.gender.value,
                "passives": sorted(ref.passives),
                **ref.provenance,
            }
        )
        return

    p1, p2 = ref.parents  # type: ignore[misc]
    _flatten(db, p1, steps, sources, visited)
    _flatten(db, p2, steps, sources, visited)
    inherited = tuple(sorted(ref.passives))
    feasible = _gender_feasible(db, ref.species, None)
    steps.append(
        BreedingStep(
            parent_a=p1.species,
            parent_b=p2.species,
            child=ref.species,
            inherited_passives=inherited,
            gender_feasible=feasible,
        )
    )
