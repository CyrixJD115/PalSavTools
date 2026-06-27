"""Map data service — enriches bases and players with pixel coordinates.

ALL coordinate math happens here using the real ``palworld_coord`` Python
module (the same one the desktop app uses). The frontend receives ready-to-
render pixel coordinates and never does sav↔map conversion itself.

Mirrors the logic in:
  - ``palworld_aio/ui/tabs/map_tab.py::_get_guild_bases``
  - ``palworld_aio/ui/tabs/map_tab.py::_get_players``
  - ``palworld_aio/ui/tabs/map_tab.py::_to_image_coordinates``
"""

from __future__ import annotations

import logging
import os
import importlib.util
from pathlib import Path
from typing import Any

# Load palworld_coord directly from its source path. We deliberately do NOT
# add ``src/`` to sys.path because that would shadow the editable ``palsav``
# install (src/palsav/ is a namespace dir). This targeted load gets us the
# exact same coordinate math the desktop app uses without import side-effects.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PALWORLD_COORD_PATH = _REPO_ROOT / "src" / "palworld_coord" / "__init__.py"
_spec = importlib.util.spec_from_file_location("palworld_coord", _PALWORLD_COORD_PATH)
assert _spec is not None and _spec.loader is not None, "palworld_coord not found"
palworld_coord = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(palworld_coord)

from web.backend.services import save_service, world_service
from web.backend.state import save_state

logger = logging.getLogger(__name__)

# Map image is square; the desktop uses 2048×2048 but the value is read from
# the actual image at draw time. We use 2048 for coordinate math since that's
# the canonical T_WorldMap.webp / T_TreeMap.webp resolution.
MAP_SIZE = 2048
WORLD_COORD_RANGE = 1000
TREE_COORD_RANGE = palworld_coord.get_treemap_coord_range()  # 2500


def _world_to_image(x_world: float, y_world: float, width: int, height: int,
                    coord_range: int = WORLD_COORD_RANGE) -> tuple[int, int]:
    """Exact port of MapTab._to_image_coordinates."""
    x_min, x_max = -coord_range, coord_range
    y_min, y_max = -coord_range, coord_range
    x_scale = width / (x_max - x_min)
    y_scale = height / (y_max - y_min)
    img_x = int((x_world - x_min) * x_scale)
    img_y = int((y_max - y_world) * y_scale)
    img_x = max(0, min(width - 1, img_x))
    img_y = max(0, min(height - 1, img_y))
    return img_x, img_y


def _classify_map_type(raw_x: float, raw_y: float) -> str:
    """Decide whether an entity belongs on the world map or tree map.

    Mirrors the inline logic in MapTab._get_guild_bases / _get_players.
    """
    pt = palworld_coord.sav_to_map(raw_x, raw_y, new=True)
    if abs(pt.x) > WORLD_COORD_RANGE or abs(pt.y) > WORLD_COORD_RANGE:
        pt2 = palworld_coord.sav_to_treemap(raw_x, raw_y)
        if abs(pt2.x) <= TREE_COORD_RANGE and abs(pt2.y) <= TREE_COORD_RANGE:
            return "tree"
    return "world"


def _project_world(raw_x: float, raw_y: float) -> dict | None:
    """Project save coords onto the world map image. None if off-map."""
    pt = palworld_coord.sav_to_map(raw_x, raw_y, new=True)
    if abs(pt.x) > WORLD_COORD_RANGE or abs(pt.y) > WORLD_COORD_RANGE:
        return None
    img_x, img_y = _world_to_image(pt.x, pt.y, MAP_SIZE, MAP_SIZE, WORLD_COORD_RANGE)
    return {"x": img_x, "y": img_y, "world_x": pt.x, "world_y": pt.y}


def _project_tree(raw_x: float, raw_y: float) -> dict | None:
    """Project save coords onto the tree map image. None if off-map."""
    pt = palworld_coord.sav_to_treemap(raw_x, raw_y)
    if abs(pt.x) > TREE_COORD_RANGE or abs(pt.y) > TREE_COORD_RANGE:
        return None
    img_x, img_y = palworld_coord.treemap_to_pixel(pt.x, pt.y, MAP_SIZE, MAP_SIZE)
    return {"x": img_x, "y": img_y, "world_x": pt.x, "world_y": pt.y}


