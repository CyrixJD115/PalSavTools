
from __future__ import annotations
import os
from pathlib import Path
from uuid import UUID

from app.backend.services.palsav_rs_wrapper import decode_sav, encode_sav
from app.backend.services import world_service
from .core import (
    _NIL, _g, _k, _nu, _k_set, _map_entries, _wsd,
    _decode_level_sav, _encode_level_sav, _guild_struct, _guild_top_raw, _guild_players,
    _LazyOwnership
)


# Character Transfer — cross-save player migration (Rust shape)


# Headless pal-data helpers (pure dict logic, no Qt).
_PAL_BASE_DATA_CACHE: dict = {}


def _load_pal_base_data() -> dict:
    if _PAL_BASE_DATA_CACHE:
        return _PAL_BASE_DATA_CACHE
    try:
        from app.backend.services.data_service import load_game_data
        data = load_game_data("characters")
        for p in data.get("pals", []):
            a = p.get("asset", "").lower()
            if a:
                _PAL_BASE_DATA_CACHE[a] = p
        for n in data.get("npcs", []):
            a = n.get("asset", "").lower()
            if a and a not in _PAL_BASE_DATA_CACHE:
                _PAL_BASE_DATA_CACHE[a] = n
    except Exception:
        pass
    return _PAL_BASE_DATA_CACHE


def get_pal_base_data(cid: str | None) -> dict | None:
    if not cid:
        return None
    cache = _load_pal_base_data()
    cid_lower = cid.lower()
    entry = cache.get(cid_lower)
    if entry:
        return entry
    normalized = cid_lower.replace("boss_", "").replace("b_o_s_s_", "")
    entry = cache.get(normalized)
    if entry:
        return entry
    for prefix in ("gym_", "tower_", "raid_", "predator_"):
        prefixed = f"{prefix}{normalized}"
        if prefixed in cache:
            return cache[prefixed]
    for ckey, centry in cache.items():
        if normalized in ckey or ckey in normalized:
            return centry
    return None


_FRIENDSHIP_THRESHOLDS: list[int] | None = None


def _ensure_friendship_thresholds() -> list[int]:
    global _FRIENDSHIP_THRESHOLDS
    if _FRIENDSHIP_THRESHOLDS is not None:
        return _FRIENDSHIP_THRESHOLDS
    _FRIENDSHIP_THRESHOLDS = []
    try:
        from app.backend.services.data_service import load_game_data
        data = load_game_data("friendship")
        entries = []
        for v in data.values():
            r = v.get("FriendshipRank", -1)
            if r >= 0:
                entries.append((r, v.get("RequiredPoint", 0)))
        entries.sort()
        _FRIENDSHIP_THRESHOLDS = [pt for _, pt in entries]
    except Exception:
        _FRIENDSHIP_THRESHOLDS = [0, 6000, 13000, 21000, 30000, 40000, 55000, 80000, 110000, 150000, 200000]
    return _FRIENDSHIP_THRESHOLDS


def _fast_deepcopy(obj):
    import pickle
    return pickle.loads(pickle.dumps(obj, -1))


def _extract_value(data, key, default=None):
    """Read a SaveParameter field that may be bare or wrapped (Rust shape: bare)."""
    v = _k(data, key)
    if isinstance(v, dict):
        v = _k(v, "value", default)
    return v if v is not None else default


def _scan_source_pals(source_wsd: dict, source_player_sd: dict, source_player_uid: str):
    """Scan source Level for a player's owned pals (Rust shape)."""
    try:
        pal_ctr = _g(source_player_sd, "PalStorageContainerId", "ID")
        oto_ctr = _g(source_player_sd, "OtomoCharacterContainerId", "ID")
    except Exception:
        return []
    pal_ctr_s = _nu(pal_ctr) if pal_ctr else ""
    oto_ctr_s = _nu(oto_ctr) if oto_ctr else ""
    char_map = _map_entries(source_wsd, "CharacterSaveParameterMap")
    containers = _map_entries(source_wsd, "CharacterContainerSaveData")
    ownership = _LazyOwnership.build(char_map, containers)

    pals = []
    for ch in char_map:
        try:
            sp = world_service._pal_entry_raw(ch)
            owner = _k(sp, "OwnerPlayerUId")
            inst_id = _g(ch, "key", "InstanceId")
            if not ownership.belongs_to_player(inst_id, owner, source_player_uid):
                continue
            slot_cid = _g(sp, "SlotId", "ContainerId", "ID")
            slot_cid_s = _nu(slot_cid) if slot_cid else ""
            slot_idx = _g(sp, "SlotId", "SlotIndex") or 0
            if slot_cid_s == pal_ctr_s:
                is_palbox = True
            elif slot_cid_s == oto_ctr_s:
                is_palbox = False
            else:
                continue
            group_id = _g(ch, "value", "RawData", "group_id") or ""
            pals.append({
                "source_entry": ch, "save_parameter": sp,
                "instance_id": str(inst_id) if inst_id else "",
                "is_palbox": is_palbox, "slot_index": slot_idx,
                "group_id": group_id,
            })
        except Exception:
            continue
    return pals


