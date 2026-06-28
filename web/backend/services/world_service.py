"""Read-only queries over the decoded world save dict.

Pure functions: input is the dumped ``level_dict`` (and optionally a character
name map), output is plain dicts matching the pydantic schemas. Every access is
defensive (``.get`` + ``try/except``) because raw save shapes drift across game
versions.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

CharacterNameMap = dict[str, str]


# ---- small unwrap helpers ---------------------------------------------------

def _u(node: Any, *path, default=None) -> Any:
    """Walk a chain of ``['value']``-and-key accesses, never raising.

    Auto-unwraps simple wrappers (Int/Float/Str/Byte/StructProperty) by
    recognising they carry their payload in ``value``.  Uses ``<= 5``
    because StructProperty wrappers have 5 keys; standard ones have 3.
    """
    cur = node
    for key in path:
        if isinstance(cur, Mapping):
            cur = cur.get(key, default)
        else:
            return default
        if isinstance(cur, Mapping) and "value" in cur and len(cur) <= 5:
            cur = cur.get("value", cur)
    if isinstance(cur, Mapping) and "value" in cur and len(cur) <= 5:
        cur = cur.get("value", cur)
    return cur


def get_world_save_data(level_dict: dict) -> dict:
    return (
        level_dict.get("properties", {})
        .get("worldSaveData", {})
        .get("value", {})
    )


def get_tick(wsd: dict) -> int:
    try:
        return int(
            wsd["GameTimeSaveData"]["value"]["RealDateTimeTicks"]["value"]
        )
    except Exception:
        return 0


def _map_values(wsd: dict, key: str) -> list[dict]:
    """Return the inner ``value`` list of a ``{key: {value: [...]}}`` map."""
    node = wsd.get(key, {})
    if isinstance(node, dict):
        return node.get("value", []) or []
    return []


# ---- counts -----------------------------------------------------------------

def count_world(level_dict: dict) -> dict:
    wsd = get_world_save_data(level_dict)
    guilds = [g for g in _map_values(wsd, "GroupSaveDataMap")
              if _group_type(g) == "EPalGroupType::Guild"]
    players = sum(
        len(_gplayers(g)) for g in guilds
    )
    total_chars = _map_values(wsd, "CharacterSaveParameterMap")
    pals = sum(1 for c in total_chars if _is_pal_entry(c))
    return {
        "guilds": len(guilds),
        "players": players,
        "bases": len(_map_values(wsd, "BaseCampSaveData")),
        "containers": len(_map_values(wsd, "ItemContainerSaveData")),
        "characters": len(total_chars),
        "pals": pals,
    }


# ---- guilds / players -------------------------------------------------------

def _group_type(g: dict) -> str:
    try:
        return g["value"]["GroupType"]["value"]["value"]
    except Exception:
        return ""


def _gplayers(g: dict) -> list[dict]:
    try:
        return g["value"]["RawData"]["value"].get("players", []) or []
    except Exception:
        return []


def _gname(g: dict) -> str:
    try:
        return g["value"]["RawData"]["value"].get("guild_name", "Unnamed Guild")
    except Exception:
        return "Unnamed Guild"


def _gbase_ids(g: dict) -> list[str]:
    try:
        return [str(b) for b in g["value"]["RawData"]["value"].get("base_ids", [])]
    except Exception:
        return []


def _gadmin(g: dict) -> str | None:
    try:
        v = g["value"]["RawData"]["value"].get("admin_player_uid")
        return str(v) if v else None
    except Exception:
        return None


def list_guilds(level_dict: dict) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    out = []
    for g in _map_values(wsd, "GroupSaveDataMap"):
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
            "player_uids": [str(p.get("player_uid", "")) for p in players],
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
    for g in _map_values(wsd, "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        gid = str(g["key"]) if g.get("key") else ""
        gname = _gname(g)
        try:
            guild_level = g["value"]["RawData"]["value"].get("base_camp_level", 1)
        except Exception:
            guild_level = 1
        try:
            admin_uid = str(g["value"]["RawData"]["value"].get("admin_player_uid", "")).replace("-", "").lower()
        except Exception:
            admin_uid = ""
        for p in _gplayers(g):
            uid = str(p.get("player_uid", "")) or ""
            if not uid or uid in seen:
                continue
            seen.add(uid)
            info = p.get("player_info") or {}
            name = info.get("player_name", "Unknown")
            last = info.get("last_online_real_time")
            elapsed = None
            if isinstance(last, (int, float)) and tick:
                elapsed = (tick - last) / 10_000_000.0
            is_leader = uid.replace("-", "").lower() == admin_uid
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
    try:
        t = raw["transform"]["translation"]
        return (float(t["x"]), float(t["y"]), float(t["z"]))
    except Exception:
        return None


def list_bases(level_dict: dict) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    out = []
    for b in _map_values(wsd, "BaseCampSaveData"):
        try:
            raw = b["value"]["RawData"]["value"]
        except Exception:
            raw = {}
        gid = raw.get("group_id_belong_to")
        gid = str(gid) if gid else None
        out.append({
            "id": str(raw.get("id", b.get("key", ""))),
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
    for c in _map_values(wsd, "ItemContainerSaveData"):
        v = c.get("value", {})
        belong = _u(v, "BelongInfo") or {}
        slot_num = _u(v, "SlotNum")
        try:
            slot_count = int(slot_num) if slot_num is not None else 0
        except Exception:
            slot_count = 0
        cid = str(_u(c, "key") or "")
        out.append({
            "id": cid,
            "owner_player_uid": _norm_uid(_u(belong, "PlayerUId") or "" if isinstance(belong, dict) else None),
            "guild_id": _norm_uid(_u(belong, "GroupId") or "" if isinstance(belong, dict) else None),
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


# ---- pals -------------------------------------------------------------------

def _pal_field(sp: dict, key: str) -> Any:
    """Read a SaveParameter field, unwrapping value/ByteProperty nesting."""
    node = sp.get(key)
    if node is None:
        return None
    if isinstance(node, Mapping):
        if "value" in node:
            inner = node["value"]
            if isinstance(inner, Mapping) and "value" in inner and "type" in inner:
                return inner["value"]
            return inner
        return node
    return node


def _pal_entry_raw(ch: dict) -> dict:
    """Extract the SaveParameter dict from a CharacterSaveParameterMap entry."""
    try:
        return ch["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
    except Exception:
        return {}


def _is_pal_entry(ch: dict) -> bool:
    """True if this CharacterSaveParameterMap entry is a pal (not a player)."""
    sp = _pal_entry_raw(ch)
    return "IsPlayer" not in sp


def _int_field(sp: dict, key: str, default: int = 0) -> int:
    v = _pal_field(sp, key)
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _str_field(sp: dict, key: str, default: str = "") -> str:
    v = _pal_field(sp, key)
    return str(v) if v is not None else default


def _gender_str(sp: dict) -> str:
    gv = _pal_field(sp, "Gender")
    gv_str = str(gv) if gv else ""
    return {
        "EPalGenderType::Male": "Male",
        "EPalGenderType::Female": "Female",
    }.get(gv_str, "Unknown")


def _skill_list(sp: dict, key: str) -> list[str]:
    """Extract a list of skill strings from a repeated-value field."""
    try:
        raw = sp.get(key, {})
        vals = raw.get("value", {}).get("values", [])
        return [str(s) for s in vals if s]
    except Exception:
        return []


def list_pals(
    level_dict: dict,
    name_map: CharacterNameMap | None = None,
    limit: int = 500,
) -> list[dict]:
    wsd = get_world_save_data(level_dict)
    nm = name_map or {}
    out = []
    for ch in _map_values(wsd, "CharacterSaveParameterMap"):
        if not _is_pal_entry(ch):
            continue
        try:
            owner = _norm_uid(_u(ch, "key", "PlayerUId"))
            inst = str(_u(ch, "key", "InstanceId") or "")
        except Exception:
            owner, inst = None, ""
        sp = _pal_entry_raw(ch)
        cid = _pal_field(sp, "CharacterID") or ""
        cid_str = str(cid)
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
    for ch in _map_values(wsd, "CharacterSaveParameterMap"):
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
    # Sort skill dicts by freq descending, keep top 10
    stats["common_passives"] = dict(
        sorted(stats["common_passives"].items(), key=lambda x: -x[1])[:10]
    )
    stats["common_active"] = dict(
        sorted(stats["common_active"].items(), key=lambda x: -x[1])[:10]
    )
    return stats
