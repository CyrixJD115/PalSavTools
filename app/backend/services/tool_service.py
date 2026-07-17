"""Headless tool wrappers using the palsav-rs (Rust uesave) engine.

Each function wraps save-file manipulation logic from the corresponding
``src/toolsets/`` tool but uses only the Rust ``uesave`` binary (bridged via
``palsav_rs_wrapper``) and the Rust-shape dict navigation in
``world_service`` / ``base_service`` / ``player_service`` — no Qt, no PySide6,
no legacy Python ``palsav`` package.

The dict (in the Rust uesave JSON shape ``{header, schemas, root, extra}``) is
the source of truth: tools decode a ``.sav`` into a dict, mutate it, then
re-encode. Property keys carry an ``_<index>`` suffix; scalars are bare; maps
are flat ``[{key, value}]`` lists; the helpers in ``world_service``
(``_k``/``_g``/``_k_set``/``_map_entries``) tolerate the suffix.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from pathlib import Path
from uuid import UUID

from app.backend.services import world_service
from app.backend.services.palsav_rs_wrapper import (
    PalsavRsError,
    decode_sav,
    detect_save_type,
    encode_sav,
)

logger = logging.getLogger(__name__)

_NIL = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Shared Rust-shape helpers (local aliases for terseness)
# ---------------------------------------------------------------------------

def _k(node, name):
    return world_service._k(node, name)


def _g(node, *names, default=None):
    return world_service._g(node, *names, default=default)


def _map_entries(wsd, key):
    return world_service._map_entries(wsd, key)


def _wsd(level_dict):
    return world_service.get_world_save_data(level_dict)


def _nu(x: str) -> str:
    return str(x).replace("-", "").lower()


def _fmt(guid: str) -> str:
    g = str(guid).replace("-", "").lower()
    return f"{g[:8]}-{g[8:12]}-{g[12:16]}-{g[16:20]}-{g[20:]}"


def _k_set(node, name, value) -> None:
    """Set node[name_0] preserving the existing key form."""
    if not isinstance(node, dict):
        return
    suffixed = name + "_0"
    if suffixed in node:
        node[suffixed] = value
    elif name in node:
        node[name] = value
    else:
        node[suffixed] = value


def _guild_struct(g: dict) -> dict:
    """The typed ``PalGroupData -> Guild`` sub-struct of a guild group entry."""
    return _g(g, "value", "RawData", "data", "Guild") or {}


def _guild_top_raw(g: dict) -> dict:
    """The top-level ``RawData`` struct (group_id, handles, ...) of a group."""
    return _g(g, "value", "RawData") or {}


def _guild_players(g: dict) -> list:
    return _g(_guild_struct(g), "tail", "PreUpdate", "players") or []


# ---------------------------------------------------------------------------
# Ownership resolver (Rust shape)
# ---------------------------------------------------------------------------

class _LazyOwnership:
    """Resolve which player owns a character instance (Rust shape).

    Mirrors ``palworld_aio.inventory.container_ownership.ContainerOwnership``
    but reads the Rust uesave shape directly. Used by fix_guild / transfer.
    """

    def __init__(self, cmap: list, containers: list) -> None:
        self._container_owner: dict[str, str] = {}
        self._inst_container: dict[str, str] = {}
        for c in containers:
            cid = c.get("key")
            cid_s = _nu(cid) if isinstance(cid, dict) else _nu(str(cid or ""))
            if not cid_s:
                cid_obj = c.get("value", {}).get("ID", {})
                cid_s = _nu(_k(cid_obj, "ID") or "")
            belong = _g(c, "value", "BelongInfo") or {}
            uid = _k(belong, "PlayerUId")
            if uid and cid_s:
                self._container_owner[cid_s] = _nu(str(uid))
        for ch in cmap:
            inst = _g(ch, "key", "InstanceId")
            sp = world_service._pal_entry_raw(ch)
            slot_id = _g(sp, "SlotId", "ContainerId", "ID")
            if inst and slot_id:
                self._inst_container[_nu(str(inst))] = _nu(str(slot_id))

    def get_effective_owner(self, instance_id, owner_field):
        if owner_field:
            return str(owner_field)
        cid = self._inst_container.get(_nu(str(instance_id)))
        if cid:
            return self._container_owner.get(cid)
        return None

    def belongs_to_player(self, instance_id, owner_field, player_uid):
        eff = self.get_effective_owner(instance_id, owner_field)
        return _nu(str(eff)) == _nu(str(player_uid))

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
    """Convert a .sav file to/from .json using the palsav-rs uesave binary.

    ``direction`` is ``"sav2json"`` or ``"json2sav"``.
    Returns ``{"source": ..., "target": ..., "size": ...}``.
    """
    inp = Path(input_path).resolve()
    if not inp.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")
    out = Path(output_path) if output_path else inp.with_suffix(
        ".json" if direction == "sav2json" else ".sav",
    )
    out = out.resolve()

    if direction == "sav2json":
        level_dict, _ = decode_sav(inp)
        out.write_text(json.dumps(level_dict), encoding="utf-8")
    else:  # json2sav
        with inp.open("r", encoding="utf-8") as f:
            level_dict = json.load(f)
        # Infer the original save_type from the sibling .sav if present, else PLM.
        save_type = detect_save_type(Path(input_path).read_bytes()) if inp.suffix == ".json" and inp.with_suffix(".sav").exists() else 49
        out.write_bytes(encode_sav(level_dict, save_type))

    return {"source": str(inp), "target": str(out), "size": out.stat().st_size}


# ---------------------------------------------------------------------------
# Convert IDs (Steam ID <-> Palworld UID)
# ---------------------------------------------------------------------------

# Standalone CityHash64 (CityHash by Google) — replaces palsav._cityhash.
# The exact variant Palworld uses: CityHash64 on the UTF-16-LE encoded digits.
def _cityhash64(data: bytes) -> int:
    const = 0x9DDFEA08EB382D69
    mask = 0xFFFFFFFFFFFFFFFF
    mult = 0x9E3779B97F4A7C15
    len_ = len(data)

    def fetch64(p: int) -> int:
        return int.from_bytes(data[p:p + 8], "little")

    def fetch32(p: int) -> int:
        return int.from_bytes(data[p:p + 4], "little")

    def rotate(val: int, shift: int) -> int:
        return ((val >> shift) | (val << (64 - shift))) & mask

    def shift_mix(val: int) -> int:
        return (val ^ (val >> 47)) & mask

    def hash_len_16(u, v):
        a = (u * mult) & mask
        a = rotate(a, 31)
        a = (a * mult) & mask
        b = (v * mult) & mask
        h = (a ^ b) & mask
        h = (h * mult) & mask
        b = rotate(b, 33)
        b = (b * mult) & mask
        h = (h ^ b) & mask
        return h

    def weak_hash_len_32_with_seeds(w, x, y, z, a, b):
        a = (a + w) & mask
        b = rotate((b + a + z) & mask, 21)
        c = a & mask
        a = (a + x + y) & mask
        b = (b + a) & mask
        return (a, b)

    def weak_hash_len_32_with_seeds_data(s, a, b):
        return weak_hash_len_32_with_seeds(
            fetch32(s), fetch32(s + 4), fetch32(s + 8), fetch32(s + 12), a, b,
        )

    def hash_len_0_to_16():
        if len_ >= 8:
            mul = (mult * (fetch64(0) ^ 0)) & mask
            a = (fetch64(0) + fetch64(len_ - 8)) & mask
            b = rotate(a, 43) & mask
            c = ((a * mul) ^ b) & mask
            d = (rotate(b, 31) + c) & mask
            mul = (mul * const) & mask
            h = ((c * mul) ^ (d * mult)) & mask
            h = (h * mult) ^ d
            return shift_mix(h)
        if len_ >= 4:
            mul = (mult * fetch32(0)) & mask
            return shift_mix((rotate(fetch32(0) * mul & mask, 17) * fetch32(len_ - 4) * mult) & mask)
        if len_ > 0:
            a = data[0]
            b = data[len_ >> 1]
            c = data[len_ - 1]
            y = (a + (b << 8)) & mask
            z = (len_ + (c << 2)) & mask
            return shift_mix((mult * y) ^ (const * z)) & mask
        return mult

    if len_ <= 16:
        return hash_len_0_to_16()

    x = fetch64(len_ - 40)
    y = fetch64(len_ - 16) + fetch64(len_ - 56)
    z = (hash_len_16(fetch64(len_ - 48) + len_, fetch64(len_ - 24)) +
         fetch64(0)) & mask

    while len_ > 64:
        x = (rotate(x + y + fetch64(0) + fetch32(8), 37) * const) & mask
        y = (rotate(y + fetch64(8) + fetch32(16 + 8), 42) * const) & mask
        x ^= fetch64(16 + 24)
        y = (y + fetch64(16 + 32)) & mask
        z = (rotate(z + fetch64(16 + 40), 33) * const) & mask
        v = weak_hash_len_32_with_seeds_data(16, z, y)
        w = weak_hash_len_32_with_seeds_data(16 + 32, (z + fetch64(16 + 16)) & mask, fetch64(16 + 48) + x)
        x = (x + v[0]) & mask
        y = (v[1] + y) & mask
        z = (z + w[0]) & mask
        a = (hash_len_16(v[0] + w[1], y + fetch64(16 + 8)) + z) & mask
        b = (hash_len_16(w[0] + v[1], z + fetch64(16 + 56)) + x) & mask
        data = data[64:]
        len_ -= 64

    a = (hash_len_16(fetch64(0) ^ const, fetch64(8) ^ const) + (fetch64(16) ^ len_)) & mask
    b = (hash_len_16(fetch64(24) + z, fetch64(32) + y) + a) & mask
    c = (hash_len_16(b, fetch64(40) + x) + z) & mask
    d = (hash_len_16(a, fetch64(48) + z) + b) & mask
    e = (hash_len_16(c, fetch64(56) + b) + d) & mask
    if len_ > 56:
        x = (x + fetch64(0)) & mask
        y = (y + fetch64(8)) & mask
        z = (z + fetch64(16)) & mask
        a = (hash_len_16(fetch64(0) ^ const, fetch64(8) ^ const) + (fetch64(16) ^ len_)) & mask
        b = (hash_len_16(fetch64(24) + z, fetch64(32) + y) + a) & mask
        c = (hash_len_16(b, fetch64(40) + x) + z) & mask
    return hash_len_16(c, e)


def _steam_id_to_palworld_uid(steam_id: int) -> str:
    """Convert a Steam 64-bit ID to a Palworld UUID string (w/ dashes, upper)."""
    h = _cityhash64(str(steam_id).encode("utf-16-le"))
    lo = h & 0xFFFFFFFF
    hi = (((h >> 32) & 0xFFFFFFFF) * 23 + lo) & 0xFFFFFFFF
    raw = hi.to_bytes(4, "little") + b"\x00" * 12
    return str(UUID(bytes=raw)).upper()


def _palworld_uid_to_nosteam(palworld_uid: str) -> str:
    """Palworld UUID -> NoSteam hex string (8-char prefix + suffix)."""
    u = UUID(palworld_uid)
    raw = u.bytes[0:4]
    val = int.from_bytes(raw, "little", signed=True) & 0xFFFFFFFF

    def u32(x: int) -> int:
        return x & 0xFFFFFFFF

    a = u32(u32(val << 8) ^ u32(2654435769 - val))
    b = u32(a >> 13 ^ u32(-(val + a)))
    c = u32(b >> 12 ^ u32(val - a - b))
    d = u32(u32(c << 16) ^ u32(a - c - b))
    e = u32(d >> 5 ^ b - d - c)
    f = u32(e >> 3 ^ c - d - e)
    r = u32(u32(u32(f << 10) ^ u32(d - f - e)) >> 15 ^ e - (u32(f << 10) ^ u32(d - f - e)) - f)
    return f"{r:08X}-0000-0000-0000-000000000000"


def detect_input_type(input_str: str) -> str:
    """Return ``"steam_id"``, ``"palworld_uid"``, ``"nosteam_uid"``, or ``"unknown"``."""
    s = input_str.strip()
    if s.startswith("steam_"):
        s = s[6:]
    if s.isdigit() and len(s) == 17:
        return "steam_id"
    if "steamcommunity.com/profiles/" in s:
        return "steam_id"
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
        "input": raw, "input_type": input_type,
        "steam_id": None, "palworld_uid": None, "nosteam_uid": None,
    }
    if input_type == "steam_id":
        s = raw
        if "steamcommunity.com/profiles/" in s:
            s = s.split("steamcommunity.com/profiles/")[1].split("/")[0]
        elif s.startswith("steam_"):
            s = s[6:]
        steam_id = int(s)
        puid = _steam_id_to_palworld_uid(steam_id)
        result["steam_id"] = str(steam_id)
        result["palworld_uid"] = puid
        result["nosteam_uid"] = _palworld_uid_to_nosteam(puid)
    elif input_type == "palworld_uid":
        result["palworld_uid"] = raw
        result["nosteam_uid"] = _palworld_uid_to_nosteam(raw)
    elif input_type == "nosteam_uid":
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
    level_dict, save_type = decode_sav(data)
    sd = _g(level_dict, "root", "properties", "SaveData") or {}

    world_map_cleared = False
    hidden_locations_reset = 0

    # WorldMapUISaveDataMap -> mask texture (a byte array in the Rust shape).
    wmap = _k(sd, "WorldMapUISaveDataMap")
    if isinstance(wmap, list):
        for entry in wmap:
            mask = _g(entry, "value", "MaskTextureData")
            mask_bytes = _k(mask, "Byte") if isinstance(mask, dict) else None
            if isinstance(mask_bytes, list) and mask_bytes:
                n = len(mask_bytes)
                _k_set(mask, "Byte", [0] * n)
                world_map_cleared = True
    elif isinstance(_k(sd, "WorldMapMaskTextureV4"), list):
        mask = _k(sd, "WorldMapMaskTextureV4")
        n = len(mask)
        _k_set(sd, "WorldMapMaskTextureV4", [0] * n)
        world_map_cleared = True

    # Hidden location flags.
    hl = _k(sd, "Local_HiddenLocationFlagMap")
    if isinstance(hl, list):
        for entry in hl:
            _k_set(entry.get("value", entry) if isinstance(entry, dict) else entry, "value", False)
        hidden_locations_reset = len(hl)

    p.write_bytes(encode_sav(level_dict, save_type))
    return {
        "file": str(p),
        "world_map_cleared": world_map_cleared,
        "hidden_locations_reset": hidden_locations_reset,
    }


# ---------------------------------------------------------------------------
# decode / encode Level.sav helpers (Rust shape)
# ---------------------------------------------------------------------------

def _decode_level_sav(filepath: str) -> tuple[dict, int]:
    return decode_sav(Path(filepath).read_bytes())


def _encode_level_sav(level_dict: dict, save_type: int, filepath: str) -> None:
    Path(filepath).write_bytes(encode_sav(level_dict, save_type))


# ---------------------------------------------------------------------------
# Player info / container queries (used by slot injector + UI)
# ---------------------------------------------------------------------------

def _query_player_info_from_wsd(wsd: dict, players_folder: str | None = None) -> list[dict]:
    """Extract player info from an already-decoded worldSaveData dict (Rust shape).

    Returns list of ``{"uid", "name", "guild", "party_id", "palbox_id"}``.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    players: dict[str, dict] = {}
    valid_uids: set[str] = set()

    for g in _map_entries(wsd, "GroupSaveDataMap"):
        if world_service._group_type(g) != "EPalGroupType::Guild":
            continue
        gname = _k(_guild_struct(g), "guild_name") or "Unknown Guild"
        for p in _guild_players(g):
            puid = _k(p, "player_uid")
            puid_str = _nu(puid) if puid else ""
            if not puid_str:
                continue
            valid_uids.add(puid_str)
            info = _k(p, "player_info") or {}
            players[puid_str] = {
                "uid": puid_str,
                "name": _k(info, "player_name") or "Unknown",
                "guild": gname,
                "party_id": None,
                "palbox_id": None,
            }

    for entry in _map_entries(wsd, "CharacterSaveParameterMap"):
        key = _g(entry, "key") or {}
        puid = _k(key, "PlayerUId")
        puid_str = _nu(puid) if puid else ""
        if puid_str == _nu(_NIL):
            continue
        sp = world_service._pal_entry_raw(entry)
        is_player = _k(sp, "IsPlayer")
        nick = _k(sp, "NickName")
        if is_player and puid_str not in players:
            players[puid_str] = {
                "uid": puid_str,
                "name": str(nick) if nick else "Unknown",
                "guild": "Unknown Guild",
                "party_id": None, "palbox_id": None,
            }
        elif is_player and nick and players.get(puid_str, {}).get("name") == "Unknown":
            players[puid_str]["name"] = str(nick)

    # Read player .sav files for container IDs.
    if players_folder and valid_uids:
        folder = Path(players_folder)
        if folder.exists():
            def load_player_container(fname: str):
                try:
                    pf = folder / fname
                    pdict, _ = decode_sav(pf.read_bytes())
                    psd = _g(pdict, "root", "properties", "SaveData") or {}
                    p_uid_raw = fname.replace(".sav", "").lower()
                    box = _g(psd, "PalStorageContainerId", "ID")
                    party = _g(psd, "OtomoCharacterContainerId", "ID")
                    if box or party:
                        return (p_uid_raw, {
                            "party_id": _nu(party) if party else None,
                            "palbox_id": _nu(box) if box else None,
                        })
                except Exception:
                    pass
                return None

            pfiles = [f for f in os.listdir(str(folder))
                      if f.endswith(".sav") and "_dps" not in f
                      and f.replace(".sav", "").lower() in valid_uids]
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
    level_dict, _ = _decode_level_sav(level_sav_path)
    return _query_player_info_from_wsd(_wsd(level_dict), players_folder)


