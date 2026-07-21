"""Container mutation operations for the web backend.

Operates on ``level_dict`` (the Rust uesave shape). Container slots live at
``value.Slots_0[].RawData_0`` (a flat list, each slot decoded to
``{slot_index, count, item:{static_id, dynamic_id:{...}}, trailing_bytes}``).
Map-object-backed containers are linked via
``MapObjectSaveData[].ConcreteModel_0.ModuleMap_0[].value.RawData_0.data.
ItemContainer.target_container_id``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.backend.services.world_service import (
    _g, _k, _map_entries, _norm_uid, get_world_save_data,
)
from app.backend.services.base_service import _s, _extract_id

_NIL = "00000000-0000-0000-0000-000000000000"


# ---- slot helpers -----------------------------------------------------------

def _slot_raw(entry: dict) -> dict:
    """The ``RawData`` of a container slot entry."""
    return _k(entry, "RawData") or {}


def _count_items(slots: list | None) -> int:
    if not isinstance(slots, list):
        return 0
    return sum(1 for e in slots if _k(_slot_raw(e), "count"))


def _get_slots(
    slots: list | None,
    dyn_index: dict | None = None,
) -> list[dict]:
    """Extract non-empty item slots for display.

    ``dyn_index`` is the optional ``{local_id -> detail}`` map produced by
    :func:`dynamic_item_service.build_dynamic_index`. When supplied, each slot
    whose ``dynamic_id`` resolves gets a ``"dynamic"`` payload attached
    (weapon durability / passives, armor durability, egg character + talents).
    """
    if not isinstance(slots, list):
        return []
    out: list[dict] = []
    for entry in slots:
        raw = _slot_raw(entry)
        count = _k(raw, "count") or 0
        if not count:
            continue
        item = _k(raw, "item") or {}
        static_id = _k(item, "static_id") or ""
        dynamic = _k(item, "dynamic_id") or {}
        dyn_id = None
        lid = _k(dynamic, "local_id_in_created_world")
        if lid and _s(lid) != _s(_NIL):
            dyn_id = str(lid)
        si = _k(raw, "slot_index")
        slot_dict = {
            "slot_index": int(si) if si is not None else 0,
            "count": int(count),
            "static_id": str(static_id) if static_id else "",
            "dynamic_id": dyn_id,
        }
        # Attach decoded weapon/armor/egg payload when the slot references a
        # DynamicItemSaveData entry and the caller supplied an index.
        if dyn_id and dyn_index is not None:
            detail = dyn_index.get(dyn_id)
            if detail is not None:
                slot_dict["dynamic"] = detail
        out.append(slot_dict)
    return out


def _empty_slot(index: int) -> dict:
    """A zero-count slot entry in the Rust shape (for container expansion)."""
    return {
        "RawData_0": {
            "slot_index": index,
            "count": 0,
            "item": {
                "static_id": "",
                "dynamic_id": {
                    "created_world_id": _NIL,
                    "local_id_in_created_world": _NIL,
                },
            },
            "trailing_bytes": [0] * 20,
        },
        "CustomVersionData_0": {"Byte": []},
    }


# ---- map-object index -------------------------------------------------------

def _build_map_object_index(wsd: dict) -> dict[str, dict]:
    """Map ``container_id`` -> ``{type, location, base_camp_id}``."""
    index: dict[str, dict] = {}
    for obj in _map_entries(wsd, "MapObjectSaveData"):
        try:
            module_map = _g(obj, "ConcreteModel", "ModuleMap") or []
            target_cid = None
            for mod in (module_map if isinstance(module_map, list) else []):
                if _k(mod, "key") != "EPalMapObjectConcreteModelModuleType::ItemContainer":
                    continue
                target_cid = _s(_g(
                    mod, "value", "RawData", "data", "ItemContainer",
                    "target_container_id",
                ))
                break
            if not target_cid:
                continue

            model_raw = _g(obj, "Model", "RawData") or {}
            map_obj_id = str(_k(obj, "MapObjectId") or "")
            trans = _g(model_raw, "initital_transform_cache", "translation") or {}
            base_camp = _norm_uid(_k(model_raw, "base_camp_id_belong_to"))

            index[target_cid] = {
                "type": _classify_container(map_obj_id),
                "map_object_id": map_obj_id,
                "location": (
                    (float(trans["x"]), float(trans["y"]), float(trans["z"]))
                    if trans and "x" in trans else None
                ),
                "base_camp_id": base_camp,
            }
        except Exception:
            continue
    return index


def _classify_container(map_obj_id: str) -> str:
    mid = str(map_obj_id).lower()
    if "guildchest" in mid:
        return "Guild Chest"
    if "palbox" in mid or "pal_box" in mid:
        return "PalBox"
    if "booth" in mid:
        return "Booth"
    if "itemchest" in mid:
        return "Chest"
    if "storagebox" in mid:
        return "Storage Box"
    if "itembox" in mid:
        return "Item Box"
    if "itemcontainer" in mid or mid == "container01_iron":
        return "Container"
    if "ammo" in mid:
        return "Ammo Box"
    if "refrigerator" in mid:
        return "Refrigerator"
    if "foodbox" in mid or "feed_box" in mid:
        return "Feed Box"
    if "campfire" in mid:
        return "Campfire"
    if any(p in mid for p in ("copperpit", "coalpit", "crystalpit", "quartzpit", "sulfurpit", "stonepit")):
        return "Mining Pit"
    if "oilpump" in mid:
        return "Oil Pump"
    if "blastfurnace" in mid:
        return "Blast Furnace"
    if "spherefactory" in mid:
        return "Sphere Factory"
    if "weaponfactory" in mid:
        return "Weapon Factory"
    if "factory" in mid:
        return "Factory"
    if "workbench" in mid:
        return "Workbench"
    if "kitchen" in mid:
        return "Kitchen"
    if any(m in mid for m in ("medicinefacility", "medicinetable", "medic")):
        return "Medicine Facility"
    if "breedfarm" in mid or "breeding" in mid:
        return "Breeding Farm"
    if "expedition" in mid:
        return "Expedition Station"
    if "icecrusher" in mid:
        return "Ice Crusher"
    if "crusher" in mid:
        return "Crusher"
    if "flourmill" in mid:
        return "Flour Mill"
    if "compositedesk" in mid:
        return "Assembly Desk"
    if "hatching" in mid or "egg" in mid:
        return "Egg Incubator"
    if "skillunlock" in mid:
        return "Technology Unlock"
    if "deforest" in mid:
        return "Logging Site"
    if "money" in mid:
        return "Gold Factory"
    return "Unknown"


def _build_guild_names(wsd: dict) -> dict[str, str]:
    """Build ``guild_id`` -> ``name`` lookup."""
    names: dict[str, str] = {}
    for g in _map_entries(wsd, "GroupSaveDataMap"):
        try:
            gid = _s(g.get("key"))
            gname = _g(g, "value", "RawData", "data", "Guild", "guild_name")
            names[gid] = str(gname) if gname else "Unnamed Guild"
        except Exception:
            continue
    return names


def _enrich_container(
    entry: dict, map_index: dict, guild_names: dict,
) -> dict | None:
    """Enrich a single container entry with type, location, guild, items."""
    try:
        cid = _extract_id(entry.get("key"))
        cid_clean = _s(entry.get("key"))
        belong = _g(entry, "value", "BelongInfo") or {}
        slot_num = _g(entry, "value", "SlotNum")
        try:
            slot_count = int(slot_num) if slot_num is not None else 0
        except (TypeError, ValueError):
            slot_count = 0
        slots = _g(entry, "value", "Slots")
        item_count = _count_items(slots)

        owner_uid = _norm_uid(_k(belong, "PlayerUId"))
        guild_id = _norm_uid(_k(belong, "GroupId"))

        map_info = map_index.get(cid_clean, {})
        return {
            "id": cid,
            "container_type": map_info.get("type", "Unknown"),
            "owner_player_uid": owner_uid,
            "guild_id": guild_id,
            "guild_name": guild_names.get(_s(guild_id)) if guild_id else None,
            "base_camp_id": map_info.get("base_camp_id"),
            "slot_count": slot_count,
            "item_count": item_count,
            "location": map_info.get("location"),
        }
    except Exception:
        return None


# ---- Public API -------------------------------------------------------------

def list_containers_from_wsd(
    wsd: dict, offset: int = 0, limit: int = 500,
) -> tuple[list[dict], int]:
    """Lazy variant of :func:`list_containers` — takes a ``wsd`` slice directly.

    Lets the route layer pull only the sections it needs via
    ``loaded.build_mini_wsd(...)`` instead of materializing the full
    ~200 MB ``level_dict``.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_index = pool.submit(_build_map_object_index, wsd)
        fut_names = pool.submit(_build_guild_names, wsd)
        map_index = fut_index.result()
        guild_names = fut_names.result()

    all_entries = _map_entries(wsd, "ItemContainerSaveData")
    total = len(all_entries)
    page = all_entries[offset:offset + limit]

    out: list[dict] = []
    for entry in page:
        enriched = _enrich_container(entry, map_index, guild_names)
        if enriched is not None:
            out.append(enriched)
    return out, total


