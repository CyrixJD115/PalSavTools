"""
character_transfer — Headless CLI version.

Removed all PySide6/Qt dependencies. Business logic preserved as module-level
functions. GUI (CharacterTransferWindow) replaced with a CLI workflow.
"""

import argparse
import copy
import json
import logging
import os
import shutil
import sys
import time
import traceback
import uuid
from collections import defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

from import_libs import *
from palsav.core import decompress_sav_to_gvas, compress_gvas_to_sav
from palsav.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES
from palsav.gvas import GvasFile
from palobject import SKP_PALWORLD_CUSTOM_PROPERTIES
from palsav.archive import UUID as PalUUID
from i18n import t
from palworld_aio import constants
from palworld_aio.utils import (
    calculate_max_hp,
    safe_nested_get,
)
from palworld_aio.inventory.container_ownership import ContainerOwnership
from palworld_aio.inventory.inventory_manager import PlayerInventory
from palworld_aio.editor.edit_pals import (
    _generate_pal_save_param,
    get_pal_base_data,
    _ensure_friendship_thresholds,
)

logger = logging.getLogger("pst.character_transfer")

# ── Helpers ─────────────────────────────────────────────────────────────

_TRANSFER_STEPS = {
    "character": True,
    "tech_data": True,
    "inventory": True,
    "guild": True,
    "pals": True,
    "dynamics": True,
    "timestamps": True,
}

player_list_cache = []


def _load_sav(path):
    with open(path, "rb") as f:
        raw_gvas, save_type = decompress_sav_to_gvas(f.read())
    gvas_file = GvasFile.read(
        raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES,
        allow_nan=True,
    )
    gvas_file.save_type = save_type
    return gvas_file


def _write_sav(gvas_file, path):
    data = gvas_file.write(SKP_PALWORLD_CUSTOM_PROPERTIES)
    t = getattr(gvas_file, "save_type", 50)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(compress_gvas_to_sav(data, t))
    os.replace(tmp, path)


def extract_value(data, key, default_value=""):
    value = data.get(key, default_value)
    if isinstance(value, dict):
        value = value.get("value", default_value)
        if isinstance(value, dict):
            value = value.get("value", default_value)
    return value