def _last_seen_text(wsd: dict, players: list[dict], tick: int) -> str:
    """Compute a "5d 3h" style last-seen string for a guild."""
    times = [
        p.get("player_info", {}).get("last_online_real_time")
        for p in players
        if p.get("player_info", {}).get("last_online_real_time")
    ]
    if not times or not tick:
        return "Unknown"
    diff = (tick - max(times)) / 10_000_000.0
    days = int(diff // 86400)
    hours = int(diff % 86400 // 3600)
    mins = int(diff % 3600 // 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def list_map_bases(level_dict: dict) -> list[dict]:
    """Build the enriched base list with pre-computed pixel coordinates.

    Mirrors MapTab._get_guild_bases.
    """
    wsd = world_service.get_world_save_data(level_dict)
    group_map = world_service._map_values(wsd, "GroupSaveDataMap")
    base_map = {
        str(b["key"]).replace("-", ""): b["value"]
        for b in world_service._map_values(wsd, "BaseCampSaveData")
    }
    tick = world_service.get_tick(wsd)

    out: list[dict] = []
    for entry in group_map:
        try:
            if entry["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue

        gid = str(entry["key"])
        g_val = entry["value"]
        raw = g_val.get("RawData", {}).get("value", {})
        admin_uid = str(raw.get("admin_player_uid", ""))
        guild_name = raw.get("guild_name", "Unnamed Guild")
        guild_level = raw.get("base_camp_level", 1)
        players = raw.get("players", []) or []
        member_count = len(players)
        base_ids = raw.get("base_ids", []) or []
        total_bases = len(base_ids)

        # leader name
        leader_name = None
        for p in players:
            if str(p.get("player_uid", "")) == admin_uid:
                leader_name = p.get("player_info", {}).get("player_name", admin_uid)
                break
        if not leader_name and players:
            leader_name = players[0].get("player_info", {}).get("player_name", admin_uid)
        if not leader_name:
            leader_name = admin_uid or "Unknown"

        base_position = 1
        for bid in base_ids:
            bid_str = str(bid).replace("-", "")
            if bid_str not in base_map:
                continue
            base_val = base_map[bid_str]
            try:
                translation = base_val["RawData"]["value"]["transform"]["translation"]
                raw_x = float(translation["x"])
                raw_y = float(translation["y"])
                raw_z = float(translation.get("z", 0.0))
            except Exception:
                continue

            area_range = float(
                base_val.get("RawData", {}).get("value", {}).get("area_range", 3500.0)
            )
            map_type = _classify_map_type(raw_x, raw_y)

            out.append({
                "id": str(bid),
                "guild_id": gid,
                "guild_name": guild_name,
                "guild_level": guild_level,
                "leader_name": leader_name,
                "member_count": member_count,
                "total_bases": total_bases,
                "base_position": base_position,
                "location": [raw_x, raw_y, raw_z],
                "area_range": area_range,
                "map_type": map_type,
                "world_img": _project_world(raw_x, raw_y),
                "tree_img": _project_tree(raw_x, raw_y),
            })
            base_position += 1

    return out


def _read_player_position(sav_path: Path) -> tuple[float, float, float] | None:
    """Decode a player .sav and extract LastTransform translation.

    Returns None if the file can't be read or has no transform.
    """
    try:
        gvas, _save_type, _level_dict = save_service.decode_bytes(sav_path.read_bytes())
    except Exception as exc:
        logger.debug("Failed to decode player sav %s: %s", sav_path, exc)
        return None
    try:
        save_data = gvas.properties.get("SaveData", {}).get("value", {})
        last_transform = save_data.get("LastTransform", {}).get("value", {})
        translation = last_transform.get("Translation", {}).get("value", {})
        if "x" not in translation:
            return None
        return (
            float(translation.get("x", 0.0)),
            float(translation.get("y", 0.0)),
            float(translation.get("z", 0.0)),
        )
    except Exception:
        return None


def _count_pals_for_owner(level_dict: dict, owner_uid: str) -> int:
    """Count pal entries in CharacterSaveParameterMap owned by a player."""
    wsd = world_service.get_world_save_data(level_dict)
    owner_norm = owner_uid.replace("-", "").lower()
    count = 0
    for ch in world_service._map_values(wsd, "CharacterSaveParameterMap"):
        if not world_service._is_pal_entry(ch):
            continue
        try:
            key = ch.get("key", {})
            if isinstance(key, dict):
                player_uid = str(key.get("PlayerUId", ""))
            else:
                player_uid = ""
        except Exception:
            player_uid = ""
        if player_uid.replace("-", "").lower() == owner_norm:
            count += 1
    return count


def list_map_players(level_dict: dict, players_dir: str | None) -> list[dict]:
    """Build the enriched player list with pre-computed pixel coordinates.

    Players are ALWAYS included in the list (for the sidebar), even when their
    position can't be read (e.g. drag-drop upload where Players/ isn't
    accessible). Players without positions get null projections and simply
    won't appear as map markers — the frontend's makePlayerMarker returns null
    for null world_img/tree_img.
    """
    base_players = world_service.list_players(level_dict)
    if not base_players:
        return []

    real_dir: Path | None = None
    if players_dir and Path(players_dir).is_dir():
        real_dir = Path(players_dir)

    out: list[dict] = []
    for p in base_players:
        uid = p["uid"]
        uid_clean = uid.replace("-", "").upper()
        location: tuple[float, float, float] | None = None
        if real_dir is not None:
            sav_path = real_dir / f"{uid_clean}.sav"
            if sav_path.is_file():
                location = _read_player_position(sav_path)

        pal_count = _count_pals_for_owner(level_dict, uid)

        if location is not None:
            raw_x, raw_y, raw_z = location
            map_type = _classify_map_type(raw_x, raw_y)
            out.append({
                "uid": uid,
                "name": p["name"],
                "level": 0,
                "guild_id": p["guild_id"],
                "guild_name": p["guild_name"] or "",
                "last_seen_text": p["last_seen_text"] or "Unknown",
                "pal_count": pal_count,
                "location": [raw_x, raw_y, raw_z],
                "map_type": map_type,
                "world_img": _project_world(raw_x, raw_y),
                "tree_img": _project_tree(raw_x, raw_y),
            })
        else:
            # No position data (e.g. drag-drop upload) — still include in list
            # so the sidebar can show them. They just won't appear as markers.
            out.append({
                "uid": uid,
                "name": p["name"],
                "level": 0,
                "guild_id": p["guild_id"],
                "guild_name": p["guild_name"] or "",
                "last_seen_text": p["last_seen_text"] or "Unknown",
                "pal_count": pal_count,
                "location": None,
                "map_type": "world",
                "world_img": None,
                "tree_img": None,
            })
    return out


def get_map_data(level_dict: dict, players_dir: str | None) -> dict:
    """Build the full map data payload for ``GET /api/map/data``."""
    return {
        "bases": list_map_bases(level_dict),
        "players": list_map_players(level_dict, players_dir),
        "map_size": MAP_SIZE,
        "world_coord_range": WORLD_COORD_RANGE,
        "tree_coord_range": TREE_COORD_RANGE,
    }
