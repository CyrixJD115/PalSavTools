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

from palsav.archive import FArchiveReader, FArchiveWriter
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


def get_player_info(level_sav_path: str, players_folder: str | None = None) -> list[dict]:
    """Extract player info from a Level.sav.

    Returns list of ``{"uid", "name", "guild", "party_id", "palbox_id"}``.
    """
    gvas, _st = _decode_level_sav(level_sav_path)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    wsd = gvas.properties.get("worldSaveData", {}).get("value", {})
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


def get_player_containers(level_sav_path: str, players_folder: str | None = None) -> list[dict]:
    """List all character containers with player info.

    Returns list of ``{"index", "container_id", "slot_num", "used_slots", "player_uid", "player_name", "guild", "container_type"}``.
    """
    gvas, _st = _decode_level_sav(level_sav_path)
    players_list = get_player_info(level_sav_path, players_folder)
    players_map = {p["uid"]: p for p in players_list}

    wsd = gvas.properties.get("worldSaveData", {}).get("value", {})
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


def apply_slot_injector(
    level_sav_path: str,
    players_folder: str | None = None,
    new_slot_count: int = 960,
    container_ids: list[str] | None = None,
) -> dict:
    """Modify pal container slot counts in a Level.sav.

    If ``container_ids`` is ``None``, applies to ALL containers.
    Returns ``{"containers_modified": int, "pals_removed": int, "container_ids": list}``.
    """
    gvas, save_type = _decode_level_sav(level_sav_path)
    wsd = gvas.properties["worldSaveData"]["value"]
    container = wsd.get("CharacterContainerSaveData", {}).get("value", [])

    # Build owner mapping to detect player containers
    players_list = get_player_info(level_sav_path, players_folder)
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

    _encode_level_sav(gvas, save_type, level_sav_path)

    return {
        "containers_modified": len(modified_ids),
        "pals_removed": removed_total,
        "container_ids": modified_ids,
    }
