"""
slot_injector — headless pal container slot modification tool.

Provides functions to:
  - Load and save Level.sav files
  - Query player container information (palbox, party) from a save
  - Modify character container slot counts
  - Clean up excess pal references after slot reduction

No Qt/PySide6 dependencies.  Fully safe to import in a headless environment.
"""

import copy
import logging
import os
import sys

from concurrent.futures import ThreadPoolExecutor

from palsav.gvas import GvasFile
from palsav.paltypes import PALWORLD_TYPE_HINTS
from palobject import SKP_PALWORLD_CUSTOM_PROPERTIES
from palsav.core import decompress_sav_to_gvas, compress_gvas_to_sav
from import_libs import backup_whole_directory

logger = logging.getLogger("pst.slot_injector")


# Save file I/O


def sav_to_gvasfile(filepath: str) -> GvasFile:
    """Read a ``.sav`` file and return a parsed ``GvasFile`` object."""
    with open(filepath, "rb") as f:
        data = f.read()
        raw_gvas, save_type = decompress_sav_to_gvas(data)
    return GvasFile.read(
        raw_gvas,
        PALWORLD_TYPE_HINTS,
        SKP_PALWORLD_CUSTOM_PROPERTIES,
        allow_nan=True,
    )


def gvasfile_to_sav(gvas_file: GvasFile, output_filepath: str) -> None:
    """Serialize a ``GvasFile`` and write it to ``output_filepath``."""
    cls_name = gvas_file.header.save_game_class_name
    if "Pal.PalworldSaveGame" in cls_name or "Pal.PalLocalWorldSaveGame" in cls_name:
        save_type = 50
    elif "PalPalLocalWorldSaveGame" in cls_name:
        save_type = 50
    else:
        save_type = 49
    sav_file = compress_gvas_to_sav(
        gvas_file.write(SKP_PALWORLD_CUSTOM_PROPERTIES), save_type
    )
    with open(output_filepath, "wb") as f:
        f.write(sav_file)



# Player / container query helpers



def load_player_container_mapping(
    players_folder: str, valid_player_uids: set
) -> dict:
    """Scan ``players_folder`` for ``.sav`` files matching ``valid_player_uids``.

    Returns a dict mapping player UID → ``{"party_id": …, "palbox_id": …}``.
    """
    player_containers: dict = {}
    if not os.path.exists(players_folder):
        return player_containers

    player_files = [
        f
        for f in os.listdir(players_folder)
        if f.endswith(".sav")
        and "_dps" not in f
        and (f.replace(".sav", "").lower() in valid_player_uids)
    ]
    if not player_files:
        return player_containers

    def load_player_file(filename: str):
        try:
            p_gvas = sav_to_gvasfile(os.path.join(players_folder, filename))
            p_prop = p_gvas.properties.get("SaveData", {}).get("value", {})
            p_uid_raw = filename.replace(".sav", "")
            p_uid = p_uid_raw.lower()
            p_box = (
                p_prop.get("PalStorageContainerId", {})
                .get("value", {})
                .get("ID", {})
                .get("value")
            )
            p_party = (
                p_prop.get("OtomoCharacterContainerId", {})
                .get("value", {})
                .get("ID", {})
                .get("value")
            )
            if p_box or p_party:
                return (
                    p_uid,
                    {
                        "party_id": str(p_party).lower() if p_party else None,
                        "palbox_id": str(p_box).lower() if p_box else None,
                    },
                )
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(
        max_workers=min(32, os.cpu_count() or 1) + 4
    ) as executor:
        results = executor.map(load_player_file, player_files)
        for result in results:
            if result:
                player_containers[result[0]] = result[1]

    return player_containers


