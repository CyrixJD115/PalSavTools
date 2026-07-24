
from __future__ import annotations
from pathlib import Path
from app.backend.services.palsav_rs_wrapper import decode_sav, encode_sav
from uuid import UUID
import os

from .core import (
    _NIL, _g, _k, _nu, _k_set, _map_entries, _wsd,
    _decode_level_sav, _encode_level_sav, _guild_struct, _guild_top_raw, _guild_players,
    _LazyOwnership
)
from app.backend.services import world_service


# Fix Guild — move a player to a different guild within the same save


def _apply_fix_guild_to_gvas(
    level_dict: dict,
    save_type: int,
    player_uid: str,
    target_guild_id: str,
    players_folder: str | None = None,
) -> dict:
    """Move a player to a different guild in an already-loaded dict (Rust shape)."""
    wsd = _wsd(level_dict)
    guild_map = _map_entries(wsd, "GroupSaveDataMap")
    base_list = _map_entries(wsd, "BaseCampSaveData")

    player_key = _nu(player_uid)
    target_key = _nu(target_guild_id)

    target_group = None
    origin_group = None
    found_entry = None

    for g in guild_map:
        if world_service._group_type(g) != "EPalGroupType::Guild":
            continue
        gid = _nu(g.get("key"))
        if gid == target_key:
            target_group = g
        for p in _guild_players(g):
            pu = _k(p, "player_uid")
            if pu and _nu(pu) == player_key:
                origin_group = g
                found_entry = p

    if not found_entry or not target_group or not origin_group:
        return {"success": False, "error": "Player or target guild not found"}
    if origin_group is target_group:
        return {"success": True, "message": "Player already in target guild"}

    # Remove player from origin.
    origin_pre = _g(_guild_struct(origin_group), "tail", world_service._guild_tail_key(origin_group)) or {}
    origin_players = _k(origin_pre, "players") or []
    new_players = [p for p in origin_players if _nu(_k(p, "player_uid")) != player_key]
    _k_set(origin_pre, "players", new_players)

    if not new_players:
        gid_key = origin_group.get("key")
        # Drop bases owned by the now-empty origin guild.
        _filter_in_place(
            base_list,
            lambda b: _nu(_g(b, "value", "RawData", "group_id_belong_to")) != _nu(gid_key),
        )
        _filter_in_place(guild_map, lambda x: x is not origin_group)
    else:
        admin = _nu(_k(origin_pre, "admin_player_uid"))
        if admin not in {_nu(_k(p, "player_uid")) for p in new_players}:
            _k_set(origin_pre, "admin_player_uid", _k(new_players[0], "player_uid"))

    # Add player to target.
    target_struct = _guild_struct(target_group)
    target_pre = _g(target_struct, "tail", world_service._guild_tail_key(target_group)) or {}
    tplayers = _k(target_pre, "players") or []
    tplayer_set = {_nu(_k(p, "player_uid")) for p in tplayers}

    if player_key not in tplayer_set:
        info = _k(found_entry, "player_info")
        if not isinstance(info, dict):
            info = {}
            _k_set(found_entry, "player_info", info)
        if not _k(info, "player_name"):
            _k_set(info, "player_name", "Player")
        if _k(info, "last_online_real_time") is None:
            _k_set(info, "last_online_real_time", 0)
        tplayers.append(found_entry)
    _k_set(target_pre, "players", tplayers)
    _k_set(found_entry, "_u8_flag", 3)

    if _nu(_k(target_pre, "admin_player_uid")) not in tplayer_set:
        _k_set(target_pre, "admin_player_uid", _k(found_entry, "player_uid"))
        _k_set(found_entry, "_u8_flag", 1)

    new_gid_obj = _k(_guild_top_raw(target_group), "group_id") or _NIL

    # Update group_id on the player's character entries.
    cmap = _map_entries(wsd, "CharacterSaveParameterMap")
    moved_instances: set[str] = set()
    ownership = _LazyOwnership.build(
        cmap, _map_entries(wsd, "CharacterContainerSaveData"),
    )
    for character in cmap:
        try:
            sp = world_service._pal_entry_raw(character)
            key = _g(character, "key") or {}
            inst_val = _k(key, "InstanceId")
            inst_str = str(inst_val) if inst_val else ""
            if not inst_str:
                continue
            is_player_char = (
                bool(_k(sp, "IsPlayer"))
                and _nu(_k(key, "PlayerUId")) == player_key
            )
            if not is_player_char:
                owner = _k(sp, "OwnerPlayerUId")
                eff = ownership.get_effective_owner(inst_val, owner)
                if _nu(eff) != player_key:
                    continue
            top = _g(character, "value", "RawData") or {}
            _k_set(top, "group_id", new_gid_obj)
            moved_instances.add(inst_str)
            if _k(sp, "OwnerPlayerUId") is not None:
                _k_set(sp, "OwnerPlayerUId", player_uid)
        except Exception:
            pass

    # Clean up origin guild handles + add to target.
    origin_top = _guild_top_raw(origin_group)
    origin_handles = _k(origin_top, "individual_character_handle_ids")
    if isinstance(origin_handles, list):
        _k_set(origin_top, "individual_character_handle_ids", _dedup_handles(
            [h for h in origin_handles
             if _nu(_k(h, "instance_id")) not in moved_instances]
        ))

    target_top = _guild_top_raw(target_group)
    target_handles = _k(target_top, "individual_character_handle_ids")
    if not isinstance(target_handles, list):
        target_handles = []
        _k_set(target_top, "individual_character_handle_ids", target_handles)
    target_handles[:] = _dedup_handles(target_handles)
    seen = {_nu(_k(h, "instance_id")) for h in target_handles}
    for inst_str in moved_instances:
        if _nu(inst_str) not in seen:
            target_handles.append({"guid": _NIL, "instance_id": inst_str})
            seen.add(_nu(inst_str))

    # Update player .sav GroupId.
    if players_folder:
        try:
            player_sav = Path(players_folder) / f"{_nu(player_uid).upper()}.sav"
            if player_sav.exists():
                pdict, pst = decode_sav(player_sav.read_bytes())
                psd = _g(pdict, "root", "properties", "SaveData") or {}
                _k_set(psd, "GroupId", new_gid_obj)
                player_sav.write_bytes(encode_sav(pdict, pst))
        except Exception:
            pass

    return {
        "success": True, "player_uid": player_uid,
        "target_guild_id": target_key, "pals_moved": len(moved_instances),
    }


def _dedup_handles(handles: list) -> list:
    seen = set()
    out = []
    for h in handles:
        inst = _nu(_k(h, "instance_id"))
        if inst and inst not in seen:
            seen.add(inst)
            out.append(h)
    return out


def _filter_in_place(lst: list, keep) -> None:
    lst[:] = [x for x in lst if keep(x)]


def fix_guild(
    level_sav_path: str,
    player_uid: str,
    target_guild_id: str,
) -> dict:
    """Move a player to a different guild in a Level.sav on disk."""
    level_dict, save_type = _decode_level_sav(level_sav_path)
    players_folder = str(Path(level_sav_path).parent / "Players")
    result = _apply_fix_guild_to_gvas(
        level_dict, save_type, player_uid, target_guild_id, players_folder,
    )
    if result.get("success"):
        _encode_level_sav(level_dict, save_type, level_sav_path)
    return result


