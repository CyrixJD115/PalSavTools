"""Container mutation operations for the web backend."""

from __future__ import annotations

from web.backend.services.world_service import (
    get_world_save_data, _map_values, _u, _norm_uid,
)
from web.backend.services.base_service import _s, _extract_id


def _count_items(slots_node: dict | None) -> int:
    """Count non-empty slots in a container's Slots array."""
    if slots_node is None:
        return 0
    try:
        values = slots_node.get("value", {}).get("values", [])
        return sum(
            1 for entry in values
            if entry.get("RawData", {}).get("value", {}).get("count", 0) > 0
        )
    except Exception:
        return 0


def _get_slots(slots_node: dict | None) -> list[dict]:
    """Extract item slots from a container's Slots array."""
    if slots_node is None:
        return []
    try:
        values = slots_node.get("value", {}).get("values", [])
        out = []
        for entry in values:
            raw = entry.get("RawData", {}).get("value", {})
            si = raw.get("slot_index")
            count = raw.get("count", 0)
            item = raw.get("item", {})
            if count is None or count == 0:
                continue
            static_id = item.get("static_id", "")
            dynamic = item.get("dynamic_id", {})
            dyn_id = None
            lid = dynamic.get("local_id_in_created_world") if isinstance(dynamic, dict) else None
            if lid and str(lid).replace("-", "") != "00000000000000000000000000000000":
                dyn_id = str(lid)
            out.append({
                "slot_index": int(si) if si is not None else 0,
                "count": int(count) if count is not None else 0,
                "static_id": str(static_id) if static_id else "",
                "dynamic_id": dyn_id,
            })
        return out
    except Exception:
        return []


