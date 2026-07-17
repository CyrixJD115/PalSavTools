"""
game_pass_save_fix — XGP / Steam save conversion (headless CLI version).

Removed all PySide6/Qt dependencies.  Business logic preserved as
module-level functions.  GUI interactions replaced with logging/print/input.
"""

import logging
import os
import random
import shutil
import string
import subprocess
import sys
import threading
import time
import traceback
import zipfile

from import_libs import *
from palworld_aio.utils import sav_to_json, json_to_sav, extract_value
from common import get_base_directory
from loading_manager import run_with_loading

logger = logging.getLogger("pst.game_pass_save_fix")

saves = []
save_info_map = {}
save_extractor_done = threading.Event()
save_converter_done = threading.Event()
base_dir = get_base_directory()
root_dir = base_dir


# ============================================================================
# Utility / helper functions
# ============================================================================

def find_valid_saves(base_path):
    """Walk *base_path* returning a list of save-root directories that
    contain a ``Level/01.sav`` file."""
    valid = []
    if not os.path.isdir(base_path):
        return valid
    for root, dirs, files in os.walk(base_path):
        if "01.sav" in files:
            parent_dir = os.path.basename(root)
            if parent_dir == "Level":
                save_root = os.path.dirname(root)
                folder_name = os.path.basename(save_root)
                if folder_name.lower().startswith("slot"):
                    continue
                if save_root not in valid:
                    valid.append(save_root)
    return valid


def list_folders_in_directory(directory):
    """Return a list of subdirectory names in *directory*."""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
        return [
            item
            for item in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, item))
        ]
    except Exception:
        return []


def is_folder_empty(directory):
    """Return True if *directory* exists and is empty (or doesn't exist)."""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
        return len(os.listdir(directory)) == 0
    except Exception:
        return False


