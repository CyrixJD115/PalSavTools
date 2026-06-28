"""Headless tool wrappers using palsav primitives.

Each function wraps save-file manipulation logic from the corresponding
``src/toolsets/`` tool but uses only the installed ``palsav``
package -- no Qt, no PySide6, no desktop-only imports.
"""

from __future__ import annotations

import io
import logging
import os
import sys
from pathlib import Path

from palsav.archive import FArchiveReader, FArchiveWriter, UUID as PalUUID
from palsav.core import compress_gvas_to_sav, decompress_sav_to_gvas
from palsav.gvas import GvasFile
from palsav.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

logger = logging.getLogger(__name__)

# Same 6 heavy-path skip overrides as save_service.py
_SKIP_PATHS = [
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldLocation",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldRotation",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldScale3D",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.Model.Value.EffectMap",
    ".worldSaveData.FoliageGridSaveDataMap",
    ".worldSaveData.MapObjectSpawnerInStageSaveData",
]
_CUSTOM_PROPS: dict = {}
for _prop_path, (_decode_fn, _encode_fn) in PALWORLD_CUSTOM_PROPERTIES.items():
    _CUSTOM_PROPS[_prop_path] = (_decode_fn, _encode_fn)
for _p in _SKIP_PATHS:
    _CUSTOM_PROPS[_p] = (_CUSTOM_PROPS.get(_p) or (None, None))

_TYPE_HINTS = PALWORLD_TYPE_HINTS


# ---------------------------------------------------------------------------
# Fallback ownership resolver (when palworld_aio is not importable)
# ---------------------------------------------------------------------------

class _LazyOwnership:
    """Minimal fallback when palworld_aio.inventory.container_ownership is unavailable."""
    def __init__(self, cmap, containers):
        self._container_owner: dict[str, str | None] = {}
        self._inst_container: dict[str, str] = {}
        for c in containers:
            cid = c.get("value", {}).get("ID", {}).get("value")
            if not cid:
                continue
            uid = c.get("value", {}).get("BelongInfo", {}).get("value", {}).get("PlayerUId", {}).get("value")
            if uid:
                self._container_owner[str(cid).lower()] = str(uid).lower()
        for ch in cmap:
            try:
                inst = ch["key"]["InstanceId"]["value"]
                slot_id = ch["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"].get("SlotId", {}).get("value", {})
                cid = slot_id.get("ContainerId", {}).get("value", {}).get("ID", {}).get("value")
                if cid:
                    self._inst_container[str(inst).lower()] = str(cid).lower()
            except Exception:
                pass

    def get_effective_owner(self, instance_id, owner_field):
        if owner_field:
            if isinstance(owner_field, dict):
                return owner_field.get("value")
            return str(owner_field)
        cid = self._inst_container.get(str(instance_id).lower())
        if cid:
            uid = self._container_owner.get(cid)
            if uid:
                return uid
        return None

    def belongs_to_player(self, instance_id, owner_field, player_uid):
        eff = self.get_effective_owner(instance_id, owner_field)
        return str(eff).lower() == str(player_uid).lower()

    @classmethod
    def build(cls, cmap, containers):
        return cls(cmap, containers)


# ---------------------------------------------------------------------------
# Convert SAV <-> JSON
# ---------------------------------------------------------------------------

def convert_sav_json(
    input_path: str, output_path: str | None = None,
    direction: str = "sav2json",
) -> dict:
    """Convert a .sav file to/from .json using the palsav convert engine.

    ``direction`` is ``"sav2json"`` or ``"json2sav"``.
    Returns ``{"source": ..., "target": ..., "size": ...}``.
    """
    from palsav.commands.convert import main as convert_main

    inp = Path(input_path).resolve()
    if not inp.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")
    out = Path(output_path) if output_path else inp.with_suffix(
        ".json" if direction == "sav2json" else ".sav",
    )
    out = out.resolve()

    old_argv = sys.argv
    try:
        sys.argv = [
            "convert", str(inp),
            "--output", str(out),
            "--force",
        ]
        if direction == "sav2json":
            sys.argv.append("--to-json")
        else:
            sys.argv.append("--from-json")
        convert_main()
    finally:
        sys.argv = old_argv

    return {
        "source": str(inp),
        "target": str(out),
        "size": out.stat().st_size,
    }


# ---------------------------------------------------------------------------
# Convert IDs (Steam ID <-> Palworld UID)
# ---------------------------------------------------------------------------

def _steam_id_to_palworld_uid(steam_id: int) -> str:
    """Convert a Steam 64-bit ID to a Palworld UUID string (w/ dashes)."""
    from palsav._cityhash import cityhash64

    h = cityhash64(str(steam_id).encode("utf-16-le"))
    lo = (h & 0xFFFFFFFF) & 0xFFFFFFFF
    hi = ((h >> 32) & 0xFFFFFFFF) * 23
    # emulate u32 wrapping
    lo = lo & 0xFFFFFFFF
    hi = (hi + ((h & 0xFFFFFFFF) & 0xFFFFFFFF)) & 0xFFFFFFFF
    raw = lo.to_bytes(4, "little") + b"\x00" * 12
    from uuid import UUID
    return str(UUID(bytes=raw)).upper()


def _palworld_uid_to_nosteam(palworld_uid: str) -> str:
    """Palworld UUID -> NoSteam hex string (8-char prefix + suffix)."""
    from uuid import UUID

    u = UUID(palworld_uid)
    raw = u.bytes[0:4]
    val = int.from_bytes(raw, "little", signed=True) & 0xFFFFFFFF
    # Unreal hash function
    def _u32(x: int) -> int:
        return x & 0xFFFFFFFF
    a = _u32(_u32(val << 8) ^ _u32(2654435769 - val))
    b = _u32(a >> 13 ^ _u32(-(val + a)))
    c = _u32(b >> 12 ^ _u32(val - a - b))
    d = _u32(_u32(c << 16) ^ _u32(a - c - b))
    e = _u32(d >> 5 ^ b - d - c)
    f = _u32(e >> 3 ^ c - d - e)
    r = _u32(_u32(_u32(f << 10) ^ _u32(d - f - e)) >> 15 ^ e - (_u32(f << 10) ^ _u32(d - f - e)) - f)
    return f"{r:08X}-0000-0000-0000-000000000000"


def detect_input_type(input_str: str) -> str:
    """Return ``"steam_id"``, ``"palworld_uid"``, ``"nosteam_uid"``, or ``"unknown"``."""
    import re
    s = input_str.strip()
    if s.startswith("steam_"):
        s = s[6:]
    if s.isdigit() and len(s) == 17:
        return "steam_id"
    # Steam URL
    if "steamcommunity.com/profiles/" in s:
        return "steam_id"
    # UUID with dashes (Palworld UID)
    if re.match(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4,}$", s):
        return "palworld_uid" if s.count("-") == 4 else "nosteam_uid"
    if re.match(r"^[0-9A-Fa-f]{8}-0{4}-0{4}-0{4}-0{12}$", s):
        return "nosteam_uid"
    return "unknown"


def convert_ids(input_str: str) -> dict:
    """Convert between Steam ID, Palworld UID, and NoSteam UID formats."""
    raw = input_str.strip()
    input_type = detect_input_type(raw)

    result: dict = {
        "input": raw,
        "input_type": input_type,
        "steam_id": None,
        "palworld_uid": None,
        "nosteam_uid": None,
    }

    if input_type == "steam_id":
        # Strip URL / prefix
        s = raw
        if "steamcommunity.com/profiles/" in s:
            s = s.split("steamcommunity.com/profiles/")[1].split("/")[0]
        elif s.startswith("steam_"):
            s = s[6:]
        steam_id = int(s)
        puid = _steam_id_to_palworld_uid(steam_id)
        nuid = _palworld_uid_to_nosteam(puid)
        result["steam_id"] = str(steam_id)
        result["palworld_uid"] = puid
        result["nosteam_uid"] = nuid

    elif input_type == "palworld_uid":
        nuid = _palworld_uid_to_nosteam(raw)
        result["palworld_uid"] = raw
        result["nosteam_uid"] = nuid

    elif input_type == "nosteam_uid":
        # Can only derive Palworld UID from Steam ID, not reverse
        result["nosteam_uid"] = raw

    return result


# ---------------------------------------------------------------------------
# Restore Map (clear fog)
# ---------------------------------------------------------------------------

