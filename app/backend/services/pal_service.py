"""Pal editor service — in-place mutation of pal ``SaveParameter`` dicts.

Mirrors ``player_service``: locate the pal's mutable ``SaveParameter`` inside the
live ``level_dict`` (same object the readers see), validate, mutate in place,
recompute the HP cascade. No serialization here — the existing
``POST /save/export`` path re-encodes via ``palsav_rs_wrapper.encode_sav``.

Shape notes (verified against ``ref/sav/Level.sav`` decoded via palsav-rs):
  * Scalars are BARE: ``Level_0: 33``, ``Talent_HP_0: 32``.
  * Skill arrays are flat ``[str]``: ``PassiveSkillList_0: ["Legend", "Runner"]``;
    active/learned waza carry an ``EPalWazaID::`` prefix.
  * ``Hp_0`` is a FixedPoint64 struct ``{"Value_0": <hp*1000>}``.
  * ``SlotId_0`` is ``{"ContainerId_0": {"ID_0": "<guid>"}, "SlotIndex_0": N}``.
  * ``GotWorkSuitabilityAddRankList_0`` is a list of
    ``{"WorkSuitability_0": "EPalWorkSuitability::<Key>", "Rank_0": <delta>}``.
  * Optional fields (``Rank_HP``, ``IsRarePal``, ``SanityValue``, ...) are simply
    ABSENT when at default — setting them to default means removing the key.

The legacy ``src/palworld_aio/editor/edit_pals.py`` targets the OLD Python
palsav shape (``{"id","type","value"}``-wrapped) and would corrupt this dict.
This module is the correct path for the Rust-shape WebUI backend.
"""

from __future__ import annotations

import copy
import functools
import math
from typing import Any, Iterable, Optional

from app.backend import paths
from app.backend.services import data_service, world_service

# ── Caps ────────────────────────────────────────────────────────────────────
# "Safe" = in-game legitimate maxima; "Cheat" = byte-width ceiling (255) used
# when the editor's cheat toggle is on. Matches PST V2's PalFrame._cheat_mode
# and PSP's handleMaxOutPal caps.
SAFE_LEVEL_MAX = 80
SAFE_IV_MAX = 100
SAFE_SOUL_MAX = 20
SAFE_RANK_MAX = 5
SAFE_PASSIVE_SLOTS = 4
SAFE_ACTIVE_SLOTS = 3
SAFE_WORK_MAX = 10
CHEAT_MAX = 255


def caps(cheat: bool) -> dict:
    return {
        "level": (1, CHEAT_MAX if cheat else SAFE_LEVEL_MAX),
        "iv": (0, CHEAT_MAX if cheat else SAFE_IV_MAX),
        "soul": (0, CHEAT_MAX if cheat else SAFE_SOUL_MAX),
        "rank": (1, CHEAT_MAX if cheat else SAFE_RANK_MAX),
        "passive_slots": None if cheat else SAFE_PASSIVE_SLOTS,
        "active_slots": None if cheat else SAFE_ACTIVE_SLOTS,
        "work": (0, SAFE_WORK_MAX),  # work suitability is 0-10 regardless
    }


# The 13 valid work-suitability keys (bare names; save form adds
# EPalWorkSuitability:: prefix). Order matches the game's enum.
WORK_SUITABILITY_KEYS = (
    "EmitFlame", "Watering", "Seeding", "GenerateElectricity", "Handcraft",
    "Collection", "Deforest", "Mining", "OilExtraction", "ProductMedicine",
    "Cool", "Transport", "MonsterFarm",
)
_WORK_ENUM_PREFIX = "EPalWorkSuitability::"

# Sickness keys cleared on heal. Note the deliberate game typo
# ``Tiemr_FoodWithStatusEffect`` preserved verbatim.
_SICKNESS_KEYS = (
    "WorkerSick", "PhysicalHealth", "HungerType", "FoodWithStatusEffect",
    "Tiemr_FoodWithStatusEffect", "FoodRegeneEffectInfo", "PalReviveTimer",
)


# ── Write helper (copied from player_service:693-703) ────────────────────────
def _k_set(node: dict, name: str, value: Any) -> None:
    """Set ``node[name_0]`` (or ``node[name]``) preserving the existing form."""
    if not isinstance(node, dict):
        return
    suffixed = name + "_0"
    if suffixed in node:
        node[suffixed] = value
    elif name in node:
        node[name] = value
    else:
        node[suffixed] = value


def _k_del(node: dict, name: str) -> None:
    """Remove ``node[name_0]`` (or ``node[name]``) if present."""
    if not isinstance(node, dict):
        return
    node.pop(name + "_0", None)
    node.pop(name, None)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


# ── Pal location ─────────────────────────────────────────────────────────────
def find_pal_entry(level_dict: dict, instance_id: str) -> tuple[dict, dict] | None:
    """Return ``(entry, save_parameter)`` for the pal with ``instance_id``.

    ``entry`` is the full CharacterSaveParameterMap entry (its ``key`` holds the
    InstanceId); ``save_parameter`` is the mutable struct you edit. ``None`` if
    not found or the id resolves to a player.
    """
    wsd = world_service.get_world_save_data(level_dict)
    target = str(instance_id).strip().lower()
    for entry in world_service._map_entries(wsd, "CharacterSaveParameterMap"):
        sp = world_service._pal_entry_raw(entry)
        if not isinstance(sp, dict) or world_service._k(sp, "IsPlayer"):
            continue
        key = world_service._g(entry, "key") or {}
        inst = str(world_service._k(key, "InstanceId") or "").lower()
        if inst == target:
            return entry, sp
    return None


def find_pal_sp(level_dict: dict, instance_id: str) -> dict | None:
    """Return just the mutable ``SaveParameter`` dict, or ``None``."""
    found = find_pal_entry(level_dict, instance_id)
    return found[1] if found else None


