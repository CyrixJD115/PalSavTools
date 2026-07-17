"""Player mutation operations for the web backend.

Operates on ``level_dict`` (the Rust uesave shape) for world-level player data,
and on per-player ``.sav`` dicts (also Rust shape) for tech points / viewing
cage / relic data. Player ``.sav`` files are decoded/encoded through
``palsav_rs_wrapper`` (the uesave binary).

Player .sav shape
-----------------
The interesting struct is ``root.properties.SaveData_0`` — its keys are the
player's fields (``TechnologyPoint_0``, ``bossTechnologyPoint_0``,
``RecordData_0``, ``UnlockedRecipeTechnologyNames_0``, ...). Scalars are bare;
tech-name lists are flat ``[str, ...]``.

Player .sav cache
-----------------
``LoadedSave.player_savs`` holds the decoded dicts for every ``Players/*.sav``
that was batch-decoded at load time (see ``save_service.decode_player_savs``).
``_read_player_sav`` consults that cache first, falling back to a one-off disk
decode only if the UID wasn't pre-loaded. ``_write_player_sav`` updates the
cache after writing so subsequent reads stay consistent without re-reading
disk. Both code paths route bytes through the Rust ``decode_sav``/``encode_sav``
engine — no Python parser logic is duplicated.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from app.backend.services import world_service
from app.backend.services.save_service import (
    SaveDecodeError, decode_file, encode_bytes,
)
from app.backend.services.palsav_rs_wrapper import (
    SAVE_TYPE_PLM, decode_sav, encode_sav,
)

logger = logging.getLogger(__name__)

_NIL = "00000000-0000-0000-0000-000000000000"


def _uid_clean(uid: str) -> str:
    return str(uid).replace("-", "").lower()


def _uid_upper(uid: str) -> str:
    return str(uid).replace("-", "").upper()


def normalize_uid(uid) -> str:
    if uid is None:
        return ""
    return str(uid).replace("-", "").lower()


def _loaded() -> "object | None":
    """Return the currently loaded ``LoadedSave`` if any (lazy import to avoid
    a circular import with ``app.backend.state`` at module load time)."""
    from app.backend.state import save_state
    return save_state.get()


def _is_disk_players_dir(players_dir: str | None) -> bool:
    """Whether ``players_dir`` points at a real on-disk ``Players/`` folder.

    Path-load stores the actual OS path; bundle/upload loads store sentinel
    strings (``"(unknown)"`` / ``"(bundle: …)"``) because the player saves live
    only in memory. Used by both read and write paths to decide whether a disk
    fallback / write is even possible.
    """
    if not players_dir:
        return False
    return not (
        players_dir == "(unknown)" or players_dir.startswith("(bundle:")
    )


# ---- world-level player lookup ---------------------------------------------

def _find_player_sp(level_dict: dict, uid: str) -> dict | None:
    """A player's ``SaveParameter`` struct (the Rust shape), or ``None``."""
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    for entry in world_service._map_entries(wsd, "CharacterSaveParameterMap"):
        sp = world_service._pal_entry_raw(entry)
        if not world_service._k(sp, "IsPlayer"):
            continue
        key = world_service._g(entry, "key") or {}
        if _uid_clean(str(world_service._k(key, "PlayerUId") or "")) == uid_clean:
            return sp
    return None


def _find_player_in_guilds(level_dict: dict, uid: str) -> tuple[dict, list, dict] | None:
    """``(guild_data_struct, players_list, player_entry)`` or ``None``."""
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    for g in world_service._map_entries(wsd, "GroupSaveDataMap"):
        if world_service._group_type(g) != "EPalGroupType::Guild":
            continue
        g_raw = world_service._g(g, "value", "RawData", "data", "Guild") or {}
        players = world_service._g(g_raw, "tail", "PreUpdate", "players") or []
        for p in players:
            if _uid_clean(str(world_service._k(p, "player_uid") or "")) == uid_clean:
                return g_raw, players, p
    return None


# ---- player .sav I/O --------------------------------------------------------

def _player_sav_path(players_dir: str, uid: str) -> Path:
    return Path(players_dir) / f"{_uid_upper(uid)}.sav"


