"""Breeding calculator service — thin bridge to the engine in ``src/``.

The breeding engine (``src/palworld_aio/breeding/``) is pure Python with zero
deps on ``palsav`` / Qt / save-decode code. We load it via ``importlib`` — the
same pattern ``map_service`` uses for ``map_data_service`` — because the parent
package ``palworld_aio`` eagerly imports ``main`` (which pulls Qt/i18n deps).

This module owns:
  * the importlib load of the engine (once, cached at module scope);
  * the ``BreedingDB`` cache (the engine itself also lru_caches ``load``);
  * wiring between the API request shape and the engine's ``solve``/``direct_*``.

Per the WebUI build contract: no domain math here — this is validate → call
engine → serialize. Save Mode reuses ``world_service.list_pals`` (already
extracts gender + passives); we just filter by owner and feed the dicts to
``OwnedSource`` verbatim.
"""

from __future__ import annotations

import importlib.util
import logging
import time
from pathlib import Path

from app.backend import paths
from app.backend.schemas import (
    BreedablePal,
    BreedablePalsResponse,
    ChainRequest,
    ChainResponse,
    ChainSchema,
    BreedingStepSchema,
    DirectChildRequest,
    DirectChildResponse,
    DirectParentsRequest,
    DirectParentsResponse,
    DirectPartnersRequest,
    DirectPartnersResponse,
    DirectResultItem,
)
from app.backend.services import data_service, world_service

logger = logging.getLogger(__name__)

# ── Load the breeding engine via importlib (mirrors map_service) ─────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BREEDING_PKG = _REPO_ROOT / "src" / "palworld_aio" / "breeding" / "__init__.py"

try:
    _spec = importlib.util.spec_from_file_location(
        "pst_breeding", _BREEDING_PKG, submodule_search_locations=[str(_BREEDING_PKG.parent)]
    )
    assert _spec is not None and _spec.loader is not None
    breeding = importlib.util.module_from_spec(_spec)
    import sys
    sys.modules["pst_breeding"] = breeding
    _spec.loader.exec_module(breeding)
    _ENGINE_AVAILABLE = True
    _ENGINE_ERROR: str | None = None
except Exception as exc:  # noqa: BLE001 — engine load must not crash the app
    logger.warning("breeding engine unavailable; breeding routes will 503", exc_info=True)
    breeding = None  # type: ignore[assignment]
    _ENGINE_AVAILABLE = False
    _ENGINE_ERROR = str(exc)


def _db():
    """Return the cached ``BreedingDB``. Raises 503 if the engine failed to load."""
    if not _ENGINE_AVAILABLE:
        from fastapi import HTTPException
        raise HTTPException(503, f"Breeding engine unavailable: {_ENGINE_ERROR}")
    # The engine's BreedingDB.load is lru_cached on the dir path.
    return breeding.BreedingDB.load(paths.GAME_DATA_DIR)


def engine_ready() -> bool:
    """True if the breeding engine imported successfully."""
    return _ENGINE_AVAILABLE


# ----------------------------------------------------------------------
# breedable pal list (for pickers)
# ----------------------------------------------------------------------
def breedable_pals() -> BreedablePalsResponse:
    db = _db()
    out: list[BreedablePal] = []
    for tribe in db.breedable_tribes():
        info = db.pal_info.get(tribe, {})
        out.append(
            BreedablePal(
                tribe=tribe,
                display_name=db.display_name(tribe),
                icon=db.icon_path(tribe),
                combi_rank=info.get("combi_rank", 0),
                rarity=info.get("rarity", 0),
                gender_prob=db.gender_probability(tribe),
            )
        )
    return BreedablePalsResponse(pals=out, total=len(out))


# ----------------------------------------------------------------------
# Direct Mode
# ----------------------------------------------------------------------
def direct_child(req: DirectChildRequest) -> DirectChildResponse:
    db = _db()
    r = breeding.direct_child(db, req.parent_a, req.parent_b)
    if r is None:
        return DirectChildResponse(result=None)
    return DirectChildResponse(result=_direct_item(db, r))


def direct_partners(req: DirectPartnersRequest) -> DirectPartnersResponse:
    db = _db()
    rows = breeding.direct_partners(db, req.parent_a, req.target_child)
    return DirectPartnersResponse(partners=[_direct_item(db, r) for r in rows])


def direct_parents(req: DirectParentsRequest) -> DirectParentsResponse:
    """target → ALL parent pairs (no Parent A pinned)."""
    db = _db()
    rows = breeding.direct_parents(db, req.target_child)
    return DirectParentsResponse(parents=[_direct_item(db, r) for r in rows])


