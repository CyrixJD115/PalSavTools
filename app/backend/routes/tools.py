"""Tool execution API — wraps headless palsav-based tool_service.py.

Each endpoint accepts paths on the server filesystem (no upload/download).
Tools that require Qt/PySide6 return 501 with a descriptive message.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from pathlib import Path

from app.backend.schemas import (
    CharacterTransferRequest, ConvertExportRequest, ConvertIdsRequest,
    ConvertIdsResponse, ConvertRequest, FixGuildRequest, FixHostSaveRequest,
    PlayerMigrateRequest, SlotInjectorRequest, ToolInfo, ToolResponse,
    ToolsListResponse,
)
from app.backend.services import save_service, tool_service
from app.backend.state import save_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tools"])


# Tool registry — 11 tools in 3 categories


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



# Stub handler for tools not yet implemented


def _not_implemented(tool_id: str | None = None, windows_only: bool = False) -> ToolResponse:
    msg = f"Tool '{tool_id}' is not yet available as a web API endpoint."
    if windows_only:
        msg = "This tool requires Windows (PySide6 desktop only) and is not available via the web API."
    return ToolResponse(success=False, message=msg, details=None)



# Endpoints



@router.get("/tools", response_model=ToolsListResponse)
async def list_tools():
    """Return the complete tool catalogue with metadata."""
    return ToolsListResponse(tools=_TOOLS)


@router.post("/tools/convert", response_model=ToolResponse)
async def convert_sav_json(body: ConvertRequest):
    """Convert a .sav file to/from .json on the server filesystem."""
    try:
        result = tool_service.convert_sav_json(
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
    """Modify pal container slot counts in a Level.sav.

    When ``use_loaded_save`` is true (or ``level_sav_path`` is omitted and a
    save is already loaded), operates on the in-memory save from ``save_state``
    and writes changes back to disk automatically.
    """
    try:
        use_loaded = body.use_loaded_save or not body.level_sav_path
        if use_loaded and save_state.is_loaded():
            loaded = save_state.require()
            with save_state.lock:
                result = tool_service._apply_slot_injector_to_gvas(
                    loaded.level_dict, loaded.save_type,
                    players_folder=body.players_folder or loaded.players_dir,
                    new_slot_count=body.new_slot_count,
                    container_ids=body.container_ids,
                )
                sav = save_service.encode_bytes(loaded.level_dict, loaded.save_type)
                Path(loaded.save_dir, loaded.filename).write_bytes(sav)
            return ToolResponse(
                success=True,
                message=f"Slot injection complete. Modified {result['containers_modified']} container(s), removed {result['pals_removed']} pal(s).",
                details=result,
            )
        if not body.level_sav_path:
            return ToolResponse(success=False, message="No save loaded and no path provided.", details=None)
        result = tool_service.apply_slot_injector(
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
async def fix_host_save(body: FixHostSaveRequest):
    """Swap two players' GUIDs in a Level.sav to fix a corrupted host save."""
    try:
        use_loaded = body.use_loaded_save or not body.level_sav_path
        if use_loaded and save_state.is_loaded():
            loaded = save_state.require()
            with save_state.lock:
                result = tool_service._apply_fix_host_save_to_gvas(
                    loaded.level_dict, loaded.save_type,
                    players_folder=loaded.players_dir,
                    old_uid=body.old_uid, new_uid=body.new_uid,
                    guild_fix=body.guild_fix,
                )
                if result.get("success"):
                    sav = save_service.encode_bytes(loaded.level_dict, loaded.save_type)
                    Path(loaded.save_dir, loaded.filename).write_bytes(sav)
            return ToolResponse(success=result.get("success", False), message="Fix host save complete.", details=result)
        if not body.level_sav_path:
            return ToolResponse(success=False, message="No save loaded and no path provided.", details=None)
        result = tool_service.fix_host_save(
            body.level_sav_path, body.old_uid, body.new_uid, body.guild_fix,
        )
        return ToolResponse(success=result.get("success", False), message="Fix host save complete.", details=result)
    except FileNotFoundError as e:
        return ToolResponse(success=False, message=str(e), details=None)
    except Exception as e:
        logger.exception("Fix host save failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/fix-guild", response_model=ToolResponse)
