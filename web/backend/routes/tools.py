"""Tool execution API — wraps headless palsav-based tool_service.py.

Each endpoint accepts paths on the server filesystem (no upload/download).
Tools that require Qt/PySide6 return 501 with a descriptive message.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException

from web.backend.schemas import (
    ConvertIdsRequest, ConvertIdsResponse, ConvertRequest,
    SlotInjectorRequest, ToolInfo, ToolResponse, ToolsListResponse,
)
from web.backend.services import tool_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tools"])

# ---------------------------------------------------------------------------
# Tool registry — 11 tools in 3 categories
# ---------------------------------------------------------------------------

_TOOLS: list[ToolInfo] = [
    ToolInfo(
        id="convert",
        name="Convert SAV ↔ JSON",
        category="converting",
        category_label="Converting",
        icon="FileSymlink",
        description="Convert between binary .sav and human-readable .json formats.",
    ),
    ToolInfo(
        id="convert-ids",
        name="Steam ID ↔ Palworld UID",
        category="utility",
        category_label="Utility",
        icon="Hash",
        description="Convert Steam IDs to Palworld UIDs and vice versa.",
    ),
    ToolInfo(
        id="slot-injector",
        name="Slot Injector",
        category="management",
        category_label="Management",
        icon="PackagePlus",
        description="Increase pal container slot counts (max 960) across all player palboxes/parties.",
    ),
    ToolInfo(
        id="restore-map",
        name="Restore Map",
        category="management",
        category_label="Management",
        icon="Map",
        description="Clear fog of war and reveal hidden map locations.",
    ),
    ToolInfo(
        id="fix-host-save",
        name="Fix Host Save",
        category="management",
        category_label="Management",
        icon="Wrench",
        description="Migrate guild membership from one player to another in a corrupted host save.",
    ),
    ToolInfo(
        id="game-pass-fix",
        name="GamePass Save Fix",
        category="utility",
        category_label="Utility",
        icon="Gamepad2",
        description="Fix Xbox GamePass saves that fail to load.",
        windows_only=True,
    ),
    ToolInfo(
        id="xgp-extract",
        name="XGP Save Extract",
        category="utility",
        category_label="Utility",
        icon="FileArchive",
        description="Extract XGP container files to standalone .sav format.",
        windows_only=True,
    ),
    ToolInfo(
        id="player-migrate",
        name="Player Migrate",
        category="management",
        category_label="Management",
        icon="ArrowRightFromLine",
        description="Migrate a player's guild / base / pals to another save file.",
    ),
    ToolInfo(
        id="character-transfer",
        name="Character Transfer",
        category="converting",
        category_label="Converting",
        icon="UserRoundPlus",
        description="Transfer a character between two save files.",
    ),
    ToolInfo(
        id="fix-guild",
        name="Fix Guild",
        category="management",
        category_label="Management",
        icon="Users",
        description="Repair guild membership issues in save data.",
    ),
    ToolInfo(
        id="backup",
        name="Backup Save",
        category="utility",
        category_label="Utility",
        icon="HardDrive",
        description="Create a timestamped backup of the current save folder.",
    ),
]


# ---------------------------------------------------------------------------
# Stub handler for tools not yet implemented
# ---------------------------------------------------------------------------

def _not_implemented(tool_id: str | None = None, windows_only: bool = False) -> ToolResponse:
    msg = f"Tool '{tool_id}' is not yet available as a web API endpoint."
    if windows_only:
        msg = "This tool requires Windows (PySide6 desktop only) and is not available via the web API."
    return ToolResponse(success=False, message=msg, details=None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/tools", response_model=ToolsListResponse)
async def list_tools():
    """Return the complete tool catalogue with metadata."""
    return ToolsListResponse(tools=_TOOLS)


@router.post("/tools/convert", response_model=ToolResponse)
async def convert_sav_json(body: ConvertRequest):
    """Convert a .sav file to/from .json on the server filesystem."""
    try:
        result = await tool_service.convert_sav_json(
            body.input_path, body.output_path, body.direction,
        )
        return ToolResponse(success=True, message="Conversion complete.", details=result)
    except FileNotFoundError as e:
        return ToolResponse(success=False, message=str(e), details=None)
    except Exception as e:
        logger.exception("Convert failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/convert-ids", response_model=ConvertIdsResponse)
async def convert_ids(body: ConvertIdsRequest):
    """Convert between Steam ID, Palworld UID, and NoSteam UID formats."""
    try:
        result = tool_service.convert_ids(body.input)
        return ConvertIdsResponse(**result)
    except Exception as e:
        logger.exception("Convert IDs failed")
        raise HTTPException(422, str(e))


@router.post("/tools/restore-map", response_model=ToolResponse)
async def restore_map(body: dict):
    """Clear fog of war from a LocalData.sav file.

    Accepts ``{"path": "/path/to/LocalData.sav"}``.
    """
    path = body.get("path", "")
    if not path:
        return ToolResponse(success=False, message="'path' is required.", details=None)
    try:
        result = tool_service.restore_map_fog(path)
        return ToolResponse(success=True, message="Map fog cleared.", details=result)
    except FileNotFoundError as e:
        return ToolResponse(success=False, message=str(e), details=None)
    except Exception as e:
        logger.exception("Restore map failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/slot-injector", response_model=ToolResponse)
async def slot_injector(body: SlotInjectorRequest):
    """Modify pal container slot counts in a Level.sav."""
    try:
        result = await tool_service.apply_slot_injector(
            body.level_sav_path,
            players_folder=body.players_folder,
            new_slot_count=body.new_slot_count,
            container_ids=body.container_ids,
        )
        return ToolResponse(success=True, message="Slot injection complete.", details=result)
    except FileNotFoundError as e:
        return ToolResponse(success=False, message=str(e), details=None)
    except Exception as e:
        logger.exception("Slot injector failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/fix-host-save", response_model=ToolResponse)
async def fix_host_save(body: dict):
    """Stub — Fix Host Save is desktop-only for now."""
    return _not_implemented("fix-host-save")


@router.post("/tools/game-pass-fix", response_model=ToolResponse)
async def game_pass_fix(body: dict):
    """501 — GamePass tools require Windows (PySide6 desktop)."""
    return _not_implemented("game-pass-fix", windows_only=True)


@router.post("/tools/xgp-extract", response_model=ToolResponse)
async def xgp_extract(body: dict):
    """501 — XGP tools require Windows (PySide6 desktop)."""
    return _not_implemented("xgp-extract", windows_only=True)