def _migrate_pal_to_target(
    pal_data: dict, target_uid: str, target_wsd: dict,
    target_player_sd: dict, target_guild_id: str,
) -> bool:
    """Migrate one pal from source to target save (Rust shape).

    Copies the source pal entry wholesale (preserving all decoded fields +
    trailing_bytes), reassigns owner/slot/guild, and appends it to the target.
    """
    try:
        pal_ctr = _g(target_player_sd, "PalStorageContainerId", "ID")
        oto_ctr = _g(target_player_sd, "OtomoCharacterContainerId", "ID")
        container_id = pal_ctr if pal_data["is_palbox"] else oto_ctr
    except Exception:
        return False
    if not container_id:
        return False

    src_sp = pal_data["save_parameter"]
    cid = _extract_value(src_sp, "CharacterID", "")
    nick = _extract_value(src_sp, "NickName", "")
    slot_idx = pal_data["slot_index"]

    # Deep-copy the whole source entry and reassign identity fields.
    skeleton = _fast_deepcopy(pal_data["source_entry"])
    new_instance = str(UUID(bytes=os.urandom(16))).upper()
    skey = skeleton.get("key")
    if isinstance(skey, dict):
        _k_set(skey, "InstanceId", new_instance)
        _k_set(skey, "PlayerUId", target_uid)
    skel_sp = world_service._pal_entry_raw(skeleton)
    _k_set(skel_sp, "OwnerPlayerUId", target_uid)
    slot_id = _g(skel_sp, "SlotId") or {}
    _k_set(_g(slot_id, "ContainerId"), "ID", container_id)
    _k_set(slot_id, "SlotIndex", slot_idx)
    skel_top = _g(skeleton, "value", "RawData") or {}
    _k_set(skel_top, "group_id", target_guild_id)
    # Sanitize HP/sanity/stomach.
    base_data = get_pal_base_data(cid)
    max_stomach = (base_data.get("stats", {}).get("max_full_stomach", 300) if base_data else 300)
    _k_set(skel_sp, "FullStomach", float(max_stomach))
    _k_set(skel_sp, "SanityValue", 100.0)
    # Drop stale transient keys.
    for cleanup_key in ("MapObjectConcreteInstanceIdAssignedToExpedition",):
        for form in (cleanup_key, cleanup_key + "_0"):
            skel_sp.pop(form, None)

    _map_entries(target_wsd, "CharacterSaveParameterMap").append(skeleton)

    # Add slot to the target character container.
    char_containers = _map_entries(target_wsd, "CharacterContainerSaveData")
    found = False
    for cont in char_containers:
        ckey = cont.get("key")
        cont_id = _k(ckey, "ID") if isinstance(ckey, dict) else ckey
        if _nu(cont_id) == _nu(container_id):
            slots = _g(cont, "value", "Slots")
            if not isinstance(slots, list):
                slots = []
                _k_set(_g(cont, "value"), "Slots", slots)
            slots.append({
                "SlotIndex_0": slot_idx,
                "RawData_0": {
                    "player_uid": _NIL,
                    "instance_id": new_instance,
                    "permission_tribe_id": 0,
                    "trailing_bytes": [0, 0, 0, 0],
                },
            })
            found = True
            break
    if not found:
        char_containers.append({
            "key": {"ID_0": container_id},
            "value": {
                "SlotNum_0": slot_idx + 1,
                "Slots_0": [{
                    "SlotIndex_0": slot_idx,
                    "RawData_0": {
                        "player_uid": _NIL, "instance_id": new_instance,
                        "permission_tribe_id": 0, "trailing_bytes": [0, 0, 0, 0],
                    },
                }],
            },
        })

    # Add to target guild handles.
    for g in _map_entries(target_wsd, "GroupSaveDataMap"):
        top = _guild_top_raw(g)
        if _nu(_k(top, "group_id")) == _nu(target_guild_id):
            handles = _k(top, "individual_character_handle_ids")
            if not isinstance(handles, list):
                handles = []
                _k_set(top, "individual_character_handle_ids", handles)
            handles.append({"guid": _NIL, "instance_id": new_instance})
            break

    return True