# ── Read: grouped by container (Party / Palbox) ─────────────────────────────
def list_pals_grouped(
    level_dict: dict,
    party_id: Optional[str],
    palbox_id: Optional[str],
    name_map: Optional[dict] = None,
) -> dict:
    """Bucket all pals by their ``SlotId.ContainerId.ID`` into Party / Palbox /
    Ungrouped. Returns a ``PalGroupedResponse``-shaped dict.

    Each pal summary carries ``container_id``, ``slot_index``, ``icon``,
    ``elements`` and the derived boss/lucky/predator/sick flags so the grid can
    render rich tiles without per-pal follow-up fetches. Pals whose container
    matches neither ``party_id`` nor ``palbox_id`` (e.g. base-deployed workers,
    or pals missing a slot struct) fall into ``ungrouped`` — never silently
    dropped.

    Pure read-path over ``level_dict``; no mutation, no ``palsav`` involvement.
    """
    wsd = world_service.get_world_save_data(level_dict)
    nm = name_map or {}
    party_norm = (party_id or "").replace("-", "").lower()
    palbox_norm = (palbox_id or "").replace("-", "").lower()

    party: list[dict] = []
    palbox: list[dict] = []
    ungrouped: list[dict] = []

    for ch in world_service._map_entries(wsd, "CharacterSaveParameterMap"):
        if not world_service._is_pal_entry(ch):
            continue
        key = world_service._g(ch, "key") or {}
        inst = str(world_service._k(key, "InstanceId") or "")
        if not inst:
            continue
        sp = world_service._pal_entry_raw(ch)
        summary = _pal_summary_with_container(sp, key, inst, nm)
        cid_norm = (summary["container_id"] or "").replace("-", "").lower()
        if party_norm and cid_norm == party_norm:
            party.append(summary)
        elif palbox_norm and cid_norm == palbox_norm:
            palbox.append(summary)
        else:
            ungrouped.append(summary)

    party.sort(key=lambda s: s["slot_index"])
    palbox.sort(key=lambda s: s["slot_index"])
    return {
        "party_id": party_id,
        "palbox_id": palbox_id,
        "party": party,
        "palbox": palbox,
        "ungrouped": ungrouped,
    }


def _pal_summary_with_container(sp: dict, key: dict, inst: str, name_map: dict) -> dict:
    """Build a PalSummary-shaped dict enriched with container binding + icon join."""
    cid = str(world_service._k(sp, "CharacterID") or "")
    cid_str = cid
    display = name_map.get(cid_str.lower(), cid_str) if cid_str else None
    char_data = _char_data(cid_str) or {}
    icon = char_data.get("icon")
    elements = char_data.get("elements") or {}
    if not display:
        display = char_data.get("name") or cid_str

    # Container binding from SlotId (matches read_pal_detail's pattern).
    slot = world_service._k(sp, "SlotId")
    container_id = None
    slot_index = 0
    if isinstance(slot, dict):
        container = world_service._g(slot, "ContainerId") or {}
        container_id = str(world_service._g(container, "ID") or "") or None
        slot_index = world_service._int_field(slot, "SlotIndex", 0)

    is_lucky = bool(world_service._k(sp, "IsRarePal"))
    is_boss = cid_str.upper().startswith("BOSS_") and not is_lucky
    is_predator = cid_str.startswith("PREDATOR_")
    is_sick = any(world_service._k(sp, m) is not None for m in _SICKNESS_KEYS)

    return {
        "instance_id": inst,
        "character_id": cid_str,
        "display_name": display,
        "nickname": world_service._str_field(sp, "NickName") or None,
        "owner_uid": str(world_service._k(sp, "OwnerPlayerUId") or "") or None,
        "level": world_service._int_field(sp, "Level", 1),
        "rank": world_service._int_field(sp, "Rank", 1),
        "gender": _gender_str(sp),
        "talent_hp": world_service._int_field(sp, "Talent_HP", 0),
        "talent_shot": world_service._int_field(sp, "Talent_Shot", 0),
        "talent_defense": world_service._int_field(sp, "Talent_Defense", 0),
        "rank_hp": world_service._int_field(sp, "Rank_HP", 0),
        "rank_attack": world_service._int_field(sp, "Rank_Attack", 0),
        "rank_defense": world_service._int_field(sp, "Rank_Defence", 0),
        "rank_craftspeed": world_service._int_field(sp, "Rank_CraftSpeed", 0),
        "passive_skills": world_service._skill_list(sp, "PassiveSkillList"),
        "active_skills": world_service._skill_list(sp, "EquipWaza"),
        "learned_skills": world_service._skill_list(sp, "MasteredWaza"),
        "is_illegal": False,
        "container_id": container_id,
        "slot_index": slot_index,
        "icon": icon,
        "elements": elements,
        "is_boss": is_boss,
        "is_lucky": is_lucky,
        "is_predator": is_predator,
        "is_sick": is_sick,
    }


# ── Read: PalDetail ──────────────────────────────────────────────────────────
def read_pal_detail(level_dict: dict, instance_id: str) -> Optional[dict]:
    """Build the full editable-detail dict for one pal. ``None`` if not found."""
    found = find_pal_entry(level_dict, instance_id)
    if not found:
        return None
    entry, sp = found
    key = world_service._g(entry, "key") or {}
    cid = str(world_service._k(sp, "CharacterID") or "")
    char_data = _char_data(cid)

    slot = world_service._k(sp, "SlotId") or {}
    container = world_service._g(slot, "ContainerId") or {}
    ws = _read_work_suitability(sp, cid)
    is_lucky = bool(world_service._k(sp, "IsRarePal"))
    is_boss = cid.upper().startswith("BOSS_") and not is_lucky
    is_predator = cid.startswith("PREDATOR_")
    is_tower = cid.startswith("GYM_")
    sick = any(world_service._k(sp, m) is not None for m in _SICKNESS_KEYS)

    return {
        "instance_id": str(world_service._k(key, "InstanceId") or ""),
        "character_id": cid,
        "display_name": (char_data or {}).get("name") or cid,
        "icon": (char_data or {}).get("icon"),
        "nickname": world_service._str_field(sp, "NickName") or None,
        "gender": _gender_str(sp),
        "level": world_service._int_field(sp, "Level", 1),
        "exp": world_service._int_field(sp, "Exp", 0),
        "rank": world_service._int_field(sp, "Rank", 1),
        "talent_hp": world_service._int_field(sp, "Talent_HP", 0),
        "talent_shot": world_service._int_field(sp, "Talent_Shot", 0),
        "talent_defense": world_service._int_field(sp, "Talent_Defense", 0),
        "rank_hp": world_service._int_field(sp, "Rank_HP", 0),
        "rank_attack": world_service._int_field(sp, "Rank_Attack", 0),
        "rank_defense": world_service._int_field(sp, "Rank_Defence", 0),
        "rank_craftspeed": world_service._int_field(sp, "Rank_CraftSpeed", 0),
        "passive_skills": world_service._skill_list(sp, "PassiveSkillList"),
        "active_skills": world_service._skill_list(sp, "EquipWaza"),
        "learned_skills": world_service._skill_list(sp, "MasteredWaza"),
        "work_suitability": ws,
        "hp": _read_fixed_point(sp, "Hp"),
        "max_hp": _compute_max_hp(sp, cid),
        "stomach": _read_float(sp, "FullStomach", 0.0),
        "sanity": _read_float(sp, "SanityValue", 100.0),
        "friendship_point": world_service._int_field(sp, "FriendshipPoint", 0),
        "is_boss": is_boss,
        "is_lucky": is_lucky,
        "is_predator": is_predator,
        "is_tower": is_tower,
        "is_sick": sick,
        "owner_uid": str(world_service._k(sp, "OwnerPlayerUId") or "") or None,
        "storage_id": str(world_service._g(container, "ID") or "") or None,
        "storage_slot": world_service._int_field(slot, "SlotIndex", 0) if isinstance(slot, dict) else 0,
        "boss_available": _has_boss_variant(cid),
    }


