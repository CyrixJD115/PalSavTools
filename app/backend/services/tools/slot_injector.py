
from __future__ import annotations
from .core import (
    _g, _k, _nu, _k_set, _map_entries, _wsd,
    _decode_level_sav, _encode_level_sav, _query_player_info_from_wsd
)
from app.backend.services import world_service


# Slot Injector


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