def get_player_info_from_save(
    gvas_file: GvasFile, players_folder: str | None = None
) -> dict:
    """Extract player information (name, guild, UID, container IDs) from a save.

    Returns a dict keyed by lower-cased player UID.
    """
    players: dict = {}
    wsd = gvas_file.properties.get("worldSaveData", {}).get("value", {})
    valid_player_uids: set = set()
    guild_map = wsd.get("GroupSaveDataMap", {}).get("value", [])

    # First pass: collect valid player UIDs from guilds
    if isinstance(guild_map, list):
        for entry in guild_map:
            value = entry.get("value", {})
            group_type = (
                value.get("GroupType", {}).get("value", {}).get("value", "")
            )
            if group_type == "EPalGroupType::Guild":
                raw_data = value.get("RawData", {}).get("value", {})
                players_list = raw_data.get("players", [])
                for p in players_list:
                    player_uid = p.get("player_uid", "N/A")
                    uid_str = (
                        str(player_uid).replace("-", "").lower()
                        if player_uid
                        else "N/A"
                    )
                    if uid_str != "n/a":
                        valid_player_uids.add(uid_str)

    # Second pass: build player records with guild info
    if isinstance(guild_map, list):
        for entry in guild_map:
            value = entry.get("value", {})
            group_type = (
                value.get("GroupType", {}).get("value", {}).get("value", "")
            )
            if group_type == "EPalGroupType::Guild":
                raw_data = value.get("RawData", {}).get("value", {})
                guild_name = raw_data.get("guild_name", "Unknown Guild")
                players_list = raw_data.get("players", [])
                for p in players_list:
                    player_uid = p.get("player_uid", "N/A")
                    uid_str = (
                        str(player_uid).replace("-", "").lower()
                        if player_uid
                        else "N/A"
                    )
                    player_info = p.get("player_info", {})
                    player_name = player_info.get("player_name", "Unknown")
                    players[uid_str] = {
                        "name": player_name,
                        "guild": guild_name,
                        "uid": uid_str,
                        "party_id": None,
                        "palbox_id": None,
                    }

    # Third pass: pick up any players missing from guild data
    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    if isinstance(char_map, list):
        for entry in char_map:
            key = entry.get("key", {})
            value = entry.get("value", {})
            raw_data = value.get("RawData", {}).get("value", {})
            player_uid = key.get("PlayerUId", {}).get("value", "N/A")
            uid_str = (
                str(player_uid).replace("-", "").lower()
                if player_uid
                else "N/A"
            )
            obj = raw_data.get("object", {})
            sp = obj.get("SaveParameter", {})
            sp_val = sp.get("value", {})
            is_player = sp_val.get("IsPlayer", {}).get("value", False)
            nick_name = sp_val.get("NickName", {}).get("value", "")

            if uid_str == "00000000000000000000000000000001":
                continue
            if is_player and uid_str not in players:
                players[uid_str] = {
                    "name": nick_name if nick_name else "Unknown",
                    "guild": "Unknown Guild",
                    "uid": uid_str,
                    "party_id": None,
                    "palbox_id": None,
                }
            elif is_player and nick_name and players.get(uid_str, {}).get("name") == "Unknown":
                players[uid_str]["name"] = nick_name

    # Fourth pass: attach container IDs from player save files
    if players_folder and valid_player_uids:
        container_mapping = load_player_container_mapping(
            players_folder, valid_player_uids
        )
        for uid, containers in container_mapping.items():
            if uid in players:
                players[uid]["party_id"] = containers.get("party_id")
                players[uid]["palbox_id"] = containers.get("palbox_id")

    return players