def _read_player_sav(players_dir: str, uid: str) -> tuple[dict, int] | None:
    """Return ``(player_dict, save_type)`` for a player, or ``None``.

    Cache-first: if the player's ``.sav`` was batch-decoded at load time and is
    resident in ``LoadedSave.player_savs``, return that dict directly (no disk
    read, no re-decode). Otherwise fall back to a one-off disk decode through
    the Rust ``decode_sav`` engine. Decode errors are logged (not silently
    swallowed) so parser mismatches surface during migration.
    """
    uid_clean = _uid_clean(uid)

    # Cache hit — the common path now that load pre-decodes Players/.
    loaded = _loaded()
    if loaded is not None:
        cached = loaded.player_savs.get(uid_clean)
        if cached is not None:
            save_type = loaded.player_save_types.get(uid_clean, SAVE_TYPE_PLM)
            return cached, save_type

    # Cache miss — fall back to disk (e.g. save loaded before this feature,
    # or a UID whose file failed to decode at load). Bundle/upload loads have
    # no disk path, so a cache miss there is terminal.
    if not _is_disk_players_dir(players_dir):
        return None
    sav_path = _player_sav_path(players_dir, uid)
    if not sav_path.exists():
        return None
    try:
        player_dict, save_type = decode_sav(sav_path)
    except Exception as exc:
        logger.warning("Failed to decode player save %s: %s", sav_path.name, exc)
        return None
    # Populate the cache so subsequent reads of this UID stay in-memory.
    if loaded is not None:
        loaded.player_savs[uid_clean] = player_dict
        loaded.player_save_types[uid_clean] = save_type
    return player_dict, save_type


def _write_player_sav(player_dict: dict, save_type: int, players_dir: str, uid: str) -> bool:
    """Encode + write a player ``.sav`` and update the in-memory cache.

    The encode always goes through the Rust ``encode_sav`` engine. After a
    successful disk write, the cache entry is refreshed so the next read sees
    the mutated dict without re-reading the file.
    """
    uid_clean = _uid_clean(uid)
    try:
        raw = encode_sav(player_dict, save_type)
    except Exception as exc:
        logger.warning("Failed to encode player save for %s: %s", uid_clean, exc)
        return False

    written = False
    if _is_disk_players_dir(players_dir):
        sav_path = _player_sav_path(players_dir, uid)
        try:
            sav_path.write_bytes(raw)
            written = True
        except OSError as exc:
            logger.warning("Failed to write player save %s: %s", sav_path, exc)
            written = False
    else:
        # No on-disk Players/ dir (bundle upload / lone Level.sav upload). The
        # mutation lives in the in-memory cache only — still update it so a
        # follow-up read within the session reflects the change.
        written = True

    if written:
        loaded = _loaded()
        if loaded is not None:
            loaded.player_savs[uid_clean] = player_dict
            loaded.player_save_types[uid_clean] = save_type
    return written


def _save_data(player_dict: dict) -> dict:
    """The ``root.properties.SaveData`` struct of a player .sav."""
    return world_service._g(player_dict, "root", "properties", "SaveData") or {}


# ---- Public API -------------------------------------------------------------

def get_player_detail(
    level_dict: dict,
    uid: str,
    player_pal_counts: dict[str, int],
    player_levels: dict[str, int],
    players_dir: str = "",
) -> dict | None:
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    tick = world_service.get_tick(wsd)

    for g in world_service._map_entries(wsd, "GroupSaveDataMap"):
        if world_service._group_type(g) != "EPalGroupType::Guild":
            continue
        gid = str(g.get("key", ""))
        gname = world_service._gname(g)
        g_raw = world_service._g(g, "value", "RawData", "data", "Guild") or {}
        try:
            guild_level = int(world_service._k(g_raw, "base_camp_level") or 1)
        except (TypeError, ValueError):
            guild_level = 1
        admin_uid = world_service._norm_uid(
            world_service._g(g_raw, "tail", "PreUpdate", "admin_player_uid")
        ) or ""
        for p in world_service._gplayers(g):
            puid = str(world_service._k(p, "player_uid") or "")
            if _uid_clean(puid) != uid_clean:
                continue
            info = world_service._k(p, "player_info") or {}
            name = world_service._k(info, "player_name") or "Unknown"
            last = world_service._k(info, "last_online_real_time")
            elapsed = None
            if isinstance(last, (int, float)) and tick:
                elapsed = (tick - last) / 10_000_000.0
            detail = {
                "uid": puid,
                "name": name,
                "level": player_levels.get(uid_clean, 0),
                "pal_count": player_pal_counts.get(uid_clean, 0),
                "guild_id": gid,
                "guild_name": gname,
                "guild_level": guild_level,
                "is_leader": _uid_clean(puid) == _uid_clean(admin_uid),
                "last_seen_seconds": elapsed,
                "last_seen_text": world_service._fmt_last_seen(elapsed),
                "party_id": None,
                "palbox_id": None,
            }
            # Read party (OtomoCharacterContainerId) + palbox (PalStorageContainerId)
            # from the player's .sav (cache-first). Used by the pal-editor grid.
            if players_dir:
                party_id, palbox_id = _read_container_ids(players_dir, puid)
                detail["party_id"] = party_id
                detail["palbox_id"] = palbox_id
            return detail
    return None