def restore_map_fog(path: str) -> dict:
    """Clear map-of-war fog from a ``LocalData.sav`` file.

    Returns ``{"file": ..., "world_map_cleared": bool, "hidden_locations_reset": int}``.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"LocalData.sav not found: {path}")

    data = p.read_bytes()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas = GvasFile.read(raw_gvas, _TYPE_HINTS, _CUSTOM_PROPS)
    d = gvas.dump()
    sd = d["properties"]["SaveData"]["value"]

    world_map_cleared = False
    hidden_locations_reset = 0

    if "WorldMapUISaveDataMap" in sd:
        for entry in sd["WorldMapUISaveDataMap"]["value"]:
            mask = entry["value"]["MaskTextureData"]["value"]
            mask["values"] = b"\x00" * len(mask["values"])
        world_map_cleared = True
    elif "WorldMapMaskTextureV4" in sd:
        mask = sd["WorldMapMaskTextureV4"]["value"]
        mask["values"] = b"\x00" * len(mask["values"])
        world_map_cleared = True

    hl = sd.get("Local_HiddenLocationFlagMap", {}).get("value", [])
    for entry in hl:
        entry["value"] = False
    hidden_locations_reset = len(hl)

    ng = GvasFile.load(d)
    st = (
        50
        if "Pal.PalworldSaveGame" in ng.header.save_game_class_name
        or "Pal.PalLocalWorldSaveGame" in ng.header.save_game_class_name
        else 49
    )
    sav = compress_gvas_to_sav(ng.write(_CUSTOM_PROPS), st)
    p.write_bytes(sav)

    return {
        "file": str(p),
        "world_map_cleared": world_map_cleared,
        "hidden_locations_reset": hidden_locations_reset,
    }


# ---------------------------------------------------------------------------
# Slot Injector
# ---------------------------------------------------------------------------

def _decode_level_sav(filepath: str) -> tuple[GvasFile, int]:
    data = Path(filepath).read_bytes()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas = GvasFile.read(raw_gvas, _TYPE_HINTS, _CUSTOM_PROPS, allow_nan=True)
    return gvas, save_type


def _encode_level_sav(gvas: GvasFile, save_type: int, filepath: str) -> None:
    sav = compress_gvas_to_sav(gvas.write(_CUSTOM_PROPS), save_type)
    Path(filepath).write_bytes(sav)


def _query_player_info_from_wsd(
    wsd: dict,
    players_folder: str | None = None,
) -> list[dict]:
    """Extract player info from an already-decoded worldSaveData dict.

    Returns list of ``{"uid", "name", "guild", "party_id", "palbox_id"}``.
    ``players_folder`` is still needed for reading per-player .sav files
    (container ID resolution) — pass ``None`` to skip that step.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    guild_map = wsd.get("GroupSaveDataMap", {}).get("value", [])

    players: dict[str, dict] = {}
    valid_player_uids: set[str] = set()

    for entry in guild_map if isinstance(guild_map, list) else []:
        value = entry.get("value", {})
        gt = value.get("GroupType", {}).get("value", {}).get("value", "")
        if gt != "EPalGroupType::Guild":
            continue
        raw_data = value.get("RawData", {}).get("value", {})
        guild_name = raw_data.get("guild_name", "Unknown Guild")
        for p in raw_data.get("players", []):
            puid = p.get("player_uid", "N/A")
            puid_str = str(puid).replace("-", "").lower() if puid != "N/A" else "N/A"
            if puid_str != "n/a":
                valid_player_uids.add(puid_str)
                pinfo = p.get("player_info", {})
                pname = pinfo.get("player_name", "Unknown")
                players[puid_str] = {
                    "uid": puid_str,
                    "name": pname,
                    "guild": guild_name,
                    "party_id": None,
                    "palbox_id": None,
                }

    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    for entry in char_map if isinstance(char_map, list) else []:
        key = entry.get("key", {})
        raw_data = entry.get("value", {}).get("RawData", {}).get("value", {})
        puid = key.get("PlayerUId", {}).get("value", "N/A")
        puid_str = str(puid).replace("-", "").lower() if puid != "N/A" else "N/A"
        if puid_str == "00000000000000000000000000000001":
            continue
        sp = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
        is_player = sp.get("IsPlayer", {}).get("value", False)
        nick_name = sp.get("NickName", {}).get("value", "")
        if is_player and puid_str not in players:
            players[puid_str] = {
                "uid": puid_str,
                "name": nick_name if nick_name else "Unknown",
                "guild": "Unknown Guild",
                "party_id": None,
                "palbox_id": None,
            }
        elif is_player and nick_name and players.get(puid_str, {}).get("name") == "Unknown":
            players[puid_str]["name"] = nick_name

    # Read player .sav files for container IDs
    if players_folder and valid_player_uids:
        folder = Path(players_folder)
        if folder.exists():
            def load_player_container(fname: str) -> tuple[str, dict] | None:
                try:
                    pf = folder / fname
                    p_data = pf.read_bytes()
                    p_raw_gvas, _pt = decompress_sav_to_gvas(p_data)
                    p_gvas = GvasFile.read(p_raw_gvas, _TYPE_HINTS, _CUSTOM_PROPS)
                    p_prop = p_gvas.properties.get("SaveData", {}).get("value", {})
                    p_uid_raw = fname.replace(".sav", "").lower()
                    p_box = p_prop.get("PalStorageContainerId", {}).get("value", {}).get("ID", {}).get("value")
                    p_party = p_prop.get("OtomoCharacterContainerId", {}).get("value", {}).get("ID", {}).get("value")
                    if p_box or p_party:
                        return (p_uid_raw, {
                            "party_id": str(p_party).lower() if p_party else None,
                            "palbox_id": str(p_box).lower() if p_box else None,
                        })
                except Exception:
                    pass
                return None

            pfiles = [f for f in os.listdir(str(folder))
                      if f.endswith(".sav") and "_dps" not in f
                      and f.replace(".sav", "").lower() in valid_player_uids]
            with ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) + 4)) as ex:
                futs = [ex.submit(load_player_container, f) for f in pfiles]
                for fut in as_completed(futs):
                    r = fut.result()
                    if r and r[0] in players:
                        players[r[0]]["party_id"] = r[1]["party_id"]
                        players[r[0]]["palbox_id"] = r[1]["palbox_id"]

    return list(players.values())


def get_player_info(level_sav_path: str, players_folder: str | None = None) -> list[dict]:
    """Extract player info from a Level.sav on disk."""
    gvas, _st = _decode_level_sav(level_sav_path)
    wsd = gvas.properties.get("worldSaveData", {}).get("value", {})
    return _query_player_info_from_wsd(wsd, players_folder)


def _query_player_containers_from_wsd(
    wsd: dict,
    players_list: list[dict],
) -> list[dict]:
    """Query containers from an already-decoded worldSaveData dict.

    Returns list of ``{"index", "container_id", "slot_num", "used_slots", "player_uid", "player_name", "guild", "container_type"}``.
    """
    players_map = {p["uid"]: p for p in players_list}
    container = wsd.get("CharacterContainerSaveData", {}).get("value", [])

    # Build container-to-owner map
    container_to_player: dict[str, dict] = {}
    for p in players_list:
        if p.get("party_id"):
            container_to_player[p["party_id"]] = {"type": "Party", **p}
        if p.get("palbox_id"):
            container_to_player[p["palbox_id"]] = {"type": "PalBox", **p}

    result = []
    for i, entry in enumerate(container if isinstance(container, list) else []):
        key = entry.get("key", {})
        value = entry.get("value", {})
        slot_num = value.get("SlotNum", {}).get("value", 0)
        if slot_num >= 960:
            cid = key.get("ID", {}).get("value", "N/A")
            cid_str = str(cid).lower() if cid else "N/A"
            slots = value.get("Slots", {}).get("value", {})
            used = len(slots.get("values", []))
            owner = container_to_player.get(cid_str)
            result.append({
                "index": i,
                "container_id": cid_str,
                "slot_num": slot_num,
                "used_slots": used,
                "player_uid": owner["uid"] if owner else (cid_str[:8] + "..."),
                "player_name": owner["name"] if owner else "Unknown Player",
                "guild": owner["guild"] if owner else "Unknown Guild",
                "container_type": owner["type"] if owner else "Unknown",
            })
    return result


def get_player_containers(level_sav_path: str, players_folder: str | None = None) -> list[dict]:
    """List all character containers from a Level.sav on disk."""
    gvas, _st = _decode_level_sav(level_sav_path)
    wsd = gvas.properties.get("worldSaveData", {}).get("value", {})
    players_list = get_player_info(level_sav_path, players_folder)
    return _query_player_containers_from_wsd(wsd, players_list)


