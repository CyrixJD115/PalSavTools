"""Player mutation operations for the web backend.

Adapts logic from ``src/palworld_aio/managers/player_manager.py`` and
``data_manager.py`` but operates on ``level_dict`` (from ``save_state``)
instead of the ``constants.loaded_level_json`` global.

Player .sav file operations (tech points, viewing cage, etc.) use
``players_dir`` which is stored in ``LoadedSave.players_dir``.
"""

from __future__ import annotations

import os
from pathlib import Path
from web.backend.services import world_service
from web.backend.services.save_service import decode_file, encode_bytes, SaveDecodeError
from palsav.gvas import GvasFile


def _uid_clean(uid: str) -> str:
    return str(uid).replace("-", "").lower()


def _uid_upper(uid: str) -> str:
    return str(uid).replace("-", "").upper()


def normalize_uid(uid: str | dict | None) -> str:
    if uid is None:
        return ""
    if isinstance(uid, dict):
        uid = uid.get("value", "")
    return str(uid).replace("-", "").lower()


def _find_player_sp(level_dict: dict, uid: str) -> tuple[dict, dict, dict] | None:
    """Find a player's SaveParameter entry in CharacterSaveParameterMap.

    Returns ``(entry, raw_data, save_parameter_value)`` or ``None``.
    """
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    for entry in char_map:
        try:
            raw = entry["value"]["RawData"]["value"]
            sp = raw["object"]["SaveParameter"]
            if sp.get("struct_type") != "PalIndividualCharacterSaveParameter":
                continue
            sp_val = sp.get("value", {})
            if not sp_val.get("IsPlayer", {}).get("value"):
                continue
            uid_obj = entry.get("key", {}).get("PlayerUId", {})
            e_uid = str(uid_obj.get("value", "")).replace("-", "") if isinstance(uid_obj, dict) else ""
            if e_uid == uid_clean:
                return entry, raw, sp_val
        except Exception:
            continue
    return None


def _find_player_in_guilds(level_dict: dict, uid: str) -> tuple[dict, dict, int] | None:
    """Find a player entry and guild in GroupSaveDataMap.

    Returns ``(guild_entry, player_entry, player_index)`` or ``None``.
    """
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    for g in wsd.get("GroupSaveDataMap", {}).get("value", []):
        try:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        raw = g.get("value", {}).get("RawData", {}).get("value", {})
        for i, p in enumerate(raw.get("players", [])):
            if _uid_clean(str(p.get("player_uid", ""))) == uid_clean:
                return g, raw, i
    return None


def _read_player_sav(players_dir: str, uid: str) -> GvasFile | None:
    """Read a player's .sav file and decode it."""
    sav_path = Path(players_dir) / f"{_uid_upper(uid)}.sav"
    if not sav_path.exists():
        return None
    try:
        gvas, _, _, _ = decode_file(sav_path)
        return gvas
    except SaveDecodeError:
        return None


def _write_player_sav(gvas: GvasFile, players_dir: str, uid: str) -> bool:
    """Re-encode and write a player's .sav file."""
    sav_path = Path(players_dir) / f"{_uid_upper(uid)}.sav"
    try:
        raw = encode_bytes(gvas, 49)
        sav_path.write_bytes(raw)
        return True
    except Exception:
        return False


def _player_sav_path(players_dir: str, uid: str) -> str:
    return os.path.join(players_dir, f"{_uid_upper(uid)}.sav")


# ---- Public API --------------------------------------------------------------


def get_player_detail(
    level_dict: dict,
    uid: str,
    player_pal_counts: dict[str, int],
    player_levels: dict[str, int],
) -> dict | None:
    """Get detailed info for a single player.

    Returns None if not found.
    """
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    tick = world_service.get_tick(wsd)

    for g in world_service._map_values(wsd, "GroupSaveDataMap"):
        if world_service._group_type(g) != "EPalGroupType::Guild":
            continue
        gid = str(g.get("key", ""))
        gname = world_service._gname(g)
        try:
            guild_level = g["value"]["RawData"]["value"].get("base_camp_level", 1)
        except Exception:
            guild_level = 1
        for p in world_service._gplayers(g):
            puid = str(p.get("player_uid", ""))
            if _uid_clean(puid) != uid_clean:
                continue
            info = p.get("player_info", {})
            name = info.get("player_name", "Unknown")
            last = info.get("last_online_real_time")
            elapsed = None
            if isinstance(last, (int, float)) and tick:
                elapsed = (tick - last) / 10_000_000.0

            # Check if admin (leader)
            try:
                admin = str(g["value"]["RawData"]["value"].get("admin_player_uid", "")).replace("-", "").lower()
                is_leader = admin == uid_clean
            except Exception:
                is_leader = False

            return {
                "uid": puid,
                "name": name,
                "level": player_levels.get(uid_clean, 0),
                "pal_count": player_pal_counts.get(uid_clean, 0),
                "guild_id": gid,
                "guild_name": gname,
                "guild_level": guild_level,
                "is_leader": is_leader,
                "last_seen_seconds": elapsed,
                "last_seen_text": world_service._fmt_last_seen(elapsed),
            }
    return None


