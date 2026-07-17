"""
CLI / headless host-save GUID migrator for Palworld save files.

Replaces old-UID/new-UID references in Level.sav and individual player .sav
files so that a save originally owned by one player can be transferred to
another player's identity.

Usage (CLI)::

    python -m src.toolsets.fix_host_save <save_folder> <old_guid> <new_guid>

The module is also importable and provides the public business-logic
functions without any Qt/PySide6 dependency.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import shutil
import struct
import sys
from typing import Any, Callable

from import_libs import backup_whole_directory
from palsav.core import decompress_sav_to_gvas, compress_gvas_to_sav
from palsav.gvas import GvasFile, GvasHeader
from palsav.archive import FArchiveReader, FArchiveWriter
from palsav.paltypes import PALWORLD_TYPE_HINTS
from palobject import SKP_PALWORLD_CUSTOM_PROPERTIES
from loading_manager import show_information, show_warning
from palworld_aio.inventory.container_ownership import ContainerOwnership

logger = logging.getLogger("pst.fix_host_save")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

player_list_cache: list[tuple[str, str, str, int, int, str]] = []


def extract_value(data: dict, key: str, default_value: Any = "") -> Any:
    """Safely extract a possibly-nested *value* key from a dict."""
    value = data.get(key, default_value)
    if isinstance(value, dict):
        value = value.get("value", default_value)
        if isinstance(value, dict):
            value = value.get("value", default_value)
    return value


class MyReader(FArchiveReader):
    """Patched archive reader that collects per-property results."""

    def __init__(
        self,
        data: bytes,
        type_hints: dict[str, str] | None = None,
        custom_properties: dict[str, tuple[Callable, Callable]] | None = None,
        debug: bool = False,
        allow_nan: bool = True,
    ):
        super().__init__(
            data,
            type_hints=type_hints or {},
            custom_properties=custom_properties or {},
            debug=debug,
            allow_nan=allow_nan,
        )
        self.orig_data = data
        self.data = io.BytesIO(data)

    def curr_property(self, path: str = "") -> dict[str, Any]:
        properties: dict[str, Any] = {}
        name = self.fstring()
        type_name = self.fstring()
        size = self.u64()
        properties[name] = self.property(type_name, size, f"{path}.{name}")
        return properties


class SkipGvasFile(GvasFile):
    """Minimal GvasFile that reads properties until the end (skipping schema)."""

    header: GvasHeader
    properties: dict[str, Any]
    trailer: bytes

    @staticmethod
    def read(
        data: bytes,
        type_hints: dict[str, str] | None = None,
        custom_properties: dict[str, tuple[Callable, Callable]] | None = None,
        allow_nan: bool = True,
    ) -> SkipGvasFile:
        gvas_file = SkipGvasFile()
        with MyReader(
            data,
            type_hints=type_hints or {},
            custom_properties=custom_properties or {},
            allow_nan=allow_nan,
        ) as reader:
            gvas_file.header = GvasHeader.read(reader)
            gvas_file.properties = reader.properties_until_end()
            gvas_file.trailer = reader.read_to_end()
            if gvas_file.trailer != b"\x00\x00\x00\x00":
                print(
                    f"{len(gvas_file.trailer)} bytes of trailer data, "
                    "file may not have fully parsed"
                )
        return gvas_file

    def write(
        self,
        custom_properties: dict[str, tuple[Callable, Callable]] | None = None,
    ) -> bytes:
        writer = FArchiveWriter(custom_properties or {})
        self.header.write(writer)
        writer.properties(self.properties)
        writer.write(self.trailer)
        return writer.bytes()


# ---------------------------------------------------------------------------
# Save-format helpers
# ---------------------------------------------------------------------------

SAVE_TYPE_PALWORLD = 50
SAVE_TYPE_LEGACY = 49


def gvas_to_sav(output_filepath: str, gvas_bytes: bytes) -> None:
    """Compress GVAS bytes and write a .sav file."""
    gvas_file = GvasFile.read(
        gvas_bytes, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES
    )
    save_type = (
        SAVE_TYPE_PALWORLD
        if "Pal.PalworldSaveGame" in gvas_file.header.save_game_class_name
        or "Pal.PalLocalWorldSaveGame" in gvas_file.header.save_game_class_name
        else SAVE_TYPE_LEGACY
    )
    sav_file = compress_gvas_to_sav(gvas_file.write(SKP_PALWORLD_CUSTOM_PROPERTIES), save_type)
    with open(output_filepath, "wb") as f:
        f.write(sav_file)


def sav_to_json(filepath: str) -> dict:
    """Read a .sav file and return its JSON (dict) representation."""
    with open(filepath, "rb") as f:
        data = f.read()
    raw_gvas, _ = decompress_sav_to_gvas(data)
    gvas_file = GvasFile.read(
        raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES, allow_nan=True
    )
    return gvas_file.dump()


def json_to_sav(json_data: dict, output_filepath: str) -> None:
    """Write a JSON (dict) representation back to a .sav file."""
    gvas_file = GvasFile.load(json_data)
    save_type = (
        SAVE_TYPE_PALWORLD
        if "Pal.PalworldSaveGame" in gvas_file.header.save_game_class_name
        or "Pal.PalLocalWorldSaveGame" in gvas_file.header.save_game_class_name
        else SAVE_TYPE_LEGACY
    )
    sav_file = compress_gvas_to_sav(
        gvas_file.write(SKP_PALWORLD_CUSTOM_PROPERTIES), save_type
    )
    with open(output_filepath, "wb") as f:
        f.write(sav_file)


# ---------------------------------------------------------------------------
# Player-list helpers
# ---------------------------------------------------------------------------

def format_last_seen(last_online_time: int | None, current_tick: int) -> str:
    """Format tick-difference into a human-readable age string."""
    try:
        if last_online_time is None or last_online_time == 0:
            return "Unknown"
        diff = (current_tick - last_online_time) / 10_000_000.0
        days = int(diff // 86400)
        hours = int(diff % 86400 // 3600)
        mins = int(diff % 3600 // 60)
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {mins}m"
        else:
            return f"{mins}m"
    except Exception:
        return "Unknown"


def get_player_level_from_cspm(level_json: dict, player_uid: str) -> int:
    """Look up a player's level from the CharacterSaveParameterMap."""
    try:
        player_uid_clean = str(player_uid).lower().replace("-", "")
        char_map = (
            level_json.get("properties", {})
            .get("worldSaveData", {})
            .get("value", {})
            .get("CharacterSaveParameterMap", {})
            .get("value", [])
        )
        uid_level_map: dict[str, int] = {}
        for entry in char_map:
            try:
                sp = entry["value"]["RawData"]["value"]["object"]["SaveParameter"]
                if sp["struct_type"] != "PalIndividualCharacterSaveParameter":
                    continue
                sp_val = sp["value"]
                if not sp_val.get("IsPlayer", {}).get("value", False):
                    continue
                key = entry.get("key", {})
                uid_obj = key.get("PlayerUId", {})
                uid = str(uid_obj.get("value", "") if isinstance(uid_obj, dict) else uid_obj)
                if uid:
                    uid_clean = uid.lower().replace("-", "")
                    level = extract_value(sp_val, "Level", 1)
                    uid_level_map[uid_clean] = int(level) if level is not None else 1
            except Exception:
                continue
        return uid_level_map.get(player_uid_clean, 1)
    except Exception:
        return 1