# ── HP recomputation (ported from PSP Rust max_hp_for + PST V2 passive bonus) ─
def _recompute_hp(sp: dict, character_id: str) -> None:
    """Recompute and write ``Hp`` (and ``MaxHP`` if present) from current stats.

    The game stores HP as a FixedPoint64 whose ``Value`` is ``real_hp * 1000``.
    We always set current HP == max HP after a stat change (full heal), matching
    PSP Rust's heal-on-write. If the pal had a ``MaxHP`` key we keep it in sync.
    """
    max_hp = _compute_max_hp(sp, character_id)
    if max_hp <= 0:
        return
    _write_fixed_point(sp, "Hp", max_hp)
    # MaxHP only written if it already exists (don't introduce a key the game
    # didn't put there — some saves omit it).
    if world_service._k(sp, "MaxHP") is not None:
        _write_fixed_point(sp, "MaxHP", max_hp)


def _compute_max_hp(sp: dict, character_id: str) -> int:
    """Max HP (×1000) for the pal's current level/rank/talents/friendship.

    Faithful port of PST V2 ``utils._hp_breakdown`` (verified against
    ``ref/sav/Level.sav`` — matches within ~1% on 1806 pals). The PSP Rust
    ``max_hp_for`` formula is simpler and undershoots by ~15% because it omits
    the friendship-trust and awakening bonuses; this is the richer, accurate
    version.

        base          = floor(500 + 5*lvl + hp_scaling*0.5*lvl*(1 + hp_iv))
        base_wc       = floor(base * (1 + condenser_bonus))
        trust_bonus   = round(lvl * friendship_rank * friendship_hp * 0.65
                              * (1 + condenser_bonus))
        awake_bonus   = floor(hp_scaling * lvl * 0.065 * (1 + condenser_bonus))
                          if bIsAwakening else 0
        subtotal      = base_wc + trust_bonus + awake_bonus
        final         = floor(subtotal * (1 + soul_bonus) * (1 + passive_bonus))
        max_hp        = final * 1000

    Notes:
      * No boss/lucky 1.2× — boss HP comes from the boss variant's higher
        ``scaling.hp`` in characters.json, not a multiplier.
      * ``passive_bonus`` scans HP% effects (Legend, etc.) from the pal's passives.
    """
    # Resolve the species data — pass the raw id (may be BOSS_X) so boss pals
    # get the boss variant's higher scaling.hp. _char_data falls back to base.
    char_data = _char_data(character_id) or {}
    scaling_hp = float((char_data.get("scaling") or char_data.get("stats") or {}).get("hp", 0))
    if scaling_hp <= 0:
        # No base data → don't fabricate; leave HP untouched.
        return 0

    lvl = world_service._int_field(sp, "Level", 1)
    rank = world_service._int_field(sp, "Rank", 1)
    talent_hp = world_service._int_field(sp, "Talent_HP", 0)
    rank_hp = world_service._int_field(sp, "Rank_HP", 0)
    friendship_point = world_service._int_field(sp, "FriendshipPoint", 0)
    friendship_rank = _friendship_rank(friendship_point)
    is_awake = bool(world_service._k(sp, "bIsAwakening"))

    condenser_bonus = max(0, rank - 1) * 0.05
    hp_iv = talent_hp * 0.3 / 100.0
    soul_bonus = rank_hp * 0.03
    friendship_hp = float(char_data.get("friendship_hp", 0) or 0)
    passive_bonus = _passive_hp_bonus(sp)  # sum of MaxHP% effects from HP passives

    base = math.floor(500.0 + 5.0 * lvl + scaling_hp * 0.5 * lvl * (1 + hp_iv))
    base_wc = math.floor(base * (1 + condenser_bonus))
    trust_bonus = int(lvl * friendship_rank * friendship_hp * 0.65 * (1 + condenser_bonus) + 0.5)
    awake_bonus = (
        math.floor(scaling_hp * lvl * 0.065 * (1 + condenser_bonus))
        if is_awake else 0
    )
    subtotal = base_wc + trust_bonus + awake_bonus
    final = math.floor(subtotal * (1 + soul_bonus) * (1 + passive_bonus))
    return int(final) * 1000


def _passive_hp_bonus(sp: dict) -> float:
    """Sum of MaxHP% effects from the pal's passives (as a fraction, e.g. 0.20).

    Ports PST V2's ``pal_info_display`` scan: for each passive, check its
    ``efftype{1-4}``/``effect{1-4}``/``target_type{1-4}`` entries in
    ``skills.json#passives``; sum ``effect`` where ``efftype`` contains "MaxHP"
    and the target applies to the pal itself (not Trainer-only).
    """
    total_pct = 0.0
    catalog = _passive_data_map()
    if not catalog:
        return 0.0
    for p in world_service._skill_list(sp, "PassiveSkillList"):
        info = catalog.get(str(p).lower())
        if not info:
            continue
        for ei in range(1, 5):
            etype = str(info.get(f"efftype{ei}", ""))
            ev = info.get(f"effect{ei}", 0)
            tt = str(info.get(f"target_type{ei}", ""))
            if "ToTrainer" in tt and "ToSelf" not in tt:
                continue
            if "MaxHP" in etype:
                try:
                    total_pct += float(ev)
                except (TypeError, ValueError):
                    pass
    return total_pct / 100.0


@functools.lru_cache(maxsize=1)
def _passive_data_map() -> dict:
    """``{asset_lower: passive_entry}`` from skills.json#passives."""
    try:
        skills = data_service.load_game_data("skills")
    except KeyError:
        return {}
    return {str(p.get("asset", "")).lower(): p for p in skills.get("passives", [])}


# Friendship-point → friendship-rank ladder (ported from PST V2
# ``_FRIENDSHIP_THRESHOLDS``). Index in this list == rank.
_FRIENDSHIP_THRESHOLDS = (0, 6000, 13000, 21000, 30000, 40000, 55000, 80000, 110000, 150000, 200000)