def rename_player(level_dict: dict, uid: str, new_name: str) -> bool:
    """Rename a player in both GroupSaveDataMap and CharacterSaveParameterMap."""
    uid_clean = _uid_clean(uid)

    # Update in guild players list
    result = _find_player_in_guilds(level_dict, uid)
    if result:
        _, raw, _ = result
        for p in raw.get("players", []):
            if _uid_clean(str(p.get("player_uid", ""))) == uid_clean:
                p.setdefault("player_info", {})["player_name"] = new_name
                break

    # Update in character save parameter
    sp_found = _find_player_sp(level_dict, uid)
    if sp_found:
        _, _, sp_val = sp_found
        sp_val.setdefault("NickName", {})["value"] = new_name

    return True


def delete_player(level_dict: dict, uid: str) -> bool:
    """Delete a player from all group data and character map.

    Uses logic adapted from ``data_manager.delete_player``.
    """
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    group_map = wsd.get("GroupSaveDataMap", {}).get("value", [])
    base_list = wsd.get("BaseCampSaveData", {}).get("value", [])

    # Remove from character map
    to_remove = []
    for ch in char_map:
        try:
            raw = ch["value"]["RawData"]["value"]
            sp = raw["object"]["SaveParameter"]["value"]
            if sp.get("IsPlayer", {}).get("value"):
                p_uid = ch["key"]["PlayerUId"]["value"]
                if _uid_clean(str(p_uid)) == uid_clean:
                    to_remove.append(ch)
                    continue
            owner = sp.get("OwnerPlayerUId", {}).get("value")
            if owner and _uid_clean(str(owner)) == uid_clean:
                to_remove.append(ch)
        except Exception:
            continue
    for ch in to_remove:
        char_map.remove(ch)

    # Remove from guilds
    to_remove_guilds = []
    for g in group_map:
        try:
            if g["value"]["GroupType"]["value"]["value"] != "EPalGroupType::Guild":
                continue
        except Exception:
            continue
        raw = g.get("value", {}).get("RawData", {}).get("value", {})
        players = raw.get("players", [])
        new_players = [p for p in players if _uid_clean(str(p.get("player_uid", ""))) != uid_clean]
        if len(new_players) == len(players):
            continue
        raw["players"] = new_players
        if not new_players:
            gid = g.get("key")
            # Clean up bases belonging to this guild
            for b in base_list[:]:
                try:
                    if world_service._norm_uid(b["value"]["RawData"]["value"].get("group_id_belong_to")) == _uid_clean(str(gid)):
                        base_list.remove(b)
                except Exception:
                    pass
            # Remove guild extra data
            gid_clean = _uid_clean(str(gid)) if gid else ""
            guild_extra = wsd.get("GuildExtraSaveDataMap", {}).get("value", [])
            guild_extra[:] = [e for e in guild_extra if normalize_uid(e.get("key")) != gid_clean]
            to_remove_guilds.append(g)
        else:
            admin = str(raw.get("admin_player_uid", "")).replace("-", "").lower()
            if admin == uid_clean and new_players:
                raw["admin_player_uid"] = new_players[0]["player_uid"]

    for g in to_remove_guilds:
        group_map.remove(g)

    # Cleanup references
    _cleanup_player_references(wsd, {uid_clean})

    return True


def _cleanup_player_references(wsd: dict, deleted_uids: set[str]) -> None:
    """Remove references to deleted player UIDs (adapted from data_manager)."""
    if not deleted_uids:
        return

    # MapObjectSaveData — clear build_player_uid
    for obj in wsd.get("MapObjectSaveData", {}).get("value", {}).get("values", []):
        try:
            raw = obj.get("Model", {}).get("value", {}).get("RawData", {}).get("value", {})
            build_uid = raw.get("build_player_uid")
            if build_uid and normalize_uid(build_uid) in deleted_uids:
                raw["build_player_uid"] = "00000000-0000-0000-0000-000000000000"
            stage_id = raw.get("stage_instance_id_belong_to", {})
            if isinstance(stage_id, dict):
                stage_guid = stage_id.get("id")
                if stage_guid and normalize_uid(stage_guid) in deleted_uids:
                    stage_id["id"] = "00000000-0000-0000-0000-000000000000"
        except Exception:
            pass

    # CharacterContainerSaveData — clear player_uid in slots
    for cont in wsd.get("CharacterContainerSaveData", {}).get("value", []):
        try:
            for slot in cont["value"]["Slots"]["value"]["values"]:
                puid = slot.get("RawData", {}).get("value", {}).get("player_uid")
                if puid and normalize_uid(puid) in deleted_uids:
                    slot["RawData"]["value"]["player_uid"] = "00000000-0000-0000-0000-000000000000"
        except Exception:
            pass

    # Group individual_character_handle_ids
    for g in wsd.get("GroupSaveDataMap", {}).get("value", []):
        try:
            raw = g["value"]["RawData"]["value"]
            handles = raw.get("individual_character_handle_ids", [])
            if not handles:
                continue
            raw["individual_character_handle_ids"] = [
                h for h in handles
                if not (isinstance(h, dict) and normalize_uid(h.get("guid", "")) in deleted_uids)
            ]
        except Exception:
            pass


