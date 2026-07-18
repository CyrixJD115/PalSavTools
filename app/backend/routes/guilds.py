"""Guild detail and mutation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.backend.schemas import (
    GuildDetail, RenameGuildRequest, SetGuildLevelRequest, SetLeaderRequest,
)
from app.backend.services import guild_service
from app.backend.services.cache_invalidation import invalidate_caches
from app.backend.state import save_state

router = APIRouter(prefix="/guilds")


def _require() -> dict:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded.level_dict


@router.get("/{guild_id}", response_model=GuildDetail)
async def get_guild_detail(guild_id: str) -> GuildDetail:
    detail = guild_service.get_guild_detail(_require(), guild_id)
    if detail is None:
        raise HTTPException(404, f"Guild not found: {guild_id}")
    return GuildDetail(**detail)


@router.put("/{guild_id}/name")
async def rename_guild(guild_id: str, body: RenameGuildRequest) -> dict:
    if not body.name.strip():
        raise HTTPException(400, "Name cannot be empty")
    if not guild_service.rename_guild(_require(), guild_id, body.name.strip()):
        raise HTTPException(404, f"Guild not found: {guild_id}")
    invalidate_caches()
    return {"status": "ok"}


@router.put("/{guild_id}/level")
async def set_guild_level(guild_id: str, body: SetGuildLevelRequest) -> dict:
    if body.level < 1 or body.level > 35:
        raise HTTPException(400, "Level must be between 1 and 35")
    if not guild_service.set_guild_level(_require(), guild_id, body.level):
        raise HTTPException(404, f"Guild not found: {guild_id}")
    invalidate_caches()
    return {"status": "ok"}


@router.put("/{guild_id}/leader")
async def set_leader(guild_id: str, body: SetLeaderRequest) -> dict:
    if not guild_service.make_member_leader(_require(), guild_id, body.player_uid):
        raise HTTPException(404, "Guild or player not found")
    invalidate_caches()
    return {"status": "ok"}


@router.delete("/{guild_id}/members/{player_uid}")
async def remove_member(guild_id: str, player_uid: str) -> dict:
    if not guild_service.remove_member(_require(), guild_id, player_uid):
        raise HTTPException(404, "Guild not found or cannot remove leader")
    invalidate_caches()
    return {"status": "ok"}


@router.delete("/{guild_id}")
async def delete_guild(guild_id: str) -> dict:
    if not guild_service.delete_guild(_require(), guild_id):
        raise HTTPException(404, f"Guild not found: {guild_id}")
    invalidate_caches()
    return {"status": "ok"}
