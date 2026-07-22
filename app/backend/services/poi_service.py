"""POI (Point of Interest) service — static datasets + coord projection.

Loads 6 PSP-Rust-sourced JSON datasets at import time and projects every
POI's raw-cm coordinates through the same ``project_world`` / ``project_tree``
pipeline used by ``map_service.py``.  The result is cached for the lifetime
of the module (POI data is static — it never changes between saves).
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Locate the data dir (relative to this file) ────────────────────────────
#   app/backend/services/poi_service.py  →  ../../../src/_resources/data/map_pois/
_DATA_DIR = Path(__file__).resolve().parents[3] / "src" / "_resources" / "data" / "map_pois"

# ── Import projection functions from the legacy map_data_service ───────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MDS_PATH = _REPO_ROOT / "src" / "palworld_aio" / "map" / "map_data_service.py"

_project_world = None
_project_tree = None
_CLASSIFY_MAP_TYPE = None
try:
    _mds_spec = importlib.util.spec_from_file_location("map_data_service", _MDS_PATH)
    assert _mds_spec is not None and _mds_spec.loader is not None
    mds = importlib.util.module_from_spec(_mds_spec)
    _mds_spec.loader.exec_module(mds)
    _project_world = getattr(mds, "project_world", None)
    _project_tree = getattr(mds, "project_tree", None)
    _CLASSIFY_MAP_TYPE = getattr(mds, "classify_map_type", None)
except Exception:
    logger.warning("map_data_service projection unavailable; POIs will not project", exc_info=True)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _project_point(x: float, y: float) -> tuple[dict | None, dict | None]:
    """Project raw-cm (x, y) to world and tree pixel coords.

    Returns (world_img, tree_img), each either a ``MapProjection``-style
    dict (``{x, y, world_x, world_y}``) or ``None`` when the point is
    outside that map's coordinate range.
    """
    w = _project_world(x, y) if _project_world else None
    t = _project_tree(x, y) if _project_tree else None
    return w, t


def _split_pascal(name: str) -> str:
    """Split PascalCase into words: ``WeaselDragon`` → ``Weasel Dragon``."""
    if not name:
        return name
    result = [name[0]]
    for ch in name[1:]:
        if ch.isupper() and result[-1].islower():
            result.append(" ")
        result.append(ch)
    return "".join(result)


def _load_json(name: str) -> Any:
    """Load a JSON file from the map_pois directory."""
    path = _DATA_DIR / name
    if not path.exists():
        logger.warning("POI data file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Cached dataset loads ──────────────────────────────────────────────────

_BOSSES: list[dict] | None = None
_MAP_OBJECTS: dict | None = None
_FAST_TRAVEL_POINTS: dict | None = None
_RELICS: dict | None = None
_EFFIGIES: dict | None = None
_RELIC_DATA: dict | None = None
_CHARACTER_MAP: dict[str, str] | None = None  # asset → display_name


def _build_character_map() -> dict[str, str]:
    """Build asset → display_name lookup from ``characters.json``."""
    path = _DATA_DIR.parent.parent / "game_data" / "characters.json"
    mapping: dict[str, str] = {}
    try:
        if not path.exists():
            logger.warning("characters.json not found at %s", path)
            return mapping
        with open(path, encoding="utf-8") as f:
            chars = json.load(f)
        for entry in chars.get("pals", []):
            asset = entry.get("asset", "")
            name = entry.get("name", "")
            if asset:
                mapping[asset] = name
        for entry in chars.get("npcs", []):
            asset = entry.get("asset", "")
            name = entry.get("name", "")
            if asset:
                mapping[asset] = name
    except Exception:
        logger.warning("Failed to load characters.json", exc_info=True)
    return mapping


def _display_name(asset: str, fallback: str = "") -> str:
    """Look up the display name for an asset (pal ID or character_id suffix)."""
    if not asset:
        return fallback or asset
    name = _CHARACTER_MAP.get(asset)
    if name:
        return name
    return fallback or asset


def _ensure_loaded() -> None:
    global _BOSSES, _MAP_OBJECTS, _FAST_TRAVEL_POINTS, _RELICS, _EFFIGIES, _RELIC_DATA, _CHARACTER_MAP
    if _BOSSES is not None:
        return  # already loaded

    try:
        _MAP_OBJECTS = _load_json("map_objects.json")
        _BOSSES = _load_json("bosses.json")
        _FAST_TRAVEL_POINTS = _load_json("fast_travel_points.json")
        _RELICS = _load_json("relics.json")
        _EFFIGIES = _load_json("effigies.json")
        _RELIC_DATA = _load_json("relic_data.json")
        _CHARACTER_MAP = _build_character_map()
    except Exception:
        logger.exception("Failed to load POI data files")


# ── Public API ─────────────────────────────────────────────────────────────


def get_all_pois() -> dict:
    """Return every POI dataset with pre-computed world/tree projections.

    Structure mirrors PSP Rust's data layout for easy frontend consumption:

    .. code-block:: python

        {
            "bosses": [{
                "id": str,           # unique key (spawner_id)
                "name": str,          # human-readable boss name
                "character_id": str,  # e.g. "BOSS_Horus_Water"
                "level": int,
                "defeated": False,    # placeholder — save lookup not wired
                "spawner_id": str,
                "world_img": dict|None, "tree_img": dict|None,
            }, ...],
            "dungeons": [{ "id", "x", "y", "world_img", "tree_img" }, ...],
            "alpha_pals": [{ "id", "pal", "x", "y", "world_img", "tree_img" }, ...],
            "predator_pals": [{ "id", "pal", "x", "y", "world_img", "tree_img" }, ...],
            "fast_travel": [{ "id", "name", "x", "y", "class", "world_img", "tree_img" }, ...],
            "relics": [{ "id", "x", "y", "z", "relic_type", "class", "world_img", "tree_img" }, ...],
            "relic_data": ...,  # per-type metadata table
        }
    """
    _ensure_loaded()

    result: dict[str, Any] = {}
    result["relic_data"] = _RELIC_DATA or {}

    # ── Bosses + Alpha pals + Predator pals → unified "entities" ────────────
    raw_bosses: dict = _BOSSES if isinstance(_BOSSES, dict) else {}
    raw_objects: list = _MAP_OBJECTS if isinstance(_MAP_OBJECTS, list) else []
    entities: list[dict] = []

    # From bosses.json
    for key in sorted(raw_bosses.keys(), key=int):
        e = raw_bosses[key]
        widx, tidx = _project_point(e.get("x", 0), e.get("y", 0))
        char_id = e.get("character_id", "")
        # Extract the asset part from character_id: "BOSS_Horus_Water" → "Horus_Water"
        if char_id and char_id != "None":
            asset = char_id.replace("BOSS_", "").replace("Boss_", "")
            name = _display_name(asset, _split_pascal(asset.replace("_", " ")))
        else:
            asset = ""
            name = _split_pascal(e.get("spawner_id", "").replace("BOSS_", "").replace("REGION_", "").replace("_", " "))
        entities.append({
            "id": f"boss_{key}",
            "name": name or e.get("spawner_id", f"Boss {key}"),
            "subtype": "boss",
            "x": e.get("x", 0), "y": e.get("y", 0),
            "character_id": char_id,
            "spawner_id": e.get("spawner_id", ""),
            "level": e.get("level", 0),
            "world_img": widx, "tree_img": tidx,
        })

    # From map_objects (alpha_pal + predator_pal merged into entities)
    subtype_map = {"alpha_pal": "alpha", "predator_pal": "predator"}
    for idx, e in enumerate(raw_objects):
        obj_type = e.get("type", "")
        normed_subtype = subtype_map.get(obj_type)
        if normed_subtype is None:
            continue
        widx, tidx = _project_point(e.get("x", 0), e.get("y", 0))
        pal_id = e.get("pal", "")
        name = _display_name(pal_id, pal_id)
        entities.append({
            "id": f"ent_{idx}",
            "name": name or pal_id or f"{obj_type}_{idx}",
            "subtype": normed_subtype,
            "x": e.get("x", 0), "y": e.get("y", 0),
            "pal": pal_id,
            "character_id": "",
            "spawner_id": "",
            "level": 0,
            "world_img": widx, "tree_img": tidx,
        })
    result["entities"] = entities

    # ── Map objects: dungeons ──────────────────────────────────────────────
    dungeons: list[dict] = []
    for idx, e in enumerate(raw_objects):
        if e.get("type") != "dungeon":
            continue
        widx, tidx = _project_point(e.get("x", 0), e.get("y", 0))
        dungeons.append({
            "id": f"dng_{idx}",
            "name": e.get("name", f"Dungeon {idx}"),
            "x": e.get("x", 0), "y": e.get("y", 0),
            "world_img": widx, "tree_img": tidx,
        })
    result["dungeons"] = dungeons

    # ── Fast travel points (dict → list) ───────────────────────────────────
    raw_ft: dict = _FAST_TRAVEL_POINTS if isinstance(_FAST_TRAVEL_POINTS, dict) else {}
    ft_list: list[dict] = []
    for guid, e in raw_ft.items():
        widx, tidx = _project_point(e.get("x", 0), e.get("y", 0))
        ft_list.append({
            "id": guid,
            "class": e.get("class", ""),
            "name": e.get("localized_name", e.get("id", guid)),
            "x": e.get("x", 0),
            "y": e.get("y", 0),
            "z": e.get("z", 0),
            "world_img": widx,
            "tree_img": tidx,
        })
    result["fast_travel"] = ft_list

    # ── Relics (dict → list) ───────────────────────────────────────────────
    raw_relics: dict = _RELICS if isinstance(_RELICS, dict) else {}
    relic_list: list[dict] = []
    for guid, e in raw_relics.items():
        widx, tidx = _project_point(e.get("x", 0), e.get("y", 0))
        relic_list.append({
            "id": guid,
            "class": e.get("class", ""),
            "relic_type": e.get("relic_type", "capture_power"),
            "x": e.get("x", 0),
            "y": e.get("y", 0),
            "z": e.get("z", 0),
            "world_img": widx,
            "tree_img": tidx,
        })
    result["relics"] = relic_list

    return result