def _query_player_containers_from_wsd(wsd: dict, players_list: list[dict]) -> list[dict]:
    """List character containers with slot counts (Rust shape).

    Returns ``[{"index","container_id","slot_num","used_slots","player_uid",
    "player_name","guild","container_type"}]``.
    """
    c2p: dict[str, dict] = {}
    for p in players_list:
        if p.get("party_id"):
            c2p[p["party_id"]] = {"type": "Party", **p}
        if p.get("palbox_id"):
            c2p[p["palbox_id"]] = {"type": "PalBox", **p}

    result = []
    for i, entry in enumerate(_map_entries(wsd, "CharacterContainerSaveData")):
        slot_num = _g(entry, "value", "SlotNum") or 0
        try:
            slot_num = int(slot_num)
        except (TypeError, ValueError):
            slot_num = 0
        if slot_num < 960:
            continue
        key = entry.get("key")
        cid = _k(key, "ID") if isinstance(key, dict) else key
        cid_str = _nu(cid) if cid else ""
        slots = _g(entry, "value", "Slots")
        used = len(slots) if isinstance(slots, list) else 0
        owner = c2p.get(cid_str)
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
    level_dict, _ = _decode_level_sav(level_sav_path)
    wsd = _wsd(level_dict)
    players_list = _query_player_info_from_wsd(wsd, players_folder)
    return _query_player_containers_from_wsd(wsd, players_list)


