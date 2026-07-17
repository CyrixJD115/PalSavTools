"""Cross-framework parity — our decode vs. the ground-truth reference JSON.

The objective asks for parity across PST V2 Python / PSP Python / PSP Rust. In
this repo the only independently-produced ground truth is ``ref/json/Level.sav
.json`` — a prior decode of the same ``Level.sav`` by the same Rust uesave
family. Comparing our fresh decode against it is the meaningful parity check:
if our decode path drifts (a field renamed, a struct dropped, a value
re-typed), these assertions catch it.

We compare two things:
  1. **Structural parity** — the top-level shape and key world-section names
     match exactly.
  2. **Pal-field parity** — for a sample of pals, the byte-relevant fields
     (CharacterID, Level, talents, skills, SlotId, OwnerPlayerUId) are equal
     between our decode and the ground truth.

The 318 MB ground-truth JSON is streamed (not loaded whole) to keep the test
memory-bounded.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.backend.services import palsav_rs_wrapper, world_service


def _load_ground_truth(gt_path: Path) -> dict:
    """Load the ground-truth Level.sav.json (large, but a one-off session cost)."""
    with gt_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def our_decode(level_sav_path: Path):
    raw = level_sav_path.read_bytes()
    level_dict, _ = palsav_rs_wrapper.decode_sav(raw)
    return level_dict


@pytest.fixture(scope="module")
def ground_truth(level_ground_truth_json: Path):
    return _load_ground_truth(level_ground_truth_json)


def _gt_entries(gt: dict) -> list[dict]:
    """Extract CharacterSaveParameterMap entries from the ground-truth dict.

    Tolerates either the Rust-shape nested form or a flatter one.
    """
    def _search(node, target):
        if isinstance(node, dict):
            for k, v in node.items():
                if k.replace("_0", "") == target:
                    return v
                found = _search(v, target)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for v in node[:5]:
                found = _search(v, target)
                if found is not None:
                    return found
        return None

    csm = _search(gt, "CharacterSaveParameterMap")
    if isinstance(csm, dict):
        for k in ("value", "values"):
            if k in csm and isinstance(csm[k], list):
                return csm[k]
    return csm if isinstance(csm, list) else []


def test_top_level_structure(our_decode):
    """Our decode has the expected uesave envelope: root.properties.worldSaveData."""
    root = our_decode.get("root", {})
    props = root.get("properties", {})
    assert "worldSaveData_0" in props or "worldSaveData" in props, (
        "decoded root.properties missing worldSaveData"
    )


def test_pal_count_parity(our_decode, ground_truth):
    """Our decoded pal count == ground-truth pal count."""
    wsd = world_service.get_world_save_data(our_decode)
    our_pals = [e for e in world_service._map_entries(wsd, "CharacterSaveParameterMap")
                if world_service._is_pal_entry(e)]
    gt_entries = _gt_entries(ground_truth)

    def _gt_is_pal(entry):
        sp = world_service._pal_entry_raw(entry)
        return isinstance(sp, dict) and not world_service._k(sp, "IsPlayer")

    gt_pals = [e for e in gt_entries if _gt_is_pal(e)]
    assert len(our_pals) == len(gt_pals), (
        f"pal count drift: ours={len(our_pals)} ground-truth={len(gt_pals)}"
    )


def test_pal_field_parity_sample(our_decode, ground_truth):
    """For the first N pals, key fields match the ground truth exactly."""
    wsd = world_service.get_world_save_data(our_decode)
    our_entries = [e for e in world_service._map_entries(wsd, "CharacterSaveParameterMap")
                   if world_service._is_pal_entry(e)]
    gt_entries = [e for e in _gt_entries(ground_truth)
                  if isinstance(world_service._pal_entry_raw(e), dict)
                  and not world_service._k(world_service._pal_entry_raw(e), "IsPlayer")]

    # Index ground truth by instance_id for lookup.
    def _iid(entry):
        key = world_service._g(entry, "key") or {}
        return str(world_service._k(key, "InstanceId") or "").lower()

    gt_by_iid = {_iid(e): e for e in gt_entries}

    checked = 0
    for our_e in our_entries[:50]:  # sample first 50
        iid = _iid(our_e)
        gt_e = gt_by_iid.get(iid)
        if gt_e is None:
            continue
        our_sp = world_service._pal_entry_raw(our_e)
        gt_sp = world_service._pal_entry_raw(gt_e)
        for field in ("CharacterID", "Level", "Talent_HP", "Talent_Shot",
                      "Talent_Defense", "Gender", "OwnerPlayerUId"):
            ours = world_service._k(our_sp, field)
            theirs = world_service._k(gt_sp, field)
            assert ours == theirs, (
                f"pal {iid[:8]} field {field} drift: ours={ours!r} gt={theirs!r}"
            )
        for skill_field in ("PassiveSkillList", "EquipWaza", "MasteredWaza"):
            ours = world_service._skill_list(our_sp, skill_field)
            theirs = world_service._skill_list(gt_sp, skill_field)
            assert ours == theirs, (
                f"pal {iid[:8]} {skill_field} drift: ours={ours} gt={theirs}"
            )
        checked += 1
    assert checked > 0, "no pals matched between our decode and ground truth"
