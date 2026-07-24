"""Base camp mutation operations for the web backend.

Operates on ``level_dict`` (the Rust uesave shape) from ``save_state``.
Navigation uses :func:`world_service._g`/``_k`` which tolerate the ``_0``
property-key suffix uesave emits.
"""

from __future__ import annotations

from typing import Any

from app.backend.services.world_service import (
    _fmt_last_seen, _g, _guild_tail, _guild_tail_key, _gplayers, _group_type,
    _k, _map_entries, _norm_uid, get_tick, get_world_save_data,
)

_NIL_UID = "00000000-0000-0000-0000-000000000000"


def _extract_id(raw: Any) -> str:
    """Extract a clean UUID string from any shape the save data uses.

    In the Rust shape UUIDs are bare strings, but a MapProperty key may be a
    ``{"ID_0": "<uuid>"}`` dict (container keys) — handle both.
    """
    if raw is None:
        return ""
    if isinstance(raw, dict):
        v = _k(raw, "ID")
        if v is not None:
            return str(v)
        # fall back to any scalar value present
        return ""
    return str(raw)


def _s(uid: Any) -> str:
    """Normalized UID for comparison: lowercase, no hyphens."""
    return _extract_id(uid).replace("-", "").lower()


# ---- lookup -----------------------------------------------------------------

def _find_base_entry(level_dict: dict, base_id: str) -> dict | None:
    wsd = get_world_save_data(level_dict)
    bid_clean = _s(base_id)
    for b in _map_entries(wsd, "BaseCampSaveData"):
        if _s(b.get("key")) == bid_clean:
            return b
    return None