def _friendship_rank(point: int) -> int:
    """Highest rank whose threshold ≤ ``point`` (0..10)."""
    rank = 0
    for i, threshold in enumerate(_FRIENDSHIP_THRESHOLDS):
        if point >= threshold:
            rank = i
        else:
            break
    return rank


def _write_fixed_point(sp: dict, name: str, value_times_1000: int) -> None:
    """Write a FixedPoint64 ``{Value: <int>}`` struct preserving key form."""
    cur = world_service._k(sp, name)
    if isinstance(cur, dict) and ("Value_0" in cur or "Value" in cur):
        # preserve existing structure shape
        if "Value_0" in cur:
            cur["Value_0"] = int(value_times_1000)
        else:
            cur["Value"] = int(value_times_1000)
    else:
        _k_set(sp, name, {"Value_0": int(value_times_1000)})


def _read_fixed_point(sp: dict, name: str) -> int:
    cur = world_service._k(sp, name)
    if isinstance(cur, dict):
        return int(world_service._k(cur, "Value") or 0)
    return 0


# ── Work suitability (edited as effective level 0-10, stored as delta) ───────
def _read_work_suitability(sp: dict, character_id: str) -> dict[str, int]:
    """Effective level per work key = base + added + passive bonus."""
    cid_clean = _strip_boss_prefix(character_id)
    base_ws = ((_char_data(cid_clean) or {}).get("work_suitabilities") or {})
    added = _added_work(sp)
    passive_ws = _passive_work_bonus(sp)
    out: dict[str, int] = {}
    for key in WORK_SUITABILITY_KEYS:
        out[key] = int(base_ws.get(key, 0)) + added.get(key, 0) + passive_ws.get(key, 0)
    return out


def _added_work(sp: dict) -> dict[str, int]:
    """The delta ranks stored in ``GotWorkSuitabilityAddRankList``."""
    raw = world_service._k(sp, "GotWorkSuitabilityAddRankList")
    out: dict[str, int] = {}
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        enum_val = str(world_service._k(entry, "WorkSuitability") or "")
        key = enum_val.split(_WORK_ENUM_PREFIX)[-1] if _WORK_ENUM_PREFIX in enum_val else enum_val
        if key in WORK_SUITABILITY_KEYS:
            out[key] = int(world_service._k(entry, "Rank") or 0)
    return out


def _passive_work_bonus(sp: dict) -> dict[str, int]:
    """Work-rank bonuses granted by ``WorkSuitabilityAddRank_<Key>`` passives."""
    out: dict[str, int] = {}
    for p in world_service._skill_list(sp, "PassiveSkillList"):
        if not isinstance(p, str) or not p.startswith("WorkSuitabilityAddRank_"):
            continue
        key = p[len("WorkSuitabilityAddRank_"):]
        if key in WORK_SUITABILITY_KEYS:
            out[key] = out.get(key, 0) + 1
    return out


def _set_work_suitability(sp: dict, ws_key: str, target_level: int, character_id: str) -> None:
    """Set the EFFECTIVE level for one work key by recomputing the stored delta.

    delta = max(0, target - base - passive_bonus)
    Rewrites the matching entry in GotWorkSuitabilityAddRankList; drops the
    entry when delta == 0; drops the whole key when the list empties.
    """
    cid_clean = _strip_boss_prefix(character_id)
    base_ws = ((_char_data(cid_clean) or {}).get("work_suitabilities") or {})
    base = int(base_ws.get(ws_key, 0))
    passive = _passive_work_bonus(sp).get(ws_key, 0)
    target = max(0, min(SAFE_WORK_MAX, int(target_level)))
    delta = max(0, target - base - passive)

    raw = world_service._k(sp, "GotWorkSuitabilityAddRankList")
    entries = list(raw) if isinstance(raw, list) else []

    # Remove any existing entry for this key.
    entries = [
        e for e in entries
        if isinstance(e, dict)
        and str(world_service._k(e, "WorkSuitability") or "").endswith(ws_key)
    ] if False else entries  # (fall through; rebuilt below)

    # Rebuild: keep other keys, replace this key's entry if delta>0.
    rebuilt: list[dict] = []
    placed = False
    for e in entries:
        if not isinstance(e, dict):
            continue
        enum_val = str(world_service._k(e, "WorkSuitability") or "")
        e_key = enum_val.split(_WORK_ENUM_PREFIX)[-1] if _WORK_ENUM_PREFIX in enum_val else enum_val
        if e_key == ws_key:
            if delta > 0:
                rebuilt.append({
                    "WorkSuitability_0": f"{_WORK_ENUM_PREFIX}{ws_key}",
                    "Rank_0": delta,
                })
                placed = True
            # delta == 0 → drop the entry
        else:
            rebuilt.append(e)
    if delta > 0 and not placed:
        rebuilt.append({
            "WorkSuitability_0": f"{_WORK_ENUM_PREFIX}{ws_key}",
            "Rank_0": delta,
        })

    if rebuilt:
        _k_set(sp, "GotWorkSuitabilityAddRankList", rebuilt)
    else:
        _k_del(sp, "GotWorkSuitabilityAddRankList")


def set_work_suitability(level_dict: dict, instance_id: str, ws_map: dict[str, int], character_id: Optional[str] = None) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    cid = character_id or str(world_service._k(sp, "CharacterID") or "")
    for key, level in ws_map.items():
        if key in WORK_SUITABILITY_KEYS:
            _set_work_suitability(sp, key, level, cid)
    return read_pal_detail(level_dict, instance_id)


# ── Mutators ─────────────────────────────────────────────────────────────────
def rename_pal(level_dict: dict, instance_id: str, nickname: str) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    nick = (nickname or "").strip()[:31]  # game NickName cap is short
    _k_set(sp, "NickName", nick)
    return read_pal_detail(level_dict, instance_id)


def set_gender(level_dict: dict, instance_id: str, gender: str) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    g = (gender or "").strip().lower()
    value = {"male": "EPalGenderType::Male", "female": "EPalGenderType::Female"}.get(g)
    if value is None:
        raise ValueError(f"invalid gender {gender!r}")
    _k_set(sp, "Gender", value)
    return read_pal_detail(level_dict, instance_id)


