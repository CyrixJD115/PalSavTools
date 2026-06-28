"""Base mutation operations for the web backend.

Adapts logic from ``data_manager``, ``guild_manager``, and ``base_manager``
but operates on ``level_dict`` (from ``save_state``) instead of
``constants.loaded_level_json``.
"""

from __future__ import annotations

from web.backend.services.world_service import (
    _fmt_last_seen, _gplayers, _group_type,
    get_tick, get_world_save_data, _map_values,
)


def _extract_id(raw: object) -> str:
    """Extract a clean UUID string from any format the save data uses."""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        id_field = raw.get("ID")
        if isinstance(id_field, dict):
            v = id_field.get("value")
            if v is not None:
                return str(v)
        v = raw.get("value")
        if v is not None:
            return str(v)
        return ""
    return str(raw)


def _s(uid: str | dict | None) -> str:
    return _extract_id(uid).replace("-", "").lower()


def _find_base_entry(level_dict: dict, base_id: str) -> dict | None:
    wsd = get_world_save_data(level_dict)
    bid_clean = _s(base_id)
    for b in _map_values(wsd, "BaseCampSaveData"):
        if _s(b.get("key")) == bid_clean:
            return b
    return None


def _find_guild_by_base(level_dict: dict, base_id: str) -> dict | None:
    """Find the guild entry that owns a base, and the base entry."""
    wsd = get_world_save_data(level_dict)
    bid_clean = _s(base_id)
    for g in _map_values(wsd, "GroupSaveDataMap"):
        try:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        raw = g.get("value", {}).get("RawData", {}).get("value", {})
        for bid in raw.get("base_ids", []):
            if _s(bid) == bid_clean:
                return g
    return None


# ---- Public API --------------------------------------------------------------


def get_base_detail(level_dict: dict, base_id: str) -> dict | None:
    """Get enriched detail for a single base."""
    wsd = get_world_save_data(level_dict)
    base_entry = _find_base_entry(level_dict, base_id)
    if base_entry is None:
        return None

    try:
        raw = base_entry["value"]["RawData"]["value"]
    except Exception:
        raw = {}

    try:
        trans = raw.get("transform", {}).get("translation", {})
        location = (float(trans["x"]), float(trans["y"]), float(trans.get("z", 0)))
    except Exception:
        location = None

    area_range = float(raw.get("area_range", 3500.0))

    guild_id = raw.get("group_id_belong_to")
    guild_id = str(guild_id) if guild_id else None
    guild_name = None
    guild_level = 1
    leader_name = None
    member_count = 0
    total_bases = 0
    base_position = 1

    guild_entry = _find_guild_by_base(level_dict, base_id)
    if guild_entry:
        try:
            g_raw = guild_entry["value"]["RawData"]["value"]
            guild_name = g_raw.get("guild_name", "Unnamed Guild")
            guild_level = int(g_raw.get("base_camp_level", 1))
            players = g_raw.get("players", [])
            member_count = len(players)
            base_ids = g_raw.get("base_ids", [])
            total_bases = len(base_ids)

            admin_uid = str(g_raw.get("admin_player_uid", ""))
            for p in players:
                if str(p.get("player_uid", "")) == admin_uid:
                    leader_name = p.get("player_info", {}).get("player_name", admin_uid)
                    break
            if not leader_name and players:
                leader_name = players[0].get("player_info", {}).get("player_name", admin_uid)

            # Find position
            for i, bid in enumerate(base_ids):
                if _s(bid) == _s(base_id):
                    base_position = i + 1
                    break
        except Exception:
            pass

    return {
        "id": str(raw.get("id", base_entry.get("key", base_id))),
        "guild_id": guild_id,
        "guild_name": guild_name,
        "guild_level": guild_level,
        "leader_name": leader_name,
        "member_count": member_count,
        "total_bases": total_bases,
        "base_position": base_position,
        "location": location,
        "area_range": area_range,
        "worker_count": 0,
    }