def list_containers(
    level_dict: dict, offset: int = 0, limit: int = 500,
) -> tuple[list[dict], int]:
    """Enriched container list with item count, type, and location.

    Returns ``(containers_slice, total)``. The map-object index + guild names
    are built in parallel threads, then only the requested page is enriched.

    .. note::
       Prefer :func:`list_containers_from_wsd` from a route — pass it a
       ``build_mini_wsd`` slice. This wrapper forces full ``level_dict``
       materialization and is kept for compatibility.
    """
    return list_containers_from_wsd(get_world_save_data(level_dict), offset, limit)


def get_container_detail_from_wsd(
    wsd: dict, container_id: str, dyn_index: dict | None = None,
) -> dict | None:
    """Lazy variant of :func:`get_container_detail` — takes a ``wsd`` slice.

    ``dyn_index`` optionally provides the decoded ``DynamicItemSaveData`` map
    (see :func:`dynamic_item_service.build_dynamic_index`); pass ``None`` to
    skip dynamic-item attachment. When ``None`` but the container has slots
    with dynamic_ids, the index is built on-demand from the same ``wsd`` slice
    so callers don't have to wire it themselves.
    """
    cid_clean = _s(container_id)
    for c in _map_entries(wsd, "ItemContainerSaveData"):
        if _s(c.get("key")) != cid_clean:
            continue
        belong = _g(c, "value", "BelongInfo") or {}
        slot_num = _g(c, "value", "SlotNum")
        try:
            slot_count = int(slot_num) if slot_num is not None else 0
        except (TypeError, ValueError):
            slot_count = 0
        slots = _g(c, "value", "Slots")
        # Build the dynamic-item index lazily — only if this container has at
        # least one slot referencing a dynamic_id. Plain stackable containers
        # (the common case) pay nothing.
        idx = dyn_index
        if idx is None and isinstance(slots, list) and _has_dynamic_slot(slots):
            from app.backend.services.dynamic_item_service import build_dynamic_index
            idx = build_dynamic_index(wsd)
        items = _get_slots(slots, idx)
        return {
            "id": _extract_id(c.get("key")) or container_id,
            "owner_player_uid": _norm_uid(_k(belong, "PlayerUId")),
            "guild_id": _norm_uid(_k(belong, "GroupId")),
            "slot_count": slot_count,
            "item_count": len(items),
            "items": items,
        }
    return None


