"""Map data endpoints — save-based data + static POIs.

``GET /api/map/data`` returns bases and players (save-dependent, projected).
``GET /api/map/pois`` returns static POI datasets (bosses, dungeons, …)
ported from PSP Rust — no save access required.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.backend.schemas import MapDataResponse, MapPoiResponse
from app.backend.services import map_service, poi_service
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


@router.get("/pois", response_model=MapPoiResponse)
async def get_map_pois() -> MapPoiResponse:
    """Return all static POI datasets with pre-computed map projections.

    Unlike ``/api/map/data`` this endpoint does **not** touch the loaded
    save — the data is static from PSP Rust's JSON files and projected at
    import time.  It works even when no save is loaded.
    """
    return MapPoiResponse(**poi_service.get_all_pois())