def _apply_slot_injector_to_gvas(
    gvas: GvasFile,
    save_type: int,
    players_folder: str | None = None,
    new_slot_count: int = 960,
    container_ids: list[str] | None = None,
) -> dict:
    """Modify pal container slot counts in an already-loaded GvasFile.

    Mutates ``gvas.properties`` in place. Returns result dict.
    Caller is responsible for persisting.
    """
    wsd = gvas.properties["worldSaveData"]["value"]
    container = wsd.get("CharacterContainerSaveData", {}).get("value", [])

    # Build owner mapping to detect player containers
    players_list = _query_player_info_from_wsd(wsd, players_folder)
    container_to_player: dict[str, dict] = {}
    for p in players_list:
        if p.get("party_id"):
            container_to_player[p["party_id"]] = p
        if p.get("palbox_id"):
            container_to_player[p["palbox_id"]] = p

    targets = []
    for entry in container if isinstance(container, list) else []:
        key = entry.get("key", {})
        cid = key.get("ID", {}).get("value", "N/A")
        cid_str = str(cid).lower() if cid else ""
        if container_ids and cid_str not in container_ids:
            continue
        targets.append((cid_str, entry))

    if not targets:
        return {"containers_modified": 0, "pals_removed": 0, "container_ids": []}

    removed_total = 0
    modified_ids = []
    char_map = wsd.get("CharacterSaveParameterMap", {}).get("value", [])

    for cid_str, entry in targets:
        old_slot_num = entry["value"]["SlotNum"]["value"]
        entry["value"]["SlotNum"]["value"] = new_slot_count
        slots_data = entry["value"]["Slots"]["value"]
        slots_values = slots_data.get("values", [])
        if slots_values:
            filtered = [s for s in slots_values if s.get("SlotIndex", {}).get("value", 0) < new_slot_count]
            slots_data["values"] = filtered

        if old_slot_num > new_slot_count:
            removed = []
            filtered_char = []
            for ce in char_map:
                try:
                    raw = ce["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
                    sid = raw.get("SlotId", {})
                    if sid:
                        cont_ref = sid.get("value", {}).get("ContainerId", {}).get("value", {}).get("ID", {}).get("value")
                        slot_idx = sid.get("value", {}).get("SlotIndex", {}).get("value")
                        if cont_ref and str(cont_ref).lower() == cid_str and slot_idx is not None and slot_idx >= new_slot_count:
                            removed.append(str(ce["key"]["InstanceId"]["value"]))
                            continue
                    filtered_char.append(ce)
                except Exception:
                    filtered_char.append(ce)
            wsd["CharacterSaveParameterMap"]["value"] = filtered_char
            char_map = filtered_char  # update local ref
            removed_total += len(removed)

            # Clean up guild references
            guild_map = wsd.get("GroupSaveDataMap", {}).get("value", [])
            removed_lower = [r.lower() for r in removed]
            for ge in guild_map:
                try:
                    raw = ge.get("value", {}).get("RawData", {}).get("value", {})
                    handles = raw.get("individual_character_handle_ids", [])
                    if handles and isinstance(handles, list):
                        raw["individual_character_handle_ids"] = [
                            h for h in handles
                            if str(h.get("instance_id", "")).lower() not in removed_lower
                        ]
                except Exception:
                    pass

        modified_ids.append(cid_str)

    return {
        "containers_modified": len(modified_ids),
        "pals_removed": removed_total,
        "container_ids": modified_ids,
    }


def apply_slot_injector(
    level_sav_path: str,
    players_folder: str | None = None,
    new_slot_count: int = 960,
    container_ids: list[str] | None = None,
) -> dict:
    """Modify pal container slot counts in a Level.sav on disk."""
    gvas, save_type = _decode_level_sav(level_sav_path)
    result = _apply_slot_injector_to_gvas(
        gvas, save_type,
        players_folder=players_folder,
        new_slot_count=new_slot_count,
        container_ids=container_ids,
    )
    _encode_level_sav(gvas, save_type, level_sav_path)
    return result


# ---------------------------------------------------------------------------
# Convert — export loaded save as JSON
# ---------------------------------------------------------------------------

def export_loaded_save_json(gvas: GvasFile, output_path: str) -> dict:
    """Dump an already-loaded GvasFile to pretty-printed JSON on disk."""
    level_dict = gvas.dump()
    from palsav.json_tools import dump
    dump(level_dict, str(output_path))
    return {"output": output_path, "size": Path(output_path).stat().st_size}


# ---------------------------------------------------------------------------
# Fix Host Save — GUID swap between two players in the same save
# ---------------------------------------------------------------------------

def _normalize_uid(uid: str) -> str:
    return uid.replace("-", "").lower()


def _format_guid(guid: str) -> str:
    g = guid.replace("-", "").lower()
    return f"{g[:8]}-{g[8:12]}-{g[12:16]}-{g[16:20]}-{g[20:]}"


def _deep_swap(data, old_uid: str, new_uid: str):
    """Recursively swap old_uid <-> new_uid in OwnerPlayerUId/owner_player_uid fields."""
    if isinstance(data, dict):
        for k in ("OwnerPlayerUId", "owner_player_uid", "build_player_uid", "private_lock_player_uid"):
            v = data.get(k)
            if isinstance(v, dict) and v.get("value") == old_uid:
                v["value"] = new_uid
            elif isinstance(v, dict) and v.get("value") == new_uid:
                v["value"] = old_uid
            elif v == old_uid:
                data[k] = new_uid
            elif v == new_uid:
                data[k] = old_uid
        for x in data.values():
            _deep_swap(x, old_uid, new_uid)
    elif isinstance(data, list):
        for i in data:
            _deep_swap(i, old_uid, new_uid)


def _copy_dps_file(
    players_folder: str,
    src_uid: str,
    tgt_uid: str,
    target_pal_storage_id,
):
    """Copy _dps.sav from source to target, rewriting container IDs."""
    src_file = Path(players_folder) / f"{_normalize_uid(src_uid).upper()}_dps.sav"
    tgt_file = Path(players_folder) / f"{_normalize_uid(tgt_uid).upper()}_dps.sav"
    if not src_file.exists():
        return None
    try:
        data = src_file.read_bytes()
        raw_gvas, save_type = decompress_sav_to_gvas(data)
        from palsav.gvas import GvasFile as GvasFileCls
        dps = GvasFileCls.read(raw_gvas, _TYPE_HINTS, _CUSTOM_PROPS)
        updated = 0
        sp_array = dps.properties.get("SaveParameterArray", {})
        inner = sp_array.get("value", {})
        pal_list = inner.get("values", []) if isinstance(inner, dict) else []
        for pal_entry in pal_list:
            save_param = pal_entry.get("SaveParameter", {})
            sp_val = save_param.get("value", {})
            slot_id = sp_val.get("SlotId", {})
            sid_val = slot_id.get("value", {})
            cid = sid_val.get("ContainerId", {})
            cid_val = cid.get("value", {})
            id_obj = cid_val.get("ID", {})
            if isinstance(id_obj, dict) and "value" in id_obj:
                id_obj["value"] = target_pal_storage_id
                updated += 1
        _encode_level_sav(dps, save_type, str(tgt_file))
        return updated
    except Exception:
        import shutil
        shutil.copy2(str(src_file), str(tgt_file))
        return 0


def _apply_fix_host_save_to_gvas(
    gvas: GvasFile,
    save_type: int,
    players_folder: str | None,
    old_uid: str,
    new_uid: str,
    guild_fix: bool = True,
) -> dict:
    """Swap two players' GUIDs in an already-loaded GvasFile.

    Mutates gvas.properties in place. Returns result dict.
    Caller is responsible for persisting Level.sav + player .sav files.
    """
    wsd = gvas.properties["worldSaveData"]["value"]
    level_dict = gvas.dump()
    lvl_wsd = level_dict["properties"]["worldSaveData"]["value"]

    old_uid_fmt = _format_guid(old_uid)
    new_uid_fmt = _format_guid(new_uid)

    # Find character entries and swap their PlayerUId
    cspm = lvl_wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    old_inst = None
    new_inst = None
    for e in cspm:
        puid = str(e["key"].get("PlayerUId", {}).get("value", ""))
        inst = e["key"].get("InstanceId", {}).get("value")
        if _normalize_uid(puid) == _normalize_uid(old_uid_fmt):
            old_inst = inst
        elif _normalize_uid(puid) == _normalize_uid(new_uid_fmt):
            new_inst = inst

    if old_inst is None or new_inst is None:
        return {"success": False, "error": "Could not find one or both player entries in CharacterSaveParameterMap"}

    # Swap InstanceId and PlayerUId in level
    for e in cspm:
        puid_val = e["key"].get("PlayerUId", {}).get("value", "")
        inst_val = e["key"].get("InstanceId", {}).get("value")
        if inst_val == old_inst:
            e["key"]["PlayerUId"]["value"] = new_uid_fmt
        elif inst_val == new_inst:
            e["key"]["PlayerUId"]["value"] = old_uid_fmt

    # Guild membership swap
    if guild_fix:
        guild_map = lvl_wsd.get("GroupSaveDataMap", {}).get("value", [])
        for g in guild_map:
            if g.get("value", {}).get("GroupType", {}).get("value", {}).get("value") != "EPalGroupType::Guild":
                continue
            raw = g["value"]["RawData"]["value"]
            for h in raw.get("individual_character_handle_ids", []):
                if str(h.get("instance_id", "")) == str(old_inst):
                    h["guid"] = new_uid_fmt
                elif str(h.get("instance_id", "")) == str(new_inst):
                    h["guid"] = old_uid_fmt
            if _normalize_uid(str(raw.get("admin_player_uid", ""))) == _normalize_uid(old_uid_fmt):
                raw["admin_player_uid"] = new_uid_fmt
            elif _normalize_uid(str(raw.get("admin_player_uid", ""))) == _normalize_uid(new_uid_fmt):
                raw["admin_player_uid"] = old_uid_fmt
            for p in raw.get("players", []):
                if _normalize_uid(str(p.get("player_uid", ""))) == _normalize_uid(old_uid_fmt):
                    p["player_uid"] = new_uid_fmt
                elif _normalize_uid(str(p.get("player_uid", ""))) == _normalize_uid(new_uid_fmt):
                    p["player_uid"] = old_uid_fmt

    # Deep swap across all save data
    _deep_swap(lvl_wsd, old_uid_fmt, new_uid_fmt)
    _deep_swap(lvl_wsd, _normalize_uid(old_uid_fmt), _normalize_uid(new_uid_fmt))

    # Reconstruct gvas.properties from mutated level_dict
    gvas.properties["worldSaveData"]["value"] = lvl_wsd

    # DPS file handling
    try:
        tgt_sd = None
        if players_folder:
            tgt_path = Path(players_folder) / f"{_normalize_uid(new_uid_fmt).upper()}.sav"
            if tgt_path.exists():
                tgt_data = tgt_path.read_bytes()
                tgt_rg, _ = decompress_sav_to_gvas(tgt_data)
                tgt_g = GvasFile.read(tgt_rg, _TYPE_HINTS, _CUSTOM_PROPS)
                tgt_sd = tgt_g.properties.get("SaveData", {}).get("value", {})
    except Exception:
        tgt_sd = None

    target_pal_storage_id = None
    if tgt_sd:
        target_pal_storage_id = tgt_sd.get("PalStorageContainerId", {}).get("value", {}).get("ID", {}).get("value")

    dps_updated = 0
    if players_folder and target_pal_storage_id:
        dps_updated = _copy_dps_file(players_folder, old_uid_fmt, new_uid_fmt, target_pal_storage_id) or 0

    return {
        "success": True,
        "old_uid": old_uid_fmt,
        "new_uid": new_uid_fmt,
        "dps_updated": dps_updated,
    }


def fix_host_save(
    level_sav_path: str,
    old_uid: str,
    new_uid: str,
    guild_fix: bool = True,
) -> dict:
    """Swap two players' GUIDs in a Level.sav on disk (file-path wrapper)."""
    gvas, save_type = _decode_level_sav(level_sav_path)
    players_folder = str(Path(level_sav_path).parent / "Players")
    result = _apply_fix_host_save_to_gvas(
        gvas, save_type, players_folder, old_uid, new_uid, guild_fix,
    )
    if result.get("success"):
        _encode_level_sav(gvas, save_type, level_sav_path)
        old_fmt = _format_guid(old_uid)
        new_fmt = _format_guid(new_uid)
        players_dir = Path(level_sav_path).parent / "Players"
        src_path = players_dir / f"{_normalize_uid(old_fmt).upper()}.sav"
        dst_path = players_dir / f"{_normalize_uid(new_fmt).upper()}.sav"
        tmp_path = players_dir / f"{_normalize_uid(old_fmt).upper()}.sav.tmp_swap"

        # Swap player .sav files on disk
        if src_path.exists():
            src_path.rename(tmp_path)
        if dst_path.exists():
            dst_path.rename(src_path)
        if tmp_path.exists():
            tmp_path.rename(dst_path)
    return result


# ---------------------------------------------------------------------------
# Fix Guild — move a player to a different guild within the same save
# ---------------------------------------------------------------------------

def _apply_fix_guild_to_gvas(
    gvas: GvasFile,
    save_type: int,
    player_uid: str,
    target_guild_id: str,
    players_folder: str | None = None,
) -> dict:
    """Move a player to a different guild in an already-loaded GvasFile.

    Mutates gvas.properties in place. Returns result dict.
    """
    wsd = gvas.properties["worldSaveData"]["value"]
    guild_map = wsd.get("GroupSaveDataMap", {}).get("value", [])
    base_list = wsd.get("BaseCampSaveData", {}).get("value", [])

    def nu(x):
        return str(x).replace("-", "").lower()

    player_key = nu(player_uid)
    target_key = nu(target_guild_id)
    zero = "00000000-0000-0000-0000-000000000000"

    player_to_guild = {}
    target_group = None
    origin_group = None
    found_entry = None

    for g in guild_map:
        try:
            if g.get("value", {}).get("GroupType", {}).get("value", {}).get("value") != "EPalGroupType::Guild":
                continue
            gid = str(g.get("key", "") if isinstance(g.get("key"), str) else g.get("key", {}).get("InstanceId", {}).get("value", ""))
            raw = g["value"]["RawData"]["value"]
            if nu(gid) == target_key:
                target_group = g
            for p in raw.get("players", []):
                pu = p.get("player_uid", "")
                if pu:
                    pu_norm = nu(pu)
                    player_to_guild[pu_norm] = {"group": g, "entry": p, "raw": raw}
                    if pu_norm == player_key:
                        origin_group = g
                        found_entry = p
        except Exception:
            pass

    if not found_entry or not target_group or not origin_group:
        return {"success": False, "error": "Player or target guild not found"}

    if origin_group is target_group:
        return {"success": True, "message": "Player already in target guild"}

    origin_raw = origin_group["value"]["RawData"]["value"]
    new_players = [p for p in origin_raw.get("players", []) if nu(p.get("player_uid", "")) != player_key]
    origin_raw["players"] = new_players

    if not new_players:
        gid_key = origin_group["key"]
        for b in base_list[:]:
            try:
                bgid = b.get("value", {}).get("RawData", {}).get("value", {}).get("group_id_belong_to")
                if bgid and nu(str(bgid)) == nu(str(gid_key) if isinstance(gid_key, str) else str(gid_key.get("InstanceId", {}).get("value", ""))):
                    base_list.remove(b)
            except Exception:
                pass
        guild_map.remove(origin_group)
    else:
        admin = nu(origin_raw.get("admin_player_uid", ""))
        if admin not in {nu(p["player_uid"]) for p in new_players}:
            origin_raw["admin_player_uid"] = new_players[0]["player_uid"]

    target_raw = target_group["value"]["RawData"]["value"]
    tplayers = target_raw.get("players", [])
    tplayer_set = {nu(p["player_uid"]) for p in tplayers}

    if player_key not in tplayer_set:
        if "player_info" not in found_entry:
            found_entry["player_info"] = {}
        if "player_name" not in found_entry["player_info"]:
            found_entry["player_info"]["player_name"] = "Player"
        if "last_online_real_time" not in found_entry["player_info"]:
            found_entry["player_info"]["last_online_real_time"] = 0
        tplayers.append(found_entry)

    target_raw["players"] = tplayers
    found_entry["_u8_flag"] = 3
    if nu(target_raw.get("admin_player_uid", "")) not in tplayer_set:
        target_raw["admin_player_uid"] = found_entry["player_uid"]
        found_entry["_u8_flag"] = 1

    new_gid_obj = target_raw.get("group_id", zero)

    # Update group_id on all character entries for this player
    cmap = wsd["CharacterSaveParameterMap"]["value"]
    moved_instances = set()
    try:
        from palworld_aio.inventory.container_ownership import ContainerOwnership
    except ImportError:
        class ContainerOwnership:
            @staticmethod
            def build(_cmap, _containers):
                return _LazyOwnership(_cmap, _containers)
    ownership = ContainerOwnership.build(cmap, wsd.get("CharacterContainerSaveData", {}).get("value", []))

    for character in cmap:
        try:
            raw = character["value"]["RawData"]["value"]
            sp = raw["object"]["SaveParameter"]["value"]
            inst_val = character["key"]["InstanceId"]["value"]
            inst_str = str(inst_val) if inst_val else ""
            if not inst_str:
                continue
            owner = sp.get("OwnerPlayerUId", {}).get("value")
            is_player_char = (
                sp.get("IsPlayer", {}).get("value", False)
                and nu(str(character["key"]["PlayerUId"]["value"])) == player_key
            )
            if not is_player_char:
                eff = ownership.get_effective_owner(inst_val, owner)
                if nu(str(eff)) != player_key:
                    continue
            raw["group_id"] = new_gid_obj
            moved_instances.add(inst_str)
            if "OwnerPlayerUId" in sp:
                sp["OwnerPlayerUId"]["value"] = player_uid
            sp.pop("MapObjectConcreteInstanceIdAssignedToExpedition", None)
        except Exception:
            pass

    # Clean up origin guild handles
    if origin_group:
        try:
            origin_raw = origin_group["value"]["RawData"]["value"]
            origin_handles = origin_raw.get("individual_character_handle_ids", [])
            if isinstance(origin_handles, list):
                keep = [h for h in origin_handles if str(h.get("instance_id", "")) not in moved_instances]
                seen = set()
                unique = []
                for h in keep:
                    inst = str(h.get("instance_id", ""))
                    if inst not in seen:
                        seen.add(inst)
                        unique.append(h)
                origin_raw["individual_character_handle_ids"] = unique
        except Exception:
            pass

    # Add handles to target guild
    try:
        handles = target_raw.get("individual_character_handle_ids")
        if not isinstance(handles, list):
            handles = []
            target_raw["individual_character_handle_ids"] = handles
        seen = set()
        unique = []
        for h in handles:
            inst = str(h.get("instance_id", ""))
            if inst not in seen:
                seen.add(inst)
                unique.append(h)
        handles[:] = unique
        for inst_str in moved_instances:
            if inst_str not in seen:
                handles.append({"guid": UUID_from_str(zero), "instance_id": inst_str})
                seen.add(inst_str)
    except Exception:
        pass

    # Update player .sav GroupId
    if players_folder:
        try:
            player_sav = Path(players_folder) / f"{_normalize_uid(player_uid).upper()}.sav"
            if player_sav.exists():
                p_data = player_sav.read_bytes()
                p_rg, _pt = decompress_sav_to_gvas(p_data)
                p_g = GvasFile.read(p_rg, _TYPE_HINTS, _CUSTOM_PROPS)
                p_sd = p_g.properties.get("SaveData", {}).get("value", {})
                if p_sd:
                    p_sd["GroupId"] = {
                        "id": None, "value": new_gid_obj,
                        "type": "StructProperty",
                        "struct_type": "Guid",
                        "struct_id": "00000000-0000-0000-0000-000000000000",
                    }
                _encode_level_sav(p_g, _pt, str(player_sav))
        except Exception:
            pass

    return {"success": True, "player_uid": player_uid, "target_guild_id": target_key, "pals_moved": len(moved_instances)}


def fix_guild(
    level_sav_path: str,
    player_uid: str,
    target_guild_id: str,
) -> dict:
    """Move a player to a different guild in a Level.sav on disk."""
    gvas, save_type = _decode_level_sav(level_sav_path)
    players_folder = str(Path(level_sav_path).parent / "Players")
    result = _apply_fix_guild_to_gvas(gvas, save_type, player_uid, target_guild_id, players_folder)
    if result.get("success"):
        _encode_level_sav(gvas, save_type, level_sav_path)
    return result


# ---------------------------------------------------------------------------
# Character Transfer — cross-save player migration
# ---------------------------------------------------------------------------

def UUID_from_str(s: str):
    from palsav.archive import UUID as PalUUID
    return PalUUID.from_str(s)


def _fast_deepcopy(obj):
    import pickle
    return pickle.loads(pickle.dumps(obj, -1))


def _extract_value(data, key, default=None):
    v = data.get(key, default)
    if isinstance(v, dict):
        v = v.get("value", default)
        if isinstance(v, dict):
            v = v.get("value", default)
    return v


# ---------------------------------------------------------------------------
# Headless pal data helpers (recovered from deleted pal_editor package)
# All three functions are pure dict logic — no Qt dependencies.
# ---------------------------------------------------------------------------

_PAL_BASE_DATA_CACHE: dict = {}

def _load_pal_base_data() -> dict:
    if _PAL_BASE_DATA_CACHE:
        return _PAL_BASE_DATA_CACHE
    try:
        from palsav import json_tools
        from resource_resolver import resource_path
        from palworld_aio import constants
        base_dir = constants.get_base_path()
        path = resource_path(base_dir, 'game_data', 'characters.json')
        data = json_tools.load(path)
        for p in data.get('pals', []):
            a = p.get('asset', '').lower()
            if not a:
                continue
            _PAL_BASE_DATA_CACHE[a] = p
        for n in data.get('npcs', []):
            a = n.get('asset', '').lower()
            if not a or a in _PAL_BASE_DATA_CACHE:
                continue
            _PAL_BASE_DATA_CACHE[a] = n
        for a, p in list(_PAL_BASE_DATA_CACHE.items()):
            if p.get('elements') or 'boss_' in a:
                continue
            boss_key = f'boss_{a}'
            boss_entry = _PAL_BASE_DATA_CACHE.get(boss_key)
            if boss_entry and boss_entry.get('elements'):
                p = dict(p)
                p['elements'] = boss_entry['elements']
                if boss_entry.get('stats'):
                    p['stats'] = {**boss_entry['stats'], **p.get('stats', {})}
                _PAL_BASE_DATA_CACHE[a] = p
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
    normalized = cid_lower.replace('boss_', '').replace('b_o_s_s_', '')
    entry = cache.get(normalized)
    if entry:
        return entry
    for prefix in ('gym_', 'tower_', 'raid_', 'predator_'):
        prefixed = f'{prefix}{normalized}'
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
        from palsav import json_tools
        from resource_resolver import resource_path
        from palworld_aio import constants
        base_dir = constants.get_base_path()
        path = resource_path(base_dir, 'game_data', 'friendship.json')
        data = json_tools.load(path)
        entries = []
        for v in data.values():
            r = v.get('FriendshipRank', -1)
            if r >= 0:
                entries.append((r, v.get('RequiredPoint', 0)))
        entries.sort()
        _FRIENDSHIP_THRESHOLDS = [pt for _, pt in entries]
    except Exception:
        _FRIENDSHIP_THRESHOLDS = [0, 6000, 13000, 21000, 30000, 40000, 55000, 80000, 110000, 150000, 200000]
    return _FRIENDSHIP_THRESHOLDS


def _generate_pal_save_param(character_id, nickname, owner_uid, container_id, slot_index, group_id=None):
    import uuid
    if group_id is None:
        group_id = str(uuid.uuid4()).upper()
    instance_id = str(uuid.uuid4()).upper()
    empty_uuid = '00000000-0000-0000-0000-000000000000'
    time_val = 638486453957560000
    base = get_pal_base_data(character_id)
    max_stomach = (base.get('stats', {}).get('max_full_stomach', 300) if base else 300)
    return {'key': {'PlayerUId': {'struct_type': 'Guid', 'struct_id': empty_uuid, 'id': None, 'value': empty_uuid, 'type': 'StructProperty'}, 'InstanceId': {'struct_type': 'Guid', 'struct_id': empty_uuid, 'id': None, 'value': instance_id, 'type': 'StructProperty'}, 'DebugName': {'id': None, 'type': 'StrProperty', 'value': ''}}, 'value': {'RawData': {'array_type': 'ByteProperty', 'id': None, 'value': {'object': {'SaveParameter': {'struct_type': 'PalIndividualCharacterSaveParameter', 'struct_id': empty_uuid, 'id': None, 'value': {'CharacterID': {'id': None, 'type': 'NameProperty', 'value': character_id}, 'Gender': {'id': None, 'type': 'EnumProperty', 'value': {'type': 'EPalGenderType', 'value': 'EPalGenderType::Female'}}, 'NickName': {'id': None, 'type': 'StrProperty', 'value': nickname}, 'EquipWaza': {'array_type': 'EnumProperty', 'id': None, 'value': {'values': [f'EPalWazaID::Unique_{character_id}_Roll'] if character_id == 'SheepBall' else []}, 'type': 'ArrayProperty'}, 'MasteredWaza': {'array_type': 'EnumProperty', 'id': None, 'value': {'values': []}, 'type': 'ArrayProperty'}, 'Hp': {'struct_type': 'FixedPoint64', 'struct_id': empty_uuid, 'id': None, 'value': {'Value': {'id': None, 'value': 1000, 'type': 'Int64Property'}}, 'type': 'StructProperty'}, 'Talent_HP': {'id': None, 'type': 'ByteProperty', 'value': {'type': 'None', 'value': 100}}, 'Talent_Shot': {'id': None, 'type': 'ByteProperty', 'value': {'type': 'None', 'value': 100}}, 'Talent_Defense': {'id': None, 'type': 'ByteProperty', 'value': {'type': 'None', 'value': 100}}, 'FullStomach': {'id': None, 'type': 'FloatProperty', 'value': float(max_stomach)}, 'SanityValue': {'id': None, 'type': 'FloatProperty', 'value': 100.0}, 'Level': {'id': None, 'type': 'ByteProperty', 'value': {'type': 'None', 'value': 1}}, 'Exp': {'id': None, 'type': 'Int64Property', 'value': 0}, 'Rank': {'id': None, 'type': 'ByteProperty', 'value': {'type': 'None', 'value': 1}}, 'PassiveSkillList': {'array_type': 'NameProperty', 'id': None, 'value': {'values': []}, 'type': 'ArrayProperty'}, 'OwnedTime': {'struct_type': 'DateTime', 'struct_id': empty_uuid, 'id': None, 'value': time_val, 'type': 'StructProperty'}, 'OwnerPlayerUId': {'struct_type': 'Guid', 'struct_id': empty_uuid, 'id': None, 'value': owner_uid, 'type': 'StructProperty'}, 'OldOwnerPlayerUIds': {'array_type': 'StructProperty', 'id': None, 'value': {'prop_name': 'OldOwnerPlayerUIds', 'prop_type': 'StructProperty', 'values': [owner_uid], 'type_name': 'Guid', 'id': empty_uuid}, 'type': 'ArrayProperty'}, 'SlotId': {'struct_type': 'PalCharacterSlotId', 'struct_id': empty_uuid, 'id': None, 'value': {'ContainerId': {'struct_type': 'PalContainerId', 'struct_id': empty_uuid, 'id': None, 'value': {'ID': {'struct_type': 'Guid', 'struct_id': empty_uuid, 'id': None, 'value': container_id, 'type': 'StructProperty'}}, 'type': 'StructProperty'}, 'SlotIndex': {'id': None, 'type': 'IntProperty', 'value': slot_index}}, 'type': 'StructProperty'}, 'GotStatusPointList': {'array_type': 'StructProperty', 'id': None, 'value': {'prop_name': 'GotStatusPointList', 'prop_type': 'StructProperty', 'values': [{'StatusName': {'id': None, 'type': 'NameProperty', 'value': '最大HP'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '最大SP'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '攻撃力'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '所持重量'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '捕獲率'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '作業速度'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}], 'type_name': 'PalGotStatusPoint', 'id': empty_uuid}, 'type': 'ArrayProperty'}, 'GotExStatusPointList': {'array_type': 'StructProperty', 'id': None, 'value': {'prop_name': 'GotExStatusPointList', 'prop_type': 'StructProperty', 'values': [{'StatusName': {'id': None, 'type': 'NameProperty', 'value': '最大HP'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '最大SP'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '攻撃力'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '所持重量'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}, {'StatusName': {'id': None, 'type': 'NameProperty', 'value': '作業速度'}, 'StatusPoint': {'id': None, 'type': 'IntProperty', 'value': 0}}], 'type_name': 'PalGotStatusPoint', 'id': empty_uuid}, 'type': 'ArrayProperty'}, 'LastNickNameModifierPlayerUid': {'struct_type': 'Guid', 'struct_id': empty_uuid, 'id': None, 'value': owner_uid, 'type': 'StructProperty'}}, 'type': 'StructProperty'}}, 'unknown_bytes': [0, 0, 0, 0], 'group_id': group_id, 'trailing_bytes': [0, 0, 0, 0]}, 'custom_type': '.worldSaveData.CharacterSaveParameterMap.Value.RawData', 'type': 'ArrayProperty'}}}


def _scan_source_pals(source_wsd: dict, source_player_sd: dict, source_player_uid: str):
    """Scan source Level for a player's owned pals."""
    host_guid = source_player_uid
    try:
        pal_ctr = source_player_sd["PalStorageContainerId"]["value"]["ID"]["value"]
        oto_ctr = source_player_sd["OtomoCharacterContainerId"]["value"]["ID"]["value"]
    except KeyError:
        return []

    pal_ctr_s = str(pal_ctr).lower()
    oto_ctr_s = str(oto_ctr).lower()
    char_map = source_wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    containers = source_wsd.get("CharacterContainerSaveData", {}).get("value", [])
    try:
        from palworld_aio.inventory.container_ownership import ContainerOwnership
    except ImportError:
        ContainerOwnership = _LazyOwnership
    ownership = ContainerOwnership.build(char_map, containers)

    pals = []
    for ch in char_map:
        try:
            v = ch["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
            owner = v.get("OwnerPlayerUId")
            inst_id = ch["key"]["InstanceId"]["value"]
            if not ownership.belongs_to_player(inst_id, owner, host_guid):
                continue
            slot_cid = v.get("SlotId", {}).get("value", {}).get("ContainerId", {}).get("value", {}).get("ID", {}).get("value")
            slot_cid_s = str(slot_cid).lower() if slot_cid else ""
            slot_idx = v.get("SlotId", {}).get("value", {}).get("SlotIndex", {}).get("value", 0)
            if slot_cid_s == pal_ctr_s:
                is_palbox = True
            elif slot_cid_s == oto_ctr_s:
                is_palbox = False
            else:
                continue
            group_id = ch.get("value", {}).get("RawData", {}).get("value", {}).get("group_id", "")
            pals.append({
                "source_entry": ch,
                "save_parameter": v,
                "instance_id": inst_id,
                "is_palbox": is_palbox,
                "slot_index": slot_idx,
                "group_id": group_id,
            })
        except Exception:
            continue
    return pals


def _migrate_pal_to_target(
    pal_data: dict,
    target_uid: str,
    target_wsd: dict,
    target_player_sd: dict,
    target_guild_id: str,
):
    """Migrate one pal from source to target save."""
    sd = target_player_sd
    try:
        pal_ctr = sd["PalStorageContainerId"]["value"]["ID"]["value"]
        oto_ctr = sd["OtomoCharacterContainerId"]["value"]["ID"]["value"]
        container_id = pal_ctr if pal_data["is_palbox"] else oto_ctr
    except KeyError:
        return False

    src_sp = pal_data["save_parameter"]
    cid = _extract_value(src_sp, "CharacterID", "")
    nick = _extract_value(src_sp, "NickName", "")
    slot_idx = pal_data["slot_index"]

    # Build skeleton pal entry (headless helpers)
    try:
        from palworld_aio.utils import calculate_max_hp, safe_nested_get
    except ImportError:
        def calculate_max_hp(*_a, **_kw): return 1000
        def safe_nested_get(d, p, default=None):
            from palsav.json_tools import safe_dict_get
            return safe_dict_get(d, *p, default=default)

    skeleton = _generate_pal_save_param(cid, nick, target_uid, container_id, slot_idx, target_guild_id)
    instance_id = skeleton["key"]["InstanceId"]["value"]

    used_ids = set()
    cmap = target_wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    for ch in cmap:
        used_ids.add(str(ch["key"]["InstanceId"]["value"]))

    def _bump_guid(s):
        v = str(s).lower()
        t = str.maketrans("0123456789abcdef", "123456789abcdef0")
        bumped = v.translate(t)
        max_iter = 1000
        it = 0
        while bumped in used_ids:
            bumped = bumped.translate(t)
            it += 1
            if it >= max_iter:
                raise RuntimeError("GUID exhaustion")
        used_ids.add(bumped)
        return bumped

    new_inst_str = _bump_guid(instance_id)
    new_instance = UUID_from_str(new_inst_str)
    skeleton["key"]["InstanceId"]["value"] = new_instance

    sp = skeleton["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
    for k, v in src_sp.items():
        if k in ("OwnerPlayerUId", "IndividualId", "SlotId"):
            continue
        sp[k] = _fast_deepcopy(v)

    sp["OwnerPlayerUId"] = {
        "struct_type": "Guid", "struct_id": "00000000-0000-0000-0000-000000000000",
        "id": None, "value": target_uid, "type": "StructProperty",
    }
    sp["SlotId"]["value"]["SlotIndex"]["value"] = slot_idx
    sp["SlotId"]["value"]["ContainerId"]["value"]["ID"]["value"] = container_id

    for cleanup_key in [
        "OldOwnerPlayerUIds", "MapObjectConcreteInstanceIdAssignedToExpedition",
        "HungerType", "PhysicalHealth", "WorkerSick", "CurrentWorkSuitability",
        "FoodWithStatusEffect", "Tiemr_FoodWithStatusEffect", "FoodRegeneEffectInfo",
        "ArenaRestoreParameter", "WorkSuitabilityOptionInfo",
    ]:
        sp.pop(cleanup_key, None)

    # Recalculate HP
    base_data = get_pal_base_data(cid)
    if base_data:
        max_stomach = base_data.get("stats", {}).get("max_full_stomach", 300)
        sp["FullStomach"] = {"id": None, "type": "FloatProperty", "value": float(max_stomach)}
    sp["SanityValue"] = {"id": None, "type": "FloatProperty", "value": 100.0}

    max_hp = safe_nested_get(sp, ["MaxHP", "value", "Value", "value"], 0)
    if max_hp <= 0 and base_data:
        is_boss = cid.upper().startswith("BOSS_")
        is_lucky = _extract_value(sp, "IsRarePal", False)
        lv = int(_extract_value(sp, "Level", 1))
        talent_hp = int(_extract_value(sp, "Talent_HP", 0))
        rank_hp = int(_extract_value(sp, "Rank_HP", 0))
        trust = int(_extract_value(sp, "FriendshipPoint", 0))
        rank = int(_extract_value(sp, "Rank", 0))
        is_awake = bool(_extract_value(sp, "bIsAwakening", False))
        thr = _ensure_friendship_thresholds()
        trust_rank = 0
        for r in range(len(thr) - 1, 0, -1):
            if trust >= thr[r]:
                trust_rank = r
                break
        condenser = rank
        max_hp = calculate_max_hp(base_data, lv, talent_hp, rank_hp, is_boss, is_lucky, trust_rank, condenser, is_awake)

    if max_hp > 0:
        sp["Hp"] = {
            "struct_type": "FixedPoint64",
            "struct_id": "00000000-0000-0000-0000-000000000000",
            "id": None,
            "value": {"Value": {"id": None, "value": int(max_hp), "type": "Int64Property"}},
            "type": "StructProperty",
        }

    cmap.append(skeleton)

    # Add to container
    char_containers = target_wsd.setdefault("CharacterContainerSaveData", {}).setdefault("value", [])
    found = False
    for cont in char_containers:
        if cont.get("key", {}).get("ID", {}).get("value") == container_id:
            slots = cont.setdefault("value", {}).setdefault("Slots", {}).setdefault("value", {}).setdefault("values", [])
            slots.append({
                "SlotIndex": {"id": None, "type": "IntProperty", "value": slot_idx},
                "RawData": {
                    "array_type": "ByteProperty", "id": None,
                    "value": {
                        "player_uid": "00000000-0000-0000-0000-000000000000",
                        "instance_id": new_instance,
                        "permission_tribe_id": 0,
                    },
                    "custom_type": ".worldSaveData.CharacterContainerSaveData.Value.Slots.Slots.RawData",
                    "type": "ArrayProperty",
                },
            })
            cont_val = cont.setdefault("value", {})
            if "SlotNum" not in cont_val:
                cont_val["SlotNum"] = {"id": None, "value": slot_idx + 1, "type": "IntProperty"}
            elif cont_val["SlotNum"]["value"] < slot_idx + 1:
                cont_val["SlotNum"]["value"] = slot_idx + 1
            found = True
            break

    if not found:
        char_containers.append({
            "key": {
                "ID": {
                    "struct_type": "Guid", "struct_id": "00000000-0000-0000-0000-000000000000",
                    "id": None, "value": container_id, "type": "StructProperty",
                },
            },
            "value": {
                "SlotNum": {"id": None, "value": slot_idx + 1, "type": "IntProperty"},
                "Slots": {
                    "id": None,
                    "value": {
                        "values": [{
                            "SlotIndex": {"id": None, "type": "IntProperty", "value": slot_idx},
                            "RawData": {
                                "array_type": "ByteProperty", "id": None,
                                "value": {
                                    "player_uid": "00000000-0000-0000-0000-000000000000",
                                    "instance_id": new_instance,
                                    "permission_tribe_id": 0,
                                },
                                "custom_type": ".worldSaveData.CharacterContainerSaveData.Value.Slots.Slots.RawData",
                                "type": "ArrayProperty",
                            },
                        }],
                        "type": "ArrayProperty",
                    },
                    "key_type": "None", "value_type": "StructProperty",
                    "type": "StructProperty",
                },
            },
        })

    # Add to guild handles
    zero = UUID_from_str("00000000-0000-0000-0000-000000000000")
    for g in target_wsd.get("GroupSaveDataMap", {}).get("value", []):
        try:
            if str(g["value"]["RawData"]["value"].get("group_id", "")) == str(target_guild_id):
                hids = g["value"]["RawData"]["value"].setdefault("individual_character_handle_ids", [])
                hids.append({"guid": zero, "instance_id": new_instance})
                break
        except Exception:
            pass

    return True


def _transfer_character_to_target(
    source_wsd: dict,
    target_wsd: dict,
    source_player_sd: dict,
    target_player_sd: dict,
    source_player_uid: str,
    target_player_uid: str,
):
    """Copy source player's character entry to target save."""
    try:
        host_instance_id = source_player_sd["IndividualId"]["value"]["InstanceId"]["value"]
    except KeyError:
        return False

    # Find the source character entry in level
    exported_map = None
    for character in source_wsd.get("CharacterSaveParameterMap", {}).get("value", []):
        try:
            uid = character["key"]["PlayerUId"]["value"]
            inst = character["key"]["InstanceId"]["value"]
            if str(uid) == str(source_player_uid) and str(inst) == str(host_instance_id):
                exported_map = character
                break
        except Exception:
            continue

    if not exported_map:
        return False

    targ_instance_id = target_player_sd["IndividualId"]["value"]["InstanceId"]["value"]
    char_list = target_wsd.setdefault("CharacterSaveParameterMap", {}).setdefault("value", [])
    updated = False

    for c in char_list:
        key = c.get("key", {})
        if str(key.get("PlayerUId", {}).get("value", "")) == str(target_player_uid):
            try:
                spv = c["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
                if not spv.get("IsPlayer", {}).get("value", False):
                    continue
            except Exception:
                continue
            c["value"] = _fast_deepcopy(exported_map["value"])
            c["key"]["InstanceId"]["value"] = targ_instance_id
            sp = c["value"].get("RawData", {}).get("value", {}).get("object", {}).get("SaveParameter", {}).get("value", {})
            if "OwnerPlayerUId" in sp:
                sp["OwnerPlayerUId"]["value"] = target_player_uid
            ind = sp.get("IndividualId", {}).get("value")
            if ind:
                ind["InstanceId"]["value"] = targ_instance_id
                ind["PlayerUId"]["value"] = target_player_uid
            updated = True
            break

    if not updated:
        new_entry = _fast_deepcopy(exported_map)
        new_entry["key"]["PlayerUId"]["value"] = target_player_uid
        new_entry["key"]["InstanceId"]["value"] = targ_instance_id
        sp = new_entry["value"].get("RawData", {}).get("value", {}).get("object", {}).get("SaveParameter", {}).get("value", {})
        if "OwnerPlayerUId" in sp:
            sp["OwnerPlayerUId"]["value"] = target_player_uid
        ind = sp.get("IndividualId", {}).get("value")
        if ind:
            ind["InstanceId"]["value"] = targ_instance_id
            ind["PlayerUId"]["value"] = target_player_uid
        char_list.append(new_entry)

    # Copy containers
    host_sd = source_player_sd
    src_char_ids = {
        host_sd.get("PalStorageContainerId", {}).get("value", {}).get("ID", {}).get("value"),
        host_sd.get("OtomoCharacterContainerId", {}).get("value", {}).get("ID", {}).get("value"),
    }
    inv_info = host_sd.get("InventoryInfo", {}).get("value", {})
    src_item_ids = {
        inv_info.get("CommonContainerId", {}).get("value", {}).get("ID", {}).get("value"),
        inv_info.get("EssentialContainerId", {}).get("value", {}).get("ID", {}).get("value"),
        inv_info.get("WeaponLoadOutContainerId", {}).get("value", {}).get("ID", {}).get("value"),
        inv_info.get("PlayerEquipArmorContainerId", {}).get("value", {}).get("ID", {}).get("value"),
        inv_info.get("FoodEquipContainerId", {}).get("value", {}).get("ID", {}).get("value"),
    }
    drop = inv_info.get("DropSlotContainerId", {}).get("value", {}).get("ID", {}).get("value")
    if drop:
        src_item_ids.add(drop)

    for container_key, src_ids in (("CharacterContainerSaveData", src_char_ids), ("ItemContainerSaveData", src_item_ids)):
        existing_ids = {c.get("key", {}).get("ID", {}).get("value") for c in target_wsd.get(container_key, {}).get("value", [])}
        for c in source_wsd.get(container_key, {}).get("value", []):
            cid = c["key"]["ID"]["value"]
            if cid in src_ids and cid not in existing_ids:
                target_wsd.setdefault(container_key, {}).setdefault("value", []).append(_fast_deepcopy(c))

    return True


def _transfer_tech_and_data(source_player_sd: dict, target_player_sd: dict):
    """Copy technology and appearance data between player save datas."""
    src = source_player_sd
    tgt = target_player_sd

    tech_keys = ["SkillMap", "PlayerTechData", "player_tech_data",
                 "PlayerTechnologyData", "PlayerTechnologyData2",
                 "TechnologyPoint", "TechnologyPoint2",
                 "BossTechnologyPoint", "AdditionalTechnologyPoint"]
    for k in tech_keys:
        if k in src:
            tgt[k] = _fast_deepcopy(src[k])

    appearance_keys = [
        "PlayerCharacterAppearanceData", "PlayerCustomName",
        "PlayerCustomNameCharacterName", "PlayerCustomNameCharacterName2",
        "PlayerCustomNameCharacterName3", "PlayerInputAllowDieData",
    ]
    for k in appearance_keys:
        if k in src:
            tgt[k] = _fast_deepcopy(src[k])

    record_keys = [
        "RecordData", "PlayerCaptureRecordData", "PlayerCaptureRecordData2",
        "PlayerDefeatBossRecordData", "PlayerDiscoverMapData",
        "PlayerExploreMapData", "PlayerExploreMapData2", "PlayerMapPingData",
        "PlayerDungeonData", "PlayerDungeonData2",
        "BuildObjectMapData", "SkyPresetData", "PlayerSpawnLocationData",
    ]
    for k in record_keys:
        if k in src:
            tgt[k] = _fast_deepcopy(src[k])

    return True


def _transfer_guild_to_target(
    target_wsd: dict,
    target_player_sd: dict,
    source_player_uid: str,
    target_player_uid: str,
    source_guild_dict: dict,
):
    """Copy guild membership from source player to target save."""
    guilds = target_wsd.get("GroupSaveDataMap", {}).get("value", [])
    if not source_guild_dict:
        return False

    target_guild = None
    for g in guilds:
        raw = g.get("value", {}).get("RawData", {}).get("value", {})
        if any(str(p.get("player_uid")) == str(target_player_uid) for p in raw.get("players", [])):
            target_guild = g
            break

    source_player = None
    source_entry = None
    for g in source_guild_dict.values():
        raw = g.get("value", {}).get("RawData", {}).get("value", {})
        for p in raw.get("players", []):
            if str(p.get("player_uid")) == str(source_player_uid):
                source_player = _fast_deepcopy(p)
                source_entry = g
                break
        if source_entry:
            break

    if source_entry is None:
        return False

    if source_player:
        source_player["player_uid"] = target_player_uid
        if "player_info" in source_player:
            source_player["player_info"]["last_online_real_time"] = 0

    if target_guild:
        target_raw = target_guild["value"]["RawData"]["value"]
        target_raw["players"] = [p for p in target_raw.get("players", []) if str(p.get("player_uid")) != str(target_player_uid)]
        if source_player:
            target_raw["players"].append(source_player)
        if str(target_raw.get("admin_player_uid")) == str(source_player_uid):
            target_raw["admin_player_uid"] = target_player_uid

        new_gid = target_raw.get("group_id")
        if new_gid:
            target_player_sd["GroupId"] = {
                "id": None, "value": new_gid,
                "type": "StructProperty",
                "struct_type": "Guid",
                "struct_id": "00000000-0000-0000-0000-000000000000",
            }
        return True

    # Create new guild
    cloned = _fast_deepcopy(source_entry)
    cloned["key"] = UUID_from_str(os.urandom(16).hex())
    raw = cloned["value"]["RawData"]["value"]
    raw["group_id"] = UUID_from_str(os.urandom(16).hex())
    raw["group_name"] = "Transferred Guild"
    raw["guild_name"] = "Transferred Guild"
    raw["players"] = [source_player] if source_player else [{
        "player_uid": target_player_uid,
        "player_info": {"last_online_real_time": 0, "player_name": "Player"},
    }]
    raw["admin_player_uid"] = target_player_uid
    player_inst_id = target_player_sd.get("IndividualId", {}).get("value", {}).get("InstanceId", {}).get("value")
    zero = UUID_from_str("00000000-0000-0000-0000-000000000000")
    raw["individual_character_handle_ids"] = [{"guid": zero, "instance_id": player_inst_id}]
    guilds.append(cloned)

    new_gid = raw["group_id"]
    target_player_sd["GroupId"] = {
        "id": None, "value": new_gid,
        "type": "StructProperty",
        "struct_type": "Guid",
        "struct_id": "00000000-0000-0000-0000-000000000000",
    }
    return True


def _transfer_pals_to_target(
    source_wsd: dict,
    target_wsd: dict,
    source_player_sd: dict,
    target_player_sd: dict,
    source_player_uid: str,
    target_player_uid: str,
    target_guild_id,
):
    """Migrate all owned pals from source player to target save."""
    zero = PalUUID.from_str("00000000-0000-0000-0000-000000000000")

    if not target_guild_id:
        target_guild_id = str(zero)

    # Remove existing pal entries for target player
    removed = set()
    cmap = target_wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    new_cmap = []
    for ch in cmap:
        try:
            spv = ch["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
            if str(spv.get("OwnerPlayerUId", {}).get("value")) == str(target_player_uid):
                removed.add(str(ch["key"]["InstanceId"]["value"]))
                continue
        except Exception:
            pass
        new_cmap.append(ch)
    cmap[:] = new_cmap

    # Clean container slots for removed pals
    t_pal_id = target_player_sd.get("PalStorageContainerId", {}).get("value", {}).get("ID", {}).get("value")
    t_oto_id = target_player_sd.get("OtomoCharacterContainerId", {}).get("value", {}).get("ID", {}).get("value")
    for cont in target_wsd.get("CharacterContainerSaveData", {}).get("value", []):
        cid = cont.get("key", {}).get("ID", {}).get("value")
        if cid in (t_pal_id, t_oto_id):
            slots = cont.get("value", {}).get("Slots", {}).get("value", {}).get("values", [])
            if slots:
                slots[:] = [s for s in slots if str(s.get("RawData", {}).get("value", {}).get("instance_id", "")) not in removed]

    # Clean guild handles
    for entry in target_wsd.get("GroupSaveDataMap", {}).get("value", []):
        try:
            raw = entry["value"]["RawData"]["value"]
            if str(raw.get("group_id")) == str(target_guild_id):
                handles = raw.get("individual_character_handle_ids", [])
                if handles:
                    handles[:] = [h for h in handles if str(h.get("instance_id", "")) not in removed]
        except Exception:
            pass

    # Scan and migrate source pals
    source_pals = _scan_source_pals(source_wsd, source_player_sd, source_player_uid)
    for pal_data in source_pals:
        if not _migrate_pal_to_target(pal_data, target_player_uid, target_wsd, target_player_sd, target_guild_id):
            return False

    return True


def _sync_player_timestamps(
    target_wsd: dict,
    target_player_uid: str,
    world_tick: int,
):
    """Sync player timestamps in target save."""
    if not world_tick:
        return
    t_uid_str = str(target_player_uid).lower()
    cmap = target_wsd.get("CharacterSaveParameterMap", {}).get("value", [])
    for char in cmap:
        try:
            if str(char["key"]["PlayerUId"]["value"]).lower() == t_uid_str:
                raw = char["value"]["RawData"]["value"]
                raw["last_online_real_time"] = world_tick
                params = raw.get("object", {}).get("SaveParameter", {}).get("value", {})
                if "LastOnlineRealTime" in params:
                    params["LastOnlineRealTime"]["value"] = world_tick
        except Exception:
            continue

    for gdata in target_wsd.get("GroupSaveDataMap", {}).get("value", []):
        try:
            raw = gdata["value"]["RawData"]["value"]
            for p_info in raw.get("players", []):
                if str(p_info.get("player_uid")).lower() == t_uid_str:
                    if "player_info" in p_info:
                        p_info["player_info"]["last_online_real_time"] = world_tick
        except Exception:
            continue


def _sync_dynamic_containers(source_wsd: dict, target_wsd: dict):
    """Merge dynamic item containers from source to target."""
    src_items = source_wsd.get("DynamicItemSaveData", {}).get("value", {}).get("values", [])
    tgt_items = target_wsd.setdefault("DynamicItemSaveData", {}).setdefault("value", {}).setdefault("values", [])
    tgt_by_id = {}
    for item in tgt_items:
        try:
            lid = item.get("RawData", {}).get("value", {}).get("id", {}).get("local_id_in_created_world")
            if lid:
                tgt_by_id[lid] = item
        except Exception:
            continue
    for item in src_items:
        try:
            lid = item.get("RawData", {}).get("value", {}).get("id", {}).get("local_id_in_created_world")
            if lid:
                tgt_by_id[lid] = item
        except Exception:
            continue
    target_wsd["DynamicItemSaveData"]["value"]["values"] = list(tgt_by_id.values())


def character_transfer(
    source_sav_path: str,
    target_sav_path: str,
    source_player_uid: str,
    target_player_uid: str | None = None,
    steps: dict | None = None,
) -> dict:
    """Transfer a character from one save to another.

    ``steps`` controls which aspects to transfer (default: all True):
    ``{"character": bool, "tech_data": bool, "inventory": bool,
       "guild": bool, "pals": bool, "dynamics": bool, "timestamps": bool}``

    Inventory transfer requires PlayerInventory (desktop-only) — skipped in headless mode.
    """
    if steps is None:
        steps = {
            "character": True, "tech_data": True, "inventory": False,
            "guild": True, "pals": True, "dynamics": True, "timestamps": True,
        }

    if not target_player_uid:
        target_player_uid = source_player_uid

    # Load source save
    src_gvas, src_st = _decode_level_sav(source_sav_path)
    src_wsd = src_gvas.properties["worldSaveData"]["value"]

    # Load target save
    tgt_gvas, tgt_st = _decode_level_sav(target_sav_path)
    tgt_wsd = tgt_gvas.properties["worldSaveData"]["value"]

    # Load player .sav files
    src_players_dir = Path(source_sav_path).parent / "Players"
    tgt_players_dir = Path(target_sav_path).parent / "Players"

    def _load_player_sd(players_dir, uid):
        uid_str = str(uid).upper()
        candidates = [
            players_dir / f"{uid_str}.sav",
            players_dir / f"{uid_str.replace('-', '')}.sav",
        ]
        for p in candidates:
            if p.exists():
                data = p.read_bytes()
                rg, _ = decompress_sav_to_gvas(data)
                g = GvasFile.read(rg, _TYPE_HINTS, _CUSTOM_PROPS)
                return g.properties.get("SaveData", {}).get("value", {})
        return None

    source_player_sd = _load_player_sd(src_players_dir, source_player_uid)
    target_player_sd = _load_player_sd(tgt_players_dir, target_player_uid)

    if not source_player_sd:
        return {"success": False, "error": f"Source player .sav not found for {source_player_uid}"}
    if not target_player_sd:
        return {"success": False, "error": f"Target player .sav not found for {target_player_uid}"}

    # Build source guild dict
    source_guild_dict = {}
    for g in src_wsd.get("GroupSaveDataMap", {}).get("value", []):
        try:
            if g.get("value", {}).get("GroupType", {}).get("value", {}).get("value") == "EPalGroupType::Guild":
                gid = g.get("value", {}).get("RawData", {}).get("value", {}).get("group_id")
                if gid:
                    source_guild_dict[str(gid)] = g
        except Exception:
            pass

    # Find or create target guild_id
    zero = UUID_from_str("00000000-0000-0000-0000-000000000000")
    target_guild_id = zero
    for g in tgt_wsd.get("GroupSaveDataMap", {}).get("value", []):
        try:
            raw = g["value"]["RawData"]["value"]
            if any(str(p.get("player_uid")) == str(target_player_uid) for p in raw.get("players", [])):
                target_guild_id = raw.get("group_id", zero)
                break
        except Exception:
            pass

    target_world_tick = 0
    try:
        target_world_tick = tgt_wsd["GameTimeSaveData"]["value"]["RealDateTimeTicks"]["value"]
    except Exception:
        pass

    if steps.get("character"):
        if not _transfer_character_to_target(src_wsd, tgt_wsd, source_player_sd, target_player_sd, source_player_uid, target_player_uid):
            return {"success": False, "error": "Character transfer failed"}

    if steps.get("tech_data"):
        _transfer_tech_and_data(source_player_sd, target_player_sd)

    if steps.get("guild"):
        if not _transfer_guild_to_target(tgt_wsd, target_player_sd, source_player_uid, target_player_uid, source_guild_dict):
            return {"success": False, "error": "Guild transfer failed"}

    if steps.get("pals"):
        if not _transfer_pals_to_target(src_wsd, tgt_wsd, source_player_sd, target_player_sd, source_player_uid, target_player_uid, target_guild_id):
            return {"success": False, "error": "Pal transfer failed"}

    if steps.get("dynamics"):
        _sync_dynamic_containers(src_wsd, tgt_wsd)

    if steps.get("timestamps"):
        _sync_player_timestamps(tgt_wsd, target_player_uid, target_world_tick)

    # Write back
    _encode_level_sav(tgt_gvas, tgt_st, target_sav_path)
    _encode_level_sav(src_gvas, src_st, source_sav_path)

    # Write player .sav files
    tgt_player_path = tgt_players_dir / f"{str(target_player_uid).upper().replace('-', '')}.sav"
    if tgt_player_path.exists():
        p_data = tgt_player_path.read_bytes()
        p_rg, p_st = decompress_sav_to_gvas(p_data)
        p_g = GvasFile.read(p_rg, _TYPE_HINTS, _CUSTOM_PROPS)
        p_g.properties["SaveData"]["value"] = target_player_sd
        _encode_level_sav(p_g, p_st, str(tgt_player_path))

    return {"success": True, "source_player": source_player_uid, "target_player": target_player_uid}


# ---------------------------------------------------------------------------
# Player Migrate — move a player's character + guild + pals to another save
# ---------------------------------------------------------------------------

def player_migrate(
    source_sav_path: str,
    target_sav_path: str,
    source_player_uid: str,
    target_player_uid: str | None = None,
) -> dict:
    """Migrate a player's guild / base / pals to another save file.

    This is a simplified character transfer that always transfers:
    character entry, tech/data, guild membership, and pals.
    """
    return character_transfer(
        source_sav_path=source_sav_path,
        target_sav_path=target_sav_path,
        source_player_uid=source_player_uid,
        target_player_uid=target_player_uid,
        steps={
            "character": True, "tech_data": True, "inventory": False,
            "guild": True, "pals": True, "dynamics": True, "timestamps": True,
        },
    )
