"""Guild mutation operations for the web backend."""

from __future__ import annotations

from web.backend.services.world_service import (
    _gadmin, _gname, _gplayers, _group_type,
    get_tick, get_world_save_data, _map_values,
)
from web.backend.services.base_service import _s


def _find_guild(level_dict: dict, guild_id: str) -> dict | None:
    wsd = get_world_save_data(level_dict)
    gid_clean = _s(guild_id)
    for g in _map_values(wsd, "GroupSaveDataMap"):
        try:
            if _group_type(g) != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        if _s(g.get("key")) == gid_clean:
            return g
    return None


def get_guild_detail(level_dict: dict, guild_id: str) -> dict | None:
    """Get enriched guild detail with members, bases, etc."""
    wsd = get_world_save_data(level_dict)
    tick = get_tick(wsd)
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return None
    try:
        raw = g["value"]["RawData"]["value"]
    except Exception:
        raw = {}

    guild_name = raw.get("guild_name", "Unnamed Guild")
    guild_level = raw.get("base_camp_level", 1)
    admin_uid = _s(raw.get("admin_player_uid"))
    base_ids = raw.get("base_ids", []) or []
    players = raw.get("players", []) or []

    members = []
    for p in players:
        puid = p.get("player_uid")
        puid_str = str(puid) if puid else ""
        puid_clean = _s(puid)
        info = p.get("player_info") or {}
        last = info.get("last_online_real_time")
        elapsed = None
        if isinstance(last, (int, float)) and tick:
            elapsed = (tick - last) / 10_000_000.0

        members.append({
            "uid": puid_str,
            "name": info.get("player_name", "Unknown"),
            "is_leader": puid_clean == admin_uid,
            "_u8_flag": p.get("_u8_flag", 3),
            "last_seen_seconds": elapsed,
        })

    return {
        "id": str(g.get("key", guild_id)),
        "name": guild_name,
        "level": guild_level,
        "admin_uid": str(raw.get("admin_player_uid", "")),
        "member_count": len(members),
        "base_count": len(base_ids),
        "members": members,
        "base_ids": [str(b) for b in base_ids],
    }


def rename_guild(level_dict: dict, guild_id: str, new_name: str) -> bool:
    """Rename a guild."""
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    try:
        g["value"]["RawData"]["value"]["guild_name"] = new_name
        return True
    except Exception:
        return False


def set_guild_level(level_dict: dict, guild_id: str, level: int) -> bool:
    """Set guild level (1-35)."""
    level = max(1, min(35, level))
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    try:
        g["value"]["RawData"]["value"]["base_camp_level"] = level
        return True
    except Exception:
        return False


def make_member_leader(level_dict: dict, guild_id: str, player_uid: str) -> bool:
    """Promote a guild member to leader/admin."""
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    try:
        raw = g["value"]["RawData"]["value"]
        raw["admin_player_uid"] = player_uid
        pu_clean = _s(player_uid)
        for p in raw.get("players", []):
            p["_u8_flag"] = 1 if _s(p.get("player_uid")) == pu_clean else 3
        return True
    except Exception:
        return False


def remove_member(level_dict: dict, guild_id: str, player_uid: str) -> bool:
    """Remove a player from a guild."""
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    try:
        raw = g["value"]["RawData"]["value"]
        pu_clean = _s(player_uid)
        players = raw.get("players", [])
        admin_uid = _s(raw.get("admin_player_uid"))

        # Cannot remove the leader
        if pu_clean == admin_uid:
            return False

        raw["players"] = [p for p in players if _s(p.get("player_uid")) != pu_clean]

        # Also remove from character handles
        for hkey in ("individual_character_handle_ids", "worker_character_handle_ids"):
            handles = raw.get(hkey, [])
            raw[hkey] = [
                h for h in handles
                if _s(h.get("guid")) != pu_clean
            ]

        return True
    except Exception:
        return False


def delete_guild(level_dict: dict, guild_id: str) -> bool:
    """Delete a guild and all its associated bases.

    Simpler version of ``data_manager.delete_guild`` — removes the guild entry,
    all owned bases, and associated containers/workers via ``delete_base``.
    """
    from web.backend.services.base_service import _find_base_entry

    wsd = get_world_save_data(level_dict)
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False

    base_list = wsd.get("BaseCampSaveData", {}).get("value", [])
    gid_clean = _s(guild_id)

    # Delete all bases owned by this guild
    for b in base_list[:]:
        try:
            bgid = _s(b.get("value", {}).get("RawData", {}).get("value", {}).get("group_id_belong_to"))
            if bgid == gid_clean:
                from web.backend.services.base_service import delete_base
                bid = str(b.get("key", ""))
                delete_base(level_dict, bid, delete_workers=True)
        except Exception:
            pass

    # Check if the guild entry still exists (delete_base might have removed it)
    for g2 in _map_values(wsd, "GroupSaveDataMap"):
        if _s(g2.get("key")) == gid_clean:
            group_list = wsd.get("GroupSaveDataMap", {}).get("value", [])
            group_list[:] = [g3 for g3 in group_list if _s(g3.get("key")) != gid_clean]
            break

    # Remove all character entries belonging to guild members
    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    guild_player_uids = set()
    try:
        for p in g["value"]["RawData"]["value"].get("players", []):
            guild_player_uids.add(_s(p.get("player_uid")))
    except Exception:
        pass

    char_map[:] = [
        ch for ch in char_map
        if _s(ch.get("value", {}).get("RawData", {}).get("value", {}).get("group_id")) != gid_clean
        or _s(ch.get("value", {}).get("RawData", {}).get("value", {}).get("object", {}).get("SaveParameter", {}).get("value", {}).get("OwnerPlayerUId")) not in guild_player_uids
    ]

    return True