def _transfer_character_to_target(
    source_wsd: dict, target_wsd: dict, source_player_sd: dict,
    target_player_sd: dict, source_player_uid: str, target_player_uid: str,
) -> bool:
    """Copy source player's character entry to target save (Rust shape)."""
    host_instance_id = _g(source_player_sd, "IndividualId", "InstanceId")
    if not host_instance_id:
        return False

    exported = None
    for character in _map_entries(source_wsd, "CharacterSaveParameterMap"):
        key = _g(character, "key") or {}
        uid = _k(key, "PlayerUId")
        inst = _k(key, "InstanceId")
        if _nu(uid) == _nu(source_player_uid) and _nu(inst) == _nu(host_instance_id):
            exported = character
            break
    if not exported:
        return False

    targ_instance_id = _g(target_player_sd, "IndividualId", "InstanceId")
    char_list = _map_entries(target_wsd, "CharacterSaveParameterMap")
    updated = False
    for c in char_list:
        key = _g(c, "key") or {}
        if _nu(_k(key, "PlayerUId")) == _nu(target_player_uid):
            sp = world_service._pal_entry_raw(c)
            if not _k(sp, "IsPlayer"):
                continue
            c["value"] = _fast_deepcopy(exported["value"])
            _k_set(key, "InstanceId", targ_instance_id)
            nsp = world_service._pal_entry_raw(c)
            if _k(nsp, "OwnerPlayerUId") is not None:
                _k_set(nsp, "OwnerPlayerUId", target_player_uid)
            updated = True
            break
    if not updated:
        new_entry = _fast_deepcopy(exported)
        nkey = _g(new_entry, "key") or {}
        _k_set(nkey, "PlayerUId", target_player_uid)
        _k_set(nkey, "InstanceId", targ_instance_id)
        char_list.append(new_entry)

    # Copy associated containers.
    src_char_ids = {
        _g(source_player_sd, "PalStorageContainerId", "ID"),
        _g(source_player_sd, "OtomoCharacterContainerId", "ID"),
    }
    inv = _g(source_player_sd, "InventoryInfo") or {}
    src_item_ids = {
        _g(inv, "CommonContainerId", "ID"),
        _g(inv, "EssentialContainerId", "ID"),
        _g(inv, "WeaponLoadOutContainerId", "ID"),
        _g(inv, "PlayerEquipArmorContainerId", "ID"),
        _g(inv, "FoodEquipContainerId", "ID"),
    }
    drop = _g(inv, "DropSlotContainerId", "ID")
    if drop:
        src_item_ids.add(drop)
    src_char_ids.discard(None)
    src_item_ids.discard(None)

    for container_key, src_ids in (
        ("CharacterContainerSaveData", src_char_ids),
        ("ItemContainerSaveData", src_item_ids),
    ):
        existing = {
            _k(c.get("key"), "ID") if isinstance(c.get("key"), dict) else c.get("key")
            for c in _map_entries(target_wsd, container_key)
        }
        existing = {_nu(e) if e else "" for e in existing}
        for c in _map_entries(source_wsd, container_key):
            cid = c.get("key")
            cid_val = _k(cid, "ID") if isinstance(cid, dict) else cid
            if cid_val and _nu(cid_val) in {_nu(s) for s in src_ids} and _nu(cid_val) not in existing:
                _map_entries(target_wsd, container_key).append(_fast_deepcopy(c))
    return True


