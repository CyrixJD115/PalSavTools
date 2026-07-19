from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.backend.schemas import (
    BaseListResponse, GuildListResponse,
    PalListResponse, PlayerListResponse,
)
from app.backend.services import base_service, data_service, world_service
from app.backend.state import save_state

router = APIRouter()


def _require():
    """Return the loaded ``LoadedSave`` or raise 409."""
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded


def _paginate(items: list, limit: int, offset: int) -> tuple[list, int, bool]:
    """Apply (offset, limit) and return (page, total, has_more)."""
    total = len(items)
    page = items[offset:offset + limit] if limit > 0 else items[offset:]
    has_more = (offset + limit) < total
    return page, total, has_more


def _search_filter(items: list, search: str, fields: list[str]) -> list:
    """Case-insensitive substring filter across multiple fields.

    Returns the original list when ``search`` is empty.
    """
    if not search:
        return items
    needle = search.lower()
    out = []
    for item in items:
        haystack = " ".join(str(item.get(f, "")) for f in fields).lower()
        if needle in haystack:
            out.append(item)
    return out


@router.get("/players", response_model=PlayerListResponse)
async def get_players(
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str = Query("", max_length=64),
) -> PlayerListResponse:
    """Paginated player list (default 20 per page).

    Pulls only ``GroupSaveDataMap`` + ``GameTimeSaveData`` (~1 MB) instead of
    materializing the full ~200 MB ``level_dict``. ``search`` matches name or
    UID substring.
    """
    loaded = _require()
    wsd = loaded.build_mini_wsd(
        "GroupSaveDataMap", "GameTimeSaveData", "CharacterSaveParameterMap",
    )
    players = world_service.list_players_from_wsd(wsd)
    pal_counts = loaded.player_pal_counts
    levels = loaded.player_levels
    for p in players:
        uid_clean = p["uid"].replace("-", "").lower()
        p["level"] = levels.get(uid_clean, 0)
        p["pal_count"] = pal_counts.get(uid_clean, 0)
    # Filter AFTER enrichment so search hits resolved levels/names.
    players = _search_filter(players, search, ["name", "uid", "guild_name"])
    page, total, has_more = _paginate(players, limit, offset)
    return PlayerListResponse(players=page, total=total) if not has_more else \
        PlayerListResponse(players=page, total=total)


@router.get("/guilds", response_model=GuildListResponse)
async def get_guilds(
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str = Query("", max_length=64),
) -> GuildListResponse:
    """Paginated guild list (default 20 per page).

    Pulls only ``GroupSaveDataMap`` (~1 MB). ``search`` matches name, leader
    UID, or guild ID substring.
    """
    loaded = _require()
    wsd = loaded.build_mini_wsd("GroupSaveDataMap")
    guilds = world_service.list_guilds_from_wsd(wsd)
    guilds = _search_filter(guilds, search, ["name", "leader_uid", "id"])
    page, total, _ = _paginate(guilds, limit, offset)
    return GuildListResponse(guilds=page, total=total)


@router.get("/bases", response_model=BaseListResponse)
async def get_bases(
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str = Query("", max_length=64),
) -> BaseListResponse:
    """Paginated base list (default 20 per page).

    Pulls only ``BaseCampSaveData`` + ``GroupSaveDataMap`` (~3 MB). ``search``
    matches guild name, guild ID, or base ID.
    """
    loaded = _require()
    wsd = loaded.build_mini_wsd("BaseCampSaveData", "GroupSaveDataMap")
    try:
        enriched = base_service.get_enriched_base_list_from_wsd(wsd)
    except AttributeError:
        # Older base_service without the _from_wsd variant — fall back to full.
        enriched = base_service.get_enriched_base_list(loaded.level_dict)
    except Exception as e:
        raise HTTPException(500, f"Failed to build base list: {e}")
    enriched = _search_filter(enriched, search, ["guild_name", "guild_id", "id"])
    page, total, _ = _paginate(enriched, limit, offset)
    return BaseListResponse(bases=page, total=total)


@router.get("/pals", response_model=PalListResponse)
async def get_pals(
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    search: str = Query("", max_length=64),
) -> PalListResponse:
    """Paginated pal list (default 50 per page).

    ``search`` matches character ID, display name, nickname, or owner UID.

    Uses :func:`list_pals_stream` which scans CharacterSaveParameterMap
    entry-by-entry and short-circuits once the requested page + filter
    matches are found — avoids building a 2000+ entry list when the user
    only wants page 1 (50 items).
    """
    loaded = _require()
    wsd = loaded.build_mini_wsd("CharacterSaveParameterMap")
    page, total = world_service.list_pals_stream(
        wsd,
        name_map=data_service.character_name_map(),
        limit=limit,
        offset=offset,
        search=search,
    )
    return PalListResponse(pals=page, total=total)


@router.get("/pals/stats")
async def get_pal_stats() -> dict:
    """Aggregate pal stats (no pagination — single object)."""
    loaded = _require()
    wsd = loaded.build_mini_wsd("CharacterSaveParameterMap")
    return world_service.get_current_stats_from_wsd(wsd)
