
from __future__ import annotations
import logging
from pathlib import Path

from app.backend.services import world_service
from app.backend.services.palsav_rs_wrapper import decode_sav, encode_sav

logger = logging.getLogger(__name__)

_NIL = "00000000-0000-0000-0000-000000000000"



# Shared Rust-shape helpers (local aliases for terseness)


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
    return world_service._gplayers(g) or []




# Ownership resolver (Rust shape)


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




# decode / encode Level.sav helpers (Rust shape)


def _decode_level_sav(filepath: str) -> tuple[dict, int]:
    return decode_sav(Path(filepath).read_bytes())


def _encode_level_sav(level_dict: dict, save_type: int, filepath: str) -> None:
    Path(filepath).write_bytes(encode_sav(level_dict, save_type))




# Player info / container queries (used by slot injector + UI)


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


