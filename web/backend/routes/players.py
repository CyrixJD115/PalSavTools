"""Player detail and mutation endpoints.

Follows the wrap-don't-rewrite pattern: all logic lives in
``services/player_service.py``, these endpoints just validate, call, and respond.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.backend.schemas import (
    MaxAbilitiesRequest, PlayerDetail, RenamePlayerRequest,
    SetLevelRequest, SetStatsRequest, SetTechPointsRequest,
)
from web.backend.services import player_service
from web.backend.state import save_state

router = APIRouter(prefix="/players")


def _require() -> tuple[dict, str, dict[str, int], dict[str, int]]:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return (
        loaded.level_dict,
        loaded.players_dir,
        loaded.player_pal_counts,
        loaded.player_levels,
    )


@router.get("/{uid}", response_model=PlayerDetail)
async def get_player_detail(uid: str) -> PlayerDetail:
    level_dict, players_dir, pal_counts, levels = _require()
    detail = player_service.get_player_detail(level_dict, uid, pal_counts, levels)
    if detail is None:
        raise HTTPException(404, f"Player not found: {uid}")
    return PlayerDetail(**detail)


@router.put("/{uid}/name")
async def rename_player(uid: str, body: RenamePlayerRequest) -> dict:
    level_dict, _, _, _ = _require()
    if not body.name.strip():
        raise HTTPException(400, "Name cannot be empty")
    player_service.rename_player(level_dict, uid, body.name.strip())
    return {"status": "ok"}


@router.delete("/{uid}")
async def delete_player(uid: str) -> dict:
    level_dict, players_dir, _, _ = _require()
    player_service.delete_player(level_dict, uid)
    return {"status": "ok"}


@router.put("/{uid}/level")
async def set_player_level(uid: str, body: SetLevelRequest) -> dict:
    level_dict, _, _, _ = _require()
    if body.level < 1 or body.level > 80:
        raise HTTPException(400, "Level must be between 1 and 80")
    player_service.set_player_level(level_dict, uid, body.level)
    return {"status": "ok"}


@router.put("/{uid}/tech-points")
async def set_player_tech_points(uid: str, body: SetTechPointsRequest) -> dict:
    _, players_dir, _, _ = _require()
    if not player_service.set_player_tech_points(players_dir, uid, body.tech_points, body.boss_tech_points):
        raise HTTPException(404, f"Player .sav not found for: {uid}")
    return {"status": "ok"}


@router.put("/{uid}/stats")
async def set_player_stats(uid: str, body: SetStatsRequest) -> dict:
    level_dict, _, _, _ = _require()
    stat_changes = {}
    stat_map = {
        "MaxHP": body.max_hp,
        "MaxSP": body.max_sp,
        "Attack": body.attack,
        "Weight": body.weight,
        "CaptureRate": body.capture_rate,
        "WorkSpeed": body.work_speed,
    }
    for k, v in stat_map.items():
        if v is not None:
            stat_changes[k] = v
    if not stat_changes and body.unused_stat_points is None:
        raise HTTPException(400, "No stats to change")
    player_service.set_player_stats(level_dict, uid, stat_changes, body.unused_stat_points)
    return {"status": "ok"}


@router.put("/{uid}/reset-timestamp")
async def reset_player_timestamp(uid: str) -> dict:
    level_dict, _, _, _ = _require()
    player_service.reset_player_timestamp(level_dict, uid)
    return {"status": "ok"}


@router.put("/{uid}/viewing-cage")
async def unlock_viewing_cage(uid: str) -> dict:
    _, players_dir, _, _ = _require()
    if not player_service.unlock_viewing_cage(players_dir, uid):
        raise HTTPException(404, f"Player .sav not found or viewing cage not applicable for: {uid}")
    return {"status": "ok"}


@router.put("/{uid}/unlock-technologies")
async def unlock_player_technologies(uid: str) -> dict:
    _, players_dir, _, _ = _require()
    if not player_service.unlock_all_technologies(players_dir, uid):
        raise HTTPException(404, f"Player .sav not found for: {uid}")
    return {"status": "ok"}


@router.post("/max-abilities")
async def max_player_abilities(body: MaxAbilitiesRequest) -> dict:
    level_dict, players_dir, _, _ = _require()
    if not body.uids:
        raise HTTPException(400, "No player UIDs provided")
    player_service.max_all_abilities(level_dict, players_dir, body.uids)
    return {"status": "ok"}
