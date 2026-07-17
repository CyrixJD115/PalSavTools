"""
Headless replacement for editor/edit_pals.py.

Provides the same business-logic functions without any Qt dependency.
"""
# flake8: noqa: F401

import uuid as _uuid
from typing import Optional as _Optional

from i18n import t as _t
from palworld_aio import constants as _constants
from palworld_aio.utils import extract_value as _extract_value
from palworld_aio.utils import safe_nested_get as _safe_nested_get
from palworld_aio.utils import calculate_max_hp as _calculate_max_hp
from palworld_aio.utils import get_pal_data as _get_pal_data
from palworld_aio.managers import data_manager as _dm
from resource_resolver import resource_path as _resource_path

# ── Data helpers  ───────────────────────────────────────────────────────

_PAL_EXP_TABLE: dict = {}
_FRIENDSHIP_THRESHOLDS: _Optional[list] = None
_PAL_BASE_DATA_CACHE: dict = {}

# Re-use the headless data module if available, otherwise define inline.
try:
    from palworld_aio.editor.pal_editor.data import (
        _ensure_friendship_thresholds,
        get_pal_base_data,
        PAL_EXP_TABLE,
    )
    _PAL_EXP_TABLE.update(PAL_EXP_TABLE)
except ImportError:
    # Minimal inline implementations
    def _ensure_friendship_thresholds() -> list:
        global _FRIENDSHIP_THRESHOLDS
        if _FRIENDSHIP_THRESHOLDS is not None:
            return _FRIENDSHIP_THRESHOLDS
        import json, os
        from palsav import json_tools as _jt
        _FRIENDSHIP_THRESHOLDS = [0, 6000, 13000, 21000, 30000, 40000, 55000, 80000, 110000, 150000, 200000]
        try:
            base = _constants.get_base_path()
            fp = _resource_path(base, "game_data", "friendship.json")
            data = _jt.load(fp)
            entries = [(v.get("FriendshipRank", -1), v.get("RequiredPoint", 0)) for v in data.values()]
            entries.sort()
            _FRIENDSHIP_THRESHOLDS = [pt for _, pt in entries]
        except Exception:
            pass
        return _FRIENDSHIP_THRESHOLDS

    def get_pal_base_data(cid: str) -> dict | None:
        global _PAL_BASE_DATA_CACHE
        if not _PAL_BASE_DATA_CACHE:
            _load_pal_base_data()
        cid_lower = cid.lower()
        entry = _PAL_BASE_DATA_CACHE.get(cid_lower)
        if entry:
            return entry
        normalized = cid_lower.replace("boss_", "").replace("b_o_s_s_", "")
        entry = _PAL_BASE_DATA_CACHE.get(normalized)
        if entry:
            return entry
        for prefix in ("gym_", "tower_", "raid_", "predator_"):
            prefixed = f"{prefix}{normalized}"
            if prefixed in _PAL_BASE_DATA_CACHE:
                return _PAL_BASE_DATA_CACHE[prefixed]
        for ckey, centry in _PAL_BASE_DATA_CACHE.items():
            if normalized in ckey or ckey in normalized:
                return centry
        return None

    def _load_pal_base_data() -> dict:
        global _PAL_BASE_DATA_CACHE
        if _PAL_BASE_DATA_CACHE:
            return _PAL_BASE_DATA_CACHE
        import json
        from palsav import json_tools as _jt
        try:
            base = _constants.get_base_path()
            fp = _resource_path(base, "game_data", "characters.json")
            data = _jt.load(fp)
            for p in data.get("pals", []):
                a = p.get("asset", "").lower()
                if a:
                    _PAL_BASE_DATA_CACHE[a] = p
            for n in data.get("npcs", []):
                a = n.get("asset", "").lower()
                if a and a not in _PAL_BASE_DATA_CACHE:
                    _PAL_BASE_DATA_CACHE[a] = n
            for a, p in list(_PAL_BASE_DATA_CACHE.items()):
                if p.get("elements") or "boss_" in a:
                    continue
                boss_key = f"boss_{a}"
                boss_entry = _PAL_BASE_DATA_CACHE.get(boss_key)
                if boss_entry and boss_entry.get("elements"):
                    p = dict(p)
                    p["elements"] = boss_entry["elements"]
                    _PAL_BASE_DATA_CACHE[a] = p
            return _PAL_BASE_DATA_CACHE
        except Exception as e:
            print(f"Error loading pal base data: {e}")
            return {}


