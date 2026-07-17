"""Pal editor routes — per-instance mutation + presets.

All routes require a loaded save (409 if none). Mutations edit
``loaded.level_dict`` in place; the existing ``POST /save/export`` path
re-encodes to ``.sav`` on demand. No serialization happens here.

Routes (prefix ``/pals``):
  GET    /pals/{instance_id}            PalDetail
  PUT    /pals/{instance_id}            edit (PalEditRequest) → PalDetail
  POST   /pals/{instance_id}/max-out    {cheat_mode} → PalDetail
  POST   /pals/{instance_id}/heal       → PalDetail
  POST   /pals/{instance_id}/learn-all  {cheat_mode} → PalDetail
  POST   /pals/{instance_id}/move       MovePalRequest → PalDetail
  DELETE /pals/{instance_id}            → {status}
  GET    /pals/catalog/skills           → PalSkillCatalogResponse
  POST   /pals/apply-preset             PresetApplyRequest → PresetApplyResponse

Presets (prefix ``/presets``):
  GET    /presets                       → PresetListResponse
  POST   /presets                       PresetSaveRequest → PalPreset
  DELETE /presets/{id}                  → {status}
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.backend.schemas import (
    PalDetail, PalDetailResponse, PalEditRequest, MovePalRequest,
    PalGroupedResponse, PalPreset, PresetApplyRequest, PresetApplyResponse,
    PresetListResponse, PresetSaveRequest, PalSkillCatalogResponse,
    SwapPalRequest,
)
from app.backend.services import data_service, pal_service, player_service, preset_service
from app.backend.state import save_state

router = APIRouter(prefix="/pals")
preset_router = APIRouter(prefix="/presets")


def _level_dict() -> dict:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded.level_dict


def _require_pal(detail) -> PalDetail:
    if detail is None:
        raise HTTPException(404, "Pal not found")
    return PalDetail(**detail)


# ── catalog (no save needed) ─────────────────────────────────────────────────
@router.get("/catalog/skills", response_model=PalSkillCatalogResponse)
async def get_skill_catalog() -> PalSkillCatalogResponse:
    try:
        skills = data_service.load_game_data("skills")
    except KeyError:
        return PalSkillCatalogResponse(passives=[], actives=[])
    return PalSkillCatalogResponse(
        passives=skills.get("passives", []),
        actives=skills.get("skills", []),
    )


# ── grouped by container (Party / Palbox) ────────────────────────────────────
@router.get("/grouped", response_model=PalGroupedResponse)
async def get_pals_grouped(owner_uid: str = Query(..., description="Player UID")) -> PalGroupedResponse:
    """Pals pre-bucketed into the player's Party and Pal Box zones.

    Reads the player's container IDs from their .sav, then buckets every pal
    by its ``SlotId.ContainerId.ID``. Pals matching neither container fall into
    ``ungrouped`` (base-deployed pals, etc.) so nothing is silently dropped.
    """
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    detail = player_service.get_player_detail(
        loaded.level_dict, owner_uid,
        loaded.player_pal_counts, loaded.player_levels,
        players_dir=loaded.players_dir,
    )
    if detail is None:
        raise HTTPException(404, f"Player not found: {owner_uid}")
    grouped = pal_service.list_pals_grouped(
        loaded.level_dict,
        detail.get("party_id"),
        detail.get("palbox_id"),
        name_map=data_service.character_name_map(),
    )
    return PalGroupedResponse(**grouped)


@router.post("/swap")
async def swap_pals(req: SwapPalRequest) -> dict:
    """Drag-and-drop slot swap: pal_a and pal_b exchange container + slot."""
    try:
        pal_service.swap_pal_slots(_level_dict(), req.pal_a, req.pal_b)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"status": "swapped", "pal_a": req.pal_a, "pal_b": req.pal_b}


# ── per-instance ─────────────────────────────────────────────────────────────
@router.get("/{instance_id}", response_model=PalDetailResponse)
async def get_pal(instance_id: str) -> PalDetailResponse:
    detail = pal_service.read_pal_detail(_level_dict(), instance_id)
    return PalDetailResponse(pal=_require_pal(detail))


@router.put("/{instance_id}", response_model=PalDetailResponse)
async def edit_pal(instance_id: str, req: PalEditRequest) -> PalDetailResponse:
    detail = pal_service.apply_edit(
        _level_dict(), instance_id, req.model_dump(exclude_none=True), cheat=req.cheat_mode
    )
    return PalDetailResponse(pal=_require_pal(detail))


@router.post("/{instance_id}/max-out", response_model=PalDetailResponse)
async def max_out_pal(instance_id: str, body: dict = {}) -> PalDetailResponse:
    detail = pal_service.max_out_pal(_level_dict(), instance_id, cheat=bool(body.get("cheat_mode", False)))
    return PalDetailResponse(pal=_require_pal(detail))


@router.post("/{instance_id}/heal", response_model=PalDetailResponse)
async def heal_pal(instance_id: str) -> PalDetailResponse:
    detail = pal_service.heal_pal(_level_dict(), instance_id)
    return PalDetailResponse(pal=_require_pal(detail))


@router.post("/{instance_id}/learn-all", response_model=PalDetailResponse)
async def learn_all_pal(instance_id: str, body: dict = {}) -> PalDetailResponse:
    detail = pal_service.learn_all_skills(_level_dict(), instance_id, cheat=bool(body.get("cheat_mode", False)))
    return PalDetailResponse(pal=_require_pal(detail))


@router.post("/{instance_id}/move", response_model=PalDetailResponse)
async def move_pal(instance_id: str, req: MovePalRequest) -> PalDetailResponse:
    try:
        detail = pal_service.move_pal(
            _level_dict(), instance_id, req.target_container_id, req.player_uid
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
    return PalDetailResponse(pal=_require_pal(detail))


@router.delete("/{instance_id}")
async def delete_pal(instance_id: str) -> dict:
    ok = pal_service.delete_pal(_level_dict(), instance_id)
    if not ok:
        raise HTTPException(404, "Pal not found")
    return {"status": "deleted"}


# ── preset apply (lives under /pals for pal-scoping) ─────────────────────────
@router.post("/apply-preset", response_model=PresetApplyResponse)
async def apply_preset(req: PresetApplyRequest) -> PresetApplyResponse:
    result = preset_service.apply_preset(
        _level_dict(), req.instance_ids, req.preset_id, cheat=req.cheat_mode
    )
    return PresetApplyResponse(**result)


# ── presets CRUD ─────────────────────────────────────────────────────────────
@preset_router.get("", response_model=PresetListResponse)
async def list_presets() -> PresetListResponse:
    return PresetListResponse(presets=[PalPreset(**p) for p in preset_service.list_presets()])


@preset_router.post("", response_model=PalPreset)
async def save_preset(req: PresetSaveRequest) -> PalPreset:
    stored = preset_service.save_preset(req.name, req.preset.model_dump(exclude_none=True))
    return PalPreset(**stored)


@preset_router.delete("/{preset_id}")
async def delete_preset(preset_id: str) -> dict:
    if not preset_service.delete_preset(preset_id):
        raise HTTPException(404, "Preset not found")
    return {"status": "deleted"}