def _read_container_ids(players_dir: str, uid: str) -> tuple[Optional[str], Optional[str]]:
    """Return ``(party_id, palbox_id)`` from the player's .sav, or ``(None, None)``.

    Ports ``tool_service``'s proven read of ``SaveData.PalStorageContainerId``
    and ``SaveData.OtomoCharacterContainerId``. Uses the cache-first
    ``_read_player_sav`` so repeated detail reads don't re-decode.
    """
    cached = _read_player_sav(players_dir, uid)
    if cached is None:
        return None, None
    pdict, _ = cached
    psd = world_service._g(pdict, "root", "properties", "SaveData") or {}
    palbox = world_service._g(psd, "PalStorageContainerId", "ID")
    party = world_service._g(psd, "OtomoCharacterContainerId", "ID")
    return (
        world_service._norm_uid(party) if party else None,
        world_service._norm_uid(palbox) if palbox else None,
    )


def rename_player(level_dict: dict, uid: str, new_name: str) -> bool:
    """Rename a player in the guild players list and the SaveParameter."""
    uid_clean = _uid_clean(uid)

    found = _find_player_in_guilds(level_dict, uid)
    if found:
        _, _, p = found
        info = world_service._k(p, "player_info")
        if isinstance(info, dict):
            _k_set(info, "player_name", new_name)

    sp = _find_player_sp(level_dict, uid)
    if sp is not None:
        _k_set(sp, "NickName", new_name)
    return True


def delete_player(level_dict: dict, uid: str) -> bool:
    """Delete a player from group data, character map, and clean references."""
    uid_clean = _uid_clean(uid)
    wsd = world_service.get_world_save_data(level_dict)
    char_map = world_service._map_entries(wsd, "CharacterSaveParameterMap")
    group_map = world_service._map_entries(wsd, "GroupSaveDataMap")
    base_list = world_service._map_entries(wsd, "BaseCampSaveData")

    # Remove the player's own character entry + any pal they own.
    char_map[:] = [
        ch for ch in char_map
        if not _char_belongs_to_player(ch, uid_clean)
    ]

    # Remove from guilds; reassign leader if needed; drop emptied guilds.
    emptied: list[dict] = []
    for g in group_map:
        if world_service._group_type(g) != "EPalGroupType::Guild":
            continue
        g_raw = world_service._g(g, "value", "RawData", "data", "Guild") or {}
        pre = world_service._g(g_raw, "tail", "PreUpdate") or {}
        players = world_service._k(pre, "players") or []
        new_players = [
            p for p in players
            if _uid_clean(str(world_service._k(p, "player_uid") or "")) != uid_clean
        ]
        if len(new_players) == len(players):
            continue
        _k_set(pre, "players", new_players)
        if not new_players:
            gid = g.get("key")
            # Drop bases owned by the now-empty guild.
            gid_clean = _uid_clean(str(gid)) if gid else ""
            base_list[:] = [
                b for b in base_list
                if world_service._s(world_service._g(b, "value", "RawData", "group_id_belong_to"))
                != gid_clean
            ]
            # Drop guild extra data.
            extra = world_service._map_entries(wsd, "GuildExtraSaveDataMap")
            extra[:] = [e for e in extra if normalize_uid(e.get("key")) != gid_clean]
            emptied.append(g)
        else:
            admin = world_service._norm_uid(world_service._k(pre, "admin_player_uid")) or ""
            if _uid_clean(admin) == uid_clean:
                _k_set(pre, "admin_player_uid",
                       str(world_service._k(new_players[0], "player_uid") or ""))

    for g in emptied:
        group_map[:] = [x for x in group_map if x is not g]

    _cleanup_player_references(wsd, {uid_clean})
    return True