def set_player_level(level_dict: dict, uid: str, new_level: int) -> bool:
    """Set a player's level (1-80) and adjust EXP."""
    if new_level < 1 or new_level > 80:
        return False

    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])

    sp_found = _find_player_sp(level_dict, uid)
    if not sp_found:
        return False

    _, _, sp_val = sp_found

    # Set level
    if "Level" not in sp_val:
        sp_val["Level"] = {}
    if "value" not in sp_val["Level"]:
        sp_val["Level"]["value"] = {}
    sp_val["Level"]["value"]["value"] = new_level

    # Set EXP to match level (simple approximation)
    # Palworld EXP table: level^3 * 10 is close enough
    total_exp = (new_level ** 3) * 10
    if "Exp" not in sp_val:
        sp_val["Exp"] = {"value": total_exp}
    else:
        sp_val["Exp"]["value"] = total_exp

    return True


def set_player_tech_points(players_dir: str, uid: str, tech_points: int, boss_tech_points: int) -> bool:
    """Set a player's TechnologyPoint and bossTechnologyPoint in their .sav."""
    gvas = _read_player_sav(players_dir, uid)
    if gvas is None:
        return False

    save_data = gvas.properties.get("SaveData", {}).get("value", {})
    if "TechnologyPoint" not in save_data:
        save_data["TechnologyPoint"] = {"id": None, "value": 0, "type": "IntProperty"}
    save_data["TechnologyPoint"]["value"] = tech_points

    if "bossTechnologyPoint" not in save_data:
        save_data["bossTechnologyPoint"] = {"id": None, "value": 0, "type": "IntProperty"}
    save_data["bossTechnologyPoint"]["value"] = boss_tech_points

    return _write_player_sav(gvas, players_dir, uid)


def set_player_stats(
    level_dict: dict,
    uid: str,
    stat_changes: dict[str, int],
    unused_stat_points: int | None = None,
) -> bool:
    """Modify a player's stat points in CharacterSaveParameterMap."""
    uid_clean = _uid_clean(uid)
    sp_found = _find_player_sp(level_dict, uid)
    if not sp_found:
        return False

    _, _, sp_val = sp_found

    # Update GotStatusPointList
    if "GotStatusPointList" in sp_val:
        for item in sp_val["GotStatusPointList"]["value"]["values"]:
            if "StatusName" in item and "StatusPoint" in item:
                sn = item["StatusName"]
                sp = item["StatusPoint"]
                if isinstance(sn, dict) and sn.get("value") in stat_changes:
                    sp["value"] = stat_changes[sn["value"]]

    # Update GotExStatusPointList
    if "GotExStatusPointList" in sp_val:
        for item in sp_val["GotExStatusPointList"]["value"]["values"]:
            if "StatusName" in item and "StatusPoint" in item:
                sn = item["StatusName"]
                sp = item["StatusPoint"]
                if isinstance(sn, dict) and sn.get("value") in stat_changes:
                    sp["value"] = stat_changes[sn["value"]]

    # Set unused points
    if "UnusedStatusPoint" in sp_val and unused_stat_points is not None:
        sp_val["UnusedStatusPoint"]["value"] = unused_stat_points

    return True


def reset_player_timestamp(level_dict: dict, uid: str) -> bool:
    """Reset a player's last-online timestamp to current game time."""
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)

    try:
        tick = wsd["GameTimeSaveData"]["value"]["RealDateTimeTicks"]["value"]
    except Exception:
        return False

    result = _find_player_in_guilds(level_dict, uid)
    if not result:
        return False

    _, raw, _ = result
    for p in raw.get("players", []):
        if _uid_clean(str(p.get("player_uid", ""))) == uid_clean:
            p.setdefault("player_info", {})["last_online_real_time"] = tick
            return True

    return False


