"""Map data endpoints.

``GET /api/map/data`` returns bases and players with pre-computed pixel
coordinates for both world and tree maps. All coordinate math is done in
``map_service`` using the real ``coord`` Python module.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.backend.schemas import MapDataResponse
from web.backend.services import map_service
from web.backend.state import save_state

router = APIRouter(prefix="/map")


def _level_dict() -> dict:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded.level_dict


@router.get("/data", response_model=MapDataResponse)
async def get_map_data() -> MapDataResponse:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    players_dir = loaded.players_dir if loaded.players_dir != "(unknown)" else None
    data = map_service.get_map_data(
        loaded.level_dict,
        players_dir,
        pal_counts=loaded.player_pal_counts,
        levels=loaded.player_levels,
        positions=loaded.player_positions,
    )
    return MapDataResponse(**data)
