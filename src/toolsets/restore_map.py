"""
restore_map — Clear fog of war from Palworld LocalData.sav files (headless CLI).

Removed all PySide6/Qt dependencies.  The core business logic
(``clear_fog_in_local_data``, ``clear_fog_in_all_subfolders``,
``backup_local_data``) is preserved unmodified.  The GUI dialog has been
replaced with a straightforward CLI entry point.
"""

import logging
import os
import shutil
import sys
import time

from import_libs import *
from palsav.core import decompress_sav_to_gvas, compress_gvas_to_sav

from loading_manager import show_critical

logger = logging.getLogger("pst.restore_map")

savegames_path = os.path.join(
    os.environ["LOCALAPPDATA"], "Pal", "Saved", "SaveGames"
)
restore_map_path = os.path.join(".", "Backups", "Restore Map")
os.makedirs(restore_map_path, exist_ok=True)


# ============================================================================
# Business logic (unchanged)
# ============================================================================

def backup_local_data(subfolder_path):
    """Back up ``LocalData.sav`` from *subfolder_path* to the restore-map
    backup directory."""
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    backup_folder = os.path.join(
        restore_map_path, timestamp, os.path.basename(subfolder_path)
    )
    os.makedirs(backup_folder, exist_ok=True)
    backup_file = os.path.join(backup_folder, "LocalData.sav")
    original_local_data = os.path.join(subfolder_path, "LocalData.sav")
    if os.path.exists(original_local_data):
        shutil.copy(original_local_data, backup_file)
        logger.info("Backup created at: %s", backup_file)


def clear_fog_in_local_data(path):
    """Clear the fog-of-war mask in the ``LocalData.sav`` file at *path*."""
    with open(path, "rb") as f:
        data = f.read()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES)
    d = gvas.dump()
    sd = d["properties"]["SaveData"]["value"]

    if "WorldMapUISaveDataMap" in sd:
        for entry in sd["WorldMapUISaveDataMap"]["value"]:
            mask = entry["value"]["MaskTextureData"]["value"]
            mask["values"] = b"\x00" * len(mask["values"])
        logger.info("  WorldMapUISaveDataMap fog cleared")
    elif "WorldMapMaskTextureV4" in sd:
        mask = sd["WorldMapMaskTextureV4"]["value"]
        mask["values"] = b"\x00" * len(mask["values"])
        logger.info("  WorldMapMaskTextureV4 fog cleared")

    hl = sd.get("Local_HiddenLocationFlagMap", {}).get("value", [])
    for entry in hl:
        entry["value"] = False
    logger.info("  Hidden locations set: %d entries", len(hl))

    ng = GvasFile.load(d)
    st = (
        50
        if "Pal.PalWorldSaveGame" in ng.header.save_game_class_name
        or "Pal.PalLocalWorldSaveGame" in ng.header.save_game_class_name
        else 49
    )
    sav = compress_gvas_to_sav(ng.write(SKP_PALWORLD_CUSTOM_PROPERTIES), st)
    with open(path, "wb") as f:
        f.write(sav)


def clear_fog_in_all_subfolders():
    """Walk all subdirectories under *savegames_path* and clear fog in every
    ``LocalData.sav`` found."""
    updated_count = 0
    for folder in os.listdir(savegames_path):
        folder_path = os.path.join(savegames_path, folder)
        if os.path.isdir(folder_path):
            subfolders = [
                subfolder
                for subfolder in os.listdir(folder_path)
                if os.path.isdir(os.path.join(folder_path, subfolder))
            ]
            for subfolder in subfolders:
                subfolder_path = os.path.join(folder_path, subfolder)
                target_path = os.path.join(subfolder_path, "LocalData.sav")
                if os.path.exists(target_path):
                    backup_local_data(subfolder_path)
                    logger.info("Clearing fog in: %s", subfolder_path)
                    clear_fog_in_local_data(target_path)
                    updated_count += 1

    logger.info("=" * 80)
    logger.info("Total worlds/servers updated: %d", updated_count)
    logger.info("=" * 80)
    print(f"Done.  {updated_count} world(s)/server(s) updated.")


# ============================================================================
# CLI entry point
# ============================================================================

def restore_map(confirm=True):
    """Run the fog-clearing operation for all LocalData.sav files.

    Parameters
    ----------
    confirm : bool
        If ``True`` (default), prompt the user for confirmation before
        proceeding.
    """
    print("Warning: This will perform the following actions:")
    print("  1. Clear fog from each existing LocalData.sav")
    print("  2. Create backups of each LocalData.sav before modifying")
    print("  3. Preserve all existing map data (icons, markers, etc.)")
    print()

    if confirm:
        answer = input("Continue? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            logger.info("Operation cancelled by user.")
            return

    clear_fog_in_all_subfolders()


def main():
    """CLI entry point.

    Usage::

        python restore_map.py [--yes]

    Use ``--yes`` to skip the confirmation prompt (useful for scripting).
    """
    skip_confirm = "--yes" in sys.argv or "-y" in sys.argv
    restore_map(confirm=not skip_confirm)


if __name__ == "__main__":
    main()