def _char_belongs_to_player(ch: dict, uid_clean: str) -> bool:
    """True if a CharacterSaveParameterMap entry is the player or their pal."""
    sp = world_service._pal_entry_raw(ch)
    key = world_service._g(ch, "key") or {}
    player_uid = world_service._k(key, "PlayerUId")
    if player_uid and _uid_clean(str(player_uid)) == uid_clean:
        return True
    owner = world_service._k(sp, "OwnerPlayerUId")
    return bool(owner and _uid_clean(str(owner)) == uid_clean)


def _cleanup_player_references(wsd: dict, deleted_uids: set[str]) -> None:
    """Zero out dangling references to deleted player UIDs."""
    if not deleted_uids:
        return

    # MapObjectSaveData — clear build_player_uid / stage id.
    for obj in world_service._map_entries(wsd, "MapObjectSaveData"):
        raw = world_service._g(obj, "Model", "RawData") or {}
        build_uid = world_service._k(raw, "build_player_uid")
        if build_uid and normalize_uid(build_uid) in deleted_uids:
            _k_set(raw, "build_player_uid", _NIL)
        stage_id = world_service._k(raw, "stage_instance_id_belong_to")
        if isinstance(stage_id, dict):
            stage_guid = world_service._k(stage_id, "id")
            if stage_guid and normalize_uid(stage_guid) in deleted_uids:
                _k_set(stage_id, "id", _NIL)

    # CharacterContainerSaveData — clear player_uid in slots.
    for cont in world_service._map_entries(wsd, "CharacterContainerSaveData"):
        slots = world_service._g(cont, "value", "Slots")
        if not isinstance(slots, list):
            continue
        for slot in slots:
            raw = world_service._k(slot, "RawData") or {}
            puid = world_service._k(raw, "player_uid")
            if puid and normalize_uid(puid) in deleted_uids:
                _k_set(raw, "player_uid", _NIL)

    # Group individual_character_handle_ids.
    for g in world_service._map_entries(wsd, "GroupSaveDataMap"):
        top = world_service._g(g, "value", "RawData") or {}
        handles = world_service._k(top, "individual_character_handle_ids")
        if isinstance(handles, list):
            _k_set(top, "individual_character_handle_ids", [
                h for h in handles
                if not (isinstance(h, dict)
                        and normalize_uid(world_service._k(h, "guid")) in deleted_uids)
            ])


def set_player_level(level_dict: dict, uid: str, new_level: int) -> bool:
    """Set a player's level (1-80) and EXP (``Level^3 * 10`` approximation)."""
    if new_level < 1 or new_level > 80:
        return False
    sp = _find_player_sp(level_dict, uid)
    if sp is None:
        return False
    _k_set(sp, "Level", new_level)
    _k_set(sp, "Exp", (new_level ** 3) * 10)
    return True


def set_player_tech_points(
    players_dir: str, uid: str, tech_points: int, boss_tech_points: int,
) -> bool:
    """Set ``TechnologyPoint`` / ``bossTechnologyPoint`` in the player ``.sav``."""
    decoded = _read_player_sav(players_dir, uid)
    if decoded is None:
        return False
    player_dict, save_type = decoded
    sd = _save_data(player_dict)
    _k_set(sd, "TechnologyPoint", int(tech_points))
    _k_set(sd, "bossTechnologyPoint", int(boss_tech_points))
    return _write_player_sav(player_dict, save_type, players_dir, uid)


# ---- stat / tech point name mappings -----------------------------------------

_STAT_NAME_MAP: dict[str, str] = {
    "MaxHP": "最大HP",
    "MaxSP": "最大SP",
    "Attack": "攻撃力",
    "Weight": "所持重量",
    "CaptureRate": "捕獲率",
    "WorkSpeed": "作業速度",
}

# Japanese stat name → lowercase result key for get_player_stats responses.
_STAT_RESULT_MAP: dict[str, str] = {
    "最大HP": "max_hp",
    "最大SP": "max_sp",
    "攻撃力": "attack",
    "所持重量": "weight",
    "捕獲率": "capture_rate",
    "作業速度": "work_speed",
}