# ---------------------------------------------------------------------------
# Slot Injector
# ---------------------------------------------------------------------------

def _apply_slot_injector_to_gvas(
    level_dict: dict,
    save_type: int,
    players_folder: str | None = None,
    new_slot_count: int = 960,
    container_ids: list[str] | None = None,
) -> dict:
    """Modify pal container slot counts in an already-loaded dict (Rust shape).

    Mutates ``level_dict`` in place. Returns result dict.
    """
    wsd = _wsd(level_dict)
    container = _map_entries(wsd, "CharacterContainerSaveData")
    players_list = _query_player_info_from_wsd(wsd, players_folder)
    c2p: dict[str, dict] = {}
    for p in players_list:
        if p.get("party_id"):
            c2p[p["party_id"]] = p
        if p.get("palbox_id"):
            c2p[p["palbox_id"]] = p

    targets = []
    for entry in container:
        key = entry.get("key")
        cid = _k(key, "ID") if isinstance(key, dict) else key
        cid_str = _nu(cid) if cid else ""
        if container_ids and cid_str not in container_ids:
            continue
        targets.append((cid_str, entry))

    if not targets:
        return {"containers_modified": 0, "pals_removed": 0, "container_ids": []}

    removed_total = 0
    modified_ids = []
    char_map = _map_entries(wsd, "CharacterSaveParameterMap")

    for cid_str, entry in targets:
        slots_node = _g(entry, "value", "Slots")
        old_slot_num = _g(entry, "value", "SlotNum") or 0
        try:
            old_slot_num = int(old_slot_num)
        except (TypeError, ValueError):
            old_slot_num = 0
        _k_set(_g(entry, "value"), "SlotNum", new_slot_count)

        if isinstance(slots_node, list):
            slots_node[:] = [
                s for s in slots_node
                if (_g(s, "SlotIndex") or 0) < new_slot_count
            ]

        if old_slot_num > new_slot_count:
            removed = []
            kept = []
            for ce in char_map:
                try:
                    sp = world_service._pal_entry_raw(ce)
                    sid = _g(sp, "SlotId")
                    if sid:
                        cont_ref = _g(sid, "ContainerId", "ID")
                        slot_idx = _k(sid, "SlotIndex")
                        if (cont_ref and _nu(cont_ref) == cid_str
                                and slot_idx is not None and slot_idx >= new_slot_count):
                            inst = _g(ce, "key", "InstanceId")
                            removed.append(str(inst) if inst else "")
                            continue
                    kept.append(ce)
                except Exception:
                    kept.append(ce)
            char_map[:] = kept
            removed_total += len(removed)

            removed_lower = {_nu(r) for r in removed}
            for ge in _map_entries(wsd, "GroupSaveDataMap"):
                top = _guild_top_raw(ge)
                handles = _k(top, "individual_character_handle_ids")
                if isinstance(handles, list):
                    _k_set(top, "individual_character_handle_ids", [
                        h for h in handles
                        if _nu(_k(h, "instance_id")) not in removed_lower
                    ])

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
    level_dict, save_type = _decode_level_sav(level_sav_path)
    result = _apply_slot_injector_to_gvas(
        level_dict, save_type,
        players_folder=players_folder,
        new_slot_count=new_slot_count,
        container_ids=container_ids,
    )
    _encode_level_sav(level_dict, save_type, level_sav_path)
    return result


