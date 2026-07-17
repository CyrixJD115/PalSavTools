"""Breeding Calculator routes.

Three modes behind a single router:
  * ``GET  /breeding/pals``            — breedable-pal list for pickers
  * ``POST /breeding/direct/child``    — Direct Mode: A + B → child
  * ``POST /breeding/direct/partners`` — Direct Mode: A + target → B options
  * ``POST /breeding/chain``           — Selection Mode + Save Mode (one solver)

Direct + Selection work without a loaded save. Save Mode (``mode="save"`` on
``/chain``) requires a save and returns 409 if none is loaded. If the engine
itself failed to import, every route 503s with the load error.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.backend.schemas import (
    BreedablePalsResponse,
    ChainRequest,
    ChainResponse,
    DirectChildRequest,
    DirectChildResponse,
    DirectPartnersRequest,
    DirectPartnersResponse,
)
from app.backend.services import breeding_service
from app.backend.state import save_state

router = APIRouter(prefix="/breeding")


def _require_engine() -> None:
    if not breeding_service.engine_ready():
        raise HTTPException(503, "Breeding engine unavailable")


@router.get("/pals", response_model=BreedablePalsResponse)
async def get_breedable_pals() -> BreedablePalsResponse:
    _require_engine()
    return breeding_service.breedable_pals()


@router.post("/direct/child", response_model=DirectChildResponse)
async def post_direct_child(req: DirectChildRequest) -> DirectChildResponse:
    _require_engine()
    return breeding_service.direct_child(req)


@router.post("/direct/partners", response_model=DirectPartnersResponse)
async def post_direct_partners(req: DirectPartnersRequest) -> DirectPartnersResponse:
    _require_engine()
    return breeding_service.direct_partners(req)


@router.post("/chain", response_model=ChainResponse)
async def post_chain(req: ChainRequest) -> ChainResponse:
    """Compute breeding chains.

    Selection Mode (``mode="selection"``) needs no save. Save Mode
    (``mode="save"``) reads the loaded save's pals; returns 409 if no save is
    loaded. Both share one solver — the only difference is the source adapter.
    """
    _require_engine()
    level_dict = None
    if req.mode == "save":
        loaded = save_state.get()
        if loaded is None:
            raise HTTPException(409, "No save loaded — Save Mode requires a loaded save")
        level_dict = loaded.level_dict
    return breeding_service.solve_chain(req, level_dict=level_dict)