def _transfer_tech_and_data(source_player_sd: dict, target_player_sd: dict) -> bool:
    """Copy technology and appearance data between player save datas (Rust shape)."""
    tech_keys = ["SkillMap", "PlayerTechData", "player_tech_data",
                 "PlayerTechnologyData", "PlayerTechnologyData2",
                 "TechnologyPoint", "TechnologyPoint2",
                 "BossTechnologyPoint", "AdditionalTechnologyPoint"]
    appearance_keys = ["PlayerCharacterAppearanceData", "PlayerCustomName",
                       "PlayerCustomNameCharacterName", "PlayerCustomNameCharacterName2",
                       "PlayerCustomNameCharacterName3", "PlayerInputAllowDieData"]
    record_keys = ["RecordData", "PlayerCaptureRecordData", "PlayerCaptureRecordData2",
                   "PlayerDefeatBossRecordData", "PlayerDiscoverMapData",
                   "PlayerExploreMapData", "PlayerExploreMapData2", "PlayerMapPingData",
                   "PlayerDungeonData", "PlayerDungeonData2",
                   "BuildObjectMapData", "SkyPresetData", "PlayerSpawnLocationData"]
    for k in tech_keys + appearance_keys + record_keys:
        # Match either bare or _0 form.
        for form in (k, k + "_0"):
            if form in source_player_sd:
                target_player_sd[form] = _fast_deepcopy(source_player_sd[form])
                break
    return True


def _transfer_guild_to_target(
    target_wsd: dict, target_player_sd: dict, source_player_uid: str,
    target_player_uid: str, source_guild_dict: dict,
) -> bool:
    """Copy guild membership from source player to target save (Rust shape)."""
    guilds = _map_entries(target_wsd, "GroupSaveDataMap")
    if not source_guild_dict:
        return False

    target_guild = None
    for g in guilds:
        if any(_nu(_k(p, "player_uid")) == _nu(target_player_uid)
               for p in _guild_players(g)):
            target_guild = g
            break

    source_player = None
    source_entry = None
    for g in source_guild_dict.values():
        for p in _guild_players(g):
            if _nu(_k(p, "player_uid")) == _nu(source_player_uid):
                source_player = _fast_deepcopy(p)
                source_entry = g
                break
        if source_entry:
            break
    if source_entry is None:
        return False

    if source_player:
        _k_set(source_player, "player_uid", target_player_uid)
        info = _k(source_player, "player_info")
        if isinstance(info, dict):
            _k_set(info, "last_online_real_time", 0)

    if target_guild:
        tstruct = _guild_struct(target_guild)
        tpre = _g(tstruct, "tail", world_service._guild_tail_key(target_guild)) or {}
        players = _k(tpre, "players") or []
        kept = [p for p in players if _nu(_k(p, "player_uid")) != _nu(target_player_uid)]
        if source_player:
            kept.append(source_player)
        _k_set(tpre, "players", kept)
        admin = _k(tpre, "admin_player_uid")
        if _nu(admin) == _nu(source_player_uid):
            _k_set(tpre, "admin_player_uid", target_player_uid)
        new_gid = _k(_guild_top_raw(target_guild), "group_id")
        if new_gid:
            _k_set(target_player_sd, "GroupId", new_gid)
        return True

    # Create a new guild cloned from the source.
    cloned = _fast_deepcopy(source_entry)
    cloned["key"] = str(UUID(bytes=os.urandom(16)))
    ctop = _guild_top_raw(cloned)
    cstruct = _guild_struct(cloned)
    new_gid = str(UUID(bytes=os.urandom(16)))
    _k_set(ctop, "group_id", new_gid)
    _k_set(cstruct, "guild_name", "Transferred Guild")
    cpre = _g(cstruct, "tail", world_service._guild_tail_key(cloned)) or {}
    _k_set(cpre, "players", [source_player] if source_player else [{
        "player_uid_0": target_player_uid,
        "player_info_0": {"last_online_real_time_0": 0, "player_name_0": "Player"},
    }])
    _k_set(cpre, "admin_player_uid", target_player_uid)
    player_inst_id = _g(target_player_sd, "IndividualId", "InstanceId")
    _k_set(ctop, "individual_character_handle_ids",
           [{"guid": _NIL, "instance_id": str(player_inst_id) if player_inst_id else ""}])
    guilds.append(cloned)
    _k_set(target_player_sd, "GroupId", new_gid)
    return True


