from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from web.backend.schemas import (
    BaseListResponse, ContainerListResponse, GuildListResponse,
    PalListResponse, PlayerDetail, PlayerListResponse,
)
from web.backend.services import base_service, data_service, player_service, world_service
from web.backend.state import save_state

router = APIRouter()


def _level_dict() -> dict:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded.level_dict


@router.get("/players", response_model=PlayerListResponse)
async def get_players() -> PlayerListResponse:
    loaded = save_state.get()
    level_dict = _level_dict()
    players = world_service.list_players(level_dict)
    enriched = []
    pal_counts = loaded.player_pal_counts if loaded else {}
    levels = loaded.player_levels if loaded else {}
    for p in players:
        uid_clean = p["uid"].replace("-", "").lower()
        p["level"] = levels.get(uid_clean, 0)
        p["pal_count"] = pal_counts.get(uid_clean, 0)
        enriched.append(p)
    return PlayerListResponse(players=enriched, total=len(enriched))


@router.get("/guilds", response_model=GuildListResponse)
async def get_guilds() -> GuildListResponse:
    guilds = world_service.list_guilds(_level_dict())
    return GuildListResponse(guilds=guilds, total=len(guilds))


@router.get("/bases", response_model=BaseListResponse)
async def get_bases() -> BaseListResponse:
    level = _level_dict()
    try:
        enriched = base_service.get_enriched_base_list(level)
    except Exception as e:
        raise HTTPException(500, f"Failed to build base list: {e}")
    return BaseListResponse(bases=enriched, total=len(enriched))


@router.get("/containers", response_model=ContainerListResponse)
async def get_containers(
    limit: int = Query(200, ge=1, le=5000),
) -> ContainerListResponse:
    containers = world_service.list_containers(_level_dict(), limit=limit)
    return ContainerListResponse(containers=containers, total=len(containers))


@router.get("/pals", response_model=PalListResponse)
async def get_pals(
    limit: int = Query(300, ge=1, le=5000),
) -> PalListResponse:
    pals = world_service.list_pals(
        _level_dict(),
        name_map=data_service.character_name_map(),
        limit=limit,
    )
    return PalListResponse(pals=pals, total=len(pals))

@router.get("/pals/stats")
async def get_pal_stats() -> dict:
    return world_service.get_current_stats(_level_dict())

