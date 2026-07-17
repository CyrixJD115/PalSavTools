"""
Headless entry point for the palworld_aio module.

Replaces the original Qt-based main.py with a CLI/script-oriented entry point.
All Qt, PySide6, and GUI code has been removed.
"""

import sys
import os

_found_root = None
if os.path.isfile(sys.executable):
    _exe_dir = os.path.dirname(os.path.realpath(sys.executable))
    if os.path.isdir(os.path.join(_exe_dir, "resources")):
        _found_root = _exe_dir
    else:
        _parent = os.path.dirname(_exe_dir)
        if os.path.isdir(os.path.join(_parent, "resources")):
            _found_root = _parent
if not _found_root:
    _probe = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.isdir(os.path.join(_probe, "resources")):
            _found_root = _probe
            break
        _probe = os.path.dirname(_probe)
    if not _found_root:
        _found_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
sys._PST_BINARY_ROOT = _found_root

import traceback
import multiprocessing

_is_frozen = getattr(sys, "frozen", False)

if _is_frozen:
    import subprocess

    multiprocessing.set_executable(sys.executable)
    _original_popen = subprocess.Popen

    class _NoConsolePopen(_original_popen):
        def __init__(self, *args, **kwargs):
            if sys.platform == "win32" and "creationflags" not in kwargs:
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = _NoConsolePopen

if __name__ == "__main__":
    multiprocessing.freeze_support()

if _is_frozen:
    import io

    class MockStdin:
        def read(self, size=-1):
            return ""
        def readline(self, size=-1):
            return "\n"
        def readlines(self, hint=-1):
            return []
        def __iter__(self):
            return iter([])
        def __next__(self):
            raise StopIteration

    if "--spawn-loader" not in sys.argv:
        sys.stdin = MockStdin()
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()

if _is_frozen:
    base_dir = sys._PST_BINARY_ROOT
else:
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

if _is_frozen:
    src_dir = os.path.join(base_dir, "src")
else:
    src_dir = (
        base_dir
        if os.path.basename(base_dir) == "src"
        else os.path.join(base_dir, "src")
    )

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

for sub in ["coord", "palsav", "xgp_import", "resources", "palworld_aio"]:
    p = os.path.join(src_dir, sub)
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
    elif sub == "resources":
        p = os.path.join(base_dir, "resources")
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pst.palworld_aio")

# Quiet down noisy libraries
logging.getLogger("palsav").setLevel(logging.WARNING)

from i18n import init_language
from import_libs import backup_whole_directory
from palworld_aio import constants