def _build_map_object_index(wsd: dict) -> dict[str, dict]:
    """Build a map of container_id -> map object info (type, location, base_camp)."""
    index: dict[str, dict] = {}
    for obj in wsd.get("MapObjectSaveData", {}).get("value", {}).get("values", []):
        try:
            # Get the concrete model's module map
            cm = obj.get("ConcreteModel", {}).get("value", {}).get("ModuleMap", {}).get("value", [])
            target_cid = None
            for mod in cm:
                try:
                    mt = mod.get("key", "")
                    if mt == "EPalMapObjectConcreteModelModuleType::ItemContainer":
                        target_cid = _s(
                            mod.get("value", {}).get("RawData", {}).get("value", {}).get("target_container_id")
                        )
                        break
                except Exception:
                    continue
            if not target_cid:
                continue

            model_raw = obj.get("Model", {}).get("value", {}).get("RawData", {}).get("value", {})
            map_obj_id = str(_u(obj, "MapObjectId") or "")
            trans = model_raw.get("initital_transform_cache", {}).get("translation", {})
            base_camp = model_raw.get("base_camp_id_belong_to")

            index[target_cid] = {
                "type": _classify_container(map_obj_id),
                "map_object_id": map_obj_id,
                "location": (
                    float(trans.get("x", 0)) if trans else None,
                    float(trans.get("y", 0)) if trans else None,
                    float(trans.get("z", 0)) if trans else None,
                ) if trans else None,
                "base_camp_id": str(base_camp) if base_camp else None,
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
    # Production / workplace buildings with item storage
    if "campfire" in mid:
        return "Campfire"
    if "copperpit" in mid or "coalpit" in mid or "crystalpit" in mid or "quartzpit" in mid or "sulfurpit" in mid or "stonepit" in mid:
        return "Mining Pit"
    if "oilpump" in mid:
        return "Oil Pump"
    if "blastfurnace" in mid:
        return "Blast Furnace"
    if "factory" in mid:
        return "Factory"
    if "spherefactory" in mid:
        return "Sphere Factory"
    if "weaponfactory" in mid:
        return "Weapon Factory"
    if "workbench" in mid:
        return "Workbench"
    if "kitchen" in mid:
        return "Kitchen"
    if "medicinefacility" in mid or "medicinetable" in mid or "medic" in mid:
        return "Medicine Facility"
    if "breedfarm" in mid or "breeding" in mid:
        return "Breeding Farm"
    if "expedition" in mid:
        return "Expedition Station"
    if "icecrusher" in mid:
        return "Ice Crusher"
    if "crusher" in mid and "icecrusher" not in mid:
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


def _get_item_name(static_id: str) -> str:
    """Convert a static_id like 'Item_Ore_Paladium' to a readable name."""
    s = static_id.replace("Item_", "").replace("Weapon_", "").replace("Armor_", "").replace("Accessory_", "")
    s = s.replace("_", " ").strip()
    return s if s else static_id


def _belong_inner(raw: dict | None) -> dict:
    """Extract the inner value dict from a PalItemContainerBelongInfo StructProperty."""
    if not raw:
        return {}
    if isinstance(raw, dict) and raw.get("type") == "StructProperty":
        return raw.get("value", {})
    return raw


def list_containers(level_dict: dict, limit: int = 500) -> list[dict]:
    """Enriched container list with item count, type, and location."""
    wsd = get_world_save_data(level_dict)
    map_index = _build_map_object_index(wsd)

    # Build guild name lookup
    guild_names: dict[str, str] = {}
    for g in _map_values(wsd, "GroupSaveDataMap"):
        try:
            gid = _s(g.get("key"))
            name = g.get("value", {}).get("RawData", {}).get("value", {}).get("guild_name", "Unnamed Guild")
            guild_names[gid] = name
        except Exception:
            continue

    out = []
    for c in _map_values(wsd, "ItemContainerSaveData"):
        try:
            v = c.get("value", {})
            cid = _extract_id(c.get("key"))
            cid_clean = _s(c.get("key"))
            belong_raw = _u(v, "BelongInfo")
            belong = _belong_inner(belong_raw)
            slot_num = _u(v, "SlotNum")
            slot_count = int(slot_num) if slot_num is not None else 0
            slots_node = v.get("Slots")
            item_count = _count_items(slots_node)

            owner_uid = _norm_uid(_extract_id(belong.get("PlayerUId")))
            guild_id = _norm_uid(_extract_id(belong.get("GroupId")))

            map_info = map_index.get(cid_clean, {})
            ctype = map_info.get("type", "Unknown")
            location = map_info.get("location")
            base_camp_id = map_info.get("base_camp_id")
            guild_name = guild_names.get(_s(guild_id)) if guild_id else None

            out.append({
                "id": cid,
                "container_type": ctype,
                "owner_player_uid": owner_uid,
                "guild_id": guild_id,
                "guild_name": guild_name,
                "base_camp_id": base_camp_id,
                "slot_count": slot_count,
                "item_count": item_count,
                "location": location,
            })
            if limit and len(out) >= limit:
                break
        except Exception:
            continue
    return out


def get_container_detail(level_dict: dict, container_id: str) -> dict | None:
    """Get full container detail including item slots."""
    wsd = get_world_save_data(level_dict)
    cid_clean = _s(container_id)

    for c in _map_values(wsd, "ItemContainerSaveData"):
        if _s(c.get("key")) != cid_clean:
            continue
        try:
            v = c.get("value", {})
            belong_raw = _u(v, "BelongInfo")
            belong = _belong_inner(belong_raw)
            slot_num = _u(v, "SlotNum")
            slot_count = int(slot_num) if slot_num is not None else 0
            slots_node = v.get("Slots")
            items = _get_slots(slots_node)

            return {
                "id": _extract_id(c.get("key")) or container_id,
                "owner_player_uid": _norm_uid(_extract_id(belong.get("PlayerUId"))),
                "guild_id": _norm_uid(_extract_id(belong.get("GroupId"))),
                "slot_count": slot_count,
                "item_count": len(items),
                "items": items,
            }
        except Exception:
            return None
    return None


def clear_container(level_dict: dict, container_id: str) -> bool:
    """Remove all items from a container."""
    wsd = get_world_save_data(level_dict)
    cid_clean = _s(container_id)
    for c in _map_values(wsd, "ItemContainerSaveData"):
        if _s(c.get("key")) != cid_clean:
            continue
        try:
            slots_node = c.get("value", {}).get("Slots")
            if slots_node is None:
                return True
            values = slots_node.get("value", {}).get("values", [])
            for entry in values:
                raw = entry.get("RawData", {}).get("value", {})
                raw["count"] = 0
            return True
        except Exception:
            return False
    return False


def expand_container(level_dict: dict, container_id: str, new_slot_count: int) -> bool:
    """Expand container capacity.
    
    Only increases capacity (never shrinks). Adds empty slots if needed.
    """
    new_slot_count = max(1, min(9999, new_slot_count))
    wsd = get_world_save_data(level_dict)
    cid_clean = _s(container_id)
    for c in _map_values(wsd, "ItemContainerSaveData"):
        if _s(c.get("key")) != cid_clean:
            continue
        try:
            v = c.get("value", {})
            slot_num = _u(v, "SlotNum")
            current = int(slot_num) if slot_num is not None else 0
            if new_slot_count <= current:
                return False  # Don't shrink

            v["SlotNum"] = {"value": new_slot_count}

            # Pad the Slots array with empty entries
            slots_node = v.get("Slots")
            if slots_node is not None:
                values = slots_node.get("value", {}).get("values", [])
                while len(values) < new_slot_count:
                    values.append({
                        "RawData": {
                            "array_type": "ByteProperty",
                            "id": None,
                            "value": {
                                "slot_index": len(values),
                                "count": 0,
                                "item": {
                                    "static_id": "",
                                    "dynamic_id": {
                                        "created_world_id": "00000000-0000-0000-0000-000000000000",
                                        "local_id_in_created_world": "00000000-0000-0000-0000-000000000000",
                                    },
                                },
                                "trailing_bytes": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                            },
                            "type": "ArrayProperty",
                            "custom_type": ".worldSaveData.ItemContainerSaveData.Value.Slots.Slots.RawData",
                        },
                        "CustomVersionData": {
                            "array_type": "ByteProperty",
                            "id": None,
                            "value": {"values": []},
                            "type": "ArrayProperty",
                        },
                    })
            return True
        except Exception:
            return False
    return False