def _find_guild_by_base(level_dict: dict, base_id: str) -> dict | None:
    """Find the guild entry that owns a base (lists it in ``base_ids``)."""
    wsd = get_world_save_data(level_dict)
    bid_clean = _s(base_id)
    for g in _map_entries(wsd, "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        raw = _g(g, "value", "RawData", "data", "Guild") or {}
        for bid in (_k(raw, "base_ids") or []):
            if _s(bid) == bid_clean:
                return g
    return None


def _guild_raw(g: dict) -> dict:
    """The ``Guild`` sub-struct of a guild group entry."""
    return _g(g, "value", "RawData", "data", "Guild") or {}


def _base_raw(b: dict) -> dict:
    """The ``RawData`` struct of a base camp entry."""
    return _g(b, "value", "RawData") or {}


# ---- Public API -------------------------------------------------------------

def get_base_detail(level_dict: dict, base_id: str) -> dict | None:
    """Get enriched detail for a single base."""
    base_entry = _find_base_entry(level_dict, base_id)
    if base_entry is None:
        return None

    raw = _base_raw(base_entry)
    trans = _g(raw, "transform", "translation")
    try:
        location = (float(trans["x"]), float(trans["y"]), float(trans["z"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        location = None

    area_range = float(_k(raw, "area_range") or 3500.0)

    gid = _norm_uid(_k(raw, "group_id_belong_to"))
    guild_name = None
    guild_level = 1
    leader_name = None
    member_count = 0
    total_bases = 0
    base_position = 1

    guild_entry = _find_guild_by_base(level_dict, base_id)
    if guild_entry:
        g_raw = _guild_raw(guild_entry)
        guild_name = _k(g_raw, "guild_name") or "Unnamed Guild"
        try:
            guild_level = int(_k(g_raw, "base_camp_level") or 1)
        except (TypeError, ValueError):
            guild_level = 1
        players = _gplayers(guild_entry)
        member_count = len(players)
        base_ids = _k(g_raw, "base_ids") or []
        total_bases = len(base_ids)

        admin_uid = _norm_uid(
            _k(_guild_tail(guild_entry), "admin_player_uid")
        ) or ""
        for p in players:
            if _s(_k(p, "player_uid")) == _s(admin_uid):
                info = _k(p, "player_info") or {}
                leader_name = _k(info, "player_name") or admin_uid
                break
        if not leader_name and players:
            info = _k(players[0], "player_info") or {}
            leader_name = _k(info, "player_name") or admin_uid

        for i, bid in enumerate(base_ids):
            if _s(bid) == _s(base_id):
                base_position = i + 1
                break

    return {
        "id": str(_k(raw, "id") or base_entry.get("key", base_id)),
        "guild_id": gid,
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
    """Delete a base camp and its associated map objects / containers / work.

    Adapted from the legacy ``data_manager.delete_base_camp`` but operates on
    the Rust-shape ``level_dict``. Removes the base entry, map objects bound to
    it, their module containers, work entries, and optionally the worker
    characters (or clears their SlotId if ``delete_workers`` is False).
    """
    wsd = get_world_save_data(level_dict)
    base_entry = _find_base_entry(level_dict, base_id)
    if base_entry is None:
        return False

    base_list = _map_entries(wsd, "BaseCampSaveData")
    group_map = _map_entries(wsd, "GroupSaveDataMap")
    containers_char = _map_entries(wsd, "CharacterContainerSaveData")
    containers_item = _map_entries(wsd, "ItemContainerSaveData")
    map_objs = _map_entries(wsd, "MapObjectSaveData")
    work_entries = _map_entries(wsd, "WorkSaveData")
    char_map = _map_entries(wsd, "CharacterSaveParameterMap")

    base_id_low = _s(base_entry.get("key"))

    # Worker container id (from the base's WorkerDirector RawData, if present).
    worker_cont_id = _norm_uid(
        _g(base_entry, "value", "WorkerDirector", "RawData", "container_id")
    )

    cont_ids_to_del: set[str] = set()
    if worker_cont_id:
        cont_ids_to_del.add(_s(worker_cont_id))

    # Collect container ids referenced by map-object modules bound to this base.
    for obj in map_objs:
        mr = _g(obj, "Model", "RawData") or {}
        if _s(_k(mr, "base_camp_id_belong_to")) != base_id_low:
            continue
        module_map = _g(obj, "ConcreteModel", "ModuleMap") or {}
        for mod in (module_map if isinstance(module_map, list) else []):
            raw_mod = _g(mod, "value", "RawData") or {}
            tgt = _k(raw_mod, "target_container_id")
            if tgt:
                cont_ids_to_del.add(_s(tgt))

    # Drop map objects bound to this base.
    _filter_in_place(
        map_objs,
        lambda o: _s(_g(o, "Model", "RawData", "base_camp_id_belong_to")) != base_id_low,
    )
    # Drop associated containers.
    _filter_in_place(
        containers_item,
        lambda c: _s(c.get("key")) not in cont_ids_to_del,
    )
    _filter_in_place(
        containers_char,
        lambda c: _s(c.get("key")) not in cont_ids_to_del,
    )
    # Drop work entries bound to this base.
    _filter_in_place(
        work_entries,
        lambda we: _s(_g(we, "RawData", "base_camp_id_belong_to")) != base_id_low,
    )

    # Handle worker characters: remove (delete_workers) or clear their slot.
    if worker_cont_id:
        wcl = _s(worker_cont_id)
        survivors: list[dict] = []
        for ch in char_map:
            raw = _g(ch, "value", "RawData") or {}
            sp = _g(raw, "object", "SaveParameter") or {}
            if _k(sp, "IsPlayer"):
                survivors.append(ch)
                continue
            slot_id = _g(sp, "SlotId", "ContainerId", "ID")
            if slot_id and _s(slot_id) == wcl:
                if delete_workers:
                    continue  # drop
                # else: clear the slot binding + group
                _set_nested(sp, ["SlotId", "ContainerId", "ID"], _NIL_UID)
                _k_set(raw, "group_id", _NIL_UID)
            survivors.append(ch)
        char_map[:] = survivors

    # Remove this base from its guild's base_ids list.
    for g in group_map:
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        g_raw = _guild_raw(g)
        g_base_ids = _k(g_raw, "base_ids")
        if isinstance(g_base_ids, list):
            _k_set(g_raw, "base_ids",
                   [bid for bid in g_base_ids if _s(bid) != base_id_low])

    # Remove the base entry itself.
    _filter_in_place(
        base_list, lambda b: _s(b.get("key")) != base_id_low,
    )
    return True


def rename_guild(level_dict: dict, guild_id: str, new_name: str) -> bool:
    """Rename a guild (sets ``data.Guild.guild_name``)."""
    gid_clean = _s(guild_id)
    for g in _map_entries(get_world_save_data(level_dict), "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        if _s(g.get("key")) == gid_clean:
            g_raw = _guild_raw(g)
            _k_set(g_raw, "guild_name", new_name)
            return True
    return False


def set_guild_level(level_dict: dict, guild_id: str, level: int) -> bool:
    """Set guild level (1-35) via ``data.Guild.base_camp_level``."""
    level = max(1, min(35, level))
    gid_clean = _s(guild_id)
    for g in _map_entries(get_world_save_data(level_dict), "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        if _s(g.get("key")) == gid_clean:
            _k_set(_guild_raw(g), "base_camp_level", level)
            return True
    return False


def update_base_radius(level_dict: dict, base_id: str, new_radius: float) -> bool:
    """Update the area range (radius) of a base camp."""
    base_entry = _find_base_entry(level_dict, base_id)
    if base_entry is None:
        return False
    try:
        _k_set(_base_raw(base_entry), "area_range", float(new_radius))
        return True
    except Exception:
        return False


def get_enriched_base_list(level_dict: dict) -> list[dict]:
    """Build enriched base list with guild info, position, radius, leader."""
    wsd = get_world_save_data(level_dict)
    return get_enriched_base_list_from_wsd(wsd)


def get_enriched_base_list_from_wsd(wsd: dict) -> list[dict]:
    """Build enriched base list from a wsd slice (lazy-friendly).

    Reads only ``BaseCampSaveData`` + ``GroupSaveDataMap`` — both cheap.
    """
    base_map = {
        _s(b.get("key")): _base_raw(b)
        for b in _map_entries(wsd, "BaseCampSaveData")
        if _s(b.get("key"))
    }

    out: list[dict] = []
    for entry in _map_entries(wsd, "GroupSaveDataMap"):
        if _group_type(entry) != "EPalGroupType::Guild":
            continue

        g_raw = _guild_raw(entry)
        admin_uid = _norm_uid(
            _k(_guild_tail(entry), "admin_player_uid")
        ) or ""
        guild_name = _k(g_raw, "guild_name") or "Unnamed Guild"
        try:
            guild_level = int(_k(g_raw, "base_camp_level") or 1)
        except (TypeError, ValueError):
            guild_level = 1
        players = _gplayers(entry)
        member_count = len(players)
        base_ids = _k(g_raw, "base_ids") or []
        total_bases = len(base_ids)

        leader_name = None
        for p in players:
            if _s(_k(p, "player_uid")) == _s(admin_uid):
                info = _k(p, "player_info") or {}
                leader_name = _k(info, "player_name") or admin_uid
                break
        if not leader_name and players:
            info = _k(players[0], "player_info") or {}
            leader_name = _k(info, "player_name") or admin_uid
        if not leader_name:
            leader_name = admin_uid or "Unknown"

        base_position = 1
        for bid in base_ids:
            bid_str = _s(bid)
            if not bid_str or bid_str not in base_map:
                continue
            base_val = base_map[bid_str]
            trans = _g(base_val, "transform", "translation")
            try:
                raw_x = float(trans["x"])
                raw_y = float(trans["y"])
                raw_z = float(trans["z"])
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            area_range = float(_k(base_val, "area_range") or 3500.0)

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


# ---- in-place mutation helpers ---------------------------------------------

def _filter_in_place(lst: list, keep) -> None:
    """Replace ``lst`` contents with elements where ``keep(x)`` is True."""
    lst[:] = [x for x in lst if keep(x)]


def _k_set(node: dict, name: str, value: Any) -> None:
    """Set ``node[name_0]`` (or ``node[name]``) preserving the existing key form."""
    if not isinstance(node, dict):
        return
    suffixed = name + "_0"
    if suffixed in node:
        node[suffixed] = value
    elif name in node:
        node[name] = value
    else:
        node[suffixed] = value  # default to the suffixed form on insert


def _set_nested(node: dict, names: list[str], value: Any) -> None:
    """Walk/create a chain of ``_0``-suffix keys and set the leaf."""
    cur: dict = node
    for n in names[:-1]:
        suffixed = n + "_0"
        nxt = _k(cur, n)
        if not isinstance(nxt, dict):
            nxt = {}
            _k_set(cur, n, nxt)
        cur = nxt if isinstance(nxt, dict) else cur
    _k_set(cur, names[-1], value)