def unzip_file(zip_file_path, extract_to_folder):
    """Extract *zip_file_path* into *extract_to_folder*.  Return bool."""
    os.makedirs(extract_to_folder, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            zip_ref.extractall(extract_to_folder)
        return True
    except Exception as e:
        logger.error("Error extracting zip file %s: %s", zip_file_path, e)
        return False


def generate_random_name(length=32):
    """Generate a random alphanumeric string of *length* characters."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def is_valid_save_id(folder_name):
    """Return True if *folder_name* looks like a 32-char alnum save ID."""
    return len(folder_name) == 32 and folder_name.isalnum()


def is_admin():
    """Return True if the current process runs as Administrator (Windows)."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def stop_gaming_services():
    """Stop Windows GamingServices (XGP helper)."""
    try:
        subprocess.run(
            ["cmd", "/c", "net stop GamingServices /y"],
            check=False, capture_output=True,
        )
        subprocess.run(
            ["cmd", "/c", "net stop GamingServicesNet /y"],
            check=False, capture_output=True,
        )
        subprocess.run(
            ["taskkill", "/f", "/im", "GamingServices.exe"],
            check=False, capture_output=True,
        )
        subprocess.run(
            ["taskkill", "/f", "/im", "GamingServicesNet.exe"],
            check=False, capture_output=True,
        )
    except Exception as e:
        logger.warning("Service stop failed: %s", e)


def start_gaming_services():
    """Start Windows GamingServices (XGP helper)."""
    try:
        subprocess.run(
            ["cmd", "/c", "net start GamingServices"],
            check=False, capture_output=True,
        )
        subprocess.run(
            ["cmd", "/c", "net start GamingServicesNet"],
            check=False, capture_output=True,
        )
    except Exception as e:
        logger.warning("Service start failed: %s", e)


# ============================================================================
# Save-info helpers
# ============================================================================

def get_save_info(save_path):
    """Return a dict with ``world_name`` and ``player_name`` for the save at
    *save_path*."""
    info = {"world_name": "Unknown World", "player_name": "Unknown Player"}
    try:
        meta_path = os.path.join(save_path, "LevelMeta.sav")
        if os.path.exists(meta_path):
            try:
                meta_json = sav_to_json(meta_path)
                info["world_name"] = extract_value(
                    meta_json["properties"]["SaveData"]["value"],
                    "WorldName",
                    "Unknown World",
                )
            except Exception as e:
                logger.warning("Failed to read LevelMeta.sav: %s", e)

        level_sav_path = os.path.join(save_path, "Level.sav")
        level_01_sav_path = os.path.join(save_path, "Level", "01.sav")
        if os.path.exists(level_sav_path):
            actual_level_path = level_sav_path
        elif os.path.exists(level_01_sav_path):
            actual_level_path = level_01_sav_path
        else:
            return info

        try:
            level_json = sav_to_json(actual_level_path)
            world_save_data = level_json["properties"]["worldSaveData"]["value"]
            group_data = world_save_data.get("GroupSaveDataMap", {}).get("value", {})
            guilds_to_process = []
            if isinstance(group_data, dict):
                guilds_to_process = group_data.items()
            elif isinstance(group_data, list):
                guilds_to_process = [(i, g) for i, g in enumerate(group_data)]
            for guild_id, guild_data in guilds_to_process:
                raw_data = (
                    guild_data.get("value", {})
                    .get("RawData", {})
                    .get("value", {})
                )
                players = raw_data.get("players", [])
                if players:
                    player = players[0]
                    if isinstance(player, dict) and "player_info" in player:
                        info["player_name"] = player["player_info"].get(
                            "player_name", "Unknown Player"
                        )
                        break
        except Exception as e:
            logger.warning(
                "Failed to read player name from %s: %s", actual_level_path, e
            )
    except Exception as e:
        logger.error("Error getting save info: %s", e)
    return info


# ============================================================================
# Conversion helpers
# ============================================================================

def _ask_string_cli(prompt, default=None):
    """Simple console-based replacement for ``ask_string_with_icon``."""
    print(prompt)
    value = input("> ").strip()
    return value if value else default


def convert_sav_JSON(save_name, direct_saves_map):
    """Convert a .sav file inside *save_name* (looked up via
    *direct_saves_map*) to JSON.  Returns *save_name* on success or an error
    string."""
    if save_name in direct_saves_map:
        source_base = direct_saves_map[save_name]
    else:
        parts = save_name.split(" - ", 1)
        folder_id = parts[0] if parts else save_name
        source_base = os.path.join(root_dir, "saves", folder_id)

    save_path = os.path.join(source_base, "Level", "01.sav")
    if not os.path.exists(save_path):
        return None

    def task():
        try:
            import logging as _logging
            _logging.disable(_logging.CRITICAL)
            from palsav.commands import convert
            old_argv = sys.argv
            sys.argv = ["convert", save_path]
            convert.main()
            sys.argv = old_argv
            return save_name
        except Exception as e:
            return str(e)
        finally:
            _logging.disable(_logging.NOTSET)

    result_container = [None]

    def _callback(res):
        result_container[0] = res

    run_with_loading(_callback, task)
    return result_container[0]


def convert_JSON_sav(save_name, direct_saves_map, message_callback=None):
    """Convert a JSON save back to .sav, producing ``Level.sav`` in the save
    root.  Calls *message_callback* (type, title, text) for user-facing
    messages."""
    if message_callback is None:
        message_callback = lambda typ, title, text: logger.info(
            "[%s] %s: %s", typ, title, text
        )

    if save_name in direct_saves_map:
        source_base = direct_saves_map[save_name]
    else:
        parts = save_name.split(" - ", 1)
        folder_id = parts[0] if parts else save_name
        source_base = os.path.join(root_dir, "saves", folder_id)

    json_path = os.path.join(source_base, "Level", "01.sav.json")
    sav_path = os.path.join(source_base, "Level", "01.sav")
    out_level = os.path.join(source_base, "Level.sav")

    if os.path.exists(out_level):
        all_saves = list(direct_saves_map.keys())
        if len(all_saves) == 1:
            message_callback("info", "Success", "All saves converted successfully.")
            return
        else:
            message_callback(
                "info", "Info", f"Save '{save_name}' already converted."
            )
            return

    def run_conversion():
        try:
            import logging as _logging
            _logging.disable(_logging.CRITICAL)
            from palsav.commands import convert
            if os.path.exists(sav_path) and (not os.path.exists(json_path)):
                old = sys.argv
                sys.argv = ["convert", sav_path]
                convert.main()
                sys.argv = old
            if not os.path.exists(json_path):
                return "err_no_json"
            old = sys.argv
            sys.argv = ["convert", json_path, "--output", out_level]
            convert.main()
            sys.argv = old
            if os.path.exists(json_path):
                os.remove(json_path)
            return "success"
        except Exception as e:
            error_str = str(e)
            if "Cannot log to objects of type" in error_str:
                return "Conversion completed(logging error suppressed)"
            return error_str
        finally:
            _logging.disable(_logging.NOTSET)

    def on_conversion_finished(result):
        if result == "success" or "Conversion completed(logging error suppressed)" in result:
            move_save_steam(save_name, direct_saves_map, message_callback)
        elif result == "err_no_json":
            message_callback("critical", "Error", "No valid saves found.")
        else:
            message_callback("critical", "Error", f"Conversion failed: {result}")

    run_with_loading(on_conversion_finished, run_conversion)


def move_save_steam(save_name, direct_saves_map, message_callback=None):
    """Copy converted save to a user-chosen destination (console prompt)."""
    if message_callback is None:
        message_callback = lambda typ, title, text: logger.info(
            "[%s] %s: %s", typ, title, text
        )

    try:
        initial = os.path.expandvars("%localappdata%\\Pal\\Saved\\SaveGames")
        if not os.path.isdir(initial):
            initial = root_dir

        print(f"Destination folder [{initial}]:")
        destination = input("> ").strip()
        if not destination:
            destination = initial
        if not os.path.isdir(destination):
            logger.warning("Destination does not exist, creating: %s", destination)
            os.makedirs(destination, exist_ok=True)

        if save_name in direct_saves_map:
            source_base = direct_saves_map[save_name]
        else:
            parts = save_name.split(" - ", 1)
            folder_id = parts[0] if parts else save_name
            source_base = os.path.join(root_dir, "saves", folder_id)

        if not os.path.isdir(source_base):
            raise FileNotFoundError(f"Source not found: {source_base}")

        if not os.path.isfile(os.path.join(source_base, "Level.sav")):
            message_callback(
                "critical",
                "Error",
                "Conversion failed: Missing Level.sav in save root",
            )
            return

        def ignore(_, names):
            return {n for n in names if n in {"Level", "Slot1", "Slot2", "Slot3"}}

        original_folder_name = os.path.basename(source_base)
        if is_valid_save_id(original_folder_name):
            destination_path = os.path.join(destination, original_folder_name)
            if os.path.exists(destination_path):
                new_name = generate_random_name()
            else:
                new_name = original_folder_name
        else:
            new_name = generate_random_name()

        xgp_out = os.path.join(root_dir, "XGP_converted_saves")
        os.makedirs(xgp_out, exist_ok=True)

        shutil.copytree(
            source_base,
            os.path.join(xgp_out, new_name),
            dirs_exist_ok=True,
            ignore=ignore,
        )
        shutil.copytree(
            source_base,
            os.path.join(destination, new_name),
            dirs_exist_ok=True,
            ignore=ignore,
        )
        message_callback("info", "Success", f"Converted and copied to {destination}")
    except Exception as e:
        logger.error("Copy failed: %s", e)
        traceback.print_exc()
        message_callback("critical", "Error", f"Copy failed: {e}")


# ============================================================================
# Extraction / scanning flows
# ============================================================================

def run_save_extractor(xgp_source_folder):
    """Extract saves from an XGP container zip into ``./saves`` and return a
    ``direct_saves_map`` (display_name -> path)."""
    import gc

    global save_info_map

    try:
        from toolsets import xgp_save_extract as extractor

        extractor.main(xgp_source_folder)

        zip_files = [
            f
            for f in os.listdir(base_dir)
            if f.startswith("palworld_") and f.endswith(".zip")
        ]
        if not zip_files:
            logger.warning("No extracted zip files found.")
            return {}

        valid_zip_path = max(
            [os.path.join(base_dir, f) for f in zip_files], key=os.path.getsize
        )

        saves_dir = os.path.join(root_dir, "saves")
        if os.path.exists(saves_dir):
            shutil.rmtree(saves_dir)
        if not unzip_file(valid_zip_path, saves_dir):
            return {}

        # Move zip to backup
        backup_dir = os.path.join(root_dir, "XGP_converted_saves")
        os.makedirs(backup_dir, exist_ok=True)
        for f in zip_files:
            try:
                dest = os.path.join(backup_dir, f)
                if os.path.exists(dest):
                    os.remove(dest)
                shutil.move(os.path.join(base_dir, f), dest)
            except Exception:
                pass

        saves_found = find_valid_saves(saves_dir)
        if not saves_found:
            logger.error("No valid saves found after extraction.")
            return {}

        direct_map = {}
        for save_path in saves_found:
            folder_name = os.path.basename(save_path)
            info = get_save_info(save_path)
            save_info_map[folder_name] = info
            display_name = f"{folder_name} - {info['world_name']} ({info['player_name']})"
            direct_map[display_name] = save_path

        logger.info("Found %d save(s) after extraction.", len(direct_map))
        return direct_map
    except Exception as e:
        logger.error("Save extraction failed: %s", e)
        traceback.print_exc()
        return {}
    finally:
        gc.collect()


def convert_save_files(direct_saves_map):
    """Convert all .sav files in *direct_saves_map* to JSON and return a new
    map."""
    save_folders = list_folders_in_directory(os.path.join(root_dir, "saves"))
    if not save_folders:
        logger.warning("No save files found")
        return {}

    successful = 0
    save_list = []
    for save_name in save_folders:
        result = convert_sav_JSON(save_name, direct_saves_map)
        if result:
            save_list.append(result)
            successful += 1

    global save_info_map
    save_info_map = {}
    new_map = {}
    for folder_name in save_list:
        save_path = os.path.join(root_dir, "saves", folder_name)
        info = get_save_info(save_path)
        save_info_map[folder_name] = info
        display_name = f"{folder_name} - {info['world_name']} ({info['player_name']})"
        new_map[display_name] = save_path

    total = len(save_folders)
    if successful > 0:
        if successful == total:
            logger.info("All %d save(s) converted successfully.", total)
        else:
            logger.info(
                "%d / %d save(s) converted successfully.", successful, total
            )
    else:
        logger.error("No saves were converted.")

    return new_map


def transfer_steam_to_gamepass(source_folder, message_callback=None):
    """Transfer a Steam save to XGP."""
    if message_callback is None:
        message_callback = lambda typ, title, text: logger.info(
            "[%s] %s: %s", typ, title, text
        )

    try:
        stop_gaming_services()
        time.sleep(1)

        from xgp_import import main as xgp_main

        old_argv = sys.argv
        try:
            sys.argv = ["main.py", source_folder]
            xgp_main.main()
            time.sleep(2)
            message_callback("info", "Success", "Steam save imported to XGP successfully.")
        finally:
            sys.argv = old_argv
            start_gaming_services()
    except Exception as e:
        logger.error("Import to XGP failed: %s", e)
        message_callback("critical", "Import Failed", str(e))


# ============================================================================
# Entry points (CLI)
# ============================================================================

def game_pass_save_fix(args=None):
    """CLI entry point for XGP/Steam save conversion.

    If *args* is ``None``, ``sys.argv[1:]`` is used.  Supported sub-commands
    via ``argparse``.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Palworld saves between XGP and Steam formats."
    )
    sub = parser.add_subparsers(dest="mode", help="Conversion mode")

    # --- XGP -> Steam ---
    xgp_parser = sub.add_parser(
        "xgp-to-steam", help="Convert an XGP (Game Pass) save to Steam format"
    )
    xgp_parser.add_argument("source", help="Path to the XGP save folder / container")
    xgp_parser.add_argument(
        "--destination", "-d",
        default=None,
        help="Destination folder for the converted save (default: prompt)",
    )

    # --- Steam -> XGP ---
    steam_parser = sub.add_parser(
        "steam-to-xgp", help="Convert a Steam save to XGP (Game Pass) format"
    )
    steam_parser.add_argument("source", help="Path to the Steam save folder")
    steam_parser.add_argument(
        "--world-name", "-w",
        default=None,
        help="New world name (default: prompt if LevelMeta.sav found)",
    )

    parsed = parser.parse_args(args)
    if parsed.mode is None:
        parser.print_help()
        return

    # Cleanup old temporary data
    saves_folder = os.path.join(root_dir, "saves")
    xgp_folder = os.path.join(root_dir, "XGP_converted_saves")
    if os.path.exists(saves_folder):
        shutil.rmtree(saves_folder)
    if os.path.exists(xgp_folder):
        shutil.rmtree(xgp_folder)

    if parsed.mode == "xgp-to-steam":
        _cli_xgp_to_steam(parsed.source, parsed.destination)
    elif parsed.mode == "steam-to-xgp":
        _cli_steam_to_xgp(parsed.source, parsed.world_name)


def _cli_xgp_to_steam(source, destination=None):
    """XGP -> Steam conversion flow."""
    global save_info_map

    def message(typ, title, text):
        if typ == "critical":
            logger.error("[%s] %s", title, text)
        else:
            logger.info("[%s] %s", title, text)

    logger.info("Starting XGP -> Steam conversion from: %s", source)

    # Determine if source is a container or regular save folder
    def _is_xgp_container(path):
        for root, _, files in os.walk(path):
            if any(f.lower().startswith("container.") for f in files):
                return True
        return False

    if _is_xgp_container(source):
        logger.info("Detected XGP container. Extracting saves...")
        direct_map = run_save_extractor(source)
        if not direct_map:
            logger.error("No saves could be extracted from container.")
            return
    else:
        saves = find_valid_saves(source)
        if not saves:
            logger.error("No valid saves found in the specified folder.")
            return
        save_info_map = {}
        direct_map = {}
        for save_path in saves:
            folder_name = os.path.basename(save_path)
            info = get_save_info(save_path)
            save_info_map[folder_name] = info
            display_name = f"{folder_name} - {info['world_name']} ({info['player_name']})"
            direct_map[display_name] = save_path

    logger.info("Available saves:")
    display_names = list(direct_map.keys())
    for i, name in enumerate(display_names, 1):
        print(f"  {i}. {name}")

    if not display_names:
        logger.error("No saves to convert.")
        return

    # Let user pick
    if len(display_names) == 1:
        selected = display_names[0]
        logger.info("Auto-selected the only save: %s", selected)
    else:
        print(f"Select a save to convert (1-{len(display_names)}): ")
        try:
            choice = int(input("> ").strip())
            selected = display_names[choice - 1]
        except (ValueError, IndexError):
            logger.error("Invalid selection.")
            return

    # Convert .sav -> .json -> .sav (produces Level.sav)
    convert_JSON_sav(selected, direct_map, message_callback=message)

    if destination:
        # Move to specified destination
        move_save_steam(selected, direct_map, message_callback=message)
    else:
        print("Save converted. Destination folder not specified; files remain in ./saves/")


def _cli_steam_to_xgp(source, world_name=None):
    """Steam -> XGP conversion flow."""

    def message(typ, title, text):
        if typ == "critical":
            logger.error("[%s] %s", typ, title, text)
        else:
            logger.info("[%s] %s", typ, title, text)

    logger.info("Starting Steam -> XGP conversion from: %s", source)

    sav_path = os.path.join(source, "Level.sav")
    if not os.path.exists(sav_path):
        logger.error("Selected folder does not contain Level.sav")
        return

    # Optionally rename world
    meta_path = os.path.join(source, "LevelMeta.sav")
    if os.path.exists(meta_path):
        try:
            meta_json = sav_to_json(meta_path)
            old_name = meta_json["properties"]["SaveData"]["value"].get(
                "WorldName", {}
            ).get("value", "Unknown World")
            print(f"Current world name: {old_name}")
            if world_name is None:
                new_name = _ask_string_cli(
                    "Enter new world name (leave blank to keep current): ",
                    default=None,
                )
            else:
                new_name = world_name

            if new_name:
                meta_json["properties"]["SaveData"]["value"]["WorldName"][
                    "value"
                ] = new_name
                json_to_sav(meta_json, meta_path)
                logger.info("World name updated to: %s", new_name)
            del meta_json
        except Exception as e:
            logger.warning("Metadata processing failed: %s", e)

    if not is_admin():
        logger.error(
            "Administrator privileges are required for Steam -> XGP transfer."
        )
        return

    # Confirm
    print("WARNING: This operation will modify your system's Gaming Services.")
    print("Continue? [y/N] ")
    answer = input("> ").strip().lower()
    if answer not in ("y", "yes"):
        logger.info("Operation cancelled by user.")
        return

    transfer_steam_to_gamepass(source, message_callback=message)


if __name__ == "__main__":
    game_pass_save_fix()
