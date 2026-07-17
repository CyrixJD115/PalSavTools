"""
constants — global state / configuration for the palworld_aio module.

Removed all Qt style/color/layout constants.  Only retains business-logic
constants and runtime state.
"""

import os
import sys
from resource_resolver import get_base_dir, get_src_dir, resource_path

GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/"
    "deafdudecomputers/PalworldSaveTools/main/src/common.py"
)
GIT_REPO_URL = "https://github.com/deafdudecomputers/PalworldSaveTools.git"
STABLE_BRANCH = "main"
BETA_BRANCH = "beta"
STABLE_VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "deafdudecomputers/PalworldSaveTools/main/src/common.py"
)
BETA_VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "deafdudecomputers/PalworldSaveTools/beta/src/common.py"
)
RELEASE_DOWNLOAD_URL = (
    "https://github.com/deafdudecomputers/"
    "PalworldSaveTools/releases/download/v{version}/"
    "PST_standalone_v{version}.7z"
)
RELEASES_PAGE_URL = (
    "https://github.com/deafdudecomputers/"
    "PalworldSaveTools/releases/latest"
)


def get_base_path():
    return get_base_dir()


def get_src_path():
    return get_src_dir()


def get_icon_path():
    return resource_path(get_base_dir(), "icon.ico")


ICON_PATH = get_icon_path()
EXCLUSIONS_FILE = os.path.join(
    get_src_path(), "data", "configs", "deletion_exclusions.json"
)
ZONE_EXCLUSIONS_FILE = os.path.join(
    get_src_path(), "data", "configs", "zone_exclusions.json"
)

# ── Runtime state (mutated by save load / operations) ──────────────────

current_save_path = None
loaded_level_json = None
original_loaded_level_json = None
backup_save_path = None
srcGuildMapping = None
player_levels = {}
player_character_cache = {}
base_guild_lookup = {}
container_lookup = {}
files_to_delete = set()
PLAYER_PAL_COUNTS = {}
PLAYER_DETAILS_CACHE = {}
PLAYER_REMAPS = {}
exclusions = {}
death_bag_protected_instance_ids = set()
death_bag_protected_container_ids = set()
selected_source_player = None
dps_executor = None
dps_futures = []
dps_tasks = []
dirty = False


def get_container_lookup():
    global container_lookup
    if container_lookup and loaded_level_json:
        return container_lookup
    if not loaded_level_json:
        return {}
    container_lookup = {}
    wsd = loaded_level_json["properties"]["worldSaveData"]["value"]
    item_containers = wsd.get("ItemContainerSaveData", {}).get("value", [])
    for cont in item_containers:
        try:
            cont_id = str(cont["key"]["ID"]["value"]).replace("-", "").lower()
            container_lookup[cont_id] = cont
        except Exception:
            pass
    return container_lookup


def invalidate_container_lookup():
    global container_lookup
    container_lookup = {}
