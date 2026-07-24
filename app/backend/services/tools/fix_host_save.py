
from __future__ import annotations
from pathlib import Path
from app.backend.services.palsav_rs_wrapper import decode_sav, encode_sav
from .core import (
    _NIL, _g, _k, _nu, _fmt, _k_set, _map_entries, _wsd,
    _decode_level_sav, _encode_level_sav, _guild_struct, _guild_top_raw
)
from app.backend.services import world_service


# Fix Host Save — GUID swap between two players in the same save


def _deep_swap(data, old_uid: str, new_uid: str) -> None:
    """Recursively swap old_uid <-> new_uid in owner fields (Rust shape)."""
    if isinstance(data, dict):
        for k in ("OwnerPlayerUId", "owner_player_uid", "build_player_uid", "private_lock_player_uid"):
            v = data.get(k)
            if v == old_uid:
                data[k] = new_uid
            elif v == new_uid:
                data[k] = old_uid
        for x in data.values():
            _deep_swap(x, old_uid, new_uid)
    elif isinstance(data, list):
        for i in data:
            _deep_swap(i, old_uid, new_uid)


def _copy_dps_file(players_folder: str, src_uid: str, tgt_uid: str, target_pal_storage_id) -> int:
    """Copy _dps.sav from source to target, rewriting container IDs (Rust shape)."""
    src_file = Path(players_folder) / f"{_nu(src_uid).upper()}_dps.sav"
    tgt_file = Path(players_folder) / f"{_nu(tgt_uid).upper()}_dps.sav"
    if not src_file.exists():
        return 0
    try:
        dps, save_type = decode_sav(src_file.read_bytes())
        updated = 0
        sp_array = _g(dps, "root", "properties", "SaveParameterArray") or []
        for pal_entry in (sp_array if isinstance(sp_array, list) else []):
            sp = _k(pal_entry, "SaveParameter") or pal_entry
            slot_id = _g(sp, "SlotId")
            id_obj = _g(slot_id, "ContainerId", "ID")
            if id_obj is not None:
                _k_set(_g(slot_id, "ContainerId"), "ID", target_pal_storage_id)
                updated += 1
        tgt_file.write_bytes(encode_sav(dps, save_type))
        return updated
    except Exception:
        import shutil
        shutil.copy2(str(src_file), str(tgt_file))
        return 0


def _apply_fix_host_save_to_gvas(
    level_dict: dict,
    save_type: int,
    players_folder: str | None,
    old_uid: str,
    new_uid: str,
    guild_fix: bool = True,
) -> dict:
    """Swap two players' GUIDs in an already-loaded dict (Rust shape)."""
    wsd = _wsd(level_dict)
    old_fmt = _fmt(old_uid)
    new_fmt = _fmt(new_uid)

    cspm = _map_entries(wsd, "CharacterSaveParameterMap")
    old_inst = None
    new_inst = None
    for e in cspm:
        key = _g(e, "key") or {}
        puid = _k(key, "PlayerUId")
        inst = _k(key, "InstanceId")
        if _nu(puid) == _nu(old_fmt):
            old_inst = inst
        elif _nu(puid) == _nu(new_fmt):
            new_inst = inst

    if old_inst is None or new_inst is None:
        return {"success": False, "error": "Could not find one or both player entries in CharacterSaveParameterMap"}

    # Swap PlayerUId on the two player entries (key by InstanceId).
    for e in cspm:
        key = e.get("key")
        if not isinstance(key, dict):
            continue
        inst_val = _k(key, "InstanceId")
        if inst_val == old_inst:
            _k_set(key, "PlayerUId", new_fmt)
        elif inst_val == new_inst:
            _k_set(key, "PlayerUId", old_fmt)

    if guild_fix:
        for g in _map_entries(wsd, "GroupSaveDataMap"):
            if world_service._group_type(g) != "EPalGroupType::Guild":
                continue
            top = _guild_top_raw(g)
            gstruct = _guild_struct(g)
            pre = _g(gstruct, "tail", world_service._guild_tail_key(g)) or {}
            # Swap handles.
            for h in (_k(top, "individual_character_handle_ids") or []):
                inst_id = _k(h, "instance_id")
                if inst_id == old_inst:
                    _k_set(h, "guid", new_fmt)
                elif inst_id == new_inst:
                    _k_set(h, "guid", old_fmt)
            # Swap admin.
            admin = _k(pre, "admin_player_uid")
            if _nu(admin) == _nu(old_fmt):
                _k_set(pre, "admin_player_uid", new_fmt)
            elif _nu(admin) == _nu(new_fmt):
                _k_set(pre, "admin_player_uid", old_fmt)
            # Swap member player_uid.
            for p in (_k(pre, "players") or []):
                pu = _k(p, "player_uid")
                if _nu(pu) == _nu(old_fmt):
                    _k_set(p, "player_uid", new_fmt)
                elif _nu(pu) == _nu(new_fmt):
                    _k_set(p, "player_uid", old_fmt)

    # Deep swap across all save data (both dashed and no-dash forms).
    _deep_swap(wsd, old_fmt, new_fmt)
    _deep_swap(wsd, _nu(old_fmt), _nu(new_fmt))

    # DPS file handling.
    target_pal_storage_id = None
    if players_folder:
        tgt_path = Path(players_folder) / f"{_nu(new_fmt).upper()}.sav"
        if tgt_path.exists():
            try:
                tgt_dict, _ = decode_sav(tgt_path.read_bytes())
                tgt_sd = _g(tgt_dict, "root", "properties", "SaveData") or {}
                target_pal_storage_id = _g(tgt_sd, "PalStorageContainerId", "ID")
            except Exception:
                target_pal_storage_id = None

    dps_updated = 0
    if players_folder and target_pal_storage_id:
        dps_updated = _copy_dps_file(players_folder, old_fmt, new_fmt, target_pal_storage_id) or 0

    return {
        "success": True,
        "old_uid": old_fmt,
        "new_uid": new_fmt,
        "dps_updated": dps_updated,
    }


def fix_host_save(
    level_sav_path: str,
    old_uid: str,
    new_uid: str,
    guild_fix: bool = True,
) -> dict:
    """Swap two players' GUIDs in a Level.sav on disk (file-path wrapper)."""
    level_dict, save_type = _decode_level_sav(level_sav_path)
    players_folder = str(Path(level_sav_path).parent / "Players")
    result = _apply_fix_host_save_to_gvas(
        level_dict, save_type, players_folder, old_uid, new_uid, guild_fix,
    )
    if result.get("success"):
        _encode_level_sav(level_dict, save_type, level_sav_path)
        old_fmt = _fmt(old_uid)
        new_fmt = _fmt(new_uid)
        players_dir = Path(level_sav_path).parent / "Players"
        src_path = players_dir / f"{_nu(old_fmt).upper()}.sav"
        dst_path = players_dir / f"{_nu(new_fmt).upper()}.sav"
        tmp_path = players_dir / f"{_nu(old_fmt).upper()}.sav.tmp_swap"
        if src_path.exists():
            src_path.rename(tmp_path)
        if dst_path.exists():
            dst_path.rename(src_path)
        if tmp_path.exists():
            tmp_path.rename(dst_path)
    return result


