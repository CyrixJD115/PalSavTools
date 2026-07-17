"""Container detail and mutation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.backend.schemas import (
    ContainerDetail, ContainerListResponse, ExpandContainerRequest,
)
from app.backend.services import container_service
from app.backend.state import save_state

router = APIRouter(prefix="/containers")


def _require() -> dict:
    loaded = save_state.get()
    if loaded is None:
        raise HTTPException(409, "No save loaded")
    return loaded.level_dict


@router.get("", response_model=ContainerListResponse)
async def list_containers(
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=50000),
) -> ContainerListResponse:
    containers, total = container_service.list_containers(_require(), offset=offset, limit=limit)
    return ContainerListResponse(
        containers=containers, total=total, has_more=(offset + limit < total),
    )


@router.get("/{container_id}", response_model=ContainerDetail)
async def get_container_detail(container_id: str) -> ContainerDetail:
    detail = container_service.get_container_detail(_require(), container_id)
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
