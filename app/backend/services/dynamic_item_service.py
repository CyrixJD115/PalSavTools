"""Lazy decoder for ``DynamicItemSaveData`` entries.

Weapons, armor, and eggs in Palworld are *dynamic items* — their per-instance
state (durability, loaded ammo, passive skills, egg SaveParameter) lives in a
separate ``DynamicItemSaveData`` array on the world save, not in the inventory
slot. Each slot's ``item.dynamic_id.local_id_in_created_world`` GUID is the
foreign key to a ``DynamicItemSaveData`` entry whose ``RawData.id.local_id_in_created_world``
matches.

The Rust uesave engine has ``PalDynamicItem`` fully schema-registered, so the
blob arrives as a typed, externally-tagged JSON struct:

.. code-block:: python

    {
        "RawData_0": {
            "id": {
                "created_world_id": "...",
                "local_id_in_created_world": "<guid>",
            },
            "static_id": "AssaultRifle_Default1",
            "item_type": {
                "Weapon": {                              # OR "Armor" / "Egg" / "Unknown"
                    "leading_bytes": [0,0,0,0],
                    "durability": 850.5,
                    "remaining_bullets": 25,
                    "passive_skill_list": ["Skill_A"],
                    "unknown_str": null,
                    "trailing_bytes": [0,0,0,0],
                }
            },
        },
        "CustomVersionData_0": {"Byte": [...]},
    }

This module builds an in-memory index ``{local_id -> DynamicItemDetail}`` from a
``wsd`` slice so the inventory readers can attach the decoded payload to each
slot in one pass without re-walking the array per slot.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.backend.services.world_service import _g, _k

logger = logging.getLogger(__name__)

_NIL = "00000000-0000-0000-0000-000000000000"


def _egg_save_parameter(egg_fields: dict) -> dict | None:
    """The embedded ``SaveParameter`` of an egg, if present.

    Eggs may carry a full pal-shaped ``SaveParameter`` (passive skills, talents,
    gender, etc.) under ``object.SaveParameter``. Empty ``object`` dicts (common
    for spawned-but-unspecified eggs) return ``None``.
    """
    obj = egg_fields.get("object")
    if not isinstance(obj, dict) or not obj:
        return None
    sp = obj.get("SaveParameter")
    # The Properties bag may wrap the struct under "value" or inline; the Rust
    # engine emits it inline (no envelope), so accept both shapes.
    if isinstance(sp, dict):
        if "value" in sp and isinstance(sp["value"], dict):
            return sp["value"]
        return sp
    return None


def _decode_entry(entry: dict) -> dict | None:
    """Decode one ``DynamicItemSaveData`` array element into a flat dict.

    Returns ``None`` if the entry has no usable payload (empty RawData, which
    happens for placeholder / pre-allocated slots).
    """
    raw = _k(entry, "RawData")
    if not isinstance(raw, dict) or not raw:
        return None

    local_id = _g(raw, "id", "local_id_in_created_world")
    if not local_id or local_id == _NIL:
        return None

    static_id = raw.get("static_id", "") or ""
    item_type = raw.get("item_type") or {}
    if not isinstance(item_type, dict) or not item_type:
        return None

    # Externally-tagged enum: exactly one of {Weapon, Armor, Egg, Unknown}.
    variant = next(iter(item_type.keys()))
    fields = item_type.get(variant) or {}

    out: dict[str, Any] = {
        "local_id": str(local_id),
        "static_id": static_id,
        "type": variant.lower(),  # "weapon" | "armor" | "egg" | "unknown"
    }

    if variant == "Weapon":
        out["durability"] = float(fields.get("durability") or 0.0)
        out["remaining_bullets"] = int(fields.get("remaining_bullets") or 0)
        skills = fields.get("passive_skill_list") or []
        out["passive_skills"] = [str(s) for s in skills if s] if isinstance(skills, list) else []
    elif variant == "Armor":
        out["durability"] = float(fields.get("durability") or 0.0)
    elif variant == "Egg":
        out["character_id"] = str(fields.get("character_id") or "")
        sp = _egg_save_parameter(fields)
        if sp:
            # Surface the most useful pal-shaped fields without re-implementing
            # the full PalDetail reader — the tooltip only needs a summary.
            out["egg_passive_skills"] = [
                str(s) for s in (sp.get("PassiveSkillList") or [])
                if s
            ] if isinstance(sp.get("PassiveSkillList"), list) else []
            for talent_field, out_key in (
                ("Talent_HP", "egg_talent_hp"),
                ("Talent_Shot", "egg_talent_shot"),
                ("Talent_Defense", "egg_talent_defense"),
            ):
                v = sp.get(talent_field)
                if v is not None:
                    try:
                        out[out_key] = int(v)
                    except (TypeError, ValueError):
                        pass
            gender = sp.get("Gender")
            if gender:
                # Stored as "EPalGenderType::Male" etc. — strip the prefix.
                gs = str(gender).split("::")[-1]
                if gs and gs != "None":
                    out["egg_gender"] = gs

    return out


def build_dynamic_index(wsd: dict) -> dict[str, dict]:
    """Scan ``DynamicItemSaveData`` once, returning ``{local_id -> detail}``.

    ``DynamicItemSaveData`` is an ArrayProperty (flat list of structs), so we
    walk it directly rather than via ``_map_entries`` (which is for MapProperty
    ``[{key,value}]`` lists). Entries with no payload are skipped.

    The index is cheap to build (~1-2k entries, sub-millisecond) and is
    per-request — the route layer passes a fresh ``wsd`` slice each call.
    """
    # ArrayProperty: bare list under the section key.
    entries = _k(wsd, "DynamicItemSaveData")
    if not isinstance(entries, list):
        return {}

    index: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        decoded = _decode_entry(entry)
        if decoded is not None:
            index[decoded["local_id"]] = decoded
    return index


def lookup(index: dict[str, dict], local_id: Optional[str]) -> dict | None:
    """Resolve a slot's ``dynamic_id`` to its decoded detail, or ``None``.

    ``local_id`` is the slot's ``item.dynamic_id.local_id_in_created_world``
    GUID. Nil / missing GUIDs (plain stackable items) return ``None``.
    """
    if not local_id or local_id == _NIL:
        return None
    return index.get(str(local_id))