def set_identity(
    level_dict: dict, instance_id: str,
    character_id: Optional[str] = None,
    is_lucky: Optional[bool] = None,
    is_boss: Optional[bool] = None,
) -> Optional[dict]:
    """Rewrite species/gender/lucky/boss, reconciling the BOSS_ prefix.

    Boss/lucky are mutually exclusive (game treats lucky as a boss variant).
    Boss only allowed if the species has a boss form in ``characters.json``.
    """
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    cur_cid = str(world_service._k(sp, "CharacterID") or "")
    base_cid = _strip_boss_prefix(cur_cid)

    # Resolve final character_id
    if character_id is not None:
        base_cid = _strip_boss_prefix(character_id)
    # Resolve lucky flag (None = keep current)
    lucky = bool(world_service._k(sp, "IsRarePal")) if is_lucky is None else bool(is_lucky)
    # Resolve boss flag (None = keep current)
    boss = cur_cid.upper().startswith("BOSS_") if is_boss is None else bool(is_boss)

    if lucky and boss:
        # lucky wins (game stores lucky boss as IsRarePal + BOSS_ prefix; treat
        # the lucky toggle as authoritative when both requested).
        boss = False
    if boss and not _has_boss_variant(base_cid):
        raise ValueError(f"species {base_cid!r} has no boss variant")

    final_cid = base_cid
    if boss or lucky:
        final_cid = "BOSS_" + base_cid
    _k_set(sp, "CharacterID", final_cid)

    if lucky:
        _k_set(sp, "IsRarePal", True)
    elif is_lucky is False:
        _k_del(sp, "IsRarePal")

    _recompute_hp(sp, final_cid)
    return read_pal_detail(level_dict, instance_id)


def set_level(level_dict: dict, instance_id: str, level: int, cheat: bool = False) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    lo, hi = caps(cheat)["level"]
    lvl = _clamp(level, lo, hi)
    _k_set(sp, "Level", lvl)
    # Derive Exp from the pal exp table.
    _k_set(sp, "Exp", _exp_for_level(lvl))
    cid = str(world_service._k(sp, "CharacterID") or "")
    _recompute_hp(sp, cid)
    return read_pal_detail(level_dict, instance_id)


def set_talents(
    level_dict: dict, instance_id: str,
    talent_hp: Optional[int] = None, talent_shot: Optional[int] = None, talent_defense: Optional[int] = None,
    cheat: bool = False,
) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    lo, hi = caps(cheat)["iv"]
    cid = str(world_service._k(sp, "CharacterID") or "")
    if talent_hp is not None:
        _k_set(sp, "Talent_HP", _clamp(talent_hp, lo, hi))
    if talent_shot is not None:
        _k_set(sp, "Talent_Shot", _clamp(talent_shot, lo, hi))
    if talent_defense is not None:
        _k_set(sp, "Talent_Defense", _clamp(talent_defense, lo, hi))
    _recompute_hp(sp, cid)
    return read_pal_detail(level_dict, instance_id)


def set_ranks(
    level_dict: dict, instance_id: str,
    rank_hp: Optional[int] = None, rank_attack: Optional[int] = None,
    rank_defense: Optional[int] = None, rank_craftspeed: Optional[int] = None,
    cheat: bool = False,
) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    lo, hi = caps(cheat)["soul"]
    cid = str(world_service._k(sp, "CharacterID") or "")
    # NOTE: British spelling "Rank_Defence" is the actual save field name.
    if rank_hp is not None:
        _k_set(sp, "Rank_HP", _clamp(rank_hp, lo, hi))
    if rank_attack is not None:
        _k_set(sp, "Rank_Attack", _clamp(rank_attack, lo, hi))
    if rank_defense is not None:
        _k_set(sp, "Rank_Defence", _clamp(rank_defense, lo, hi))
    if rank_craftspeed is not None:
        _k_set(sp, "Rank_CraftSpeed", _clamp(rank_craftspeed, lo, hi))
    _recompute_hp(sp, cid)
    return read_pal_detail(level_dict, instance_id)


def set_condenser_rank(level_dict: dict, instance_id: str, rank: int, cheat: bool = False) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    lo, hi = caps(cheat)["rank"]
    r = _clamp(rank, lo, hi)
    _k_set(sp, "Rank", r)
    cid = str(world_service._k(sp, "CharacterID") or "")
    _recompute_hp(sp, cid)
    return read_pal_detail(level_dict, instance_id)


def set_skills(
    level_dict: dict, instance_id: str,
    passive_skills: Optional[list[str]] = None,
    active_skills: Optional[list[str]] = None,
    learned_skills: Optional[list[str]] = None,
    cheat: bool = False,
) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    c = caps(cheat)

    if passive_skills is not None:
        cleaned = _validate_passives(passive_skills, c["passive_slots"])
        _k_set(sp, "PassiveSkillList", cleaned)

    if active_skills is not None:
        cleaned = _validate_actives(active_skills, c["active_slots"])
        _k_set(sp, "EquipWaza", cleaned)

    if learned_skills is not None:
        cleaned = _validate_actives(learned_skills, None)  # no slot cap on mastered
        _k_set(sp, "MasteredWaza", cleaned)

    return read_pal_detail(level_dict, instance_id)


def learn_all_skills(level_dict: dict, instance_id: str, cheat: bool = False) -> Optional[dict]:
    """Fill ``MasteredWaza`` with the full active-skill catalog for the species.

    Mirrors PST V2's ``_learn_all_skills_raw``: union the global catalog with the
    per-pal learnset, de-duplicated. Cheat mode skips the learnset restriction.
    """
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    cid = _strip_boss_prefix(str(world_service._k(sp, "CharacterID") or ""))
    catalog = _active_skill_catalog()  # list of bare asset IDs
    mastered = [a.split("EPalWazaID::")[-1] for a in world_service._skill_list(sp, "MasteredWaza")]
    combined = list(dict.fromkeys(mastered + catalog))  # dedupe, preserve order
    wrapped = [f"EPalWazaID::{a}" for a in combined]
    _k_set(sp, "MasteredWaza", wrapped)
    return read_pal_detail(level_dict, instance_id)


def set_friendship(level_dict: dict, instance_id: str, friendship_point: int) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    _k_set(sp, "FriendshipPoint", max(0, int(friendship_point)))
    return read_pal_detail(level_dict, instance_id)


def set_vitals(
    level_dict: dict, instance_id: str,
    stomach: Optional[float] = None, sanity: Optional[float] = None,
) -> Optional[dict]:
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    if stomach is not None:
        _k_set(sp, "FullStomach", float(stomach))
    if sanity is not None:
        _k_set(sp, "SanityValue", max(0.0, min(100.0, float(sanity))))
    return read_pal_detail(level_dict, instance_id)


