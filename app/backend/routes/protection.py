"""Protection & locking REST API.

The frontend is the source of truth for protection rules (persisted in
localStorage keyed by save fingerprint). On every save load and on every
local change, the frontend pushes the full ``ProtectionState`` here via
``PUT /api/protection/state``. This endpoint replaces the in-memory state
on ``LoadedSave`` — the backend never edits rules on its own.

Endpoints:
- ``GET /api/protection``  → current ``ProtectionState`` for the loaded save.
- ``PUT /api/protection/state``  → replace rules + edit_locked (full push).
- ``PUT /api/protection/lock``  → toggle just the whole-save edit lock.

All mutations broadcast a ``save_update`` over WS so other tabs refetch.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backend.schemas import ProtectionRule, ProtectionState
from app.backend.state import save_state
from app.backend.ws_manager import manager as ws_manager

router = APIRouter(prefix="/protection")


@router.get("", response_model=ProtectionState)
async def get_protection() -> ProtectionState:
    loaded = save_state.get()
    if loaded is None:
        return ProtectionState(fingerprint="", rules=[], edit_locked=False)
    return ProtectionState(
        fingerprint=loaded.fingerprint,
        rules=[ProtectionRule(**r) for r in loaded.protection_rules],
        edit_locked=loaded.edit_locked,
    )


@router.put("/state", response_model=ProtectionState)
async def put_protection_state(body: ProtectionState) -> ProtectionState:
    """Replace the full protection state for the loaded save.

    The fingerprint in the body must match the loaded save's fingerprint —
    this guards against a stale push from a different save (e.g. after a
    rapid load swap). Returns 409 on mismatch.
    """
    loaded = save_state.require()
    if body.fingerprint and loaded.fingerprint and body.fingerprint != loaded.fingerprint:
        raise HTTPException(
            409,
            f"Fingerprint mismatch: body is for {body.fingerprint[:12]}… "
            f"but loaded save is {loaded.fingerprint[:12]}…",
        )
    loaded.protection_rules = [r.model_dump() for r in body.rules]
    loaded.edit_locked = body.edit_locked
    await ws_manager.broadcast("save_update", {})
    return ProtectionState(
        fingerprint=loaded.fingerprint,
        rules=[ProtectionRule(**r) for r in loaded.protection_rules],
        edit_locked=loaded.edit_locked,
    )


class EditLockRequest(BaseModel):
    edit_locked: bool


@router.put("/lock", response_model=ProtectionState)
async def put_edit_lock(body: EditLockRequest) -> ProtectionState:
    """Toggle just the whole-save edit lock (convenience for the master switch)."""
    loaded = save_state.require()
    loaded.edit_locked = body.edit_locked
    await ws_manager.broadcast("save_update", {})
    return ProtectionState(
        fingerprint=loaded.fingerprint,
        rules=[ProtectionRule(**r) for r in loaded.protection_rules],
        edit_locked=loaded.edit_locked,
    )
