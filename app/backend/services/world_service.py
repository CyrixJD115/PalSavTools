"""Read-only queries over the decoded world save dict (Rust uesave shape).

Pure functions: input is the decoded ``level_dict`` (the ``{header, schemas,
root, extra}`` dict produced by ``save_service``/``palsav_rs_wrapper``), output
is plain dicts matching the pydantic schemas. Every access is defensive
(``.get`` + ``try/except``) because raw save shapes drift across game
versions.

Rust uesave shape notes
-----------------------
- Property keys carry an ``_<index>`` suffix (``worldSaveData_0``,
  ``GroupSaveDataMap_0``, ``Level_0``, ...). :func:`_k` / :func:`_g` resolve a
  bare name to its suffixed key, tolerating either form.
- Scalars are bare values (``100``, ``"name"``, ``true``) — *not* wrapped in
  ``{"value": ..., "type": ...}`` like the legacy Python palsav shape.
- ``MapProperty`` is a flat ``[{"key": ..., "value": ...}, ...]`` list under
  the property name (no nested ``{"value": [...]}``).
- Decoded RawData blobs are structured: e.g. a guild's data lives at
  ``value.RawData_0.data.Guild.{base_camp_level, base_ids, guild_name,
  tail.PreUpdate.{admin_player_uid, players}}``.
"""

from __future__ import annotations

from typing import Any

CharacterNameMap = dict[str, str]

# Index suffix uesave appends to every property key. We try ``<name>_0`` then
# fall back to the bare ``<name>`` so callers can use clean names.
_IDX = "_0"


# ---- key/value resolution helpers -------------------------------------------

def _k(node: dict, name: str) -> Any:
    """Read ``node[name_0]`` falling back to ``node[name]``."""
    if not isinstance(node, dict):
        return None
    suffixed = name + _IDX
    if suffixed in node:
        return node[suffixed]
    return node.get(name)


def _g(node: Any, *names: str, default: Any = None) -> Any:
    """Walk a chain of ``_k`` accesses, never raising.

    Replaces the old ``_u`` StructProperty-unwrapper. In the Rust shape there
    are no ``{"value": ...}`` wrappers to peel, so this is a plain nested
    ``.get`` with ``_0``-suffix tolerance.
    """
    cur: Any = node
    for name in names:
        cur = _k(cur, name) if isinstance(cur, dict) else None
        if cur is None:
            return default
    return cur if cur is not None else default


def get_world_save_data(level_dict: dict) -> dict:
    """The ``worldSaveData`` struct — its keys are the inner worldsave props."""
    return (
        _g(level_dict, "root", "properties", "worldSaveData") or {}
    )


def get_tick(wsd: dict) -> int:
    """Real-time ticks from GameTimeSaveData (for last-seen computation)."""
    gt = _k(wsd, "GameTimeSaveData")
    ticks = _k(gt, "RealDateTimeTicks") if isinstance(gt, dict) else None
    try:
        return int(ticks)
    except (TypeError, ValueError):
        return 0


def _map_entries(wsd: dict, key: str) -> list[dict]:
    """The flat ``[{key, value}, ...]`` list of a MapProperty.

    Replaces the old ``_map_values`` (which dug into ``{value: [...]}``).
    """
    node = _k(wsd, key)
    if isinstance(node, list):
        return node
    return []


# ---- counts -----------------------------------------------------------------

def count_world(level_dict: dict) -> dict:
    wsd = get_world_save_data(level_dict)
    guilds = [g for g in _map_entries(wsd, "GroupSaveDataMap")
              if _group_type(g) == "EPalGroupType::Guild"]
    players = sum(len(_gplayers(g)) for g in guilds)
    total_chars = _map_entries(wsd, "CharacterSaveParameterMap")
    pals = sum(1 for c in total_chars if _is_pal_entry(c))
    return {
        "guilds": len(guilds),
        "players": players,
        "bases": len(_map_entries(wsd, "BaseCampSaveData")),
        "containers": len(_map_entries(wsd, "ItemContainerSaveData")),
        "characters": len(total_chars),
        "pals": pals,
    }


