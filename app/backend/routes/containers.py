"""Container detail and mutation endpoints.

Read endpoints (list, detail) use the lazy ``build_mini_wsd`` path so they
don't materialize the full ~200 MB ``level_dict``. Mutation endpoints (clear,
expand, set-slot-count, delete-slot) keep using ``level_dict`` directly —
mutations are infrequent, user-initiated, and need the live dict so the next
encode persists the change.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.backend.schemas import (
    ContainerDetail, ContainerListResponse, ExpandContainerRequest,
    SetSlotCountRequest,
)
from app.backend.services import container_service
from app.backend.state import save_state

router = APIRouter(prefix="/containers")


def _require_loaded():
    """The currently loaded ``LoadedSave`` (raises 409 if none)."""
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded


def _require() -> dict:
    """The live ``level_dict`` (for mutations). Forces full materialization."""
    return _require_loaded().level_dict


@router.get("", response_model=ContainerListResponse)
async def list_containers(
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=50000),
) -> ContainerListResponse:
    loaded = _require_loaded()
    # Only the sections the list view touches — keeps RAM bounded.
    wsd = loaded.build_mini_wsd("ItemContainerSaveData", "MapObjectSaveData", "GroupSaveDataMap")
    containers, total = container_service.list_containers_from_wsd(
        wsd, offset=offset, limit=limit,
    )
    return ContainerListResponse(
        containers=containers, total=total, has_more=(offset + limit < total),
    )


@router.get("/{container_id}", response_model=ContainerDetail)
async def get_container_detail(container_id: str) -> ContainerDetail:
    loaded = _require_loaded()
    # DynamicItemSaveData included so weapon/armor/egg payloads can be
    # attached to each slot (built lazily only if the container has dynamic slots).
    wsd = loaded.build_mini_wsd("ItemContainerSaveData", "DynamicItemSaveData")
    detail = container_service.get_container_detail_from_wsd(wsd, container_id)
    if detail is None:
        raise HTTPException(404, f"Container not found: {container_id}")
    return ContainerDetail(**detail)


@router.post("/{container_id}/clear")
async def clear_container(container_id: str) -> dict:
    if not container_service.clear_container(_require(), container_id):
        raise HTTPException(404, f"Container not found: {container_id}")
    return {"status": "ok"}


@router.put("/{container_id}/expand")
async def expand_container(container_id: str, body: ExpandContainerRequest) -> dict:
    if body.new_slot_count < 1 or body.new_slot_count > 9999:
        raise HTTPException(400, "Slot count must be between 1 and 9999")
    if not container_service.expand_container(_require(), container_id, body.new_slot_count):
        raise HTTPException(400, "Cannot shrink container or container not found")
    return {"status": "ok"}


@router.put("/{container_id}/slots")
async def set_slot_count(container_id: str, body: SetSlotCountRequest) -> dict:
    """Change one item slot's stack count (0 = clear the slot, keep the slot)."""
    if not container_service.set_slot_count(
        _require(), container_id, body.slot_index, body.new_count,
    ):
        raise HTTPException(404, f"Slot {body.slot_index} not found in container {container_id}")
    return {"status": "ok"}


@router.delete("/{container_id}/slots/{slot_index}")
async def delete_slot(container_id: str, slot_index: int) -> dict:
    """Remove the item from a slot (zero it out, keep the slot itself)."""
    if not container_service.delete_slot(_require(), container_id, slot_index):
        raise HTTPException(404, f"Slot {slot_index} not found in container {container_id}")
    return {"status": "ok"}
