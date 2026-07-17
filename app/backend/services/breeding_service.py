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
def solve_chain(req: ChainRequest, level_dict: dict | None = None) -> ChainResponse:
    """Run the solver. ``level_dict`` is required for ``mode="save"``."""
    db = _db()
    warnings: list[str] = []

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
    source = _build_source(req, level_dict, warnings)
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


def _build_source(req: ChainRequest, level_dict: dict | None, warnings: list[str]):
    """Construct the SourceAdapter for the request mode.

    This is the palcalc unification point: Save Mode and Selection Mode differ
    only in which adapter feeds the solver.
    """
    adapters: list = []

    if req.mode == "save":
        if level_dict is None:
            warnings.append("Save Mode requires a loaded save; returning no chains")
            return None
        pals = world_service.list_pals(
            level_dict,
            name_map=data_service.character_name_map(),
            limit=5000,
        )
        if req.owner_uid:
            wanted = req.owner_uid.replace("-", "").lower()
            pals = [p for p in pals if (p.get("owner_uid") or "").replace("-", "").lower() == wanted]
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