# ---- guilds / players -------------------------------------------------------

def _group_type(g: dict) -> str:
    """e.g. ``'EPalGroupType::Guild'`` (a bare string in the Rust shape)."""
    try:
        return str(_g(g, "value", "GroupType") or "")
    except Exception:
        return ""


def _guild_data(g: dict) -> dict:
    """The typed ``PalGroupData`` -> ``Guild`` sub-struct (or ``{}``)."""
    return _g(g, "value", "RawData", "data", "Guild") or {}


def _gplayers(g: dict) -> list[dict]:
    """Guild members at ``RawData.data.Guild.tail.PreUpdate.players``."""
    players = _g(_guild_data(g), "tail", "PreUpdate", "players")
    return players if isinstance(players, list) else []


def _gname(g: dict) -> str:
    name = _g(_guild_data(g), "guild_name")
    return str(name) if name else "Unnamed Guild"


def _gbase_ids(g: dict) -> list[str]:
    ids = _g(_guild_data(g), "base_ids")
    return [str(b) for b in ids] if isinstance(ids, list) else []


def _gadmin(g: dict) -> str | None:
    admin = _g(_guild_data(g), "tail", "PreUpdate", "admin_player_uid")
    return str(admin) if admin else None


def list_guilds(level_dict: dict) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    out = []
    for g in _map_entries(wsd, "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        try:
            gid = str(g["key"])
        except Exception:
            gid = ""
        players = _gplayers(g)
        out.append({
            "id": gid,
            "name": _gname(g),
            "player_count": len(players),
            "base_count": len(_gbase_ids(g)),
            "leader_uid": _gadmin(g),
            "player_uids": [str(_k(p, "player_uid") or "") for p in players],
        })
    return out


def _fmt_last_seen(elapsed_s: float | None) -> str | None:
    if elapsed_s is None:
        return None
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


def list_players(level_dict: dict) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    tick = get_tick(wsd)
    out = []
    seen: set[str] = set()
    for g in _map_entries(wsd, "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        gid = str(g.get("key")) if g.get("key") else ""
        gname = _gname(g)
        guild_data = _guild_data(g)
        guild_level = _k(guild_data, "base_camp_level") or 1
        try:
            guild_level = int(guild_level)
        except (TypeError, ValueError):
            guild_level = 1
        admin_uid = _norm_uid(_g(guild_data, "tail", "PreUpdate", "admin_player_uid")) or ""
        admin_clean = _s(admin_uid)
        for p in _gplayers(g):
            uid = str(_k(p, "player_uid") or "") or ""
            if not uid or uid in seen:
                continue
            seen.add(uid)
            info = _k(p, "player_info") or {}
            name = _k(info, "player_name") or "Unknown"
            last = _k(info, "last_online_real_time")
            elapsed = None
            if isinstance(last, (int, float)) and tick:
                elapsed = (tick - last) / 10_000_000.0
            is_leader = _s(uid) == admin_clean
            out.append({
                "uid": uid,
                "name": name,
                "level": 0,
                "pal_count": 0,
                "guild_id": gid,
                "guild_name": gname,
                "guild_level": guild_level,
                "is_leader": is_leader,
                "last_seen_seconds": elapsed,
                "last_seen_text": _fmt_last_seen(elapsed),
            })
    return out


# ---- bases ------------------------------------------------------------------

def _translation(raw: dict) -> tuple[float, float, float] | None:
    t = _g(raw, "transform", "translation")
    if not isinstance(t, dict):
        return None
    try:
        return (float(t["x"]), float(t["y"]), float(t["z"]))
    except (KeyError, TypeError, ValueError):
        return None


def list_bases(level_dict: dict) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    out = []
    for b in _map_entries(wsd, "BaseCampSaveData"):
        raw = _g(b, "value", "RawData") or {}
        gid = _k(raw, "group_id_belong_to")
        gid = str(gid) if gid else None
        bid = _k(raw, "id") or b.get("key", "")
        out.append({
            "id": str(bid),
            "guild_id": gid,
            "guild_name": None,
            "location": _translation(raw),
            "worker_count": 0,
            "raw": {},
        })
    return out


def attach_guild_names(bases: list[dict], guilds: list[dict]) -> None:
    by_id = {g["id"].lower(): g["name"] for g in guilds}
    for b in bases:
        if b.get("guild_id"):
            b["guild_name"] = by_id.get(b["guild_id"].lower())


# ---- containers -------------------------------------------------------------

def list_containers(level_dict: dict, limit: int = 50000) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    out = []
    for c in _map_entries(wsd, "ItemContainerSaveData"):
        belong = _g(c, "value", "BelongInfo") or {}
        slot_num = _g(c, "value", "SlotNum")
        try:
            slot_count = int(slot_num) if slot_num is not None else 0
        except (TypeError, ValueError):
            slot_count = 0
        cid = str(c.get("key") or "")
        out.append({
            "id": cid,
            "owner_player_uid": _norm_uid(_k(belong, "PlayerUId")),
            "guild_id": _norm_uid(_k(belong, "GroupId")),
            "slot_count": slot_count,
            "item_count": 0,
        })
        if limit and len(out) >= limit:
            break
    return out


def _norm_uid(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s and s != "00000000-0000-0000-0000-000000000000" else None


def _s(uid: Any) -> str:
    """Normalized UID for comparison: lowercase, no hyphens."""
    return str(uid or "").replace("-", "").lower()


# ---- pals -------------------------------------------------------------------

def _pal_entry_raw(ch: dict) -> dict:
    """The ``SaveParameter`` struct from a CharacterSaveParameterMap entry.

    In the Rust shape this is ``value.RawData_0.object.SaveParameter_0``, whose
    keys are the character's fields (``Level_0``, ``NickName_0``, ``IsPlayer_0``,
    ``PassiveSkillList_0``, ...). Scalars are bare; skill lists are flat
    ``[str, ...]``.
    """
    return _g(ch, "value", "RawData", "object", "SaveParameter") or {}


def _is_pal_entry(ch: dict) -> bool:
    """True if this CharacterSaveParameterMap entry is a pal (not a player)."""
    sp = _pal_entry_raw(ch)
    return not _k(sp, "IsPlayer")


def _pal_field(sp: dict, key: str) -> Any:
    """Read a SaveParameter field by bare name (resolves ``<name>_0``)."""
    return _k(sp, key)


def _int_field(sp: dict, key: str, default: int = 0) -> int:
    v = _pal_field(sp, key)
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _str_field(sp: dict, key: str, default: str = "") -> str:
    v = _pal_field(sp, key)
    return str(v) if v is not None else default


def _gender_str(sp: dict) -> str:
    gv = str(_pal_field(sp, "Gender") or "")
    return {
        "EPalGenderType::Male": "Male",
        "EPalGenderType::Female": "Female",
    }.get(gv, "Unknown")


def _skill_list(sp: dict, key: str) -> list[str]:
    """In the Rust shape skill lists are flat ``[str, ...]`` arrays."""
    vals = _pal_field(sp, key)
    if isinstance(vals, list):
        return [str(s) for s in vals if s]
    return []


def list_pals(
    level_dict: dict,
    name_map: CharacterNameMap | None = None,
    limit: int = 500,
) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    nm = name_map or {}
    out = []
    for ch in _map_entries(wsd, "CharacterSaveParameterMap"):
        if not _is_pal_entry(ch):
            continue
        key = _g(ch, "key") or {}
        sp = _pal_entry_raw(ch)

        # Ownership: prefer key.PlayerUId, fall back to sp.OwnerPlayerUId.
        # Base-assigned workers may have a nil key.PlayerUId even though the
        # SaveParameter still carries the original owner UID.  This mirrors
        # the dual-check pattern in player_service._char_belongs_to_player.
        owner = _norm_uid(_k(key, "PlayerUId"))
        if not owner:
            owner = _norm_uid(_k(sp, "OwnerPlayerUId"))

        inst = str(_k(key, "InstanceId") or "")
        cid = _pal_field(sp, "CharacterID")
        cid_str = str(cid) if cid is not None else ""
        display = nm.get(cid_str.lower(), cid_str) if cid_str else None
        out.append({
            "instance_id": inst,
            "character_id": cid_str,
            "display_name": display,
            "owner_uid": owner,
            "nickname": _str_field(sp, "NickName"),
            "level": _int_field(sp, "Level", 1),
            "rank": _int_field(sp, "Rank", 1),
            "gender": _gender_str(sp),
            "talent_hp": _int_field(sp, "Talent_HP"),
            "talent_shot": _int_field(sp, "Talent_Shot"),
            "talent_defense": _int_field(sp, "Talent_Defense"),
            "rank_hp": _int_field(sp, "Rank_HP"),
            "rank_attack": _int_field(sp, "Rank_Attack"),
            "rank_defense": _int_field(sp, "Rank_Defence"),
            "rank_craftspeed": _int_field(sp, "Rank_CraftSpeed"),
            "passive_skills": _skill_list(sp, "PassiveSkillList"),
            "active_skills": _skill_list(sp, "EquipWaza"),
            "learned_skills": _skill_list(sp, "MasteredWaza"),
            "is_illegal": False,
        })
        if limit and len(out) >= limit:
            break
    return out


def get_current_stats(level_dict: dict) -> dict:
    """Aggregate stats: level distribution, gender ratio, top skills, etc."""
    wsd = get_world_save_data(level_dict)
    stats = {
        "total": 0,
        "avg_level": 0.0,
        "gender": {"Male": 0, "Female": 0, "Unknown": 0},
        "level_brackets": {"1-20": 0, "21-40": 0, "41-60": 0},
        "talent_avg": {"hp": 0, "attack": 0, "defense": 0},
        "common_passives": {},
        "common_active": {},
    }
    count = 0
    sum_level = 0
    sum_t_hp = sum_t_atk = sum_t_def = 0
    for ch in _map_entries(wsd, "CharacterSaveParameterMap"):
        if not _is_pal_entry(ch):
            continue
        sp = _pal_entry_raw(ch)
        if not sp:
            continue
        count += 1
        lv = _int_field(sp, "Level", 1)
        sum_level += lv
        if lv <= 20:
            stats["level_brackets"]["1-20"] += 1
        elif lv <= 40:
            stats["level_brackets"]["21-40"] += 1
        else:
            stats["level_brackets"]["41-60"] += 1
        g = _gender_str(sp)
        stats["gender"][g] = stats["gender"].get(g, 0) + 1
        sum_t_hp += _int_field(sp, "Talent_HP")
        sum_t_atk += _int_field(sp, "Talent_Shot")
        sum_t_def += _int_field(sp, "Talent_Defense")
        for s in _skill_list(sp, "PassiveSkillList"):
            stats["common_passives"][s] = stats["common_passives"].get(s, 0) + 1
        for s in _skill_list(sp, "EquipWaza"):
            stats["common_active"][s] = stats["common_active"].get(s, 0) + 1
    if count:
        stats["total"] = count
        stats["avg_level"] = round(sum_level / count, 1)
        stats["talent_avg"]["hp"] = round(sum_t_hp / count, 1)
        stats["talent_avg"]["attack"] = round(sum_t_atk / count, 1)
        stats["talent_avg"]["defense"] = round(sum_t_def / count, 1)
    stats["common_passives"] = dict(
        sorted(stats["common_passives"].items(), key=lambda x: -x[1])[:10]
    )
    stats["common_active"] = dict(
        sorted(stats["common_active"].items(), key=lambda x: -x[1])[:10]
    )
    return stats
