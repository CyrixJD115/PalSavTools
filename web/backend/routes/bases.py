"""Base detail and mutation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.backend.schemas import (
    BaseDetail, DeleteBaseRequest, RenameGuildRequest,
    SetBaseRadiusRequest, SetGuildLevelRequest,
)
from web.backend.services import base_service
from web.backend.state import save_state

router = APIRouter(prefix="/bases")


def _require() -> dict:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded.level_dict


@router.get("/{base_id}", response_model=BaseDetail)
async def get_base_detail(base_id: str) -> BaseDetail:
    detail = base_service.get_base_detail(_require(), base_id)
    if detail is None:
        raise HTTPException(404, f"Base not found: {base_id}")
    return BaseDetail(**detail)


@router.delete("/{base_id}")
async def delete_base(base_id: str, body: DeleteBaseRequest = DeleteBaseRequest()) -> dict:
    if not base_service.delete_base(_require(), base_id, body.delete_workers):
        raise HTTPException(404, f"Base not found: {base_id}")
    return {"status": "ok"}


@router.put("/{base_id}/radius")
async def set_base_radius(base_id: str, body: SetBaseRadiusRequest) -> dict:
    if not base_service.update_base_radius(_require(), base_id, body.radius):
        raise HTTPException(404, f"Base not found: {base_id}")
    return {"status": "ok"}


@router.put("/{base_id}/guild/name")
async def rename_guild(base_id: str, body: RenameGuildRequest) -> dict:
    """Rename the guild that owns this base."""
    detail = base_service.get_base_detail(_require(), base_id)
    if detail is None:
        raise HTTPException(404, f"Base not found: {base_id}")
    guild_id = detail.get("guild_id")
    if not guild_id:
        raise HTTPException(400, "Base has no guild")
    if not body.name.strip():
        raise HTTPException(400, "Name cannot be empty")
    base_service.rename_guild(_require(), guild_id, body.name.strip())
    return {"status": "ok"}


@router.put("/{base_id}/guild/level")
async def set_guild_level(base_id: str, body: SetGuildLevelRequest) -> dict:
    """Set the level of the guild that owns this base."""
    detail = base_service.get_base_detail(_require(), base_id)
    if detail is None:
        raise HTTPException(404, f"Base not found: {base_id}")
    guild_id = detail.get("guild_id")
    if not guild_id:
        raise HTTPException(400, "Base has no guild")
    if body.level < 1 or body.level > 35:
        raise HTTPException(400, "Guild level must be between 1 and 35")
    base_service.set_guild_level(_require(), guild_id, body.level)
    return {"status": "ok"}