def get_player_stats(level_dict: dict, uid: str) -> dict | None:
    """Read current stats from CharacterSaveParameterMap.

    Returns ``{max_hp, max_sp, attack, weight, capture_rate, work_speed, unused_stat_points}``
    with values taken from GotStatusPointList / GotExStatusPointList, or ``None`` if
    the player is not found.
    """
    sp = _find_player_sp(level_dict, uid)
    if sp is None:
        return None

    result: dict[str, int] = {
        "max_hp": 0, "max_sp": 0, "attack": 0, "weight": 0,
        "capture_rate": 0, "work_speed": 0, "unused_stat_points": 0,
    }

    # Only read from GotStatusPointList (the primary stat list).
    # GotExStatusPointList exists separately with different (often lower) values;
    # reading it would overwrite the correct values from GotStatusPointList.
    items = world_service._k(sp, "GotStatusPointList")
    if isinstance(items, list):
        for item in items:
            name = world_service._k(item, "StatusName")
            point = world_service._k(item, "StatusPoint")
            if name and point is not None and str(name) in _STAT_RESULT_MAP:
                try:
                    result[_STAT_RESULT_MAP[str(name)]] = int(point)
                except (TypeError, ValueError):
                    pass

    up = world_service._k(sp, "UnusedStatusPoint")
    if up is not None:
        try:
            result["unused_stat_points"] = int(up)
        except (TypeError, ValueError):
            pass

    return result


def get_player_tech_points(players_dir: str, uid: str) -> dict | None:
    """Read TechnologyPoint / bossTechnologyPoint from the player .sav.

    Returns ``{tech_points, boss_tech_points}`` or ``None`` if the player .sav
    cannot be found or decoded.
    """
    decoded = _read_player_sav(players_dir, uid)
    if decoded is None:
        return None
    player_dict, _ = decoded
    sd = _save_data(player_dict)
    tp = world_service._k(sd, "TechnologyPoint")
    btp = world_service._k(sd, "bossTechnologyPoint")
    return {
        "tech_points": int(tp) if tp is not None else 0,
        "boss_tech_points": int(btp) if btp is not None else 0,
    }


def set_player_stats(
    level_dict: dict,
    uid: str,
    stat_changes: dict[str, int],
    unused_stat_points: int | None = None,
) -> bool:
    """Modify GotStatusPointList / GotExStatusPointList in CharacterSaveParameterMap.

    ``stat_changes`` uses English keys (``MaxHP``, ``MaxSP``, …) and the function
    maps them to the Japanese names stored internally by the game.
    """
    sp = _find_player_sp(level_dict, uid)
    if sp is None:
        return False

    # Map English stat names → Japanese (the game's internal names).
    jp_changes: dict[str, int] = {}
    for en_key, jp_key in _STAT_NAME_MAP.items():
        if en_key in stat_changes:
            jp_changes[jp_key] = stat_changes[en_key]
    if not jp_changes and unused_stat_points is None:
        return False

    for list_key in ("GotStatusPointList", "GotExStatusPointList"):
        items = world_service._k(sp, list_key)
        if not isinstance(items, list):
            continue
        for item in items:
            name = world_service._k(item, "StatusName")
            if name and str(name) in jp_changes:
                _k_set(item, "StatusPoint", jp_changes[str(name)])

    if unused_stat_points is not None:
        _k_set(sp, "UnusedStatusPoint", int(unused_stat_points))
    return True


def reset_player_timestamp(level_dict: dict, uid: str) -> bool:
    """Reset a player's last-online timestamp to current game time."""
    wsd = world_service.get_world_save_data(level_dict)
    tick = world_service.get_tick(wsd)
    if not tick:
        return False
    found = _find_player_in_guilds(level_dict, uid)
    if not found:
        return False
    _, _, p = found
    info = world_service._k(p, "player_info")
    if not isinstance(info, dict):
        info = {}
        _k_set(p, "player_info", info)
    _k_set(info, "last_online_real_time", tick)
    return True


def unlock_viewing_cage(players_dir: str, uid: str) -> bool:
    """Unlock the viewing cage (``bIsViewingCageCanUse``) in the player ``.sav``.

    Returns ``True`` if the field was set or was already ``True``.
    Returns ``False`` if the player ``.sav`` cannot be found/decoded OR if the
    save schema does not define ``bIsViewingCageCanUse`` (viewing cage not
    applicable for this save version).
    """
    decoded = _read_player_sav(players_dir, uid)
    if decoded is None:
        return False
    player_dict, save_type = decoded
    sd = _save_data(player_dict)

    # Check that the schema defines this property — uesave will refuse to encode
    # an unknown property.
    schemas = player_dict.get("schemas", {})
    schema_props = schemas.get("schemas", {}) if isinstance(schemas, dict) else {}
    schema_key = "SaveData.bIsViewingCageCanUse"
    if schema_key not in schema_props:
        return False

    # Check whether the property already exists in the data.
    existing = world_service._k(sd, "bIsViewingCageCanUse")
    if existing is True:
        return True  # already unlocked

    _k_set(sd, "bIsViewingCageCanUse", True)
    return _write_player_sav(player_dict, save_type, players_dir, uid)