def _direct_item(db, r) -> DirectResultItem:
    return DirectResultItem(
        parent_a=r.parent_a,
        parent_b=r.parent_b,
        child=r.child,
        child_display=r.child_display,
        child_icon=r.child_icon,
        child_gender_prob=r.child_gender_prob,
        combo_type=r.combo_type,
    )


# ----------------------------------------------------------------------
# Chain Mode (Selection + Save share one solver)
# ----------------------------------------------------------------------
def solve_chain(
    req: ChainRequest,
    wsd: dict | None = None,
    pal_counts: dict[str, int] | None = None,
) -> ChainResponse:
    """Run the solver. ``wsd`` (a mini-wsd with ``CharacterSaveParameterMap``)
    is required for ``mode="save"``. ``pal_counts`` is the pre-computed
    ``LoadedSave.player_pal_counts`` (keyed by ``sp.OwnerPlayerUId``,
    dash-stripped lowercase) — used to resolve host-player ambiguity in the
    owner filter."""
    db = _db()
    warnings: list[str] = []

    # Diagnostic: confirm the wsd actually has CSP entries before we filter.
    if req.mode == "save" and wsd is not None:
        csp_count = len(world_service._map_entries(wsd, "CharacterSaveParameterMap"))
        logger.debug(
            "solve_chain: wsd has %d CSP entries; pal_counts has %d owners",
            csp_count, len(pal_counts or {}),
        )

    # Build the spec (engine-side dataclass).
    target_gender = _coerce_gender(req.target_gender)
    spec = breeding.BreedingSpec(
        target_pal=req.target_pal,
        required_passives=tuple(req.required_passives),
        target_gender=target_gender,
        max_generations=req.max_generations,
        max_results=req.max_results,
    )

    # Build the source adapter from the request mode.
    source = _build_source(req, wsd, warnings, pal_counts=pal_counts)
    if source is None:
        return ChainResponse(chains=[], total=0, elapsed_ms=0, warnings=warnings)

    t0 = time.time()
    chains = breeding.solve(db, source, spec)
    elapsed_ms = int((time.time() - t0) * 1000)

    schema_chains = [_chain_schema(db, c) for c in chains]
    return ChainResponse(
        chains=schema_chains,
        total=len(schema_chains),
        elapsed_ms=elapsed_ms,
        warnings=warnings,
    )


def _build_source(
    req: ChainRequest,
    wsd: dict | None,
    warnings: list[str],
    pal_counts: dict[str, int] | None = None,
):
    """Construct the SourceAdapter for the request mode.

    This is the palcalc unification point: Save Mode and Selection Mode differ
    only in which adapter feeds the solver.

    ``wsd`` is a mini-wsd containing ``CharacterSaveParameterMap`` passed by
    the route (built via ``build_mini_wsd``, ~30 MB) instead of the full
    ~200 MB ``level_dict``.

    ``pal_counts`` is the pre-computed ``LoadedSave.player_pal_counts`` map
    (keyed by ``sp.OwnerPlayerUId``, dash-stripped lowercase). It's used as
    a tiebreaker: when the requested ``owner_uid`` (from the players
    dropdown, which uses guild ``player_uid``) doesn't directly match any
    pal's ``owner_uid`` (which can be ``key.PlayerUId`` or
    ``sp.OwnerPlayerUId``), we check whether the requested UID is a known
    owner key in ``pal_counts`` and broaden the filter accordingly.
    """
    adapters: list = []

    if req.mode == "save":
        if wsd is None:
            warnings.append("Save Mode requires a loaded save; returning no chains")
            return None
        # NOTE: limit=0 means "no cap". The previous default of 5000 silently
        # truncated saves with >5000 pals, causing some players' pals to be
        # missed entirely (the precompute that populates player_pal_counts
        # has no cap, so the dropdown showed a non-zero count but the filter
        # found nothing). Breeding needs the full pal list.
        pals = world_service.list_pals_from_wsd(
            wsd,
            name_map=data_service.character_name_map(),
            limit=0,
        )
        logger.debug("_build_source: list_pals returned %d pals", len(pals))
        if req.owner_uid:
            wanted = world_service._s(req.owner_uid)
            logger.debug("_build_source: filtering by owner_uid=%s (normalized=%s)", req.owner_uid, wanted)
            before_pals = list(pals)

            # A pal's "owner" can be recorded two ways in the save:
            #   - key.PlayerUId      — the current container holder (often the host)
            #   - sp.OwnerPlayerUId  — the true original owner
            # For breeding we want the TRUE owner. list_pals_from_wsd sets
            # `owner_uid` preferring key.PlayerUId, which can mismatch the
            # player's guild UID on host-merged saves. So when the direct
            # match fails, re-walk the wsd and rebuild the filtered list
            # using sp.OwnerPlayerUId directly.
            pals = [p for p in before_pals if world_service._s(p.get("owner_uid") or "") == wanted]
            if not pals:
                # Fallback: filter by walking the raw CSP entries and matching
                # on sp.OwnerPlayerUId. This catches the host-player case where
                # key.PlayerUId != guild.player_uid but sp.OwnerPlayerUId does.
                pals = _filter_pals_by_true_owner(wsd, wanted, before_pals)

            logger.debug("_build_source: filter kept %d / %d pals", len(pals), len(before_pals))
            if not pals and before_pals:
                # Log a few sample owner_uid values for debugging.
                sample_owners = set()
                for p in before_pals[:200]:
                    o = p.get("owner_uid")
                    if o:
                        sample_owners.add(o)
                # Also dump the raw sp.OwnerPlayerUId values seen during the
                # fallback walk, so we can tell whether the wanted UID is
                # present under that field at all.
                raw_owner_sample: set[str] = set()
                for ch in world_service._map_entries(wsd, "CharacterSaveParameterMap")[:200]:
                    if not world_service._is_pal_entry(ch):
                        continue
                    sp = world_service._pal_entry_raw(ch)
                    owner = world_service._k(sp, "OwnerPlayerUId")
                    if owner:
                        raw_owner_sample.add(str(owner))
                logger.warning(
                    "_build_source: 0 pals matched owner=%s; "
                    "sample key.PlayerUId-derived owner_uid: %s; "
                    "sample sp.OwnerPlayerUId: %s",
                    wanted, list(sample_owners)[:5], list(raw_owner_sample)[:5],
                )
        if not pals:
            warnings.append("No owned pals match the filter; returning no chains")
            return None
        adapters.append(breeding.OwnedSource(pals))
    else:  # selection
        if not req.selected_pals:
            warnings.append("Selection Mode requires at least one selected pal")
            return None
        selected_dicts = [
            {"species": s.species, "gender": s.gender, "passives": s.passives}
            for s in req.selected_pals
        ]
        sel = breeding.SelectedSource(selected_dicts)
        adapters.append(sel)
        warnings.extend(sel.warnings)

    if req.include_wild:
        adapters.append(breeding.WildSource())

    if len(adapters) == 1:
        return adapters[0]
    return breeding.CompositeSource(*adapters)


