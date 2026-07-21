"""Base camp inventory assembly for the web backend.

A base camp's inventory is two things:

1. **Storage chests** — ``ItemContainerSaveData`` entries whose owning
   ``MapObjectSaveData`` row has ``base_camp_id_belong_to == this base``.
   ``container_service._build_map_object_index`` already builds the
   ``container_id -> {type, location, base_camp_id}`` cross-reference; we
   just filter it by base id.

2. **Working pals** — the pals deployed at this base. The base's
   ``WorkerDirector.RawData.container_id`` names the
   ``CharacterContainerSaveData`` whose slots point at the worker pals.
   ``pal_service.list_pals_grouped_from_wsd`` buckets pals by
   ``SlotId.ContainerId``, so we pass the worker container id as the
   "party" bucket and take that slice.

The ``wsd`` argument is a ``build_mini_wsd(...)`` slice (NOT a full
``level_dict``). The route layer pulls:
``"ItemContainerSaveData", "MapObjectSaveData", "BaseCampSaveData",
"CharacterSaveParameterMap", "GroupSaveDataMap"``.
"""

from __future__ import annotations

import logging

from app.backend.services import pal_service, world_service
from app.backend.services.base_service import _s
from app.backend.services.container_service import (
    _build_guild_names, _build_map_object_index, get_container_detail_from_wsd,
)

logger = logging.getLogger(__name__)


def _find_base_entry_from_wsd(wsd: dict, base_id: str) -> dict | None:
    """A ``BaseCampSaveData`` entry by id, looked up directly in a wsd slice."""
    bid_clean = _s(base_id)
    for b in world_service._map_entries(wsd, "BaseCampSaveData"):
        if _s(b.get("key")) == bid_clean:
            return b
    return None


def get_base_inventory(wsd: dict, base_id: str) -> dict | None:
    """Assemble a base camp's inventory snapshot (chests + working pals).

    ``wsd`` is a ``build_mini_wsd(...)`` slice — see module docstring for the
    exact section list the route should pull.

    Returns ``None`` if the base id doesn't resolve to a
    ``BaseCampSaveData`` entry.
    """
    base_entry = _find_base_entry_from_wsd(wsd, base_id)
    if base_entry is None:
        return None

    # The worker (pal) container for this base, if any. Read straight from the
    # WorkerDirector blob — same path delete_base uses.
    worker_cont_id = world_service._norm_uid(
        world_service._g(base_entry, "value", "WorkerDirector", "RawData", "container_id")
    )

    # Storage chests: filter the map-object index by this base's id.
    map_index = _build_map_object_index(wsd)
    guild_names = _build_guild_names(wsd)

    base_id_clean = _s(base_id)
    # Build the dynamic-item index ONCE for all chests in this base — chests
    # commonly hold weapons/armor/eggs and we don't want to re-walk the array
    # per chest. Cheap when DynamicItemSaveData is absent from the wsd slice.
    from app.backend.services.dynamic_item_service import build_dynamic_index
    dyn_index = build_dynamic_index(wsd)
    containers: list[dict] = []
    for cid_clean, info in map_index.items():
        if _s(info.get("base_camp_id") or "") != base_id_clean:
            continue
        detail = get_container_detail_from_wsd(wsd, cid_clean, dyn_index)
        if detail is None:
            continue
        containers.append({
            "id": detail["id"],
            "container_type": info.get("type", "Unknown"),
            "slot_count": detail["slot_count"],
            "item_count": detail["item_count"],
            "items": detail["items"],
            "location": info.get("location"),
        })

    # Stable order: most items first, then by type for predictability.
    containers.sort(key=lambda c: (-c["item_count"], c["container_type"]))

    # Working pals: bucket every pal by SlotId.ContainerId, keep the slice
    # matching the worker container. Pass the worker id as the "party" bucket
    # so list_pals_grouped_from_wsd routes those pals there.
    workers: list[dict] = []
    if worker_cont_id:
        grouped = pal_service.list_pals_grouped_from_wsd(
            wsd, worker_cont_id, None, name_map={},
        )
        workers = grouped.get("party", [])

    # Guild name (best effort) for the header.
    guild_name: str | None = None
    gid = world_service._norm_uid(
        world_service._g(
            world_service._g(base_entry, "value", "RawData") or {},
            "group_id_belong_to",
        )
    )
    if gid:
        guild_name = guild_names.get(_s(gid))

    return {
        "base_id": str(base_id),
        "guild_name": guild_name,
        "containers": containers,
        "worker_container_id": worker_cont_id,
        "workers": workers,
    }