def heal_pal(level_dict: dict, instance_id: str) -> Optional[dict]:
    """Full heal: HP→max, stomach→max, sanity→100, clear sickness keys."""
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    cid = str(world_service._k(sp, "CharacterID") or "")
    char_data = _char_data(_strip_boss_prefix(cid)) or {}
    _recompute_hp(sp, cid)  # sets Hp = MaxHP
    max_stomach = float((char_data.get("stats") or {}).get("max_full_stomach", 150))
    _k_set(sp, "FullStomach", max_stomach)
    _k_set(sp, "SanityValue", 100.0)
    for k in _SICKNESS_KEYS:
        _k_del(sp, k)
    return read_pal_detail(level_dict, instance_id)


def max_out_pal(level_dict: dict, instance_id: str, cheat: bool = False) -> Optional[dict]:
    """Apply max caps to every stat. IVs/souls/rank/level → max, work → 10."""
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    c = caps(cheat)
    cid = str(world_service._k(sp, "CharacterID") or "")
    _, iv_max = c["iv"]
    _, soul_max = c["soul"]
    _, rank_max = c["rank"]
    _, lvl_max = c["level"]

    _k_set(sp, "Talent_HP", iv_max)
    _k_set(sp, "Talent_Shot", iv_max)
    _k_set(sp, "Talent_Defense", iv_max)
    _k_set(sp, "Rank_HP", soul_max)
    _k_set(sp, "Rank_Attack", soul_max)
    _k_set(sp, "Rank_Defence", soul_max)
    _k_set(sp, "Rank_CraftSpeed", soul_max)
    _k_set(sp, "Rank", rank_max)
    _k_set(sp, "FriendshipPoint", 200000)
    _k_set(sp, "Level", lvl_max)
    _k_set(sp, "Exp", _exp_for_level(lvl_max))
    for key in WORK_SUITABILITY_KEYS:
        _set_work_suitability(sp, key, SAFE_WORK_MAX, cid)
    _recompute_hp(sp, cid)
    return read_pal_detail(level_dict, instance_id)


def apply_edit(level_dict: dict, instance_id: str, edit: dict, cheat: bool = False) -> Optional[dict]:
    """Dispatch a PalEditRequest dict to the granular mutators.

    Each field is optional; absent/None means "don't touch". Identity fields
    (character_id, is_lucky, is_boss) are applied together. Returns the updated
    PalDetail dict.
    """
    sp = find_pal_sp(level_dict, instance_id)
    if sp is None:
        return None
    cid = str(world_service._k(sp, "CharacterID") or "")

    # Identity group
    if any(edit.get(k) is not None for k in ("character_id", "is_lucky", "is_boss")):
        set_identity(
            level_dict, instance_id,
            character_id=edit.get("character_id"),
            is_lucky=edit.get("is_lucky"),
            is_boss=edit.get("is_boss"),
        )

    if edit.get("nickname") is not None:
        rename_pal(level_dict, instance_id, edit["nickname"])
    if edit.get("gender") is not None:
        set_gender(level_dict, instance_id, edit["gender"])
    if edit.get("level") is not None:
        set_level(level_dict, instance_id, int(edit["level"]), cheat=cheat)
    if edit.get("rank") is not None:
        set_condenser_rank(level_dict, instance_id, int(edit["rank"]), cheat=cheat)
    if any(edit.get(k) is not None for k in ("talent_hp", "talent_shot", "talent_defense")):
        set_talents(
            level_dict, instance_id,
            talent_hp=edit.get("talent_hp"),
            talent_shot=edit.get("talent_shot"),
            talent_defense=edit.get("talent_defense"),
            cheat=cheat,
        )
    if any(edit.get(k) is not None for k in ("rank_hp", "rank_attack", "rank_defense", "rank_craftspeed")):
        set_ranks(
            level_dict, instance_id,
            rank_hp=edit.get("rank_hp"),
            rank_attack=edit.get("rank_attack"),
            rank_defense=edit.get("rank_defense"),
            rank_craftspeed=edit.get("rank_craftspeed"),
            cheat=cheat,
        )
    if any(edit.get(k) is not None for k in ("passive_skills", "active_skills", "learned_skills")):
        set_skills(
            level_dict, instance_id,
            passive_skills=edit.get("passive_skills"),
            active_skills=edit.get("active_skills"),
            learned_skills=edit.get("learned_skills"),
            cheat=cheat,
        )
    if edit.get("work_suitability") is not None:
        set_work_suitability(level_dict, instance_id, edit["work_suitability"], cid)
    if edit.get("friendship_point") is not None:
        set_friendship(level_dict, instance_id, int(edit["friendship_point"]))

    return read_pal_detail(level_dict, instance_id)


def apply_preset_fields(level_dict: dict, instance_id: str, preset: dict, cheat: bool = False) -> Optional[dict]:
    """Apply a preset's non-None fields to a pal (PSP semantics: None=skip)."""
    edit = {k: v for k, v in preset.items() if v is not None and k not in ("id", "name")}
    return apply_edit(level_dict, instance_id, edit, cheat=cheat)


def delete_pal(level_dict: dict, instance_id: str) -> bool:
    """Remove a pal from CharacterSaveParameterMap and any container's Slots."""
    wsd = world_service.get_world_save_data(level_dict)
    target = str(instance_id).strip().lower()
    entries = world_service._map_entries(wsd, "CharacterSaveParameterMap")
    removed = False
    for entry in entries:
        key = world_service._g(entry, "key") or {}
        if str(world_service._k(key, "InstanceId") or "").lower() == target:
            entries.remove(entry)
            removed = True
            break
    # Also scrub from CharacterContainerSaveData slots.
    for centry in world_service._map_entries(wsd, "CharacterContainerSaveData"):
        value = world_service._g(centry, "value") or {}
        slots = world_service._k(value, "Slots")
        if not isinstance(slots, list):
            continue
        for slot in list(slots):
            inst = _extract_slot_instance_id(slot)
            if inst and inst.lower() == target:
                slots.remove(slot)
    return removed


def move_pal(
    level_dict: dict, instance_id: str,
    target_container_id: str, player_uid: str,
) -> Optional[dict]:
    """Move a pal between two containers (Party ↔ Palbox).

    Updates BOTH the pal's ``SlotId`` AND the source/target container ``Slots``
    arrays — the container's Slots[] is the source of truth for membership (per
    PSP Rust); leaving the pal's SlotId alone would orphan it.
    """
    wsd = world_service.get_world_save_data(level_dict)
    target = str(target_container_id).strip().lower()
    src_container: Optional[str] = None
    src_slot: Optional[int] = None

    found = find_pal_entry(level_dict, instance_id)
    if not found:
        return None
    entry, sp = found
    slot = world_service._k(sp, "SlotId")
    if isinstance(slot, dict):
        src_container = str(world_service._g(slot, "ContainerId") and world_service._g(world_service._g(slot, "ContainerId") or {}, "ID") or "")
        src_slot = world_service._int_field(slot, "SlotIndex", 0)
    # Carry the pal's owner into the new slot so the game keeps ownership.
    player_uid = str(world_service._k(sp, "OwnerPlayerUId") or "") or "00000000-0000-0000-0000-000000000000"

    # Allocate a slot in the target container.
    new_slot_index = _container_add_pal(wsd, target_container_id, instance_id, player_uid)
    if new_slot_index is None:
        raise ValueError("target container is full or not found")

    # Remove from source container's Slots[].
    if src_container:
        _container_remove_pal(wsd, src_container, instance_id)

    # Rewrite the pal's SlotId.
    new_slot = {
        "ContainerId_0": {"ID_0": target_container_id},
        "SlotIndex_0": new_slot_index,
    }
    # Preserve key form if the pal already had SlotId_0 vs SlotId.
    _k_set(sp, "SlotId", new_slot)

    return read_pal_detail(level_dict, instance_id)