def unlock_all_technologies(players_dir: str, uid: str) -> bool:
    """Inject all technology recipe names into ``UnlockedRecipeTechnologyNames``."""
    from app.backend.services.data_service import load_game_data
    try:
        world_data = load_game_data("world")
        technologies = world_data.get("technology", [])
    except Exception:
        return False

    decoded = _read_player_sav(players_dir, uid)
    if decoded is None:
        return False
    player_dict, save_type = decoded
    sd = _save_data(player_dict)
    unlocked = world_service._k(sd, "UnlockedRecipeTechnologyNames")
    existing = set(str(v) for v in unlocked) if isinstance(unlocked, list) else set()
    if not isinstance(unlocked, list):
        unlocked = []
        _k_set(sd, "UnlockedRecipeTechnologyNames", unlocked)
    for tech in technologies:
        tid = tech.get("id", "")
        if tid and tid not in existing:
            unlocked.append(tid)
    return _write_player_sav(player_dict, save_type, players_dir, uid)


def max_all_abilities(level_dict: dict, players_dir: str, uids: list[str]) -> dict:
    """Max all relics/abilities for given players.

    Writes ``RelicPossessNum`` (and ``RelicPossessNumMap`` /
    ``RelicBonusExpTableIndex`` if the save schema supports them) to each
    player ``.sav`` and the corresponding GotStatusPointList entries in
    CharacterSaveParameterMap.

    Returns ``{"processed": int, "failed": list[str]}`` — ``failed`` contains
    UIDs whose ``.sav`` file could not be found/decoded or whose save schema
    does not support the relic fields.
    """
    from app.backend.services.data_service import load_game_data
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

    failed: list[str] = []

    for uid in uids:
        decoded = _read_player_sav(players_dir, uid)
        if decoded is None:
            failed.append(uid)
            continue
        player_dict, save_type = decoded

        # Check which relic properties the save schema supports — uesave will
        # refuse to encode unknown properties.
        schemas = player_dict.get("schemas", {})
        schema_props = schemas.get("schemas", {}) if isinstance(schemas, dict) else {}

        rd = world_service._k(_save_data(player_dict), "RecordData") or {}

        # RelicPossessNumMap (may or may not have schema support).
        if "SaveData.RecordData.RelicPossessNumMap" in schema_props:
            relic_map = [
                {"key": rk, "value": max_val}
                for rk, max_val in cumax.items()
            ]
            _k_set(rd, "RelicPossessNumMap", relic_map)

        # RelicPossessNum (always has schema in modern saves).
        if "SaveData.RecordData.RelicPossessNum" in schema_props:
            total = (
                sum(max_val for max_val in cumax.values())
                if cumax else 0
            )
            _k_set(rd, "RelicPossessNum", total)

        # RelicBonusExpTableIndex (may or may not have schema support).
        if "SaveData.RecordData.RelicBonusExpTableIndex" in schema_props:
            cur_idx = world_service._k(rd, "RelicBonusExpTableIndex")
            if not isinstance(cur_idx, int) or cur_idx < 9999:
                _k_set(rd, "RelicBonusExpTableIndex", 9999)

        if not _write_player_sav(player_dict, save_type, players_dir, uid):
            failed.append(uid)
            continue

        # CharacterSaveParameterMap GotStatusPointList.
        sp = _find_player_sp(level_dict, uid)
        if sp is None:
            continue
        sl = world_service._k(sp, "GotStatusPointList")
        if not isinstance(sl, list):
            sl = []
            _k_set(sp, "GotStatusPointList", sl)
        seen = {world_service._k(s, "StatusName"): s for s in sl}
        for rk, stat_name in relic_to_status.items():
            max_val = maxrank.get(rk, 99)
            if stat_name in seen:
                _k_set(seen[stat_name], "StatusPoint", max_val)
            else:
                sl.append({
                    "StatusName_0": stat_name,
                    "StatusPoint_0": max_val,
                })

    return {"processed": len(uids) - len(failed), "failed": failed}


# ---- local _k_set (matches world_service key-form) -------------------------

def _k_set(node: dict, name: str, value) -> None:
    """Set ``node[name_0]`` preserving the existing key form."""
    if not isinstance(node, dict):
        return
    suffixed = name + "_0"
    if suffixed in node:
        node[suffixed] = value
    elif name in node:
        node[name] = value
    else:
        node[suffixed] = value