def delete_base(level_dict: dict, base_id: str, delete_workers: bool = False) -> bool:
    """Delete a base camp from the world save data.

    Adapted from ``data_manager.delete_base_camp`` — removes the base entry,
    associated map objects, containers, work entries, and optionally workers.
    """
    from palsav.archive import UUID

    wsd = get_world_save_data(level_dict)
    base_entry = _find_base_entry(level_dict, base_id)
    if base_entry is None:
        return False

    base_list = wsd.get("BaseCampSaveData", {}).get("value", [])
    group_map = wsd.get("GroupSaveDataMap", {}).get("value", [])
    containers_char = wsd.get("CharacterContainerSaveData", {}).get("value", [])
    containers_item = wsd.get("ItemContainerSaveData", {}).get("value", [])
    map_objs = wsd.get("MapObjectSaveData", {}).get("value", {}).get("values", [])
    work_root = wsd.get("WorkSaveData", {})
    work_entries = work_root.get("value", {}).get("values", []) if isinstance(work_root.get("value"), dict) else []
    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])

    base_id_str = str(base_entry["key"])
    base_id_low = _s(base_id_str)

    worker_cont_id = None
    try:
        worker_cont_id = _s(base_entry["value"]["WorkerDirector"]["value"]["RawData"]["value"]["container_id"])
    except Exception:
        pass

    cont_ids_to_del = set()
    if worker_cont_id:
        cont_ids_to_del.add(worker_cont_id)

    for obj in map_objs:
        try:
            mr = obj["Model"]["value"]["RawData"]["value"]
            if _s(mr.get("base_camp_id_belong_to")) == base_id_low:
                mm = obj["ConcreteModel"]["value"]["ModuleMap"]["value"]
                for mod in mm:
                    try:
                        raw_mod = mod["value"]["RawData"]["value"]
                        if "target_container_id" in raw_mod:
                            cont_ids_to_del.add(_s(raw_mod["target_container_id"]))
                    except Exception:
                        pass
        except Exception:
            pass

    map_objs[:] = [
        obj for obj in map_objs
        if _s(obj.get("Model", {}).get("value", {}).get("RawData", {}).get("value", {}).get("base_camp_id_belong_to")) != base_id_low
    ]

    containers_item[:] = [
        c for c in containers_item
        if _s(c.get("key", {}).get("ID", {}).get("value")) not in cont_ids_to_del
    ]
    containers_char[:] = [
        c for c in containers_char
        if _s(c.get("key", {}).get("ID", {}).get("value")) not in cont_ids_to_del
    ]

    work_entries[:] = [
        we for we in work_entries
        if _s(we.get("RawData", {}).get("value", {}).get("base_camp_id_belong_to")) != base_id_low
    ]

    zero = UUID.from_str("00000000-0000-0000-0000-000000000000")

    if worker_cont_id:
        workers_to_remove = []
        for ch in char_map:
            try:
                raw = ch["value"]["RawData"]["value"]
                sp = raw["object"]["SaveParameter"]["value"]
                if sp.get("IsPlayer", {}).get("value"):
                    continue
                slot_id = sp.get("SlotId", {}).get("value", {}).get("ContainerId", {}).get("value", {}).get("ID", {}).get("value")
                if slot_id and _s(slot_id) == worker_cont_id:
                    if delete_workers:
                        workers_to_remove.append(ch)
                    else:
                        sp["SlotId"]["value"]["ContainerId"]["value"]["ID"]["value"] = zero
                        raw["group_id"] = zero
            except Exception:
                pass
        for ch in workers_to_remove:
            char_map.remove(ch)

    # Remove this base from its guild's base_ids list
    for g in group_map:
        try:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        g_raw = g.get("value", {}).get("RawData", {}).get("value", {})
        g_base_ids = g_raw.get("base_ids", [])
        g_raw["base_ids"] = [bid for bid in g_base_ids if _s(bid) != base_id_low]

    # Remove the base entry itself
    base_list[:] = [b for b in base_list if _s(b.get("key")) != base_id_low]

    return True