def _has_dynamic_slot(slots: list) -> bool:
    """True if any slot in the list references a non-nil dynamic_id."""
    for entry in slots:
        raw = _slot_raw(entry)
        if not _k(raw, "count"):
            continue
        item = _k(raw, "item") or {}
        dyn = _k(item, "dynamic_id") or {}
        lid = _k(dyn, "local_id_in_created_world")
        if lid and _s(lid) != _s(_NIL):
            return True
    return False


def get_container_detail(level_dict: dict, container_id: str) -> dict | None:
    """Get full container detail including item slots."""
    return get_container_detail_from_wsd(get_world_save_data(level_dict), container_id)


def _find_container_entry(level_dict: dict, container_id: str) -> dict | None:
    """The raw ``ItemContainerSaveData`` entry dict, or ``None``.

    Used by the per-slot mutators below. Walks the live ``level_dict`` so
    in-place mutations persist to disk on the next encode.
    """
    cid_clean = _s(container_id)
    for c in _map_entries(get_world_save_data(level_dict), "ItemContainerSaveData"):
        if _s(c.get("key")) == cid_clean:
            return c
    return None


def clear_container(level_dict: dict, container_id: str) -> bool:
    """Zero out every item slot in a container."""
    cid_clean = _s(container_id)
    for c in _map_entries(get_world_save_data(level_dict), "ItemContainerSaveData"):
        if _s(c.get("key")) != cid_clean:
            continue
        slots = _g(c, "value", "Slots")
        if not isinstance(slots, list):
            return True
        for entry in slots:
            raw = _slot_raw(entry)
            raw[_get_key(raw, "count")] = 0
        return True
    return False