def get_player_containers(
    gvas_file: GvasFile, players_folder: str | None = None
) -> list[dict]:
    """List all character containers (960+ slots) annotated with player info.

    Each entry contains:
      index, container_id, slot_num, used_slots, max_slots,
      player_uid, player_name, guild, container_type, entry
    """
    players = get_player_info_from_save(gvas_file, players_folder)
    wsd = gvas_file.properties.get("worldSaveData", {}).get("value", {})
    container = wsd.get("CharacterContainerSaveData", {}).get("value", [])

    container_to_player: dict = {}
    for uid, info in players.items():
        if info.get("party_id"):
            container_to_player[info["party_id"]] = {"type": "Party", **info}
        if info.get("palbox_id"):
            container_to_player[info["palbox_id"]] = {"type": "PalBox", **info}

    player_containers: list[dict] = []
    if isinstance(container, list):
        for i, entry in enumerate(container):
            key = entry.get("key", {})
            value = entry.get("value", {})
            slot_num = value.get("SlotNum", {}).get("value", 0)
            if slot_num >= 960:
                container_id = key.get("ID", {}).get("value", "N/A")
                container_id_str = (
                    str(container_id).lower() if container_id else "N/A"
                )
                slots = value.get("Slots", {}).get("value", {})
                slots_values = slots.get("values", [])
                player_info = container_to_player.get(container_id_str)

                if player_info:
                    player_name = player_info["name"]
                    player_uid = player_info["uid"]
                    guild = player_info["guild"]
                    container_type = player_info.get("type", "Unknown")
                else:
                    player_name = "Unknown Player"
                    player_uid = container_id_str[:8] + "..."
                    guild = "Unknown Guild"
                    container_type = "Unknown"

                player_containers.append(
                    {
                        "index": i,
                        "container_id": container_id_str,
                        "slot_num": slot_num,
                        "used_slots": len(slots_values),
                        "max_slots": slot_num,
                        "player_uid": player_uid,
                        "player_name": player_name,
                        "guild": guild,
                        "container_type": container_type,
                        "entry": entry,
                    }
                )

    return player_containers



# Slot modification logic



def _apply_slot_change_to_container(
    gvas_file: GvasFile, container: dict, new_value: int
) -> dict:
    """Modify a single container's slot count and optionally clean up pals.

    Returns a dict with stats about what was done.
    """
    old_slot_num = container["slot_num"]
    container_id = container["container_id"]
    entry = container["entry"]
    result = {
        "container_id": container_id,
        "old_slot_num": old_slot_num,
        "new_slot_num": new_value,
        "removed_pals": 0,
        "removed_handles": 0,
    }

    # Update slot number
    entry["value"]["SlotNum"]["value"] = new_value

    # Filter slots that exceed the new limit
    slots_data = entry["value"]["Slots"]["value"]
    slots_values = slots_data.get("values", [])
    if slots_values:
        filtered_slots = [
            s
            for s in slots_values
            if s.get("SlotIndex", {}).get("value", 0) < new_value
        ]
        slots_data["values"] = filtered_slots

    # When reducing, clean up CharacterSaveParameterMap and GroupSaveDataMap
    if old_slot_num > new_value:
        logger.info(
            "Reducing container %s: old=%d, new=%d",
            container_id,
            old_slot_num,
            new_value,
        )
        char_map = gvas_file.properties["worldSaveData"]["value"][
            "CharacterSaveParameterMap"
        ]["value"]
        removed_pals: list[str] = []
        filtered_char_map: list = []

        for entry_inner in char_map:
            try:
                raw = entry_inner["value"]["RawData"]["value"]["object"][
                    "SaveParameter"
                ]["value"]
                slot_id = raw.get("SlotId", {})
                if slot_id:
                    cont_ref = (
                        slot_id.get("value", {})
                        .get("ContainerId", {})
                        .get("value", {})
                        .get("ID", {})
                        .get("value")
                    )
                    slot_idx = slot_id.get("value", {}).get("SlotIndex", {}).get("value")
                    if (
                        cont_ref
                        and str(cont_ref).lower() == container_id
                        and slot_idx is not None
                        and slot_idx >= new_value
                    ):
                        removed_pals.append(
                            str(entry_inner["key"]["InstanceId"]["value"])
                        )
                        continue
                filtered_char_map.append(entry_inner)
            except Exception:
                filtered_char_map.append(entry_inner)

        gvas_file.properties["worldSaveData"]["value"][
            "CharacterSaveParameterMap"
        ]["value"] = filtered_char_map
        result["removed_pals"] = len(removed_pals)
        logger.info(
            "Removed %d pals with slot index >= %d from container %s",
            len(removed_pals),
            new_value,
            container_id,
        )

        # Clean up group save data (guild handle references)
        group_map = (
            gvas_file.properties["worldSaveData"]["value"]
            .get("GroupSaveDataMap", {})
            .get("value", [])
        )
        removed_handles = 0
        removed_lower = [p.lower() for p in removed_pals]
        for group_entry in group_map:
            try:
                value = group_entry.get("value", {})
                raw = value.get("RawData", {}).get("value", {})
                handle_ids = raw.get("individual_character_handle_ids", [])
                if handle_ids and isinstance(handle_ids, list):
                    filtered_handles = [
                        h
                        for h in handle_ids
                        if str(h.get("instance_id", "")).lower()
                        not in removed_lower
                    ]
                    removed_handles += len(handle_ids) - len(filtered_handles)
                    if len(filtered_handles) != len(handle_ids):
                        raw["individual_character_handle_ids"] = filtered_handles
            except Exception:
                pass

        result["removed_handles"] = removed_handles
        if removed_handles > 0:
            logger.info(
                "Removed %d handle IDs from GroupSaveDataMap", removed_handles
            )

    # Update in-memory summary
    container["slot_num"] = new_value
    container["max_slots"] = new_value

    return result