def _transfer_pals_to_target(
    source_wsd: dict, target_wsd: dict, source_player_sd: dict,
    target_player_sd: dict, source_player_uid: str, target_player_uid: str,
    target_guild_id,
) -> bool:
    """Migrate all owned pals from source player to target save (Rust shape)."""
    if not target_guild_id:
        target_guild_id = _NIL

    # Remove existing pal entries for the target player.
    removed: set[str] = set()
    cmap = _map_entries(target_wsd, "CharacterSaveParameterMap")
    kept = []
    for ch in cmap:
        sp = world_service._pal_entry_raw(ch)
        owner = _k(sp, "OwnerPlayerUId")
        if owner and _nu(owner) == _nu(target_player_uid):
            inst = _g(ch, "key", "InstanceId")
            removed.add(_nu(inst) if inst else "")
            continue
        kept.append(ch)
    cmap[:] = kept

    # Clean container slots.
    t_pal_id = _g(target_player_sd, "PalStorageContainerId", "ID")
    t_oto_id = _g(target_player_sd, "OtomoCharacterContainerId", "ID")
    for cont in _map_entries(target_wsd, "CharacterContainerSaveData"):
        ckey = cont.get("key")
        cid = _k(ckey, "ID") if isinstance(ckey, dict) else ckey
        if cid and _nu(cid) in {_nu(t_pal_id), _nu(t_oto_id)}:
            slots = _g(cont, "value", "Slots")
            if isinstance(slots, list):
                slots[:] = [s for s in slots
                            if _nu(_g(s, "RawData", "instance_id")) not in removed]

    # Clean target guild handles.
    for entry in _map_entries(target_wsd, "GroupSaveDataMap"):
        top = _guild_top_raw(entry)
        if _nu(_k(top, "group_id")) == _nu(target_guild_id):
            handles = _k(top, "individual_character_handle_ids")
            if isinstance(handles, list):
                _k_set(top, "individual_character_handle_ids", [
                    h for h in handles
                    if _nu(_k(h, "instance_id")) not in removed
                ])

    source_pals = _scan_source_pals(source_wsd, source_player_sd, source_player_uid)
    for pal_data in source_pals:
        if not _migrate_pal_to_target(
            pal_data, target_player_uid, target_wsd,
            target_player_sd, target_guild_id,
        ):
            return False
    return True


def _sync_player_timestamps(target_wsd: dict, target_player_uid: str, world_tick: int) -> None:
    """Sync player timestamps in target save (Rust shape)."""
    if not world_tick:
        return
    t_uid = _nu(target_player_uid)
    for char in _map_entries(target_wsd, "CharacterSaveParameterMap"):
        key = _g(char, "key") or {}
        if _nu(_k(key, "PlayerUId")) == t_uid:
            sp = world_service._pal_entry_raw(char)
            if _k(sp, "LastOnlineRealTime") is not None:
                _k_set(sp, "LastOnlineRealTime", world_tick)
    for gdata in _map_entries(target_wsd, "GroupSaveDataMap"):
        pre = _g(_guild_struct(gdata), "tail", world_service._guild_tail_key(gdata)) or {}
        for p_info in (_k(pre, "players") or []):
            if _nu(_k(p_info, "player_uid")) == t_uid:
                info = _k(p_info, "player_info")
                if isinstance(info, dict):
                    _k_set(info, "last_online_real_time", world_tick)


def _sync_dynamic_containers(source_wsd: dict, target_wsd: dict) -> None:
    """Merge dynamic item containers from source to target (Rust shape)."""
    src_items = _map_entries(source_wsd, "DynamicItemSaveData")
    tgt_items = _map_entries(target_wsd, "DynamicItemSaveData")
    tgt_by_id: dict = {}
    for item in tgt_items:
        lid = _g(item, "RawData", "id", "local_id_in_created_world")
        if lid:
            tgt_by_id[_nu(lid)] = item
    for item in src_items:
        lid = _g(item, "RawData", "id", "local_id_in_created_world")
        if lid:
            tgt_by_id[_nu(lid)] = item
    tgt_items[:] = list(tgt_by_id.values())