async def fix_guild(body: FixGuildRequest):
    """Move a player to a different guild within the same save."""
    try:
        use_loaded = body.use_loaded_save or not body.level_sav_path
        if use_loaded and save_state.is_loaded():
            loaded = save_state.require()
            with save_state.lock:
                result = tool_service._apply_fix_guild_to_gvas(
                    loaded.level_dict, loaded.save_type,
                    player_uid=body.player_uid,
                    target_guild_id=body.target_guild_id,
                    players_folder=loaded.players_dir,
                )
                if result.get("success"):
                    sav = save_service.encode_bytes(loaded.level_dict, loaded.save_type)
                    Path(loaded.save_dir, loaded.filename).write_bytes(sav)
            return ToolResponse(success=result.get("success", False), message="Fix guild complete.", details=result)
        if not body.level_sav_path:
            return ToolResponse(success=False, message="No save loaded and no path provided.", details=None)
        result = tool_service.fix_guild(body.level_sav_path, body.player_uid, body.target_guild_id)
        return ToolResponse(success=result.get("success", False), message="Fix guild complete.", details=result)
    except FileNotFoundError as e:
        return ToolResponse(success=False, message=str(e), details=None)
    except Exception as e:
        logger.exception("Fix guild failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/character-transfer", response_model=ToolResponse)
async def character_transfer(body: CharacterTransferRequest):
    """Transfer a character between two save files."""
    try:
        result = tool_service.character_transfer(
            source_sav_path=body.source_sav_path,
            target_sav_path=body.target_sav_path,
            source_player_uid=body.source_player_uid,
            target_player_uid=body.target_player_uid,
            steps=body.steps,
        )
        return ToolResponse(success=result.get("success", False), message="Character transfer complete.", details=result)
    except FileNotFoundError as e:
        return ToolResponse(success=False, message=str(e), details=None)
    except Exception as e:
        logger.exception("Character transfer failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/player-migrate", response_model=ToolResponse)
async def player_migrate(body: PlayerMigrateRequest):
    """Migrate a player's guild/base/pals to another save file."""
    try:
        result = tool_service.player_migrate(
            source_sav_path=body.source_sav_path,
            target_sav_path=body.target_sav_path,
            source_player_uid=body.source_player_uid,
            target_player_uid=body.target_player_uid,
        )
        return ToolResponse(success=result.get("success", False), message="Player migrate complete.", details=result)
    except FileNotFoundError as e:
        return ToolResponse(success=False, message=str(e), details=None)
    except Exception as e:
        logger.exception("Player migrate failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/convert-export", response_model=ToolResponse)
async def convert_export(body: ConvertExportRequest):
    """Export the currently loaded save as JSON to a file on the server."""
    try:
        loaded = save_state.require()
        output_path = body.output_path or str(
            Path(loaded.save_dir) / f"{Path(loaded.filename).stem}.json"
        )
        with save_state.lock:
            result = tool_service.export_loaded_save_json(loaded.level_dict, output_path)
        return ToolResponse(success=True, message="Export complete.", details=result)
    except Exception as e:
        logger.exception("Convert export failed")
        return ToolResponse(success=False, message=str(e), details=None)


@router.post("/tools/game-pass-fix", response_model=ToolResponse)
async def game_pass_fix(body: dict):
    """501 — GamePass tools require Windows (PySide6 desktop)."""
    return _not_implemented("game-pass-fix", windows_only=True)


@router.post("/tools/xgp-extract", response_model=ToolResponse)
async def xgp_extract(body: dict):
    """501 — XGP tools require Windows (PySide6 desktop)."""
    return _not_implemented("xgp-extract", windows_only=True)
