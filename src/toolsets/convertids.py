"""
convertids — Convert Steam IDs to Palworld player UIDs (headless CLI).

Removed all PySide6/Qt dependencies.  Business logic (ID conversion) preserved
as module-level functions.  GUI dialog replaced with CLI interface.
"""

import logging
import os
import sys

from import_libs import *

logger = logging.getLogger("pst.convertids")


# ============================================================================
# Business logic
# ============================================================================

def get_steam_id_from_local():
    """Return the first subdirectory name under the local Palworld save
    directory, or ``None``."""
    local_app_data_path = os.path.expandvars(
        "%localappdata%\\Pal\\Saved\\SaveGames"
    )
    if os.path.exists(local_app_data_path):
        subdirs = [
            d
            for d in os.listdir(local_app_data_path)
            if os.path.isdir(os.path.join(local_app_data_path, d))
        ]
        return subdirs[0] if subdirs else None
    return None


def convert_steam_id(steam_input=None, *, quiet=False):
    """Convert a Steam ID / profile URL to a Palworld player UID.

    Parameters
    ----------
    steam_input : str or None
        A Steam ID (numeric), ``steam_`` prefixed ID, or full profile URL.
        If ``None``, attempts auto-detection from local save folder.
    quiet : bool
        If ``True``, returns the result string instead of printing.

    Returns
    -------
    str
        The formatted result (both Palworld UID and no-Steam UID) on success,
        or an error string on failure.
    """
    if steam_input is None:
        steam_input = get_steam_id_from_local()
        if steam_input:
            if not quiet:
                logger.info("Auto-detected Steam ID from local saves: %s", steam_input)
        else:
            return "No Steam ID provided and could not auto-detect."

    steam_input = steam_input.strip()

    # Parse various input formats
    if "steamcommunity.com/profiles/" in steam_input:
        steam_input = steam_input.split("steamcommunity.com/profiles/")[1].split("/")[0]
    elif steam_input.startswith("steam_"):
        steam_input = steam_input[6:]

    try:
        steam_id = int(steam_input)
    except ValueError:
        return "Error: Invalid Steam ID. Provide a numeric ID, a 'steam_' ID, or a profile URL."

    try:
        palworld_uid = steamIdToPlayerUid(steam_id)
        nosteam_uid = (
            PlayerUid2NoSteam(
                int.from_bytes(
                    toUUID(palworld_uid).raw_bytes[0:4], byteorder="little"
                )
            )
            + "-0000-0000-0000-000000000000"
        )
        result = (
            f"Palworld UID:      {str(palworld_uid).upper()}\n"
            f"No-Steam UID:      {nosteam_uid.upper()}"
        )

        if not quiet:
            print(result)
        return result
    except Exception as e:
        msg = f"Error during conversion: {e}"
        logger.error(msg)
        return msg


# ============================================================================
# CLI entry point
# ============================================================================

def main():
    """CLI entry point.

    Usage::

        python convertids.py [steam_id]

    If *steam_id* is omitted, tries auto-detection from local save folder.
    """
    steam_input = sys.argv[1] if len(sys.argv) > 1 else None
    result = convert_steam_id(steam_input)
    if result and result.startswith("Error"):
        print(result, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