def apply_to_containers(
    gvas_file: GvasFile,
    containers: list[dict],
    new_value: int,
) -> list[dict]:
    """Apply a new slot count to each container in *containers*.

    Returns a list of result dicts (one per container) with keys:
      container_id, old_slot_num, new_slot_num, removed_pals, removed_handles.

    This function mutates ``gvas_file.properties`` in place.
    """
    results: list[dict] = []
    for container in containers:
        result = _apply_slot_change_to_container(gvas_file, container, new_value)
        results.append(result)
    return results


def cleanup_excess_slots(
    gvas_file: GvasFile, container: dict, new_slot_count: int
) -> dict:
    """Perform comprehensive cleanup of excess slots and orphaned pal references.

    This is a more thorough version of the slot cleanup that also removes
    orphaned pals (pals referencing invalid containers) and pals with
    invalid slot indices.  The simpler inline cleanup in
    ``_apply_slot_change_to_container`` is used for basic operation; this
    function provides deeper sanitisation.

    Returns a dict with cleanup statistics.
    """
    result: dict = {}
    try:
        removed_slots: list = []
        removed_instance_ids: set = set()

        slots_data = container["entry"]["value"]["Slots"]["value"]
        slots_values = slots_data.get("values", [])
        container_id = container["container_id"]

        if len(slots_values) > new_slot_count:
            removed_slots = slots_values[new_slot_count:]
            for slot in removed_slots:
                instance_id = (
                    slot.get("RawData", {})
                    .get("value", {})
                    .get("instance_id")
                )
                if instance_id:
                    removed_instance_ids.add(str(instance_id))

            new_slots = []
            if slots_values:
                for i in range(new_slot_count):
                    if i < len(slots_values):
                        new_slots.append(slots_values[i])
                    else:
                        template = copy.deepcopy(slots_values[0])
                        raw_data = template.get("RawData", {}).get("value", {})
                        if "instance_id" in raw_data:
                            raw_data["instance_id"] = (
                                "00000000-0000-0000-0000-000000000000"
                            )
                        if "player_uid" in raw_data:
                            raw_data["player_uid"] = (
                                "00000000-0000-0000-0000-000000000000"
                            )
                        new_slots.append(template)
            slots_data["values"] = new_slots
            logger.info(
                "Removed %d excess slots from container %s",
                len(removed_slots),
                container_id,
            )

        container["used_slots"] = min(container["used_slots"], new_slot_count)

        # --- Remove pals that reference removed slots -----------------
        char_map = gvas_file.properties["worldSaveData"]["value"][
            "CharacterSaveParameterMap"
        ]["value"]
        removed_pals_count = 0
        filtered_char_map: list = []
        for entry in char_map:
            try:
                instance_id = entry["key"]["InstanceId"]["value"]
                if str(instance_id) in removed_instance_ids:
                    removed_pals_count += 1
                else:
                    filtered_char_map.append(entry)
            except Exception:
                filtered_char_map.append(entry)
        gvas_file.properties["worldSaveData"]["value"][
            "CharacterSaveParameterMap"
        ]["value"] = filtered_char_map

        # --- Remove orphaned pals (invalid container refs) -----------
        container_map = gvas_file.properties["worldSaveData"]["value"][
            "CharacterContainerSaveData"
        ]["value"]
        valid_container_ids: set = set()
        if isinstance(container_map, list):
            for cont_entry in container_map:
                try:
                    cont_id = cont_entry["key"]["ID"]["value"]
                    if cont_id:
                        valid_container_ids.add(str(cont_id).lower())
                except Exception:
                    continue

        orphaned_pals_count = 0
        final_char_map: list = []
        for entry in filtered_char_map:
            try:
                raw = entry["value"]["RawData"]["value"]["object"][
                    "SaveParameter"
                ]["value"]
                slot_id = raw.get("SlotId", {})
                if slot_id:
                    container_id_ref = (
                        slot_id.get("value", {})
                        .get("ContainerId", {})
                        .get("value", {})
                        .get("ID", {})
                        .get("value")
                    )
                    if container_id_ref:
                        cid_str = str(container_id_ref).lower()
                        if cid_str not in valid_container_ids:
                            orphaned_pals_count += 1
                            continue
                final_char_map.append(entry)
            except Exception:
                final_char_map.append(entry)

        gvas_file.properties["worldSaveData"]["value"][
            "CharacterSaveParameterMap"
        ]["value"] = final_char_map

        # --- Remove pals with invalid slot indices -------------------
        invalid_slot_count = 0
        final_char_map_2: list = []
        for entry in final_char_map:
            try:
                raw = entry["value"]["RawData"]["value"]["object"][
                    "SaveParameter"
                ]["value"]
                slot_id = raw.get("SlotId", {})
                if slot_id:
                    container_id_ref = (
                        slot_id.get("value", {})
                        .get("ContainerId", {})
                        .get("value", {})
                        .get("ID", {})
                        .get("value")
                    )
                    slot_index = (
                        slot_id.get("value", {}).get("SlotIndex", {}).get("value")
                    )
                    if container_id_ref and slot_index is not None:
                        cid_str = str(container_id_ref).lower()
                        container_max_slots = None
                        for cont_entry in container_map:
                            try:
                                cont_id = cont_entry["key"]["ID"]["value"]
                                if str(cont_id).lower() == cid_str:
                                    container_max_slots = cont_entry["value"][
                                        "SlotNum"
                                    ]["value"]
                                    break
                            except Exception:
                                continue
                        if (
                            container_max_slots is not None
                            and slot_index >= container_max_slots
                        ):
                            invalid_slot_count += 1
                            continue
                final_char_map_2.append(entry)
            except Exception:
                final_char_map_2.append(entry)

        gvas_file.properties["worldSaveData"]["value"][
            "CharacterSaveParameterMap"
        ]["value"] = final_char_map_2

        # --- Clean up group handle IDs --------------------------------
        group_map = gvas_file.properties["worldSaveData"]["value"][
            "GroupSaveDataMap"
        ]["value"]
        removed_handles_count = 0
        for group in group_map:
            try:
                handle_ids = group["value"]["RawData"]["value"].get(
                    "individual_character_handle_ids", []
                )
                if handle_ids:
                    filtered_handles = []
                    for h in handle_ids:
                        if isinstance(h, dict):
                            instance_id = h.get("instance_id", "")
                            if str(instance_id) not in removed_instance_ids:
                                filtered_handles.append(h)
                            else:
                                removed_handles_count += 1
                        else:
                            filtered_handles.append(h)
                    group["value"]["RawData"]["value"][
                        "individual_character_handle_ids"
                    ] = filtered_handles
            except Exception as e:
                logger.warning("Error updating group handle IDs: %s", e)

        total_removed = (
            removed_pals_count + orphaned_pals_count + invalid_slot_count
        )
        logger.info(
            "Successfully updated container %s from %d to %d slots",
            container_id,
            len(slots_values),
            new_slot_count,
        )
        logger.info("Cleanup results:")
        logger.info("  - Removed %d excess slots", len(removed_slots))
        logger.info("  - Removed %d pals from removed slots", removed_pals_count)
        logger.info(
            "  - Removed %d orphaned pals (invalid container refs)",
            orphaned_pals_count,
        )
        logger.info(
            "  - Removed %d pals with invalid slot indices", invalid_slot_count
        )
        logger.info(
            "  - Removed %d handle IDs from GroupSaveDataMap",
            removed_handles_count,
        )
        logger.info("  - Total pals removed: %d", total_removed)
        if orphaned_pals_count > 0 or invalid_slot_count > 0:
            logger.warning(
                "Found and cleaned up %d problematic pal references",
                orphaned_pals_count + invalid_slot_count,
            )

        result = {
            "container_id": container_id,
            "removed_slots": len(removed_slots),
            "removed_pals": removed_pals_count,
            "orphaned_pals": orphaned_pals_count,
            "invalid_slot_pals": invalid_slot_count,
            "removed_handles": removed_handles_count,
            "total_removed": total_removed,
        }
    except Exception as e:
        logger.error("Error during comprehensive slot cleanup: %s", e)
        raise

    return result