def get_player_pals_count_from_cspm(level_json: dict, player_uid: str) -> int:
    """Count the number of owned pal entries for a player."""
    try:
        player_uid_clean = str(player_uid).lower().replace("-", "")
        level_data = (
            level_json.get("properties", {})
            .get("worldSaveData", {})
            .get("value", {})
        )
        char_map = level_data.get("CharacterSaveParameterMap", {}).get("value", [])
        ownership = ContainerOwnership.build(
            char_map,
            level_data.get("CharacterContainerSaveData", {}).get("value", []),
        )
        pal_count = 0
        for entry in char_map:
            try:
                sp = entry["value"]["RawData"]["value"]["object"]["SaveParameter"]
                if sp["struct_type"] != "PalIndividualCharacterSaveParameter":
                    continue
                sp_val = sp["value"]
                if sp_val.get("IsPlayer", {}).get("value", False):
                    continue
                inst_val = entry.get("key", {}).get("InstanceId", {}).get("value")
                owner_uid_obj = sp_val.get("OwnerPlayerUId", {})
                owner_uid = (
                    str(owner_uid_obj.get("value", ""))
                    if isinstance(owner_uid_obj, dict)
                    else str(owner_uid_obj)
                ) if owner_uid_obj else ""
                if ownership.get_effective_owner(inst_val, owner_uid) == player_uid_clean:
                    pal_count += 1
            except Exception:
                continue
        return pal_count
    except Exception:
        return 0


