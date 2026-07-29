"""Facade for headless tools.

All actual tool implementations have been extracted to app/backend/services/tools/
to keep file sizes manageable. This file re-exports them so routes/tools.py 
and tests/test_tool_roundtrips.py remain unchanged.
"""

from __future__ import annotations

from app.backend.services.tools.core import (
    get_player_info, 
    get_player_containers,
    _decode_level_sav,
    _encode_level_sav
)

from app.backend.services.tools.convert_generic import (
    convert_sav_json, 
    export_loaded_save_json
)

from app.backend.services.tools.convert_ids import (
    convert_ids, 
    detect_input_type
)

from app.backend.services.tools.restore_map import (
    restore_map_fog
)

from app.backend.services.tools.slot_injector import (
    apply_slot_injector, 
    _apply_slot_injector_to_gvas
)

from app.backend.services.tools.fix_host_save import (
    fix_host_save, 
    _apply_fix_host_save_to_gvas
)

from app.backend.services.tools.fix_guild import (
    fix_guild, 
    _apply_fix_guild_to_gvas
)

from app.backend.services.tools.character_transfer import (
    character_transfer,
    get_pal_base_data
)

from app.backend.services.tools.player_migrate import (
    player_migrate
)

# Export everything that might be expected from tool_service.
__all__ = [
    "convert_sav_json",
    "export_loaded_save_json",
    "convert_ids",
    "detect_input_type",
    "restore_map_fog",
    "apply_slot_injector",
    "_apply_slot_injector_to_gvas",
    "fix_host_save",
    "_apply_fix_host_save_to_gvas",
    "fix_guild",
    "_apply_fix_guild_to_gvas",
    "character_transfer",
    "player_migrate",
    "get_player_info",
    "get_player_containers",
    "_decode_level_sav",
    "_encode_level_sav",
    "get_pal_base_data"
]
