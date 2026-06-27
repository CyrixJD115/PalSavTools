"""Map data service — thin adapter over palworld_aio.map.map_data_service.

ALL real business logic lives in ``src/palworld_aio/map/map_data_service.py``
(zero PySide6 imports). This module handles:
1. Loading that module via importlib (avoids ``sys.path`` pollution).
2. Adapting its canonical dict shapes to the web API schema.

``map_data_service.py`` is self-loading: it handles its own ``coord``
and ``ContainerOwnership`` imports via try/except fallback, so we can load it
with a simple ``importlib.util.spec_from_file_location``.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from web.backend.services import world_service

logger = logging.getLogger(__name__)

# ── Load map_data_service via importlib (self-loading) ────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MDS_PATH = _REPO_ROOT / "src" / "palworld_aio" / "map" / "map_data_service.py"
_mds_spec = importlib.util.spec_from_file_location("map_data_service", _MDS_PATH)
assert _mds_spec is not None and _mds_spec.loader is not None, "map_data_service not found"
mds = importlib.util.module_from_spec(_mds_spec)
_mds_spec.loader.exec_module(mds)

# ── Public API ──────────────────────────────────────────────────────────────

MAP_SIZE = mds.MAP_SIZE
WORLD_COORD_RANGE = mds.WORLD_COORD_RANGE
TREE_COORD_RANGE = mds.TREE_COORD_RANGE


def list_map_bases(level_dict: dict) -> list[dict]:
    """Build the enriched base list with pre-computed pixel coordinates.

    Delegates to ``map_data_service.list_map_bases()``. The output schema
    already matches ``MapBase`` (extra fields like ``raw`` / ``last_seen``
    are harmless).
    """
    return mds.list_map_bases(level_dict)


def precompute_player_data(
    level_dict: dict,
) -> tuple[dict[str, int], dict[str, int], dict[str, tuple[float, float, float]]]:
    """Pre-compute pal counts, player levels, and fallback positions."""
    return mds.precompute_player_data(level_dict)


def list_map_players(
    level_dict: dict,
    players_dir: str | None,
    pal_counts: dict[str, int] | None = None,
    levels: dict[str, int] | None = None,
    positions: dict[str, tuple[float, float, float]] | None = None,
) -> list[dict]:
    """Build enriched player list, adapted to the ``MapPlayer`` API schema.

    Delegates to ``map_data_service.list_map_players()`` for the core logic
    (reading ``.sav`` files, coordinate projection, fallback positions), then
    adapts field names to match the web API contract.
    """
    raw = mds.list_map_players(
        level_dict,
        players_dir=players_dir,
        pal_counts=pal_counts,
        player_levels=levels,
        positions=positions,
    )
    out = []
    for p in raw:
        location = p.get("save_coords")
        world_img = None
        tree_img = None
        if location is not None:
            raw_x, raw_y, raw_z = location
            world_img = mds.project_world(raw_x, raw_y)
            tree_img = mds.project_tree(raw_x, raw_y)

        out.append({
            "uid": p["player_uid"],
            "name": p["player_name"],
            "level": p["level"],
            "guild_id": p["guild_id"],
            "guild_name": p.get("guild_name", "") or "",
            "last_seen_text": p.get("last_seen", None),
            "pal_count": p.get("pal_count", 0),
            "location": location,
            "map_type": p.get("map_type", "world"),
            "world_img": world_img,
            "tree_img": tree_img,
        })
    return out


def get_map_data(
    level_dict: dict,
    players_dir: str | None,
    pal_counts: dict[str, int] | None = None,
    levels: dict[str, int] | None = None,
    positions: dict[str, tuple[float, float, float]] | None = None,
) -> dict:
    """Build the full map data payload for ``GET /api/map/data``."""
    return {
        "bases": list_map_bases(level_dict),
        "players": list_map_players(
            level_dict, players_dir, pal_counts, levels, positions,
        ),
        "map_size": MAP_SIZE,
        "world_coord_range": WORLD_COORD_RANGE,
        "tree_coord_range": TREE_COORD_RANGE,
    }