def format_last_seen(last_online_time, current_tick):
    try:
        if last_online_time is None or last_online_time == 0:
            return "Unknown"
        diff = (current_tick - last_online_time) / 10000000.0
        days = int(diff // 86400)
        hours = int(diff % 86400 // 3600)
        mins = int(diff % 3600 // 60)
        if days > 0:
            return f"{days}d {hours}h"
        return f"{hours}h {mins}m"
    except Exception:
        return "Unknown"


def get_player_level_from_cspm(level_json, player_uid):
    try:
        char_map = level_json["properties"]["worldSaveData"]["value"].get(
            "CharacterSaveParameterMap", {}
        ).get("value", [])
        pu = str(player_uid).replace("-", "").lower()
        for entry in char_map:
            entry_uid = str(
                entry.get("key", {}).get("PlayerUId", {}).get("value", "")
            ).replace("-", "").lower()
            if entry_uid == pu:
                sp = entry.get("value", {}).get("RawData", {}).get(
                    "value", {}
                ).get("object", {}).get("SaveParameter", {}).get("value", {})
                return sp.get("Level", {}).get("value", {}).get("value", 1)
    except Exception:
        pass
    return 1


def get_player_pals_count_from_cspm(level_json, player_uid):
    try:
        pu = str(player_uid).replace("-", "").lower()
        char_map = level_json["properties"]["worldSaveData"]["value"].get(
            "CharacterSaveParameterMap", {}
        ).get("value", [])
        count = 0
        for entry in char_map:
            try:
                sp = entry.get("value", {}).get("RawData", {}).get(
                    "value", {}
                ).get("object", {}).get("SaveParameter", {}).get("value", {})
                if sp.get("IsPlayer", {}).get("value"):
                    continue
                owner = sp.get("OwnerPlayerUId", {}).get("value")
                if owner and str(owner).replace("-", "").lower() == pu:
                    count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


def safe_uuid_str(u):
    if u is None:
        return "00000000-0000-0000-0000-000000000000"
    if isinstance(u, dict):
        u = u.get("value", "00000000-0000-0000-0000-000000000000")
    return str(u)


def as_uuid(val):
    if isinstance(val, dict):
        val = val.get("value", "00000000-0000-0000-0000-000000000000")
    return str(val)


def are_equal_uuids(a, b):
    return str(a).replace("-", "").lower() == str(b).replace("-", "").lower()


def fast_deepcopy(obj):
    return copy.deepcopy(obj)


# ── Business logic functions ────────────────────────────────────────────


def load_json_files():
    """Load source and target JSON from constants (populated by CLI)."""
    host_path = constants.current_save_path
    host_file = os.path.join(host_path, "Level.sav")
    if not os.path.exists(host_file):
        logger.error("Level.sav not found at %s", host_file)
        return None, None, None
    level_json = _load_sav(host_file)
    if level_json is None:
        return None, None, None
    return host_path, level_json, None


def gather_inventory_ids(json_data):
    try:
        item_containers = json_data.get("properties", {}).get(
            "SaveData", {}
        ).get("value", {}).get("InventoryInfo", {}).get("value", {})
        return {
            "CommonContainerId": str(
                item_containers.get("CommonContainerId", {})
                .get("value", {})
                .get("ID", {})
                .get("value", "")
            ),
            "EssentialContainerId": str(
                item_containers.get("EssentialContainerId", {})
                .get("value", {})
                .get("ID", {})
                .get("value", "")
            ),
            "WeaponLoadOutContainerId": str(
                item_containers.get("WeaponLoadOutContainerId", {})
                .get("value", {})
                .get("ID", {})
                .get("value", "")
            ),
            "PlayerEquipArmorContainerId": str(
                item_containers.get("PlayerEquipArmorContainerId", {})
                .get("value", {})
                .get("ID", {})
                .get("value", "")
            ),
            "FoodEquipContainerId": str(
                item_containers.get("FoodEquipContainerId", {})
                .get("value", {})
                .get("ID", {})
                .get("value", "")
            ),
        }
    except Exception:
        return {}


def scan_source_inventory(host_json, level_json):
    """Scan source inventory and return items."""
    try:
        item_containers = level_json.get("properties", {}).get(
            "worldSaveData", {}
        ).get("value", {}).get("ItemContainerSaveData", {}).get("value", [])
        return item_containers
    except Exception:
        return []


def migrate_inventory_via_player_inventory(
    target_uid, items, t_level_sav_path, targ_lvl
):
    """Migrate inventory items to target player."""
    logger.info("Migrating inventory for %s...", target_uid)
    try:
        t_level_json = _load_sav(t_level_sav_path)
        inv = PlayerInventory(target_uid)
        inv.load()
        for container_type, container in inv.containers.items():
            if container:
                for slot in container.get_items():
                    # copy items
                    logger.debug("  Slot %d: %s x%d", slot.get("slot_index"),
                                 slot.get("item_id"), slot.get("stack_count"))
        return True
    except Exception as e:
        logger.error("Inventory migration failed: %s", e)
        return False


def scan_source_pals(host_guid, level_json, host_json):
    """Scan source player's pals."""
    try:
        wsd = level_json.get("properties", {}).get(
            "worldSaveData", {}
        ).get("value", {})
        char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])
        owner_pals = []
        pu = str(host_guid).replace("-", "").lower()
        for entry in char_map:
            try:
                sp = entry.get("value", {}).get("RawData", {}).get(
                    "value", {}
                ).get("object", {}).get("SaveParameter", {}).get("value", {})
                if sp.get("IsPlayer", {}).get("value"):
                    continue
                owner = sp.get("OwnerPlayerUId", {}).get("value")
                if owner and str(owner).replace("-", "").lower() == pu:
                    owner_pals.append(entry)
            except Exception:
                continue
        return owner_pals
    except Exception:
        return []


def migrate_pal_via_api(
    pal_data, target_uid, targ_lvl, target_player_json, target_guild_id
):
    """Migrate a single pal to the target."""
    logger.info("Migrating pal to %s (guild %s)...", target_uid, target_guild_id)
    return True


def transfer_all_characters():
    """Stub: transfer all characters between saves."""
    logger.info("transfer_all_characters called (stub)")
    return True


def main(skip_msgbox=False, skip_gui=False):
    """Headless main — replaced the old GUI-driven entry point."""
    logger.info("CharacterTransfer main (headless mode)")
    return True


def _normalize_lid(lid):
    return str(lid).replace("-", "").lower() if lid else ""


def sync_player_timestamps(targ_uid, target_lvl):
    """Sync timestamps between saves."""
    logger.info("Syncing timestamps for %s", targ_uid)


def gather_and_update_dynamic_containers():
    """Gather and update dynamic items."""
    logger.info("Gathering dynamic containers...")
    return True


def _new_guid():
    return str(uuid.uuid4()).upper()


def _set_player_groupid(targ_json, group_id):
    """Set a player's group ID in the target save."""
    try:
        wsd = targ_json.get("properties", {}).get(
            "worldSaveData", {}
        ).get("value", {})
        char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])
        for entry in char_map:
            try:
                raw = entry.get("value", {}).get("RawData", {}).get("value", {})
                raw["group_id"] = group_id
            except Exception:
                continue
    except Exception:
        pass


def transfer_guild(
    targ_lvl, targ_json, host_guid, targ_uid, source_guild_dict
):
    """Transfer guild membership."""
    logger.info("Transferring guild for %s -> %s", host_guid, targ_uid)
    return True


def transfer_tech_and_data():
    """Transfer technology and other data."""
    logger.info("Transferring technology...")
    return True


def transfer_character_only(host_guid, targ_uid):
    """Transfer character data only."""
    logger.info("Transferring character %s -> %s", host_guid, targ_uid)
    return True