# High-level convenience



def load_save_file(
    filepath: str, save_folder: str | None = None
) -> tuple[GvasFile, list[dict]]:
    """Load a Level.sav and return ``(gvas_file, player_containers)``.

    If ``save_folder`` is ``None`` it is inferred from ``filepath``.
    """
    if save_folder is None:
        save_folder = os.path.dirname(filepath)
    gvas_file = sav_to_gvasfile(filepath)
    players_folder = os.path.join(save_folder, "Players") if save_folder else None
    player_containers = get_player_containers(gvas_file, players_folder)
    return gvas_file, player_containers


def slot_injector() -> None:
    """Legacy stub -- previously returned a ``SlotNumUpdaterApp`` instance.

    In the headless version this function is a no-op.  Use the module-level
    functions directly (``apply_to_containers``, ``load_save_file``, etc.)
    or run this module as ``python -m toolsets.slot_injector`` for the CLI.
    """
    logger.warning(
        "slot_injector() is a legacy stub; use the module-level API "
        "or run with --help for CLI usage."
    )



# CLI entry point



def main(argv: list[str] | None = None) -> int:
    """CLI entry point for slot injection.

    Usage::

        python -m toolsets.slot_injector <Level.sav> [--new-slots N] [--apply-to CONTAINER_ID ...]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Palworld save slot injector -- modify pal container slot counts.",
    )
    parser.add_argument(
        "level_sav",
        type=str,
        help="Path to the Level.sav file to modify.",
    )
    parser.add_argument(
        "--new-slots",
        type=int,
        default=960,
        help="New slot count for containers (default: 960).",
    )
    parser.add_argument(
        "--apply-to",
        type=str,
        nargs="*",
        help="Container ID(s) to apply the new slot count to. "
        "If omitted, applies to ALL player containers.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_containers",
        help="List all player containers and exit without modifying.",
    )
    parser.add_argument(
        "--players-folder",
        type=str,
        default=None,
        help="Path to the Players folder (inferred from Level.sav dir if omitted).",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create a backup before modifying (default: True).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_false",
        dest="backup",
        help="Skip backup creation.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging.",
    )

    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    level_sav_path = os.path.abspath(args.level_sav)
    if not os.path.isfile(level_sav_path):
        logger.error("File not found: %s", level_sav_path)
        print(f"Error: file not found -- {level_sav_path}", file=sys.stderr)
        return 1

    if not level_sav_path.endswith("Level.sav"):
        logger.warning("File does not end with 'Level.sav'; proceeding anyway.")

    save_folder = os.path.dirname(level_sav_path)
    players_folder = args.players_folder or os.path.join(save_folder, "Players")

    # Backup
    if args.backup:
        try:
            backup_whole_directory(save_folder, "Backups/Slot Injector")
        except Exception as exc:
            logger.warning("Backup failed (continuing): %s", exc)

    # Load
    logger.info("Loading save file: %s", level_sav_path)
    try:
        gvas_file, player_containers = load_save_file(level_sav_path, save_folder)
    except Exception as exc:
        logger.exception("Failed to load save file")
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    logger.info("Found %d player containers.", len(player_containers))

    # List mode
    if args.list_containers:
        print(f"{'Player':<24} {'UID':<36} {'Guild':<24} {'Type':<10} {'Slots':>6} {'Used':>6} {'Container ID':<36}")
        print("-" * 142)
        for pc in player_containers:
            print(
                f"{pc['player_name']:<24} "
                f"{pc['player_uid']:<36} "
                f"{pc['guild']:<24} "
                f"{pc['container_type']:<10} "
                f"{pc['slot_num']:>6} "
                f"{pc['used_slots']:>6} "
                f"{pc['container_id']:<36}"
            )
        return 0

    # Determine which containers to modify
    if args.apply_to:
        target_ids = [c.lower() for c in args.apply_to]
        targets = [c for c in player_containers if c["container_id"] in target_ids]
        if not targets:
            logger.error(
                "None of the specified container IDs match any player containers."
            )
            print("Error: no matching container IDs found.", file=sys.stderr)
            return 1
        logger.info(
            "Applying to %d of %d containers (filtered by --apply-to).",
            len(targets),
            len(player_containers),
        )
    else:
        targets = player_containers
        logger.info("Applying to ALL %d player containers.", len(targets))

    # Confirm with user
    reduce_count = sum(1 for c in targets if c["slot_num"] > args.new_slots)
    increase_count = sum(1 for c in targets if c["slot_num"] < args.new_slots)
    unchanged_count = sum(1 for c in targets if c["slot_num"] == args.new_slots)
    msg_parts = []
    if reduce_count:
        msg_parts.append(f"{reduce_count} container(s) reduced")
    if increase_count:
        msg_parts.append(f"{increase_count} container(s) increased")
    if unchanged_count:
        msg_parts.append(f"{unchanged_count} container(s) unchanged")

    # Warn about potential data loss
    if reduce_count:
        danger_count = sum(
            1 for c in targets if c["used_slots"] > args.new_slots
        )
        if danger_count > 0:
            print(
                f"Warning: {danger_count} container(s) have more used slots "
                f"than the new limit ({args.new_slots}). "
                "Excess pals will be REMOVED.",
                file=sys.stderr,
            )

    print(
        f"Summary: {len(targets)} container(s) to modify. "
        f"{', '.join(msg_parts)}. New slot count: {args.new_slots}",
        file=sys.stderr,
    )

    # Ask for confirmation in interactive mode
    if sys.stdin.isatty():
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer not in ("y", "yes"):
            print("Aborted.", file=sys.stderr)
            return 0

    # Apply
    logger.info("Applying new slot count %d to %d containers ...", args.new_slots, len(targets))
    results = apply_to_containers(gvas_file, targets, args.new_slots)

    total_removed_pals = sum(r["removed_pals"] for r in results)
    total_removed_handles = sum(r["removed_handles"] for r in results)
    print(
        f"Modified {len(results)} container(s). "
        f"Removed {total_removed_pals} pal(s) and "
        f"{total_removed_handles} handle ID(s) from guild data.",
        file=sys.stderr,
    )
    logger.info(
        "Modified %d container(s), removed %d pal(s), %d handle ID(s).",
        len(results),
        total_removed_pals,
        total_removed_handles,
    )

    # Save
    try:
        gvasfile_to_sav(gvas_file, level_sav_path)
        logger.info("Saved changes to %s", level_sav_path)
        print(f"Changes saved to {level_sav_path}", file=sys.stderr)
    except Exception as exc:
        logger.exception("Failed to save changes")
        print(f"Error saving: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
