"""Guild mutation operations for the web backend.

Operates on ``level_dict`` (the Rust uesave shape). Guild data lives at
``value.RawData_0.data.Guild.{guild_name, base_camp_level, base_ids,
tail.PreUpdate.{admin_player_uid, players}}`` (the typed ``PalGuildGroup``
struct decoded by palsav-rs).
"""

from __future__ import annotations

from app.backend.services.world_service import (
    _g, _gplayers, _group_type, _k, _map_entries, _norm_uid,
    get_tick, get_world_save_data,
)
from app.backend.services.base_service import (
    _guild_raw, _k_set, _set_nested, _s, delete_base as _delete_base,
)


def _find_guild(level_dict: dict, guild_id: str) -> dict | None:
    gid_clean = _s(guild_id)
    for g in _map_entries(get_world_save_data(level_dict), "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
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

    g_raw = _guild_raw(g)
    guild_name = _k(g_raw, "guild_name") or "Unnamed Guild"
    try:
        guild_level = int(_k(g_raw, "base_camp_level") or 1)
    except (TypeError, ValueError):
        guild_level = 1
    admin_uid = _norm_uid(
        _g(g_raw, "tail", "PreUpdate", "admin_player_uid")
    ) or ""
    admin_clean = _s(admin_uid)
    base_ids = _k(g_raw, "base_ids") or []
    players = _gplayers(g)

    members = []
    for p in players:
        puid = _norm_uid(_k(p, "player_uid")) or ""
        info = _k(p, "player_info") or {}
        last = _k(info, "last_online_real_time")
        elapsed = None
        if isinstance(last, (int, float)) and tick:
            elapsed = (tick - last) / 10_000_000.0
        members.append({
            "uid": puid,
            "name": _k(info, "player_name") or "Unknown",
            "is_leader": _s(puid) == admin_clean,
            "_u8_flag": 3,
            "last_seen_seconds": elapsed,
        })

    return {
        "id": str(g.get("key", guild_id)),
        "name": guild_name,
        "level": guild_level,
        "admin_uid": admin_uid,
        "member_count": len(members),
        "base_count": len(base_ids),
        "members": members,
        "base_ids": [str(b) for b in base_ids],
    }


def rename_guild(level_dict: dict, guild_id: str, new_name: str) -> bool:
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    _k_set(_guild_raw(g), "guild_name", new_name)
    return True


def set_guild_level(level_dict: dict, guild_id: str, level: int) -> bool:
    level = max(1, min(35, level))
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    _k_set(_guild_raw(g), "base_camp_level", level)
    return True


def make_member_leader(level_dict: dict, guild_id: str, player_uid: str) -> bool:
    """Promote a guild member to leader/admin."""
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    g_raw = _guild_raw(g)
    _g_set(g_raw, ["tail", "PreUpdate", "admin_player_uid"], player_uid)
    return True


def remove_member(level_dict: dict, guild_id: str, player_uid: str) -> bool:
    """Remove a player from a guild."""
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False
    g_raw = _guild_raw(g)
    pu_clean = _s(player_uid)
    players = _gplayers(g)
    admin_uid = _norm_uid(
        _g(g_raw, "tail", "PreUpdate", "admin_player_uid")
    ) or ""

    if pu_clean == _s(admin_uid):
        return False  # cannot remove the leader

    # Drop the member from players list.
    new_players = [p for p in players if _s(_k(p, "player_uid")) != pu_clean]
    _g_set(g_raw, ["tail", "PreUpdate", "players"], new_players)

    # Also drop their character handles.
    raw_top = _g(g, "value", "RawData") or {}
    for hkey in ("individual_character_handle_ids", "worker_character_handle_ids"):
        handles = _k(raw_top, hkey)
        if isinstance(handles, list):
            _k_set(raw_top, hkey, [
                h for h in handles if _s(_k(h, "guid")) != pu_clean
            ])
    return True


def delete_guild(level_dict: dict, guild_id: str) -> bool:
    """Delete a guild and all its bases (and associated workers/containers)."""
    wsd = get_world_save_data(level_dict)
    g = _find_guild(level_dict, guild_id)
    if g is None:
        return False

    gid_clean = _s(guild_id)

    # Delete all bases owned by this guild.
    for b in list(_map_entries(wsd, "BaseCampSaveData")):
        bgid = _norm_uid(_g(b, "value", "RawData", "group_id_belong_to"))
        if _s(bgid) == gid_clean:
            bid = str(b.get("key", ""))
            _delete_base(level_dict, bid, delete_workers=True)

    # Remove the guild entry itself.
    group_list = _map_entries(wsd, "GroupSaveDataMap")
    group_list[:] = [g3 for g3 in group_list if _s(g3.get("key")) != gid_clean]

    # Remove character entries bound to this guild.
    char_map = _map_entries(wsd, "CharacterSaveParameterMap")
    guild_player_uids = set()
    for p in _gplayers(g):
        guild_player_uids.add(_s(_k(p, "player_uid")))

    char_map[:] = [
        ch for ch in char_map
        if _s(_g(ch, "value", "RawData", "group_id")) != gid_clean
        or _s(_g(ch, "value", "RawData", "object", "SaveParameter", "OwnerPlayerUId"))
        not in guild_player_uids
    ]
    return True


# ---- helper (local copy to avoid a circular import with base_service) -------

def _g_set(node: dict, names: list[str], value) -> None:
    """Walk/create a chain of ``_0``-suffix keys and set the leaf."""
    from app.backend.services.base_service import _set_nested
    _set_nested(node, names, value)
