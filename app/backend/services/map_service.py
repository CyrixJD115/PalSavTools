"""Map data service — coord projection + Rust-shape base/player lists.

Coordinate math (``project_world``, ``project_tree``, ``classify_map_type``,
``MAP_SIZE``) is loaded from ``src/palworld_aio/map/map_data_service.py`` via
importlib — that file owns the projection constants. Base and player lists are
built by the Rust-shape-aware ``base_service`` / ``world_service`` / ``player
_service``, so this module just projects their locations onto map pixels.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from app.backend.services import base_service, world_service

logger = logging.getLogger(__name__)

# ── Load only the coord-projection helpers from map_data_service ─────────────
# The legacy module also has Python-shape navigation, but we only import its
# projection constants/functions here; dict navigation uses the Rust-shape
# services above.

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MDS_PATH = _REPO_ROOT / "src" / "palworld_aio" / "map" / "map_data_service.py"

try:
    _mds_spec = importlib.util.spec_from_file_location("map_data_service", _MDS_PATH)
    assert _mds_spec is not None and _mds_spec.loader is not None
    mds = importlib.util.module_from_spec(_mds_spec)
    _mds_spec.loader.exec_module(mds)
    MAP_SIZE = getattr(mds, "MAP_SIZE", 2048)
    WORLD_COORD_RANGE = getattr(mds, "WORLD_COORD_RANGE", 1000)
    TREE_COORD_RANGE = getattr(mds, "TREE_COORD_RANGE", 1000)
    _project_world = getattr(mds, "project_world", None)
    _project_tree = getattr(mds, "project_tree", None)
except Exception:  # noqa: BLE001 — map_data_service may fail to import (coord deps)
    logger.warning("map_data_service projection unavailable; using stubs", exc_info=True)
    MAP_SIZE = 2048
    WORLD_COORD_RANGE = 1000
    TREE_COORD_RANGE = 1000
    _project_world = None
    _project_tree = None


def _project(loc, projector):
    """Project a (x, y, z) tuple to pixel coords, or None if unavailable."""
    if loc is None or projector is None:
        return None
    try:
        return projector(loc[0], loc[1])
    except Exception:
        return None


# ── Public API ───────────────────────────────────────────────────────────────

def list_map_bases(level_dict: dict) -> list[dict]:
    """Enriched base list with world/tree pixel coordinates."""
    out = []
    for b in base_service.get_enriched_base_list(level_dict):
        loc = b.get("location")  # [x, y, z] or None
        entry = dict(b)
        entry["world_img"] = _project(loc, _project_world)
        entry["tree_img"] = _project(loc, _project_tree)
        out.append(entry)
    return out


def precompute_player_data(
    level_dict: dict,
) -> tuple[dict[str, int], dict[str, int], dict[str, tuple[float, float, float]]]:
    """Pre-compute pal counts, player levels, and fallback positions.

    Pal counts and levels come from per-player ``.sav`` files normally, but
    since those aren't available here we derive fallbacks from the world save:
    Pal counts come from each pal's ``OwnerPlayerUId`` (the true owner, NOT the
    map key which is often the host/system); levels come from each player's own
    ``SaveParameter.Level``; positions from ``LastJumpedLocation``. All three
    are derivable from Level.sav alone — no per-player .sav files needed.
    """
    wsd = world_service.get_world_save_data(level_dict)
    pal_counts: dict[str, int] = {}
    levels: dict[str, int] = {}
    positions: dict[str, tuple[float, float, float]] = {}

    for ch in world_service._map_entries(wsd, "CharacterSaveParameterMap"):
        sp = world_service._pal_entry_raw(ch)
        if not sp:
            continue
        key = world_service._g(ch, "key") or {}
        # Keys are normalized to the dash-stripped lowercase form the routes
        # use for lookup (player_uid.replace('-','').lower()).
        key_uid = world_service._s(world_service._k(key, "PlayerUId"))

        if world_service._k(sp, "IsPlayer"):
            # This is a player's own character entry: read level + position.
            if key_uid:
                lv = world_service._k(sp, "Level")
                if lv is not None:
                    try:
                        levels[key_uid] = int(lv)
                    except (TypeError, ValueError):
                        pass
            loc = world_service._k(sp, "LastJumpedLocation")
            if isinstance(loc, dict) and "x" in loc and key_uid:
                try:
                    positions[key_uid] = (float(loc["x"]), float(loc["y"]), float(loc["z"]))
                except (TypeError, ValueError):
                    pass
        else:
            # This is a pal: count it toward its OwnerPlayerUId.
            owner = world_service._s(world_service._k(sp, "OwnerPlayerUId"))
            if owner:
                pal_counts[owner] = pal_counts.get(owner, 0) + 1

    return pal_counts, levels, positions


def list_map_players(
    level_dict: dict,
    players_dir: str | None,
    pal_counts: dict[str, int] | None = None,
    levels: dict[str, int] | None = None,
    positions: dict[str, tuple[float, float, float]] | None = None,
) -> list[dict]:
    """Enriched player list with projected map coordinates."""
    pc = pal_counts or {}
    lv = levels or {}
    pos = positions or {}
    out = []
    for p in world_service.list_players(level_dict):
        uid = p["uid"]
        uid_clean = world_service._s(uid)
        loc = pos.get(uid_clean) or pos.get(uid)
        out.append({
            "uid": uid,
            "name": p["name"],
            "level": lv.get(uid_clean, p.get("level", 0)),
            "guild_id": p.get("guild_id", ""),
            "guild_name": p.get("guild_name", "") or "",
            "last_seen_text": p.get("last_seen_text"),
            "pal_count": pc.get(uid_clean, p.get("pal_count", 0)),
            "location": loc,
            "map_type": "world",
            "world_img": _project(loc, _project_world),
            "tree_img": _project(loc, _project_tree),
        })
    return out


def get_map_data(
    level_dict: dict,
    players_dir: str | None,
    pal_counts: dict[str, int] | None = None,
    levels: dict[str, int] | None = None,
    positions: dict[str, tuple[float, float, float]] | None = None,
) -> dict:
    """Full map data payload for ``GET /api/map/data``."""
    return {
        "bases": list_map_bases(level_dict),
        "players": list_map_players(
            level_dict, players_dir, pal_counts, levels, positions,
        ),
        "map_size": MAP_SIZE,
        "world_coord_range": WORLD_COORD_RANGE,
        "tree_coord_range": TREE_COORD_RANGE,
    }