def run_headless_cli(path_arg: str, logs: bool = False, fix: bool = False) -> None:
    """
    Run the full headless pipeline: load a save, optionally generate logs,
    optionally clean up data, and save.

    Parameters
    ----------
    path_arg : str
        Path to the Level.sav file.
    logs : bool
        Generate scan logs if True.
    fix : bool
        Run cleanup/fix operations if True.
    """
    if not path_arg:
        logger.error("No path provided")
        sys.exit(1)
    if not path_arg.endswith("Level.sav"):
        logger.error("File must be Level.sav")
        sys.exit(1)

    d = os.path.dirname(path_arg)
    playerdir = os.path.join(d, "Players")
    if not os.path.isdir(playerdir):
        logger.error("Players folder not found")
        sys.exit(1)

    # Reset global state
    constants.loaded_level_json = None
    constants.current_save_path = None
    constants.backup_save_path = None
    constants.srcGuildMapping = None
    constants.base_guild_lookup = {}
    constants.files_to_delete = set()
    constants.PLAYER_PAL_COUNTS = {}
    constants.player_levels = {}
    constants.player_character_cache = {}
    constants.PLAYER_DETAILS_CACHE = {}
    constants.PLAYER_REMAPS = {}
    constants.exclusions = {}
    constants.death_bag_protected_instance_ids.clear()
    constants.death_bag_protected_container_ids.clear()
    constants.selected_source_player = None
    constants.dps_executor = None
    constants.dps_futures = []
    constants.dps_tasks = []
    constants.original_loaded_level_json = None
    from palobject import MappingCacheObject
    MappingCacheObject._MappingCacheInstances.clear()

    logger.info("Processing save file: %s", path_arg)
    constants.current_save_path = d
    constants.backup_save_path = constants.current_save_path

    backup_whole_directory(constants.backup_save_path, "Backups/AllinOneTools")

    import time
    from palworld_aio.utils import sav_to_gvas_wrapper
    from palobject import toUUID

    t0 = time.perf_counter()
    constants.loaded_level_json = sav_to_gvas_wrapper(path_arg)
    t1 = time.perf_counter()
    logger.info("Save loaded in %.2f seconds", t1 - t0)

    from palworld_aio.managers.func_manager import scan_and_protect_death_bags
    scan_and_protect_death_bags()

    from palworld_aio.managers.save_manager import save_manager
    save_manager._build_player_levels()

    if not constants.loaded_level_json:
        logger.error("Failed to load save")
        sys.exit(1)

    data_source = constants.loaded_level_json["properties"]["worldSaveData"]["value"]

    # Build guild mapping
    try:
        if hasattr(MappingCacheObject, "clear_cache"):
            MappingCacheObject.clear_cache()
        constants.srcGuildMapping = MappingCacheObject.get(data_source, use_mp=True)
        if constants.srcGuildMapping._worldSaveData.get("GroupSaveDataMap") is None:
            constants.srcGuildMapping.GroupSaveDataMap = {}
    except Exception as e:
        logger.error("Guild mapping failed: %s", e)
        constants.srcGuildMapping = None

    constants.base_guild_lookup = {}
    guild_name_map = {}
    if constants.srcGuildMapping:
        for gid_uuid, gdata in constants.srcGuildMapping.GroupSaveDataMap.items():
            gid = str(gid_uuid)
            guild_name = gdata["value"]["RawData"]["value"].get("guild_name", "Unnamed Guild")
            guild_name_map[gid.lower()] = guild_name
            for base_id_uuid in gdata["value"]["RawData"]["value"].get("base_ids", []):
                constants.base_guild_lookup[str(base_id_uuid)] = {
                    "GuildName": guild_name,
                    "GuildID": gid,
                }

    logger.info("Loading done")

    if logs:
        base_path = "."
        log_folder = os.path.join(base_path, "Logs", "Scan Save Logger")
        if os.path.exists(log_folder):
            try:
                shutil.rmtree(log_folder)
            except Exception:
                pass
        os.makedirs(log_folder, exist_ok=True)

        logger.info("Generating logs...")
        player_pals_count = {}
        save_manager._count_pals_found(
            data_source, player_pals_count, log_folder,
            constants.current_save_path, guild_name_map,
        )
        constants.PLAYER_PAL_COUNTS = player_pals_count
        save_manager._process_scan_log(
            data_source, playerdir, log_folder, guild_name_map, base_path,
        )
        logger.info("Logs generated successfully")

    if fix:
        logger.info("Running cleanup operations...")
        from palworld_aio.managers.func_manager import (
            remove_invalid_items_from_save,
            remove_invalid_pals_from_save,
            remove_invalid_passives_from_save,
            delete_invalid_structure_map_objects,
            delete_unreferenced_data,
            delete_non_base_map_objects,
            fix_illegal_pals_in_save,
        )
        remove_invalid_items_from_save()
        remove_invalid_pals_from_save()
        remove_invalid_passives_from_save()
        delete_invalid_structure_map_objects()
        delete_unreferenced_data()
        delete_non_base_map_objects()
        fixed_count = fix_illegal_pals_in_save()

        logger.info("Saving changes...")
        if constants.current_save_path and constants.loaded_level_json:
            from palworld_aio.utils import wrapper_to_sav
            level_sav_path = os.path.join(constants.current_save_path, "Level.sav")
            t0 = time.perf_counter()
            wrapper_to_sav(constants.loaded_level_json, level_sav_path)
            t1 = time.perf_counter()

            players_folder = os.path.join(constants.current_save_path, "Players")
            for uid in constants.files_to_delete:
                f = os.path.join(players_folder, uid.upper() + ".sav")
                f_dps = os.path.join(players_folder, f"{uid.upper()}_dps.sav")
                try:
                    os.remove(f)
                except FileNotFoundError:
                    pass
                try:
                    os.remove(f_dps)
                except FileNotFoundError:
                    pass
            constants.files_to_delete.clear()
            logger.info("Changes saved successfully in %.2f seconds", t1 - t0)
        else:
            logger.error("No save file loaded")

    logger.info("Done")


def run_aio():
    """Entry point: parse CLI args and dispatch to headless pipeline."""
    init_language("en_US")

    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        path_arg = sys.argv[1].strip().strip('"')
        options = {"logs": False, "fix": False}
        for arg in sys.argv[2:]:
            if arg in ("-logs", "--logs", "-log"):
                options["logs"] = True
            elif arg in ("-fix", "--fix"):
                options["fix"] = True

        if not any(options.values()):
            options["logs"] = True
            options["fix"] = True
        if options["fix"]:
            options["logs"] = True

        modes = []
        if options["logs"]:
            modes.append("logs")
        if options["fix"]:
            modes.append("fix")
        print(f"Mode: {', '.join(modes)}")

        run_headless_cli(path_arg, logs=options["logs"], fix=options["fix"])
        sys.exit(0)

    # No path argument — just print help
    print("PalworldSaveTools — Headless Mode")
    print()
    print("Usage:")
    print(f"  {sys.argv[0]} <path/to/Level.sav> [-logs] [-fix]")
    print()
    print("Options:")
    print("  -logs    Generate scan logs")
    print("  -fix     Run cleanup and fix operations (implies -logs)")
    print()
    print("To launch the WebUI, use:  src/main.py --web")
    sys.exit(0)


if __name__ == "__main__":
    run_aio()