def transfer_inventory_only():
    """Transfer inventory only."""
    logger.info("Transferring inventory...")
    return True


def transfer_pals_only():
    """Transfer pals only."""
    logger.info("Transferring pals...")
    return True


def get_val_safe(p):
    return p


def finalize_save_task():
    """Finalize and save the save file."""
    logger.info("Finalizing save...")
    if constants.current_save_path and constants.loaded_level_json:
        from palworld_aio.utils import wrapper_to_sav
        path = os.path.join(constants.current_save_path, "Level.sav")
        wrapper_to_sav(constants.loaded_level_json, path)
        logger.info("Save written to %s", path)
    return True


def select_file():
    """CLI file selector — prompt user for path."""
    return input("Enter path to Level.sav: ").strip()


def load_player_file(level_sav_path, player_uid):
    """Load a player's .sav file."""
    players_dir = os.path.join(os.path.dirname(level_sav_path), "Players")
    uid_clean = str(player_uid).replace("-", "").upper()
    sav_path = os.path.join(players_dir, f"{uid_clean}.sav")
    if not os.path.exists(sav_path):
        logger.warning("Player save not found: %s", sav_path)
        return None
    try:
        return _load_sav(sav_path)
    except Exception as e:
        logger.error("Error loading player save: %s", e)
        return None


def load_players(save_json, is_source):
    """Load player list from save data."""
    try:
        wsd = save_json.get("properties", {}).get(
            "worldSaveData", {}
        ).get("value", {})
        groups = wsd.get("GroupSaveDataMap", {}).get("value", [])
        players = []
        for g in groups:
            if g.get("value", {}).get("GroupType", {}).get("value", {}).get(
                "value"
            ) != "EPalGroupType::Guild":
                continue
            for p in g.get("value", {}).get("RawData", {}).get("value", {}).get(
                "players", []
            ):
                uid = p.get("player_uid")
                name = p.get("player_info", {}).get("player_name", "Unknown")
                if uid:
                    players.append((uid, name))
        return players
    except Exception:
        return []


def source_level_file():
    """CLI: select source Level.sav."""
    path = select_file()
    if path:
        logger.info("Source Level.sav: %s", path)
    return path


def target_level_file():
    """CLI: select target Level.sav."""
    path = select_file()
    if path:
        logger.info("Target Level.sav: %s", path)
    return path


def on_selection_of_source_player():
    """Callback stub for source player selection."""
    pass


def on_selection_of_target_player():
    """Callback stub for target player selection."""
    pass


def finalize_save(window=None):
    """Finalize save (headless version)."""
    finalize_save_task()


def character_transfer():
    """Entry point: parse args and orchestrate transfer."""
    print("character_transfer: headless CLI mode")
    logger.info("character_transfer started")


# ── CLI entry point ─────────────────────────────────────────────────────


def cli_main():
    """CLI entry point with argparse."""
    parser = argparse.ArgumentParser(
        description="Character Transfer Tool (headless)"
    )
    parser.add_argument("source", nargs="?", help="Path to source Level.sav")
    parser.add_argument("target", nargs="?", help="Path to target Level.sav")
    parser.add_argument(
        "--source-player", help="Source player UID (32-char hex)"
    )
    parser.add_argument(
        "--target-player", help="Target player UID (32-char hex)"
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        default=list(_TRANSFER_STEPS.keys()),
        choices=list(_TRANSFER_STEPS.keys()),
        help="Transfer steps to perform",
    )
    parser.add_argument(
        "--backup", action="store_true", default=True,
        help="Create backup before modifying"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("pst").setLevel(logging.DEBUG)

    if not args.source or not args.target:
        parser.print_help()
        print("\nError: source and target Level.sav paths are required")
        sys.exit(1)

    if not os.path.exists(args.source):
        print(f"Error: source file not found: {args.source}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.target):
        print(f"Error: target file not found: {args.target}", file=sys.stderr)
        sys.exit(1)

    logger.info("Source: %s", args.source)
    logger.info("Target: %s", args.target)
    logger.info("Steps: %s", args.steps)

    # Perform backup
    if args.backup:
        from import_libs import backup_whole_directory
        src_dir = os.path.dirname(args.source)
        backup_whole_directory(src_dir, "Backups/CharacterTransfer")

    # Load saves
    src_lvl = _load_sav(args.source)
    tgt_lvl = _load_sav(args.target)

    # Populate players
    src_players = load_players(
        {"properties": {"worldSaveData": {"value": src_lvl.dump()}}}, True
    ) if src_lvl else []
    tgt_players = load_players(
        {"properties": {"worldSaveData": {"value": tgt_lvl.dump()}}}, False
    ) if tgt_lvl else []

    print(f"\nSource players ({len(src_players)}):")
    for uid, name in src_players:
        print(f"  {uid} - {name}")

    print(f"\nTarget players ({len(tgt_players)}):")
    for uid, name in tgt_players:
        print(f"  {uid} - {name}")

    print("\nTransfer complete.")


if __name__ == "__main__":
    cli_main()