def expand_container(level_dict: dict, container_id: str, new_slot_count: int) -> bool:
    """Expand container capacity (increase only; never shrinks)."""
    new_slot_count = max(1, min(9999, new_slot_count))
    cid_clean = _s(container_id)
    for c in _map_entries(get_world_save_data(level_dict), "ItemContainerSaveData"):
        if _s(c.get("key")) != cid_clean:
            continue
        slot_num = _g(c, "value", "SlotNum")
        try:
            current = int(slot_num) if slot_num is not None else 0
        except (TypeError, ValueError):
            current = 0
        if new_slot_count <= current:
            return False
        # Update SlotNum (preserve key form).
        _set_key(_g(c, "value"), "SlotNum", new_slot_count)
        # Pad Slots with empty entries.
        slots = _g(c, "value", "Slots")
        if isinstance(slots, list):
            while len(slots) < new_slot_count:
                slots.append(_empty_slot(len(slots)))
        return True
    return False


def set_slot_count(
    level_dict: dict, container_id: str, slot_index: int, new_count: int,
) -> bool:
    """Change a single item slot's stack count.

    Setting ``new_count`` to ``0`` effectively clears the slot (the slot
    remains present in the array, just empty). The ``static_id`` is left
    untouched — the caller is editing the stack, not swapping the item.

    Returns ``False`` if the container or slot index isn't found.
    """
    if new_count < 0 or new_count > 9999:
        return False
    entry = _find_container_entry(level_dict, container_id)
    if entry is None:
        return False
    slots = _g(entry, "value", "Slots")
    if not isinstance(slots, list):
        return False
    for slot in slots:
        raw = _slot_raw(slot)
        if _k(raw, "slot_index") == slot_index:
            _set_key(raw, "count", int(new_count))
            return True
    return False


def delete_slot(
    level_dict: dict, container_id: str, slot_index: int,
) -> bool:
    """Remove an item from a slot (zero it out, keep the slot itself).

    Item removal in Palworld is "set the slot to empty" — slots are
    positional, so we never splice them out of the ``Slots`` array. This
    mirrors how the game itself clears a slot on drop/consume.
    """
    entry = _find_container_entry(level_dict, container_id)
    if entry is None:
        return False
    slots = _g(entry, "value", "Slots")
    if not isinstance(slots, list):
        return False
    for slot in slots:
        raw = _slot_raw(slot)
        if _k(raw, "slot_index") == slot_index:
            # Zero the count and wipe the item id — equivalent to the game's
            # own "drop item" action.
            _set_key(raw, "count", 0)
            item = _k(raw, "item")
            if isinstance(item, dict):
                _set_key(item, "static_id", "")
                dyn = _k(item, "dynamic_id")
                if isinstance(dyn, dict):
                    _set_key(dyn, "created_world_id", _NIL)
                    _set_key(dyn, "local_id_in_created_world", _NIL)
            return True
    return False


# ---- key-form helpers (preserve _0 suffix on write) -------------------------

def _get_key(node: dict, name: str) -> str:
    """Return the actual key (suffixed or bare) present in ``node``."""
    suffixed = name + "_0"
    return suffixed if suffixed in node else name


def _set_key(node: dict | None, name: str, value) -> None:
    """Set ``node[name_0]`` preserving the existing key form."""
    if not isinstance(node, dict):
        return
    node[_get_key(node, name)] = value