# ── Pal operations (from pal_ops.py)  ───────────────────────────────────


def _register_pal_instance_to_guild(instance_id, group_id) -> None:
    """Register a pal instance ID in a guild's handle list."""
    if not _constants.loaded_level_json:
        return
    wsd = _constants.loaded_level_json["properties"]["worldSaveData"]["value"]
    if "GroupSaveDataMap" not in wsd:
        return
    gid_norm = str(group_id).replace("-", "").lower()
    for g in wsd["GroupSaveDataMap"]["value"]:
        try:
            gid = str(g["key"]).replace("-", "").lower()
            if gid == gid_norm:
                g_raw = g["value"]["RawData"]["value"]
                hids = g_raw.get("individual_character_handle_ids", [])
                hids.append({"guid": "00000000-0000-0000-0000-000000000000", "instance_id": instance_id})
                g_raw["individual_character_handle_ids"] = hids
                break
        except Exception:
            pass


def _generate_pal_save_param(
    character_id: str,
    nickname: str,
    owner_uid,
    container_id,
    slot_index: int,
    group_id=None,
) -> dict:
    """
    Generate a CharacterSaveParameterMap entry for a new pal.

    Pure business logic — no Qt dependency.
    """
    if group_id is None:
        group_id = str(_uuid.uuid4()).upper()
    instance_id = str(_uuid.uuid4()).upper()
    empty_uuid = "00000000-0000-0000-0000-000000000000"
    time_val = 638486453957560000
    base = get_pal_base_data(character_id)
    max_stomach = base.get("stats", {}).get("max_full_stomach", 300) if base else 300

    return {
        "key": {
            "PlayerUId": {"struct_type": "Guid", "struct_id": empty_uuid, "id": None, "value": empty_uuid, "type": "StructProperty"},
            "InstanceId": {"struct_type": "Guid", "struct_id": empty_uuid, "id": None, "value": instance_id, "type": "StructProperty"},
            "DebugName": {"id": None, "type": "StrProperty", "value": ""},
        },
        "value": {
            "RawData": {
                "array_type": "ByteProperty",
                "id": None,
                "value": {
                    "object": {
                        "SaveParameter": {
                            "struct_type": "PalIndividualCharacterSaveParameter",
                            "struct_id": empty_uuid,
                            "id": None,
                            "value": {
                                "CharacterID": {"id": None, "type": "NameProperty", "value": character_id},
                                "Gender": {"id": None, "type": "EnumProperty", "value": {"type": "EPalGenderType", "value": "EPalGenderType::Female"}},
                                "NickName": {"id": None, "type": "StrProperty", "value": nickname},
                                "EquipWaza": {
                                    "array_type": "EnumProperty",
                                    "id": None,
                                    "value": {"values": [f"EPalWazaID::Unique_{character_id}_Roll"] if character_id == "SheepBall" else []},
                                    "type": "ArrayProperty",
                                },
                                "MasteredWaza": {"array_type": "EnumProperty", "id": None, "value": {"values": []}, "type": "ArrayProperty"},
                                "Hp": {
                                    "struct_type": "FixedPoint64",
                                    "struct_id": empty_uuid,
                                    "id": None,
                                    "value": {
                                        "Value": {
                                            "id": None,
                                            "value": _calculate_max_hp(
                                                _get_pal_data(character_id), 1, 100, 0,
                                                character_id.upper().startswith("BOSS_"), False,
                                            ),
                                            "type": "Int64Property",
                                        }
                                    },
                                    "type": "StructProperty",
                                },
                                "Talent_HP": {"id": None, "type": "ByteProperty", "value": {"type": "None", "value": 100}},
                                "Talent_Shot": {"id": None, "type": "ByteProperty", "value": {"type": "None", "value": 100}},
                                "Talent_Defense": {"id": None, "type": "ByteProperty", "value": {"type": "None", "value": 100}},
                                "FullStomach": {"id": None, "type": "FloatProperty", "value": float(max_stomach)},
                                "SanityValue": {"id": None, "type": "FloatProperty", "value": 100.0},
                                "Level": {"id": None, "type": "ByteProperty", "value": {"type": "None", "value": 1}},
                                "Exp": {"id": None, "type": "Int64Property", "value": 0},
                                "Rank": {"id": None, "type": "ByteProperty", "value": {"type": "None", "value": 1}},
                                "PassiveSkillList": {"array_type": "NameProperty", "id": None, "value": {"values": []}, "type": "ArrayProperty"},
                                "OwnedTime": {"struct_type": "DateTime", "struct_id": empty_uuid, "id": None, "value": time_val, "type": "StructProperty"},
                                "OwnerPlayerUId": {"struct_type": "Guid", "struct_id": empty_uuid, "id": None, "value": owner_uid, "type": "StructProperty"},
                                "OldOwnerPlayerUIds": {
                                    "array_type": "StructProperty",
                                    "id": None,
                                    "value": {
                                        "prop_name": "OldOwnerPlayerUIds",
                                        "prop_type": "StructProperty",
                                        "values": [owner_uid],
                                        "type_name": "Guid",
                                        "id": empty_uuid,
                                    },
                                    "type": "ArrayProperty",
                                },
                                "SlotId": {
                                    "struct_type": "PalCharacterSlotId",
                                    "struct_id": empty_uuid,
                                    "id": None,
                                    "value": {
                                        "ContainerId": {
                                            "struct_type": "PalContainerId",
                                            "struct_id": empty_uuid,
                                            "id": None,
                                            "value": {
                                                "ID": {"struct_type": "Guid", "struct_id": empty_uuid, "id": None, "value": container_id, "type": "StructProperty"}
                                            },
                                            "type": "StructProperty",
                                        },
                                        "SlotIndex": {"id": None, "type": "IntProperty", "value": slot_index},
                                    },
                                    "type": "StructProperty",
                                },
                                "GotStatusPointList": {
                                    "array_type": "StructProperty",
                                    "id": None,
                                    "value": {
                                        "prop_name": "GotStatusPointList",
                                        "prop_type": "StructProperty",
                                        "values": [
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "最大HP"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "最大SP"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "攻撃力"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "所持重量"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "捕獲率"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "作業速度"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                        ],
                                        "type_name": "PalGotStatusPoint",
                                        "id": empty_uuid,
                                    },
                                    "type": "ArrayProperty",
                                },
                                "GotExStatusPointList": {
                                    "array_type": "StructProperty",
                                    "id": None,
                                    "value": {
                                        "prop_name": "GotExStatusPointList",
                                        "prop_type": "StructProperty",
                                        "values": [
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "最大HP"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "最大SP"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "攻撃力"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "所持重量"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                            {"StatusName": {"id": None, "type": "NameProperty", "value": "作業速度"}, "StatusPoint": {"id": None, "type": "IntProperty", "value": 0}},
                                        ],
                                        "type_name": "PalGotStatusPoint",
                                        "id": empty_uuid,
                                    },
                                    "type": "ArrayProperty",
                                },
                                "LastNickNameModifierPlayerUid": {"struct_type": "Guid", "struct_id": empty_uuid, "id": None, "value": owner_uid, "type": "StructProperty"},
                            },
                            "type": "StructProperty",
                        }
                    },
                    "unknown_bytes": [0, 0, 0, 0],
                    "group_id": group_id,
                    "trailing_bytes": [0, 0, 0, 0],
                },
                "custom_type": ".worldSaveData.CharacterSaveParameterMap.Value.RawData",
                "type": "ArrayProperty",
            }
        },
    }