def _load_player_sd_from_dir(players_dir: Path, uid: str) -> dict | None:
    uid_str = str(uid).upper()
    for cand in (players_dir / f"{uid_str}.sav",
                 players_dir / f"{uid_str.replace('-', '')}.sav"):
        if cand.exists():
            try:
                pdict, _ = decode_sav(cand.read_bytes())
                return _g(pdict, "root", "properties", "SaveData") or {}
            except Exception:
                return None
    return None


def character_transfer(
    source_sav_path: str,
    target_sav_path: str,
    source_player_uid: str,
    target_player_uid: str | None = None,
    steps: dict | None = None,
) -> dict:
    """Transfer a character from one save to another (Rust shape).

    ``steps`` controls which aspects to transfer (default: all True except
    ``inventory`` which needs PlayerInventory, desktop-only).
    """
    if steps is None:
        steps = {"character": True, "tech_data": True, "inventory": False,
                 "guild": True, "pals": True, "dynamics": True, "timestamps": True}
    if not target_player_uid:
        target_player_uid = source_player_uid

    src_dict, src_st = _decode_level_sav(source_sav_path)
    src_wsd = _wsd(src_dict)
    tgt_dict, tgt_st = _decode_level_sav(target_sav_path)
    tgt_wsd = _wsd(tgt_dict)

    src_players_dir = Path(source_sav_path).parent / "Players"
    tgt_players_dir = Path(target_sav_path).parent / "Players"

    source_player_sd = _load_player_sd_from_dir(src_players_dir, source_player_uid)
    target_player_sd = _load_player_sd_from_dir(tgt_players_dir, target_player_uid)
    if not source_player_sd:
        return {"success": False, "error": f"Source player .sav not found for {source_player_uid}"}
    if not target_player_sd:
        return {"success": False, "error": f"Target player .sav not found for {target_player_uid}"}

    # Source guild dict.
    source_guild_dict: dict[str, dict] = {}
    for g in _map_entries(src_wsd, "GroupSaveDataMap"):
        if world_service._group_type(g) == "EPalGroupType::Guild":
            gid = _k(_guild_top_raw(g), "group_id")
            if gid:
                source_guild_dict[str(gid)] = g

    target_guild_id = _NIL
    for g in _map_entries(tgt_wsd, "GroupSaveDataMap"):
        if any(_nu(_k(p, "player_uid")) == _nu(target_player_uid)
               for p in _guild_players(g)):
            target_guild_id = _k(_guild_top_raw(g), "group_id") or _NIL
            break

    target_world_tick = world_service.get_tick(tgt_wsd)

    if steps.get("character"):
        if not _transfer_character_to_target(
            src_wsd, tgt_wsd, source_player_sd, target_player_sd,
            source_player_uid, target_player_uid,
        ):
            return {"success": False, "error": "Character transfer failed"}
    if steps.get("tech_data"):
        _transfer_tech_and_data(source_player_sd, target_player_sd)
    if steps.get("guild"):
        if not _transfer_guild_to_target(
            tgt_wsd, target_player_sd, source_player_uid, target_player_uid,
            source_guild_dict,
        ):
            return {"success": False, "error": "Guild transfer failed"}
    if steps.get("pals"):
        if not _transfer_pals_to_target(
            src_wsd, tgt_wsd, source_player_sd, target_player_sd,
            source_player_uid, target_player_uid, target_guild_id,
        ):
            return {"success": False, "error": "Pal transfer failed"}
    if steps.get("dynamics"):
        _sync_dynamic_containers(src_wsd, tgt_wsd)
    if steps.get("timestamps"):
        _sync_player_timestamps(tgt_wsd, target_player_uid, target_world_tick)

    _encode_level_sav(tgt_dict, tgt_st, target_sav_path)
    _encode_level_sav(src_dict, src_st, source_sav_path)

    # Write target player .sav.
    tgt_player_path = tgt_players_dir / f"{_nu(target_player_uid).upper()}.sav"
    if tgt_player_path.exists():
        try:
            tpdict, tpst = decode_sav(tgt_player_path.read_bytes())
            tsd = _g(tpdict, "root", "properties", "SaveData")
            if tsd is not None:
                # Merge the mutated player_sd fields back.
                tsd.clear()
                tsd.update(target_player_sd)
            tgt_player_path.write_bytes(encode_sav(tpdict, tpst))
        except Exception:
            pass

    return {"success": True, "source_player": source_player_uid, "target_player": target_player_uid}


