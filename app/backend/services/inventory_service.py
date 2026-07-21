"""Player inventory assembly for the web backend.

Player inventory bags are **not** stored inside the player ``.sav`` — the
``.sav`` only carries six container IDs under ``SaveData.InventoryInfo``. The
actual slot contents live in world-level ``ItemContainerSaveData`` entries in
``Level.sav``. This service:

1. Reads the player's ``.sav`` (cache-first via ``player_service``) to get the
   six bag container IDs (+ party/palbox IDs).
2. Looks each ID up in ``ItemContainerSaveData`` to fetch its slots.
3. Reads the player's stat ranks from ``CharacterSaveParameterMap``.

The ``wsd`` argument is a ``build_mini_wsd(...)`` slice (NOT a full
``level_dict``). The route layer pulls only
``"ItemContainerSaveData"`` + ``"CharacterSaveParameterMap"``.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.backend.services import player_service, world_service
from app.backend.services.base_service import _s
from app.backend.services.container_service import _get_slots

logger = logging.getLogger(__name__)


# The six player inventory bags, in display order. ``key`` is the field name
# under ``SaveData.InventoryInfo``; ``bag_type`` is the wire value used by the
# frontend to pick an icon/tab; ``label`` is the human label.
PLAYER_BAG_DEFS: list[dict] = [
    {"key": "CommonContainerId",          "bag_type": "common",    "label": "Common"},
    {"key": "EssentialContainerId",       "bag_type": "essential", "label": "Key Items"},
    {"key": "WeaponLoadOutContainerId",   "bag_type": "weapon",    "label": "Weapons"},
    {"key": "PlayerEquipArmorContainerId","bag_type": "armor",     "label": "Armor"},
    {"key": "FoodEquipContainerId",       "bag_type": "food",      "label": "Food"},
    {"key": "DropSlotContainerId",        "bag_type": "drop",      "label": "Drop Slot"},
]


def _read_bag_container_ids(player_dict: dict) -> dict[str, str]:
    """Map each ``bag_type`` → container ID (UUID string) from the player .sav.

    Returns only the bags that are actually allocated (non-nil ID). Missing or
    nil-UUID bags are omitted so the UI can show a friendly "not allocated"
    state instead of an empty grid.

    Handles both ``InventoryInfo`` and ``inventoryInfo`` casing — some save
    versions emit the lowercase form. PSP's ``player.py:705-788`` handles the
    same fallback.
    """
    sd = player_service._save_data(player_dict)
    # Try the common casing first, then the lowercase fallback.
    inv = world_service._g(sd, "InventoryInfo")
    if not inv:
        inv = world_service._g(sd, "inventoryInfo")
    if not inv:
        inv = {}
    out: dict[str, str] = {}
    for d in PLAYER_BAG_DEFS:
        cid = world_service._g(inv, d["key"], "ID")
        cid = world_service._norm_uid(cid)
        if cid:
            out[d["bag_type"]] = str(cid)
    return out


def _bag_detail_from_wsd(
    wsd: dict, bag_type: str, label: str, container_id: str,
    dyn_index: dict | None = None,
) -> dict:
    """Build an ``InventoryBag``-shaped dict for a single container ID.

    ``dyn_index`` is the decoded ``DynamicItemSaveData`` map; when ``None``,
    the slot reader skips dynamic-item attachment (the caller may have
    pre-built it for the whole player snapshot to avoid re-walking per bag).
    """
    cid_clean = _s(container_id)
    for c in world_service._map_entries(wsd, "ItemContainerSaveData"):
        if _s(c.get("key")) != cid_clean:
            continue
        slot_num = world_service._g(c, "value", "SlotNum")
        try:
            slot_count = int(slot_num) if slot_num is not None else 0
        except (TypeError, ValueError):
            slot_count = 0
        items = _get_slots(world_service._g(c, "value", "Slots"), dyn_index)
        return {
            "bag_type": bag_type,
            "label": label,
            "container_id": container_id,
            "slot_count": slot_count,
            "item_count": len(items),
            "items": items,
        }
    # Container ID present in the player .sav but missing from the world save
    # (rare — happens with cross-save imports). Still report the bag so the UI
    # shows it as allocated-but-empty.
    return {
        "bag_type": bag_type,
        "label": label,
        "container_id": container_id,
        "slot_count": 0,
        "item_count": 0,
        "items": [],
    }


def get_player_inventory(
    wsd: dict, players_dir: str, uid: str,
) -> dict | None:
    """Assemble a player's full inventory snapshot.

    ``wsd`` is a ``build_mini_wsd("ItemContainerSaveData", "CharacterSaveParameterMap")``
    slice — NOT a full ``level_dict``.

    Returns ``None`` only when the player can't be resolved at all (no
    ``CharacterSaveParameterMap`` entry). A player whose ``.sav`` is missing
    still returns a record — just with empty bags and ``party_id``/``palbox_id``
    left ``None``.

    Read path: the player ``.sav`` is cache-first (``player_savs`` LRU); the
    bag contents come from the ``wsd`` slice.
    """
    # World-level player record (name + stats). Falls back gracefully.
    sp = player_service._find_player_sp_from_wsd(wsd, uid)
    name = (
        str(world_service._k(sp, "NickName") or "Unknown")
        if sp is not None else "Unknown"
    )

    # Player .sav (cache-first, handles bundle-upload and path-load flows).
    # Uses LoadedSave.get_player_sav() rather than calling _read_player_sav()
    # directly, because get_player_sav passes the raw bundle bytes (player_raw_bytes)
    # that the in-memory zip-upload path needs.
    bag_ids: dict[str, str] = {}
    party_id: Optional[str] = None
    palbox_id: Optional[str] = None

    from app.backend.state import save_state
    loaded_state = save_state.get()
    psav = None
    if loaded_state is not None:
        psav = loaded_state.get_player_sav(player_service.normalize_uid(uid))
    if psav is not None:
        player_dict, _ = psav
        bag_ids = _read_bag_container_ids(player_dict)
        # Also read party/palbox IDs from the decoded player .sav
        sd = player_service._save_data(player_dict)
        party_id = world_service._norm_uid(world_service._g(sd, "OtomoCharacterContainerId", "ID"))
        palbox_id = world_service._norm_uid(world_service._g(sd, "PalStorageContainerId", "ID"))
    else:
        # Fallback: try _read_player_sav directly (legacy path-load flow).
        decoded = player_service._read_player_sav(players_dir, uid)
        if decoded is not None:
            player_dict, _ = decoded
            bag_ids = _read_bag_container_ids(player_dict)
            party_id, palbox_id = player_service._read_container_ids(players_dir, uid)

    bags: list[dict] = []
    # Build the DynamicItemSaveData index ONCE for the whole snapshot — the
    # weapon/armor/food bags typically reference dynamic items and we don't
    # want to re-walk the array per bag. Cheap when the section is absent.
    from app.backend.services.dynamic_item_service import build_dynamic_index
    dyn_index = build_dynamic_index(wsd)
    for d in PLAYER_BAG_DEFS:
        cid = bag_ids.get(d["bag_type"])
        if not cid:
            # Bag unallocated — still emit an empty placeholder so the UI can
            # render the tab strip consistently.
            bags.append({
                "bag_type": d["bag_type"],
                "label": d["label"],
                "container_id": None,
                "slot_count": 0,
                "item_count": 0,
                "items": [],
            })
            continue
        bags.append(_bag_detail_from_wsd(wsd, d["bag_type"], d["label"], cid, dyn_index))

    stats = player_service.get_player_stats_from_wsd(wsd, uid) if sp is not None else None

    return {
        "uid": uid,
        "name": name,
        "bags": bags,
        "party_id": party_id,
        "palbox_id": palbox_id,
        "stats": stats,
    }