def populate_player_lists(folder_path: str) -> list[tuple[str, str, str, int, int, str]]:
    """Parse Level.sav and return a list of player records.

    Each record is ``(uid, name, guild_id, level, pals_count, last_seen)``.
    Results are cached in ``player_list_cache`` for the lifetime of the
    process.
    """
    global player_list_cache
    if player_list_cache:
        return player_list_cache

    players_folder = os.path.join(folder_path, "Players")
    if not os.path.exists(players_folder):
        logger.warning("Players folder not found: %s", players_folder)
        return []

    level_json = sav_to_json(os.path.join(folder_path, "Level.sav"))
    group_data_list = (
        level_json["properties"]["worldSaveData"]["value"]
        .get("GroupSaveDataMap", {})
        .get("value", [])
    )
    world_tick = 0
    try:
        world_tick = (
            level_json["properties"]["worldSaveData"]["value"]
            .get("GameTimeSaveData", {})
            .get("value", {})
            .get("RealDateTimeTicks", {})
            .get("value", 0)
        )
    except Exception:
        pass

    player_files: list[tuple[str, str, str, int, int, str]] = []
    for group in group_data_list:
        if group["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
            continue
        key = group["key"]
        if isinstance(key, dict) and "InstanceId" in key:
            guild_id = key["InstanceId"]["value"]
        else:
            guild_id = str(key)
        players = group["value"]["RawData"]["value"].get("players", [])
        for player in players:
            uid = str(player.get("player_uid", "")).replace("-", "")
            name = player.get("player_info", {}).get("player_name", "Unknown")
            level = get_player_level_from_cspm(level_json, uid)
            pals_count = get_player_pals_count_from_cspm(level_json, uid)
            last_online_time = player.get("player_info", {}).get("last_online_real_time", 0)
            last_seen = format_last_seen(last_online_time, world_tick)
            player_files.append((uid, name, guild_id, level, pals_count, last_seen))

    player_list_cache = player_files
    return player_files


def background_load_task(path: str) -> tuple[list[tuple[str, str, str, int, int, str]], dict]:
    """Load player data from a Level.sav path without caching (for async use)."""
    level_json = sav_to_json(path)
    group_data_list = (
        level_json["properties"]["worldSaveData"]["value"]
        .get("GroupSaveDataMap", {})
        .get("value", [])
    )
    world_tick = 0
    try:
        world_tick = (
            level_json["properties"]["worldSaveData"]["value"]
            .get("GameTimeSaveData", {})
            .get("value", {})
            .get("RealDateTimeTicks", {})
            .get("value", 0)
        )
    except Exception:
        pass

    player_files: list[tuple[str, str, str, int, int, str]] = []
    for group in group_data_list:
        if group["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
            continue
        guild_id = (
            group["key"]["InstanceId"]["value"]
            if isinstance(group["key"], dict)
            else str(group["key"])
        )
        players = group["value"]["RawData"]["value"].get("players", [])
        for p in players:
            uid = str(p.get("player_uid", "")).replace("-", "")
            name = p.get("player_info", {}).get("player_name", "Unknown")
            level = get_player_level_from_cspm(level_json, uid)
            pals_count = get_player_pals_count_from_cspm(level_json, uid)
            last_online_time = p.get("player_info", {}).get("last_online_real_time", 0)
            last_seen = format_last_seen(last_online_time, world_tick)
            player_files.append((uid, name, guild_id, level, pals_count, last_seen))

    return player_files, level_json


# ---------------------------------------------------------------------------
# DPS (Display-Pal-Storage) file copy
# ---------------------------------------------------------------------------

def copy_dps_file(
    src_folder: str,
    src_uid: str,
    tgt_folder: str,
    tgt_uid: str,
    target_pal_storage_id: Any,
) -> bool | None:
    """Copy a player's DPS (display-pal-storage) file, updating container IDs."""
    src_file = os.path.join(
        src_folder, f"{str(src_uid).replace('-', '').upper()}_dps.sav"
    )
    tgt_file = os.path.join(
        tgt_folder, f"{str(tgt_uid).replace('-', '').upper()}_dps.sav"
    )
    logger.info("[DPS] Copying %s -> %s", src_uid, tgt_uid)
    if not os.path.exists(src_file):
        logger.warning("[DPS] Source file missing: %s", src_file)
        return None

    try:
        with open(src_file, "rb") as f:
            data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)
        dps = SkipGvasFile.read(raw_gvas)
        update_count = 0

        if "SaveParameterArray" in dps.properties:
            save_param_array = dps.properties["SaveParameterArray"]
            if isinstance(save_param_array, dict) and "value" in save_param_array:
                inner_value = save_param_array["value"]
                if isinstance(inner_value, dict) and "values" in inner_value:
                    pal_list: list = inner_value["values"]
                    if isinstance(pal_list, list):
                        for pal_entry in pal_list:
                            if isinstance(pal_entry, dict) and "SaveParameter" in pal_entry:
                                save_param = pal_entry["SaveParameter"]
                                if isinstance(save_param, dict) and "value" in save_param:
                                    pal_data: dict = save_param["value"]
                                    if isinstance(pal_data, dict) and "SlotId" in pal_data:
                                        slot_id = pal_data["SlotId"]
                                        if isinstance(slot_id, dict) and "value" in slot_id:
                                            slot_id_value: dict = slot_id["value"]
                                            if isinstance(slot_id_value, dict) and "ContainerId" in slot_id_value:
                                                container_id = slot_id_value["ContainerId"]
                                                if isinstance(container_id, dict) and "value" in container_id:
                                                    cid_value: dict = container_id["value"]
                                                    if isinstance(cid_value, dict) and "ID" in cid_value:
                                                        id_obj = cid_value["ID"]
                                                        if isinstance(id_obj, dict) and "value" in id_obj:
                                                            id_obj["value"] = target_pal_storage_id
                                                            update_count += 1

        logger.info("[DPS] Updated %d container IDs", update_count)
        gvas_to_sav(tgt_file, dps.write())
        logger.info("[DPS] Successfully copied to %s", tgt_uid)
        return True
    except Exception as e:
        logger.exception("[DPS] Error: %s", e)
        logger.info("[DPS] Falling back to simple copy...")
        shutil.copy2(src_file, tgt_file)
        logger.info("[DPS] Copied without container ID update")
        return False


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------

def fix_save(
    save_path: str,
    new_guid: str,
    old_guid: str,
    guild_fix: bool = True,
) -> bool:
    """Swap two players' GUIDs in a save folder.

    Parameters
    ----------
    save_path : str
        Path to the save root (containing ``Level.sav`` and ``Players/``).
    new_guid : str
        32-character hex GUID (dashes optional) of the *target* player.
    old_guid : str
        32-character hex GUID (dashes optional) of the *source* player.
    guild_fix : bool
        Whether to also swap guild membership records (default ``True``).

    Returns
    -------
    bool
        ``True`` on success, ``False`` on error.
    """
    fmt = lambda g: "{}-{}-{}-{}-{}".format(
        g[:8], g[8:12], g[12:16], g[16:20], g[20:]
    ).lower()
    old_uid, new_uid = fmt(old_guid), fmt(new_guid)

    lvl = os.path.join(save_path, "Level.sav")
    old_sav = os.path.join(save_path, "Players", old_guid.upper() + ".sav")
    new_sav = os.path.join(save_path, "Players", new_guid.upper() + ".sav")

    level = sav_to_json(lvl)
    old_j = sav_to_json(old_sav)
    new_j = sav_to_json(new_sav)

    old_player_level = get_player_level_from_cspm(level, old_uid)
    new_player_level = get_player_level_from_cspm(level, new_uid)

    if old_player_level < 2 or new_player_level < 2:
        error_msg = (
            f"Both players must be at least level 2. "
            f"Old level: {old_player_level}, New level: {new_player_level}"
        )
        logger.error(error_msg)
        show_warning(None, "Error", error_msg)
        return False

    # Swap PlayerUId / IndividualId in both player files
    old_j["properties"]["SaveData"]["value"]["PlayerUId"]["value"] = new_uid
    old_j["properties"]["SaveData"]["value"]["IndividualId"]["value"][
        "PlayerUId"
    ]["value"] = new_uid
    new_j["properties"]["SaveData"]["value"]["PlayerUId"]["value"] = old_uid
    new_j["properties"]["SaveData"]["value"]["IndividualId"]["value"][
        "PlayerUId"
    ]["value"] = old_uid

    old_inst = old_j["properties"]["SaveData"]["value"]["IndividualId"]["value"][
        "InstanceId"
    ]["value"]
    new_inst = new_j["properties"]["SaveData"]["value"]["IndividualId"]["value"][
        "InstanceId"
    ]["value"]

    try:
        new_player_pal_storage_id = new_j["properties"]["SaveData"]["value"][
            "PalStorageContainerId"
        ]["value"]["ID"]["value"]
    except Exception:
        new_player_pal_storage_id = None

    # Swap entries in CharacterSaveParameterMap
    cspm = level["properties"]["worldSaveData"]["value"][
        "CharacterSaveParameterMap"
    ]["value"]
    for e in cspm:
        if e["key"]["InstanceId"]["value"] == old_inst:
            e["key"]["PlayerUId"]["value"] = new_uid
        elif e["key"]["InstanceId"]["value"] == new_inst:
            e["key"]["PlayerUId"]["value"] = old_uid

    # Swap guild membership records
    if guild_fix:
        for g in level["properties"]["worldSaveData"]["value"][
            "GroupSaveDataMap"
        ]["value"]:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
            raw = g["value"]["RawData"]["value"]
            for h in raw.get("individual_character_handle_ids", []):
                if h["instance_id"] == old_inst:
                    h["guid"] = new_uid
                elif h["instance_id"] == new_inst:
                    h["guid"] = old_uid
            if raw.get("admin_player_uid") == old_uid:
                raw["admin_player_uid"] = new_uid
            elif raw.get("admin_player_uid") == new_uid:
                raw["admin_player_uid"] = old_uid
            for p in raw.get("players", []):
                if p.get("player_uid") == old_uid:
                    p["player_uid"] = new_uid
                elif p.get("player_uid") == new_uid:
                    p["player_uid"] = old_uid

    # Deep swap all remaining UID references in level data
    def deep_swap(data: Any) -> None:
        if isinstance(data, dict):
            for k in (
                "OwnerPlayerUId",
                "owner_player_uid",
                "build_player_uid",
                "private_lock_player_uid",
            ):
                v = data.get(k)
                if isinstance(v, dict) and v.get("value") == old_uid:
                    v["value"] = new_uid
                elif isinstance(v, dict) and v.get("value") == new_uid:
                    v["value"] = old_uid
                elif v == old_uid:
                    data[k] = new_uid
                elif v == new_uid:
                    data[k] = old_uid
            for x in data.values():
                deep_swap(x)
        elif isinstance(data, list):
            for i in data:
                deep_swap(i)

    deep_swap(level)

    # Copy DPS file with container-ID update
    players_folder = os.path.join(os.path.dirname(lvl), "Players")
    copy_dps_file(
        players_folder,
        old_guid,
        players_folder,
        new_guid,
        new_player_pal_storage_id,
    )

    # Write modified JSON back to .sav
    json_to_sav(level, lvl)
    json_to_sav(old_j, old_sav)
    json_to_sav(new_j, new_sav)

    # Swap the filenames so old_guid.sav contains the new player's data and
    # new_guid.sav contains the old player's data
    tmp_path = old_sav + ".tmp_swap"
    os.rename(old_sav, tmp_path)
    if os.path.exists(new_sav):
        os.rename(new_sav, os.path.join(save_path, "Players", old_guid.upper() + ".sav"))
    os.rename(tmp_path, os.path.join(save_path, "Players", new_guid.upper() + ".sav"))

    return True


# ---------------------------------------------------------------------------
# String-input helper (headless replacement for the Qt-based dialog)
# ---------------------------------------------------------------------------

def ask_string_with_icon(
    title: str,
    prompt: str,
    icon_path: str | None = None,
) -> str | None:
    """Prompt for a string on the console.

    This is a headless replacement for the original QDialog-based
    ``ask_string_with_icon``.  It prints *title* and *prompt* to stdout
    and reads a line from stdin.

    Returns the entered text, or ``None`` if the user entered an empty
    string.
    """
    print(f"\n--- {title} ---")
    answer = input(f"{prompt}: ").strip()
    return answer if answer else None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the ``fix_host_save`` CLI tool."""
    parser = argparse.ArgumentParser(
        description="Migrate a Palworld save between two player GUIDs."
    )
    parser.add_argument(
        "save_path",
        type=str,
        help="Path to the save root (containing Level.sav and Players/).",
    )
    parser.add_argument(
        "old_guid",
        type=str,
        help="32-character hex GUID of the source player (dashes optional).",
    )
    parser.add_argument(
        "new_guid",
        type=str,
        help="32-character hex GUID of the target player (dashes optional).",
    )
    parser.add_argument(
        "--no-guild-fix",
        action="store_true",
        help="Skip guild-membership swapping.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    save_path = args.save_path.strip().strip('"')
    if not os.path.exists(save_path):
        logger.error("Path not found: %s", save_path)
        sys.exit(1)

    # If the user passed a Level.sav path, derive the save root from it
    if save_path.endswith("Level.sav"):
        save_path = os.path.dirname(save_path)

    logger.info(
        "Starting migration: %s -> %s",
        args.old_guid,
        args.new_guid,
    )

    # Create a backup before modifying
    backup_whole_directory(save_path, "Backups/Fix Host Save")

    success = fix_save(
        save_path,
        args.new_guid,
        args.old_guid,
        guild_fix=not args.no_guild_fix,
    )

    if success:
        logger.info("Migration complete.")
        print("Fix has been applied! Have fun!")
        sys.exit(0)
    else:
        logger.error("Migration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
