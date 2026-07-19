"""Map data endpoints.

``GET /api/map/data`` returns bases and players with pre-computed pixel
coordinates for both world and tree maps. Uses ``build_mini_wsd`` to
materialise only ``BaseCampSaveData`` + ``GroupSaveDataMap`` (~3 MB total)
instead of the full ``level_dict`` (~200 MB).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.backend.schemas import MapDataResponse
from app.backend.services import map_service
from app.backend.state import save_state

router = APIRouter(prefix="/map")


@router.get("/data", response_model=MapDataResponse)
async def get_map_data() -> MapDataResponse:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    players_dir = loaded.players_dir if loaded.players_dir != "(unknown)" else None

    # Build a mini-wsd containing ONLY the sections the map actually needs:
    # BaseCampSaveData (bases, ~2 MB) + GroupSaveDataMap (guilds/players, ~1 MB).
    # This avoids materializing the full ~200 MB level_dict.
    # The pre-computed player_pal_counts / player_levels / player_positions
    # (from CharacterSaveParameterMap) are passed separately — no need to
    # re-walk that section either.
    wsd = loaded.build_mini_wsd("BaseCampSaveData", "GroupSaveDataMap")

    data = map_service.get_map_data_from_wsd(
        wsd,
        players_dir=players_dir,
        pal_counts=loaded.player_pal_counts,
        levels=loaded.player_levels,
        positions=loaded.player_positions,
    )
    return MapDataResponse(**data)