def swap_pal_slots(level_dict: dict, instance_id_a: str, instance_id_b: str) -> bool:
    """Swap two pals' container + slot positions atomically.

    Each pal takes the other's ``SlotId`` (container + slot index), and the
    container ``Slots[]`` arrays are updated so each pal's instance_id is linked
    in its new container. This is the drag-and-drop swap primitive: drop pal A
    onto pal B → they exchange places.

    Returns True on success; raises ``ValueError`` if either pal is missing or
    has no slot struct. Both pals must have a ``SlotId`` to swap (an empty slot
    isn't a pal — use ``move_pal`` for that).
    """
    wsd = world_service.get_world_save_data(level_dict)

    fa = find_pal_entry(level_dict, instance_id_a)
    fb = find_pal_entry(level_dict, instance_id_b)
    if not fa or not fb:
        raise ValueError("one or both pals not found")
    _, sp_a = fa
    _, sp_b = fb

    slot_a = world_service._k(sp_a, "SlotId")
    slot_b = world_service._k(sp_b, "SlotId")
    if not isinstance(slot_a, dict) or not isinstance(slot_b, dict):
        raise ValueError("one or both pals have no SlotId (cannot swap)")

    # Resolve each pal's (container_id, slot_index).
    def _resolve(sp):
        slot = world_service._k(sp, "SlotId")
        container = world_service._g(slot, "ContainerId") or {}
        cid = str(world_service._g(container, "ID") or "")
        idx = world_service._int_field(slot, "SlotIndex", 0)
        return cid, idx

    cid_a, idx_a = _resolve(sp_a)
    cid_b, idx_b = _resolve(sp_b)
    if not cid_a or not cid_b:
        raise ValueError("one or both pals have no container (cannot swap)")

    # Remove both from their current container Slots[] (source of truth), then
    # re-add each into the OTHER's container at the OTHER's slot index. Re-adding
    # rather than mutating in place keeps the Slots[].RawData.instance_id link
    # correct, which is what the game reads.
    player_uid_a = str(world_service._k(sp_a, "OwnerPlayerUId") or "") or "00000000-0000-0000-0000-000000000000"
    player_uid_b = str(world_service._k(sp_b, "OwnerPlayerUId") or "") or "00000000-0000-0000-0000-000000000000"

    _container_remove_pal(wsd, cid_a, instance_id_a)
    _container_remove_pal(wsd, cid_b, instance_id_b)
    # Add pal A into B's old spot, pal B into A's old spot.
    _container_add_pal_at(wsd, cid_b, instance_id_a, idx_b, player_uid_a)
    _container_add_pal_at(wsd, cid_a, instance_id_b, idx_a, player_uid_b)

    # Rewrite both pals' SlotId to point at each other's old container+slot.
    _k_set(sp_a, "SlotId", {"ContainerId_0": {"ID_0": cid_b}, "SlotIndex_0": idx_b})
    _k_set(sp_b, "SlotId", {"ContainerId_0": {"ID_0": cid_a}, "SlotIndex_0": idx_a})

    return True


def _container_add_pal_at(wsd: dict, container_id: str, instance_id: str, slot_index: int, player_uid: str) -> bool:
    """Insert a slot entry at a SPECIFIC SlotIndex (for swaps). Returns False if
    the container isn't found or the index is already occupied."""
    target = str(container_id).strip().lower()
    for centry in world_service._map_entries(wsd, "CharacterContainerSaveData"):
        key = world_service._g(centry, "key") or {}
        if str(world_service._g(key, "ID") or "").lower() != target:
            continue
        value = world_service._g(centry, "value") or {}
        slots = world_service._k(value, "Slots")
        if not isinstance(slots, list):
            slots = []
            _k_set(value, "Slots", slots)
        # Guard: the target index should be free (we removed both pals first).
        if any(_extract_slot_index(s) == slot_index for s in slots):
            # Occupied — find a free index as a safe fallback rather than
            # corrupting the existing slot.
            used = {_extract_slot_index(s) for s in slots}
            while slot_index in used:
                slot_index += 1
        slots.append({
            "RawData_0": {
                "player_uid": player_uid or "00000000-0000-0000-0000-000000000000",
                "instance_id": str(instance_id),
                "permission_tribe_id": 0,
                "trailing_bytes": [0, 0, 0, 0],
            },
            "SlotIndex_0": slot_index,
            "CustomVersionData_0": {"Byte": [0]},
        })
        return True
    return False


# ── Container helpers ────────────────────────────────────────────────────────
def _container_add_pal(wsd: dict, container_id: str, instance_id: str, player_uid: str = "") -> Optional[int]:
    """Append a slot for ``instance_id`` to the container's Slots[]; return index.

    Writes a properly-shaped slot whose ``RawData_0`` carries the pal's
    ``instance_id`` and ``player_uid`` — the slot's instance_id is the join key
    the game uses to find the pal, so omitting it would orphan the pal.
    """
    target = str(container_id).strip().lower()
    for centry in world_service._map_entries(wsd, "CharacterContainerSaveData"):
        key = world_service._g(centry, "key") or {}
        cid = str(world_service._g(key, "ID") or "").lower()
        if cid != target:
            continue
        value = world_service._g(centry, "value") or {}
        slots = world_service._k(value, "Slots")
        if not isinstance(slots, list):
            slots = []
            _k_set(value, "Slots", slots)
        # Find a free SlotIndex.
        used = {_extract_slot_index(s) for s in slots}
        idx = 0
        while idx in used:
            idx += 1
        slots.append({
            "RawData_0": {
                "player_uid": player_uid or "00000000-0000-0000-0000-000000000000",
                "instance_id": str(instance_id),
                "permission_tribe_id": 0,
                "trailing_bytes": [0, 0, 0, 0],
            },
            "SlotIndex_0": idx,
            "CustomVersionData_0": {"Byte": [0]},
        })
        return idx
    return None