def rename_guild(level_dict: dict, guild_id: str, new_name: str) -> bool:
    """Rename a guild."""
    wsd = get_world_save_data(level_dict)
    gid_clean = _s(guild_id)
    for g in _map_values(wsd, "GroupSaveDataMap"):
        try:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        if _s(g.get("key")) == gid_clean:
            g["value"]["RawData"]["value"]["guild_name"] = new_name
            return True
    return False


def set_guild_level(level_dict: dict, guild_id: str, level: int) -> bool:
    """Set guild level (1-35)."""
    level = max(1, min(35, level))
    wsd = get_world_save_data(level_dict)
    gid_clean = _s(guild_id)
    for g in _map_values(wsd, "GroupSaveDataMap"):
        try:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        if _s(g.get("key")) == gid_clean:
            g["value"]["RawData"]["value"]["base_camp_level"] = level
            return True
    return False


def update_base_radius(level_dict: dict, base_id: str, new_radius: float) -> bool:
    """Update the area range (radius) of a base camp."""
    base_entry = _find_base_entry(level_dict, base_id)
    if base_entry is None:
        return False
    try:
        base_entry["value"]["RawData"]["value"]["area_range"] = float(new_radius)
        return True
    except Exception:
        return False


def get_enriched_base_list(level_dict: dict) -> list[dict]:
    """Build enriched base list with guild info, position, radius, leader.

    Mirrors ``map_data_service.list_map_bases`` but returns flat list
    matching the web API ``BaseSummary`` schema.
    """
    wsd = get_world_save_data(level_dict)
    base_map = {
        _s(b.get("key")): b["value"]
        for b in _map_values(wsd, "BaseCampSaveData")
        if _s(b.get("key"))
    }

    out: list[dict] = []
    for entry in _map_values(wsd, "GroupSaveDataMap"):
        try:
            if _group_type(entry) != "EPalGroupType::Guild":
                continue
        except Exception:
            continue

        g_val = entry["value"]
        raw = g_val.get("RawData", {}).get("value", {})
        admin_uid = _s(raw.get("admin_player_uid"))
        guild_name = raw.get("guild_name", "Unnamed Guild")
        guild_level = raw.get("base_camp_level", 1)
        players = raw.get("players", []) or []
        member_count = len(players)
        base_ids = raw.get("base_ids", []) or []
        total_bases = len(base_ids)

        leader_name = None
        for p in players:
            if _s(p.get("player_uid")) == admin_uid:
                leader_name = p.get("player_info", {}).get("player_name", admin_uid)
                break
        if not leader_name and players:
            leader_name = players[0].get("player_info", {}).get("player_name", admin_uid)
        if not leader_name:
            leader_name = admin_uid or "Unknown"

        base_position = 1
        for bid in base_ids:
            bid_str = _s(bid)
            if not bid_str or bid_str not in base_map:
                continue
            base_val = base_map[bid_str]
            try:
                trans = base_val["RawData"]["value"]["transform"]["translation"]
                raw_x = float(trans["x"])
                raw_y = float(trans["y"])
                raw_z = float(trans.get("z", 0.0))
            except Exception:
                continue

            area_range = float(base_val.get("RawData", {}).get("value", {}).get("area_range", 3500.0))

            out.append({
                "id": str(bid),
                "guild_id": str(entry.get("key", "")),
                "guild_name": guild_name,
                "guild_level": guild_level,
                "leader_name": leader_name,
                "member_count": member_count,
                "total_bases": total_bases,
                "base_position": base_position,
                "location": [raw_x, raw_y, raw_z],
                "area_range": area_range,
                "worker_count": 0,
            })
            base_position += 1

    return out