# ---------------------------------------------------------------------------
# Export loaded save as JSON
# ---------------------------------------------------------------------------

def export_loaded_save_json(level_dict: dict, output_path: str) -> dict:
    """Dump an already-loaded level_dict to pretty-printed JSON on disk."""
    Path(output_path).write_text(json.dumps(level_dict), encoding="utf-8")
    return {"output": output_path, "size": Path(output_path).stat().st_size}


# ---------------------------------------------------------------------------
# Fix Host Save — GUID swap between two players in the same save
# ---------------------------------------------------------------------------

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
            pre = _g(gstruct, "tail", "PreUpdate") or {}
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


# ---------------------------------------------------------------------------
# Fix Guild — move a player to a different guild within the same save
# ---------------------------------------------------------------------------

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
    origin_pre = _g(_guild_struct(origin_group), "tail", "PreUpdate") or {}
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
    target_pre = _g(target_struct, "tail", "PreUpdate") or {}
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


# ---------------------------------------------------------------------------
# Character Transfer — cross-save player migration (Rust shape)
# ---------------------------------------------------------------------------

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
        tpre = _g(tstruct, "tail", "PreUpdate") or {}
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
    cpre = _g(cstruct, "tail", "PreUpdate") or {}
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
        pre = _g(_guild_struct(gdata), "tail", "PreUpdate") or {}
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


# ---------------------------------------------------------------------------
# Player Migrate — simplified character transfer
# ---------------------------------------------------------------------------

def player_migrate(
    source_sav_path: str,
    target_sav_path: str,
    source_player_uid: str,
    target_player_uid: str | None = None,
) -> dict:
    """Migrate a player's guild / base / pals to another save file."""
    return character_transfer(
        source_sav_path=source_sav_path,
        target_sav_path=target_sav_path,
        source_player_uid=source_player_uid,
        target_player_uid=target_player_uid,
        steps={"character": True, "tech_data": True, "inventory": False,
               "guild": True, "pals": True, "dynamics": True, "timestamps": True},
    )