def _container_remove_pal(wsd: dict, container_id: str, instance_id: str) -> None:
    target = str(container_id).strip().lower()
    pal = str(instance_id).strip().lower()
    for centry in world_service._map_entries(wsd, "CharacterContainerSaveData"):
        key = world_service._g(centry, "key") or {}
        if str(world_service._g(key, "ID") or "").lower() != target:
            continue
        value = world_service._g(centry, "value") or {}
        slots = world_service._k(value, "Slots")
        if not isinstance(slots, list):
            return
        for s in list(slots):
            if _extract_slot_instance_id(s).lower() == pal:
                slots.remove(s)
        return


def _extract_slot_instance_id(slot: Any) -> str:
    """Read the instance_id from a container slot's RawData.

    Verified shape (ref/sav/Level.sav): ``RawData_0`` decodes to a flat dict
    ``{"player_uid": "<guid>", "instance_id": "<guid>",
       "permission_tribe_id": <int>, "trailing_bytes": [...]}``.
    The slot's instance_id is the authoritative join key back to
    CharacterSaveParameterMap — if this drifts from the pal's SlotId, the pal
    is orphaned in-game.
    """
    if not isinstance(slot, dict):
        return ""
    raw = world_service._k(slot, "RawData")
    if isinstance(raw, dict):
        iid = world_service._k(raw, "instance_id")
        if iid:
            return str(iid)
    return ""


def _extract_slot_player_uid(slot: Any) -> str:
    """Read the player_uid from a container slot's RawData (for new slots)."""
    if not isinstance(slot, dict):
        return "00000000-0000-0000-0000-000000000000"
    raw = world_service._k(slot, "RawData")
    if isinstance(raw, dict):
        uid = world_service._k(raw, "player_uid")
        if uid:
            return str(uid)
    return "00000000-0000-0000-0000-000000000000"


def _extract_slot_index(slot: Any) -> int:
    if not isinstance(slot, dict):
        return -1
    return world_service._int_field(slot, "SlotIndex", -1)


# ── Validation ───────────────────────────────────────────────────────────────
def _validate_passives(skills: list[str], slot_cap: Optional[int]) -> list[str]:
    """Dedupe + cap passive list. Validates IDs against the catalog unless cheat."""
    catalog = _passive_catalog_set()
    cleaned: list[str] = []
    seen: set[str] = set()
    for s in skills:
        sid = str(s).strip()
        if not sid or sid in seen:
            continue
        if catalog and sid.lower() not in catalog:
            # In strict mode we'd reject; PSP writes verbatim, so we keep the
            # value but it may not render in the UI. (Cheat-mode callers can
            # pass unknown IDs.)
            pass
        seen.add(sid)
        cleaned.append(sid)
    if slot_cap is not None and len(cleaned) > slot_cap:
        cleaned = cleaned[:slot_cap]
    return cleaned


def _validate_actives(skills: list[str], slot_cap: Optional[int]) -> list[str]:
    """Normalize active waza to EPalWazaID:: form, dedupe, cap."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for s in skills:
        sid = str(s).strip()
        if not sid:
            continue
        if not sid.startswith("EPalWazaID::"):
            sid = f"EPalWazaID::{sid}"
        if sid in seen:
            continue
        seen.add(sid)
        cleaned.append(sid)
    if slot_cap is not None and len(cleaned) > slot_cap:
        cleaned = cleaned[:slot_cap]
    return cleaned


# ── Static data helpers ──────────────────────────────────────────────────────
def _char_data(character_id: str) -> Optional[dict]:
    """Look up ``characters.json`` pal data by asset id, case-insensitively.

    Tries the given id as-is first (so boss pals resolve to the boss variant's
    higher scaling), then falls back to the boss-prefix-stripped base form.
    ``characters.json`` uses mixed-case asset ids (``Boss_Anubis``) while saves
    use all-caps (``BOSS_Anubis``); case-insensitive match reconciles that.
    """
    if not character_id:
        return None
    try:
        data = data_service.load_game_data("characters")
    except KeyError:
        return None
    if not isinstance(data, dict):
        return None
    cid_lower = character_id.lower()
    base_lower = _strip_boss_prefix(character_id).lower()
    # First pass: exact (case-insensitive) match — picks the boss variant when
    # the caller passed a boss CharacterID.
    for pal in data.get("pals", []):
        if str(pal.get("asset", "")).lower() == cid_lower:
            return pal
    # Second pass: base-form match (boss-prefix-stripped).
    for pal in data.get("pals", []):
        if str(pal.get("asset", "")).lower() == base_lower:
            return pal
    return None


def _has_boss_variant(character_id: str) -> bool:
    """True if a BOSS_<cid> entry exists in characters.json."""
    base = _strip_boss_prefix(character_id)
    try:
        data = data_service.load_game_data("characters")
    except KeyError:
        return False
    boss_id = f"BOSS_{base}".lower()
    for pal in data.get("pals", []) if isinstance(data, dict) else []:
        if str(pal.get("asset", "")).lower() == boss_id:
            return True
    return False


def _strip_boss_prefix(character_id: str) -> str:
    s = str(character_id or "")
    for prefix in ("BOSS_", "B_O_S_S_", "PREDATOR_", "GYM_"):
        if s.upper().startswith(prefix):
            return s[len(prefix):]
    return s


def _exp_for_level(level: int) -> int:
    """Total EXP needed to BE at ``level`` (from pal_exp_table.json)."""
    try:
        table = data_service.load_game_data("pal_exp_table")
        entry = table.get(str(level)) or table.get(str(min(level, max(int(k) for k in table))))
        return int((entry or {}).get("PalTotalEXP", 0))
    except (KeyError, ValueError):
        return 0


def _active_skill_catalog() -> list[str]:
    try:
        skills = data_service.load_game_data("skills")
        return [s.get("asset") for s in skills.get("skills", []) if s.get("asset")]
    except KeyError:
        return []


def _passive_catalog_set() -> set[str]:
    try:
        skills = data_service.load_game_data("skills")
        return {str(s.get("asset", "")).lower() for s in skills.get("passives", [])}
    except KeyError:
        return set()


def _gender_str(sp: dict) -> str:
    gv = str(world_service._k(sp, "Gender") or "")
    if "Female" in gv:
        return "Female"
    if "Male" in gv:
        return "Male"
    return "Unknown"


def _read_float(sp: dict, name: str, default: float = 0.0) -> float:
    v = world_service._k(sp, name)
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default
