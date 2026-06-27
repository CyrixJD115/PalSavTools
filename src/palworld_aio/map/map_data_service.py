"""Pure-Python map data service — zero PySide6 imports.

Extracted from ``palworld_aio/ui/tabs/map_tab.py`` for headless reuse
(web backend, CLI, testing). All coordinate math delegates to the real
``coord`` module.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

try:
    import coord as palworld_coord
except ImportError:
    import importlib.util as _iu
    _repo = Path(__file__).resolve().parents[2]
    _spec = _iu.spec_from_file_location("coord", _repo / "coord" / "__init__.py")
    assert _spec is not None and _spec.loader is not None, "coord not found"
    palworld_coord = _iu.module_from_spec(_spec)
    _spec.loader.exec_module(palworld_coord)

try:
    from palworld_aio.inventory.container_ownership import ContainerOwnership
except ImportError:
    import importlib.util as _iu
    _repo = Path(__file__).resolve().parents[2]
    _spec = _iu.spec_from_file_location(
        "palworld_aio.inventory.container_ownership",
        _repo / "palworld_aio" / "inventory" / "container_ownership.py",
    )
    assert _spec is not None and _spec.loader is not None, "container_ownership not found"
    _mod = _iu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ContainerOwnership = _mod.ContainerOwnership

logger = logging.getLogger(__name__)

MAP_SIZE = 2048
WORLD_COORD_RANGE = 1000
TREE_COORD_RANGE = palworld_coord.get_treemap_coord_range()


# ── config ───────────────────────────────────────────────────────────────────

def load_map_config() -> dict:
    return {
        "marker": {
            "type": "icon",
            "dot": {
                "size": 24, "color": [255, 0, 0],
                "border_width": 3, "border_color": [180, 0, 0],
                "size_min": 24, "size_max": 24,
                "dynamic_sizing": False, "dynamic_sizing_formula": "sqrt",
            },
            "icon": {
                "path": "baseicon.webp",
                "size_min": 32, "size_max": 64, "base_size": 48,
                "dynamic_sizing": True, "dynamic_sizing_formula": "sqrt",
            },
        },
        "glow": {
            "enabled": True,
            "color": [59, 142, 208],
            "selected_alpha_min": 80, "selected_alpha_max": 180,
            "animation_speed": 8, "hover_alpha": 80,
            "radius_multiplier": 1.5,
        },
        "zoom": {
            "factor": 1.15, "min": 1.0, "max": 30.0,
            "double_click_target": 26.0,
            "animation_speed": 0.2, "animation_fps": 60,
        },
        "effects": {
            "delete": {
                "enabled": True, "duration": 1000, "max_radius": 150,
                "colors": {
                    "outer": [255, 80, 80], "inner": [255, 150, 0],
                    "flash": [255, 200, 0],
                },
            },
            "import": {
                "enabled": True, "duration": 1000, "pulse_count": 3,
                "color": [0, 255, 150], "sparkle_color": [100, 255, 200],
            },
            "export": {
                "enabled": True, "duration": 1000, "color": [100, 200, 255],
            },
        },
    }


# ── low-level save access (world_service equivalents, no PySide6) ────────────

def _get_wsd(level_dict: dict) -> dict:
    return (
        level_dict.get("properties", {})
        .get("worldSaveData", {})
        .get("value", {})
    )


def _map_values(wsd: dict, key: str) -> list[dict]:
    node = wsd.get(key, {})
    if isinstance(node, dict):
        return node.get("value", []) or []
    return []


def _get_tick(wsd: dict) -> int:
    try:
        return int(
            wsd["GameTimeSaveData"]["value"]["RealDateTimeTicks"]["value"]
        )
    except Exception:
        return 0


def _pal_field(sp: dict, key: str) -> Any:
    node = sp.get(key)
    if node is None:
        return None
    if isinstance(node, dict):
        if "value" in node:
            inner = node["value"]
            if isinstance(inner, dict) and "value" in inner and "type" in inner:
                return inner["value"]
            return inner
        return node
    return node


# ── coordinate math ──────────────────────────────────────────────────────────

def world_to_image(
    x_world: float, y_world: float,
    width: int = MAP_SIZE, height: int = MAP_SIZE,
    coord_range: int = WORLD_COORD_RANGE,
) -> tuple[int, int]:
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


def scene_to_world(
    scene_x: float, scene_y: float,
    map_width: int = MAP_SIZE, map_height: int = MAP_SIZE,
    coord_range: int = WORLD_COORD_RANGE,
) -> tuple[float, float]:
    """Inverse of world_to_image — scene pixels → world coords."""
    world_x = scene_x / map_width * (coord_range * 2) - coord_range
    world_y = coord_range - scene_y / map_height * (coord_range * 2)
    return world_x, world_y


def project_world(
    raw_x: float, raw_y: float,
    map_size: int = MAP_SIZE,
) -> dict | None:
    """Project save coords onto the world map. None if off-map."""
    pt = palworld_coord.sav_to_map(raw_x, raw_y, new=True)
    if abs(pt.x) > WORLD_COORD_RANGE or abs(pt.y) > WORLD_COORD_RANGE:
        return None
    img_x, img_y = world_to_image(pt.x, pt.y, map_size, map_size, WORLD_COORD_RANGE)
    return {"x": img_x, "y": img_y, "world_x": pt.x, "world_y": pt.y}


def project_tree(
    raw_x: float, raw_y: float,
    map_size: int = MAP_SIZE,
) -> dict | None:
    """Project save coords onto the tree map. None if off-map."""
    pt = palworld_coord.sav_to_treemap(raw_x, raw_y)
    if abs(pt.x) > TREE_COORD_RANGE or abs(pt.y) > TREE_COORD_RANGE:
        return None
    img_x, img_y = palworld_coord.treemap_to_pixel(pt.x, pt.y, map_size, map_size)
    return {"x": img_x, "y": img_y, "world_x": pt.x, "world_y": pt.y}


def classify_map_type(raw_x: float, raw_y: float) -> str:
    """Decide whether an entity belongs on the world or tree map."""
    pt = palworld_coord.sav_to_map(raw_x, raw_y, new=True)
    if abs(pt.x) > WORLD_COORD_RANGE or abs(pt.y) > WORLD_COORD_RANGE:
        pt2 = palworld_coord.sav_to_treemap(raw_x, raw_y)
        if abs(pt2.x) <= TREE_COORD_RANGE and abs(pt2.y) <= TREE_COORD_RANGE:
            return "tree"
    return "world"


# ── last-seen formatting ─────────────────────────────────────────────────────

def format_last_seen(elapsed_s: float | None) -> str:
    """Format seconds elapsed as "5d 3h" style string."""
    if elapsed_s is None:
        return "Unknown"
    if elapsed_s < 0:
        return "Unknown"
    days = int(elapsed_s // 86400)
    hours = int(elapsed_s % 86400 // 3600)
    mins = int(elapsed_s % 3600 // 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


# ── base radius ──────────────────────────────────────────────────────────────

def get_base_radius(base_data: dict) -> float:
    """Extract area_range from a base entry. Default 3500.0."""
    try:
        base_entry = base_data.get("data", {})
        if not base_entry:
            raw_data = base_data
        else:
            raw_data = base_entry.get("value", {}).get("RawData", {}).get("value", {})
        return float(raw_data.get("area_range", 3500.0))
    except Exception:
        return 3500.0


# ── guild / base data (flat list, matches web backend schema) ────────────────

def list_map_bases(level_dict: dict) -> list[dict]:
    """Build enriched base list with pre-computed pixel coordinates.

    Mirrors MapTab._get_guild_bases but returns a flat list of base dicts
    (matching ``web/backend/services/map_service.py::list_map_bases``).
    """
    wsd = _get_wsd(level_dict)
    group_map = _map_values(wsd, "GroupSaveDataMap")
    base_map = {
        str(b["key"]).replace("-", ""): b["value"]
        for b in _map_values(wsd, "BaseCampSaveData")
    }
    tick = _get_tick(wsd)

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

        leader_name = None
        for p in players:
            if str(p.get("player_uid", "")) == admin_uid:
                leader_name = p.get("player_info", {}).get("player_name", admin_uid)
                break
        if not leader_name and players:
            leader_name = players[0].get("player_info", {}).get("player_name", admin_uid)
        if not leader_name:
            leader_name = admin_uid or "Unknown"

        times = [
            p.get("player_info", {}).get("last_online_real_time")
            for p in players
            if p.get("player_info", {}).get("last_online_real_time")
        ]
        last_seen = (
            format_last_seen((tick - max(times)) / 10_000_000.0)
            if times and tick
            else "Unknown"
        )

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

            area_range = get_base_radius({
                "data": {"value": {"RawData": {"value": base_val}}},
            })
            map_type = classify_map_type(raw_x, raw_y)

            out.append({
                "id": str(bid),
                "guild_id": gid,
                "guild_name": guild_name,
                "guild_level": guild_level,
                "leader_name": leader_name,
                "member_count": member_count,
                "total_bases": total_bases,
                "base_position": base_position,
                "last_seen": last_seen,
                "location": [raw_x, raw_y, raw_z],
                "area_range": area_range,
                "map_type": map_type,
                "world_img": project_world(raw_x, raw_y),
                "tree_img": project_tree(raw_x, raw_y),
                "raw": base_val,
            })
            base_position += 1

    return out


# ── guild / base data (nested by guild, matches PySide6 MapTab format) ───────

def list_map_guilds(
    level_dict: dict,
    map_width: int = MAP_SIZE,
    map_height: int = MAP_SIZE,
) -> dict:
    """Build nested guild -> bases dict, matching MapTab._get_guild_bases output.

    Returns ``{guild_id: {guild_name, leader_name, last_seen, bases: [...]}}``.
    Each base entry includes ``data`` with the raw base camp entry for mutation.
    ``map_width`` / ``map_height`` control image coordinate projection.
    """
    wsd = _get_wsd(level_dict)
    group_map = _map_values(wsd, "GroupSaveDataMap")
    base_map = {
        str(b["key"]).replace("-", ""): b["value"]
        for b in _map_values(wsd, "BaseCampSaveData")
    }
    tick = _get_tick(wsd)

    guilds: dict[str, dict] = {}
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
        guild_name = raw.get("guild_name", "Unknown Guild")
        guild_level = raw.get("base_camp_level", 1)
        players = raw.get("players", []) or []
        member_count = len(players)
        base_ids = raw.get("base_ids", []) or []
        total_bases = len(base_ids)

        leader_name = None
        for p in players:
            if str(p.get("player_uid", "")) == admin_uid:
                leader_name = p.get("player_info", {}).get("player_name", admin_uid)
                break
        if not leader_name and players:
            leader_name = players[0].get("player_info", {}).get("player_name", admin_uid)
        if not leader_name:
            leader_name = admin_uid or "Unknown"

        times = [
            p.get("player_info", {}).get("last_online_real_time")
            for p in players
            if p.get("player_info", {}).get("last_online_real_time")
        ]
        last_seen = (
            format_last_seen((tick - max(times)) / 10_000_000.0)
            if times and tick
            else "Unknown"
        )

        valid_bases: list[dict] = []
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

                pt_new = palworld_coord.sav_to_map(raw_x, raw_y, new=True)
                bx_new, by_new = pt_new.x, pt_new.y
                if bx_new is None:
                    continue

                pt_old = palworld_coord.sav_to_map(raw_x, raw_y, new=False)
                bx_old, by_old = pt_old.x, pt_old.y
                img_x, img_y = world_to_image(bx_new, by_new, map_width, map_height)

                map_type = classify_map_type(raw_x, raw_y)

                valid_bases.append({
                    "base_id": bid,
                    "coords": (bx_old, by_old),
                    "map_coords": (bx_new, by_new),
                    "img_coords": (img_x, img_y),
                    "z": raw_z,
                    "map_type": map_type,
                    "raw_x": raw_x,
                    "raw_y": raw_y,
                    "data": {"key": bid, "value": base_val},
                    "guild_id": gid,
                    "guild_name": guild_name,
                    "leader_name": leader_name,
                    "guild_level": guild_level,
                    "member_count": member_count,
                    "total_bases": total_bases,
                    "base_position": base_position,
                })
                base_position += 1
            except Exception:
                continue

        guilds[gid] = {
            "guild_name": guild_name,
            "leader_name": leader_name,
            "last_seen": last_seen,
            "bases": valid_bases,
        }

    return guilds


# ── player data ──────────────────────────────────────────────────────────────

def _list_base_players(level_dict: dict) -> list[tuple]:
    """Extract player tuples from guild data (no .sav reads).

    Mirrors ``save_manager.get_players()`` output::
        (uid, name, guild_id, last_seen_text, level_or_unknown, elapsed_or_none)

    Level is looked up from the provided ``player_levels`` dict (pre-computed).
    Returns empty list if no data.
    """
    wsd = _get_wsd(level_dict)
    tick = _get_tick(wsd)
    out: list[tuple] = []
    for g in _map_values(wsd, "GroupSaveDataMap"):
        try:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        gid = str(g["key"])
        players = g["value"]["RawData"]["value"].get("players", [])
        for p in players:
            uid_raw = p.get("player_uid")
            uid = str(uid_raw) if uid_raw is not None else ""
            name = p.get("player_info", {}).get("player_name", "Unknown")
            last = p.get("player_info", {}).get("last_online_real_time")
            elapsed = None if last is None else (tick - last) / 10_000_000.0
            last_seen = format_last_seen(elapsed)
            out.append((uid, name, gid, last_seen, elapsed))
    return out


def list_map_players(
    level_dict: dict,
    players_dir: str | Path | None = None,
    pal_counts: dict[str, int] | None = None,
    player_levels: dict[str, int] | None = None,
    positions: dict[str, tuple[float, float, float]] | None = None,
    map_width: int = MAP_SIZE,
    map_height: int = MAP_SIZE,
) -> list[dict]:
    """Build enriched player list with pre-computed pixel coordinates.

    Mirrors ``MapTab._get_players()``. Players are ALWAYS included in the
    output (for sidebar), even without position data. When ``players_dir`` is
    available, reads individual ``.sav`` files for precise positions. Falls
    back to ``positions`` (``LastJumpedLocation`` from Level.sav).

    ``pal_counts``, ``player_levels``, and ``positions`` should be pre-computed
    by :func:`precompute_player_data`. ``map_width`` / ``map_height`` control
    image coordinate projection.
    """
    base_players = _list_base_players(level_dict)
    if not base_players:
        return []

    real_dir: Path | None = None
    if players_dir:
        pd = Path(players_dir)
        if pd.is_dir():
            real_dir = pd

    from palworld_aio.utils import sav_to_gvasfile

    out: list[dict] = []
    for uid, name, gid, last_seen, _ in base_players:
        uid_clean = uid.replace("-", "").upper()
        if not uid_clean:
            continue

        location: tuple[float, float, float] | None = None
        if real_dir is not None:
            sav_path = real_dir / f"{uid_clean}.sav"
            if sav_path.is_file():
                try:
                    gvas = sav_to_gvasfile(str(sav_path))
                    save_data = gvas.properties.get("SaveData", {}).get("value", {})
                    last_transform = save_data.get("LastTransform", {}).get("value", {})
                    translation = last_transform.get("Translation", {}).get("value", {})
                    if translation and "x" in translation:
                        location = (
                            float(translation.get("x", 0.0)),
                            float(translation.get("y", 0.0)),
                            float(translation.get("z", 0.0)),
                        )
                except Exception:
                    pass

        if location is None and positions:
            location = positions.get(uid_clean.lower())

        pal_count = (pal_counts or {}).get(uid_clean.lower(), 0)
        level = (player_levels or {}).get(uid_clean.lower(), "?")
        guild_name = ""
        for g in _map_values(_get_wsd(level_dict), "GroupSaveDataMap"):
            try:
                if str(g.get("key", "")) == gid:
                    guild_name = g["value"]["RawData"]["value"].get("guild_name", "")
                    break
            except Exception:
                pass

        if location is not None:
            raw_x, raw_y, raw_z = location
            map_type = classify_map_type(raw_x, raw_y)

            if map_type == "tree":
                pt = palworld_coord.sav_to_treemap(raw_x, raw_y)
                bx, by = pt.x, pt.y
                img_x, img_y = palworld_coord.treemap_to_pixel(bx, by, map_width, map_height)
            else:
                pt = palworld_coord.sav_to_map(raw_x, raw_y, new=True)
                bx, by = pt.x, pt.y
                img_x, img_y = world_to_image(bx, by, map_width, map_height)

            out.append({
                "player_uid": uid_clean,
                "player_name": name,
                "level": level,
                "coords": (bx, by),
                "img_coords": (img_x, img_y),
                "map_type": map_type,
                "save_coords": (raw_x, raw_y, raw_z),
                "guild_name": guild_name,
                "guild_id": gid,
                "last_seen": last_seen,
                "pal_count": pal_count,
            })
        else:
            out.append({
                "player_uid": uid_clean,
                "player_name": name,
                "level": level,
                "coords": None,
                "img_coords": None,
                "map_type": "world",
                "save_coords": None,
                "guild_name": guild_name,
                "guild_id": gid,
                "last_seen": last_seen,
                "pal_count": pal_count,
            })

    return out


# ── precompute player data (pal counts, levels, fallback positions) ──────────

def precompute_player_data(
    level_dict: dict,
) -> tuple[dict[str, int], dict[str, int], dict[str, tuple[float, float, float]]]:
    """Pre-compute pal counts, player levels, and fallback positions.

    Mirrors ``save_manager._build_player_levels`` + ``save_manager._count_pals_found``
    + ``MapTab._get_players`` fallback extraction. Uses ``ContainerOwnership``
    for worker-pal resolution (same as desktop app).
    """
    wsd = _get_wsd(level_dict)
    cmap = _map_values(wsd, "CharacterSaveParameterMap")
    container_data = _map_values(wsd, "CharacterContainerSaveData")
    ownership = ContainerOwnership.build(cmap, container_data)

    player_pal_counts: dict[str, int] = {}
    player_levels: dict[str, int] = {}
    player_positions: dict[str, tuple[float, float, float]] = {}

    for entry in cmap:
        try:
            raw_obj = (
                entry["value"]["RawData"]["value"]["object"]["SaveParameter"]
            )
            if raw_obj.get("struct_type") != "PalIndividualCharacterSaveParameter":
                continue
            sp = raw_obj.get("value", {})
            if not isinstance(sp, dict):
                continue
        except Exception:
            continue

        key = entry.get("key", {})

        def _unwrap(v):
            if isinstance(v, dict) and "value" in v:
                return v["value"]
            return v

        player_uid_raw = _unwrap(key.get("PlayerUId", ""))
        inst_raw = _unwrap(key.get("InstanceId", ""))
        player_uid = str(player_uid_raw).replace("-", "").lower() if player_uid_raw else ""
        inst_id = str(inst_raw) if inst_raw else ""

        if sp.get("IsPlayer", {}).get("value", False):
            level_raw = _pal_field(sp, "Level")
            try:
                level = int(level_raw) if level_raw is not None else 0
            except (ValueError, TypeError):
                level = 0
            if player_uid:
                player_levels[player_uid] = level

            ljl_raw = sp.get("LastJumpedLocation", {}).get("value", {})
            if isinstance(ljl_raw, dict) and "x" in ljl_raw:
                try:
                    player_positions[player_uid] = (
                        float(ljl_raw["x"]),
                        float(ljl_raw["y"]),
                        float(ljl_raw.get("z", 0.0)),
                    )
                except (ValueError, TypeError):
                    pass
            continue

        owner_val = _pal_field(sp, "OwnerPlayerUId")
        owner_uid = str(owner_val).replace("-", "").lower() if owner_val else ""

        is_worker = not owner_uid
        if is_worker:
            effective = ownership.get_effective_owner(inst_id, "")
            if effective:
                owner_uid = effective
                is_worker = False

        if not is_worker and owner_uid:
            player_pal_counts[owner_uid] = player_pal_counts.get(owner_uid, 0) + 1

    return player_pal_counts, player_levels, player_positions


# ── search / filter ──────────────────────────────────────────────────────────

def filter_players(search_text: str, players_data: list[dict]) -> list[dict]:
    """Filter player list by search terms (name, level, last_seen, guild, coords)."""
    if not search_text:
        return players_data
    terms = search_text.lower().split()
    filtered = []
    for player in players_data:
        pn = player["player_name"].lower()
        pl = str(player["level"]).lower()
        ls = player["last_seen"].lower()
        gn = player["guild_name"].lower()
        coords = player.get("coords")
        coords_str = ""
        if coords:
            coords_str = f"x:{int(coords[0])},y:{int(coords[1])}"
        fields = [pn, pl, ls, gn, coords_str]
        if all(any(term in field for field in fields) for term in terms):
            filtered.append(player)
    return filtered


def search_guild_bases(
    search_text: str, guilds_data: dict,
) -> dict:
    """Filter guild -> bases dict by search terms."""
    if not search_text:
        return guilds_data
    terms = search_text.lower().split()
    filtered = {}
    for gid, guild in guilds_data.items():
        gn = guild["guild_name"].lower()
        ln = guild["leader_name"].lower()
        ls = guild["last_seen"].lower()
        guild_matches = all(
            any(term in field for field in [gn, ln, ls])
            for term in terms
        )
        matching_bases = [
            b for b in guild["bases"]
            if all(
                any(
                    term in field
                    for field in [
                        str(b["base_id"]).lower(),
                        f"x:{int(b['coords'][0])},y:{int(b['coords'][1])}",
                        gn, ln, ls,
                    ]
                )
                for term in terms
            )
        ]
        if guild_matches or matching_bases:
            filtered[gid] = dict(guild)
            if not guild_matches:
                filtered[gid]["bases"] = matching_bases
    return filtered


# ── recalculation ────────────────────────────────────────────────────────────

def recalc_img_coords(
    guilds_data: dict,
    players_data: list[dict],
    current_map: str,
    map_width: int = MAP_SIZE,
    map_height: int = MAP_SIZE,
) -> None:
    """Recalculate img_coords for all bases and players (in-place).

    Mirrors MapTab._recalc_img_coords. Mutates the provided dicts/lists.
    """
    is_tree = current_map == "tree"
    coord_range = TREE_COORD_RANGE if is_tree else WORLD_COORD_RANGE

    for guild in guilds_data.values():
        for base in guild["bases"]:
            base_map = base.get("map_type", "world")
            if "raw_x" not in base or (base_map == "tree") != is_tree:
                continue
            if is_tree:
                ix, iy = palworld_coord.treemap_to_pixel(
                    base["map_coords"][0], base["map_coords"][1],
                    map_width, map_height,
                )
            else:
                ix, iy = world_to_image(
                    base["map_coords"][0], base["map_coords"][1],
                    map_width, map_height, coord_range,
                )
            base["img_coords"] = (ix, iy)

    for player in players_data:
        player_map = player.get("map_type", "world")
        if (player_map == "tree") != is_tree:
            continue
        if is_tree:
            ix, iy = palworld_coord.treemap_to_pixel(
                player["coords"][0], player["coords"][1],
                map_width, map_height,
            )
        else:
            ix, iy = world_to_image(
                player["coords"][0], player["coords"][1],
                map_width, map_height, coord_range,
            )
        player["img_coords"] = (ix, iy)


# ── calibration ──────────────────────────────────────────────────────────────

def compute_calibration(
    points: list[tuple[float, float, float, float]],
    map_width: int = MAP_SIZE,
    map_height: int = MAP_SIZE,
) -> tuple[float, float, float]:
    """Compute world-map calibration transform from user-defined control points.

    Each point is ``(raw_x, raw_y, scene_x, scene_y)``. Returns
    ``(scale, transl_x, transl_y)``.
    """
    W = float(map_width) if map_width > 0 else 8192.0
    H = float(map_height) if map_height > 0 else 8192.0

    if len(points) == 1:
        s = 706.0
        rx, ry, px, py = points[0]
        wx = px * 2000.0 / W - 1000.0
        wy = 1000.0 - py * 2000.0 / H
        ty = ry - wx * s
        tx = wy * s - rx
    elif len(points) > 1:
        n = float(len(points))
        sum_wx, sum_wy, sum_rx, sum_ry = 0.0, 0.0, 0.0, 0.0
        sum_wx2, sum_wy2, sum_wx_ry, sum_wy_rx = 0.0, 0.0, 0.0, 0.0
        for rx, ry, px, py in points:
            wx = px * 2000.0 / W - 1000.0
            wy = 1000.0 - py * 2000.0 / H
            sum_wx += wx
            sum_wy += wy
            sum_rx += rx
            sum_ry += ry
            sum_wx2 += wx * wx
            sum_wy2 += wy * wy
            sum_wx_ry += wx * ry
            sum_wy_rx += wy * rx
        denom_y = n * sum_wx2 - sum_wx * sum_wx
        denom_x = n * sum_wy2 - sum_wy * sum_wy
        if denom_y != 0.0:
            s1 = (n * sum_wx_ry - sum_wx * sum_ry) / denom_y
        else:
            s1 = sum_ry / n if n > 0 else 0.0
        if denom_x != 0.0:
            s2 = (n * sum_wy_rx - sum_wy * sum_rx) / denom_x
        else:
            s2 = sum_rx / n if n > 0 else 0.0
        s = (s1 + s2) / 2.0
        ty_sum, tx_sum = 0.0, 0.0
        for rx, ry, px, py in points:
            wx = px * 2000.0 / W - 1000.0
            wy = 1000.0 - py * 2000.0 / H
            ty_sum += ry - wx * s
            tx_sum += wy * s - rx
        ty = ty_sum / n
        tx = tx_sum / n
    else:
        s, tx, ty = 706.0, 0.0, 0.0

    return s, tx, ty


def compute_tree_calibration(
    points: list[tuple[float, float, float, float]],
    map_width: int = MAP_SIZE,
    map_height: int = MAP_SIZE,
) -> tuple[float, float, float]:
    """Compute tree-map calibration transform from user-defined control points.

    Each point is ``(raw_x, raw_y, scene_x, scene_y)``. Returns
    ``(scale, transl_x, transl_y)``.
    """
    w = map_width if map_width > 0 else 8192
    h = map_height if map_height > 0 else 8192
    W = float(w)
    H = float(h)

    if len(points) == 1:
        s = 724.0
        rx, ry, px, py = points[0]
        wx, wy = palworld_coord.treemap_pixel_to_cursor(px, py, w, h)
        ty = ry - wx * s
        tx = wy * s - rx
    elif len(points) > 1:
        n = float(len(points))
        sum_wx, sum_wy, sum_rx, sum_ry = 0.0, 0.0, 0.0, 0.0
        sum_wx2, sum_wy2, sum_wx_ry, sum_wy_rx = 0.0, 0.0, 0.0, 0.0
        for rx, ry, px, py in points:
            wx, wy = palworld_coord.treemap_pixel_to_cursor(px, py, w, h)
            sum_wx += wx
            sum_wy += wy
            sum_rx += rx
            sum_ry += ry
            sum_wx2 += wx * wx
            sum_wy2 += wy * wy
            sum_wx_ry += wx * ry
            sum_wy_rx += wy * rx
        denom_y = n * sum_wx2 - sum_wx * sum_wx
        denom_x = n * sum_wy2 - sum_wy * sum_wy
        s1 = (
            (n * sum_wx_ry - sum_wx * sum_ry) / denom_y
            if denom_y != 0.0
            else (sum_ry / n if n > 0 else 0.0)
        )
        s2 = (
            (n * sum_wy_rx - sum_wy * sum_rx) / denom_x
            if denom_x != 0.0
            else (sum_rx / n if n > 0 else 0.0)
        )
        s = (s1 + s2) / 2.0
        ty_sum, tx_sum = 0.0, 0.0
        for rx, ry, px, py in points:
            wx, wy = palworld_coord.treemap_pixel_to_cursor(px, py, w, h)
            ty_sum += ry - wx * s
            tx_sum += wy * s - rx
        ty = ty_sum / n
        tx = tx_sum / n
    else:
        s, tx, ty = 724.0, 0.0, 0.0

    return s, tx, ty


def apply_calibration(
    s: float, tx: float, ty: float,
    calibration_type: str = "world",
) -> None:
    """Write calibration values directly into ``palworld_coord.__init__.py``.

    Mirrors the file-patching logic in MapTab._compute_calibration /
    _compute_tree_calibration.
    """
    coord_path = os.path.join(os.path.dirname(palworld_coord.__file__), "__init__.py")
    with open(coord_path, "r", encoding="utf-8") as f:
        content = f.read()

    if calibration_type == "tree":
        content = re.sub(
            r"__treemap_transl_x = -?\d+",
            f"__treemap_transl_x = {round(tx)}",
            content,
        )
        content = re.sub(
            r"__treemap_transl_y = -?\d+",
            f"__treemap_transl_y = {round(ty)}",
            content,
        )
        content = re.sub(
            r"__treemap_scale = \d+",
            f"__treemap_scale = {round(s)}",
            content,
        )
    else:
        content = re.sub(
            r"__transl_x_new = -?\d+",
            f"__transl_x_new = {round(tx)}",
            content,
        )
        content = re.sub(
            r"__transl_y_new = -?\d+",
            f"__transl_y_new = {round(ty)}",
            content,
        )
        content = re.sub(
            r"__scale_new = \d+",
            f"__scale_new = {round(s)}",
            content,
        )

    with open(coord_path, "w", encoding="utf-8") as f:
        f.write(content)