def _filter_pals_by_true_owner(
    wsd: dict, wanted_uid: str, before_pals: list[dict],
) -> list[dict]:
    """Fallback ownership filter using ``sp.OwnerPlayerUId`` directly.

    The primary filter in :func:`_build_source` matches on
    ``list_pals_from_wsd``'s resolved ``owner_uid`` field, which prefers
    ``key.PlayerUId`` (the current container holder). On host-merged saves
    that field can carry the host's UID while the player's own pals still
    record the player as ``sp.OwnerPlayerUId`` — so the primary match
    returns nothing.

    This helper re-walks the raw ``CharacterSaveParameterMap`` entries,
    collects the ``InstanceId`` of every pal whose
    ``SaveParameter.OwnerPlayerUId`` normalizes to ``wanted_uid``, and
    returns the matching pal dicts from ``before_pals`` (so we reuse the
    already-built display fields instead of re-decoding).
    """
    if not wanted_uid:
        return []
    # Build a set of instance_ids whose true owner matches.
    wanted_ids: set[str] = set()
    for ch in world_service._map_entries(wsd, "CharacterSaveParameterMap"):
        if not world_service._is_pal_entry(ch):
            continue
        sp = world_service._pal_entry_raw(ch)
        owner = world_service._k(sp, "OwnerPlayerUId")
        if owner and world_service._s(owner) == wanted_uid:
            key = world_service._g(ch, "key") or {}
            inst = str(world_service._k(key, "InstanceId") or "")
            if inst:
                wanted_ids.add(inst.lower())
    if not wanted_ids:
        return []
    return [p for p in before_pals if (p.get("instance_id") or "").lower() in wanted_ids]


def _coerce_gender(raw: str | None):
    if not raw:
        return None
    return breeding.Gender.coerce(raw)


def _chain_schema(db, chain) -> ChainSchema:
    return ChainSchema(
        target=chain.target,
        generations=chain.generations,
        steps=[
            BreedingStepSchema(
                parent_a=s.parent_a,
                parent_b=s.parent_b,
                child=s.child,
                inherited_passives=list(s.inherited_passives),
                gender_feasible=s.gender_feasible,
            )
            for s in chain.steps
        ],
        final_passives=list(chain.final_passives),
        sources=list(chain.sources),
        gender_feasible=chain.gender_feasible,
        matched_passives=list(chain.matched_passives),
    )