def unlock_viewing_cage(players_dir: str, uid: str) -> bool:
    """Unlock the viewing cage for a player."""
    gvas = _read_player_sav(players_dir, uid)
    if gvas is None:
        return False

    save_data = gvas.properties.get("SaveData", {}).get("value", {})
    if "bIsViewingCageCanUse" not in save_data:
        return False
    save_data["bIsViewingCageCanUse"]["value"] = True

    return _write_player_sav(gvas, players_dir, uid)


def unlock_all_technologies(players_dir: str, uid: str) -> bool:
    """Unlock all technologies for a player by injecting all tech GUIDs."""
    from web.backend.services.data_service import load_game_data

    try:
        world_data = load_game_data("world")
        technologies = world_data.get("technology", [])
    except Exception:
        return False

    gvas = _read_player_sav(players_dir, uid)
    if gvas is None:
        return False

    save_data = gvas.properties.get("SaveData", {}).get("value", {})
    unlocked = save_data.setdefault("UnlockedRecipeTechnologyNames", {
        "id": None,
        "value": {"values": []},
        "type": "ArrayProperty",
        "array_type": "NameProperty",
    })

    existing = set(str(v) for v in unlocked.get("value", {}).get("values", []))
    added = 0
    for tech in technologies:
        tid = tech.get("id", "")
        if tid and tid not in existing:
            unlocked["value"]["values"].append(tid)
            added += 1

    return _write_player_sav(gvas, players_dir, uid)


def max_all_abilities(level_dict: dict, players_dir: str, uids: list[str]) -> bool:
    """Max all relics/abilities for given players (adapted from player_manager)."""
    from web.backend.services.data_service import load_game_data

    try:
        relic_data = load_game_data("relic_data")
        cumax = {k: v["cumulative_max"] for k, v in relic_data.items()}
        maxrank = {k: v["max_rank"] for k, v in relic_data.items()}
    except Exception:
        cumax, maxrank = {}, {}

    relic_to_status = {
        "EPalRelicType::CapturePower": "捕獲率",
        "EPalRelicType::HungerReduction": "空腹率低減",
        "EPalRelicType::SwimSpeed": "泳ぎ速度",
        "EPalRelicType::FoodDecayReduction": "食料腐敗低減",
        "EPalRelicType::JumpPower": "ジャンプ力",
        "EPalRelicType::GliderSpeed": "滑空速度",
        "EPalRelicType::ClimbSpeed": "崖登り速度",
        "EPalRelicType::StatusAilmentResist": "状態異常耐性",
        "EPalRelicType::ExpBonus": "経験値ボーナス",
        "EPalRelicType::RainbowPassiveRate": "虹パッシブ率",
        "EPalRelicType::MoveSpeed": "移動速度アップ",
        "EPalRelicType::SphereHoming": "パルスフィアホーミング",
        "EPalRelicType::StaminaReduction": "スタミナ消費軽減",
    }

    level_changed = False

    for uid in uids:
        gvas = _read_player_sav(players_dir, uid)
        if gvas is None:
            continue

        save_data = gvas.properties.get("SaveData", {}).get("value", {})
        rd = save_data.get("RecordData", {}).get("value", {})

        # Set relic map
        rmap = rd.setdefault("RelicPossessNumMap", {
            "key_type": "EnumProperty",
            "value_type": "IntProperty",
            "key_struct_type": None,
            "value_struct_type": None,
            "id": None,
            "value": [],
            "type": "MapProperty",
        })
        rmap["value"] = [{"key": rk, "value": max_val} for rk, max_val in cumax.items()]

        rd["RelicPossessNum"] = {"id": None, "value": sum(
            e.get("value", 0) for e in rmap["value"]
        ), "type": "IntProperty"}

        if rd.get("RelicBonusExpTableIndex", {}).get("value", 0) < 9999:
            rd["RelicBonusExpTableIndex"] = {"id": None, "value": 9999, "type": "IntProperty"}

        _write_player_sav(gvas, players_dir, uid)

        # Update CharacterSaveParameterMap stats
        sp_found = _find_player_sp(level_dict, uid)
        if sp_found:
            _, _, sp_val = sp_found
            sl = sp_val.setdefault("GotStatusPointList", {}).setdefault("value", {}).setdefault("values", [])
            seen = {s.get("StatusName", {}).get("value", ""): s for s in sl}
            for rk, stat_name in relic_to_status.items():
                max_val = maxrank.get(rk, 99)
                if stat_name in seen:
                    if seen[stat_name]["StatusPoint"]["value"] != max_val:
                        seen[stat_name]["StatusPoint"]["value"] = max_val
                        level_changed = True
                else:
                    sl.append({
                        "StatusName": {"id": None, "value": stat_name, "type": "NameProperty"},
                        "StatusPoint": {"id": None, "value": max_val, "type": "IntProperty"},
                    })
                    level_changed = True

    return True
