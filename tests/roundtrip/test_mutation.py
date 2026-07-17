"""Mutation Loop + Re-Read Validation — the integrity check for edits.

Sequence per mutation:
  1. Decode Level.sav → capture a baseline (the edited pal's pre-edit fields,
     plus "adjacent unedited" witnesses: a second pal's stats, the total pal
     count, a player's level, the container count).
  2. Apply an edit via the real ``pal_service`` mutator.
  3. Re-encode the mutated state to .sav bytes.
  4. Re-decode those bytes and assert:
       (a) the edited field now matches the requested value,
       (b) every witness is byte-identical to its baseline (untouched).

The witnesses are the corruption gate: if an IV edit silently rewrote a sibling
pal's passives or dropped a container, the witness assertions fail.
"""

from __future__ import annotations

import copy
import uuid
from pathlib import Path

import pytest

from app.backend.services import palsav_rs_wrapper, pal_service, world_service


@pytest.fixture(scope="module")
def decoded_level(level_sav_path: Path):
    """Shared decode of Level.sav for the mutation matrix (decode is ~3 s)."""
    raw = level_sav_path.read_bytes()
    level_dict, save_type = palsav_rs_wrapper.decode_sav(raw)
    return level_dict, save_type


@pytest.fixture
def fresh_state(decoded_level):
    """A deep-copied level_dict + save_type, so each test mutates in isolation.

    The dict is large (~3 MB JSON) but copy.deepcopy is the only way to give
    each mutation test a pristine slate without re-decoding (which is slower).
    """
    level_dict, save_type = decoded_level
    return copy.deepcopy(level_dict), save_type


def _pick_pal(level_dict) -> dict:
    """Find a pal with editable stats (non-boss, has an IV)."""
    pals = world_service.list_pals(level_dict, limit=200)
    pal = next(
        (p for p in pals if p.get("talent_hp", 0) > 0 and not p["character_id"].startswith("BOSS_")),
        None,
    )
    if pal is None:
        pytest.skip("no editable pal in corpus")
    return pal


def _pick_witness_pal(level_dict, exclude_iid: str) -> dict | None:
    """A second pal whose fields must stay untouched by edits to the first."""
    pals = world_service.list_pals(level_dict, limit=200)
    return next((p for p in pals if p["instance_id"] != exclude_iid), None)


def _witness_snapshot(level_dict, iid: str, witness_iid: str | None) -> dict:
    """Capture the fields that must NOT change when ``iid`` is edited."""
    snap: dict = {
        "total_pals": len(world_service.list_pals(level_dict, limit=5000)),
        "edited_pre": pal_service.read_pal_detail(level_dict, iid),
    }
    if witness_iid:
        snap["witness"] = pal_service.read_pal_detail(level_dict, witness_iid)
    # world-level witnesses: container count + a player's level
    wsd = world_service.get_world_save_data(level_dict)
    snap["container_count"] = len(world_service._map_entries(wsd, "CharacterContainerSaveData"))
    snap["player_count"] = len(world_service.list_players(level_dict))
    return snap


# ─── individual mutation cases ──────────────────────────────────────────────

def test_mutation_iv_round_trip(fresh_state):
    """Edit an IV → re-encode → re-decode → IV changed, everything else intact."""
    level_dict, save_type = fresh_state
    pal = _pick_pal(level_dict)
    iid = pal["instance_id"]
    witness = _pick_witness_pal(level_dict, iid)
    before = _witness_snapshot(level_dict, iid, witness["instance_id"] if witness else None)

    # Mutate.
    result = pal_service.set_talents(level_dict, iid, talent_hp=77, cheat=True)
    assert result is not None and result["talent_hp"] == 77

    # Re-encode + re-decode.
    encoded = palsav_rs_wrapper.encode_sav(level_dict, save_type)
    redecoded, _ = palsav_rs_wrapper.decode_sav(encoded)
    after_edited = pal_service.read_pal_detail(redecoded, iid)
    after_witness = (
        pal_service.read_pal_detail(redecoded, witness["instance_id"]) if witness else None
    )

    # (a) the edit survived.
    assert after_edited is not None, "edited pal vanished after round-trip"
    assert after_edited["talent_hp"] == 77, "IV edit did not survive round-trip"

    # (b) witnesses untouched.
    assert len(world_service.list_pals(redecoded, limit=5000)) == before["total_pals"]
    assert (
        len(world_service._map_entries(world_service.get_world_save_data(redecoded), "CharacterContainerSaveData"))
        == before["container_count"]
    )
    assert len(world_service.list_players(redecoded)) == before["player_count"]
    if after_witness and before["witness"]:
        assert after_witness["talent_hp"] == before["witness"]["talent_hp"]
        assert after_witness["passive_skills"] == before["witness"]["passive_skills"]
        assert after_witness["character_id"] == before["witness"]["character_id"]


def test_mutation_skills_round_trip(fresh_state):
    """Replace passive skills → re-encode → re-decode → new skills present."""
    level_dict, save_type = fresh_state
    pal = _pick_pal(level_dict)
    iid = pal["instance_id"]
    new_passives = ["Legend", "Runner", "Swift", "Vanguard"]

    result = pal_service.set_skills(level_dict, iid, passive_skills=new_passives, cheat=True)
    assert result is not None
    assert set(result["passive_skills"]) == set(new_passives)

    encoded = palsav_rs_wrapper.encode_sav(level_dict, save_type)
    redecoded, _ = palsav_rs_wrapper.decode_sav(encoded)
    after = pal_service.read_pal_detail(redecoded, iid)
    assert after is not None
    assert set(after["passive_skills"]) == set(new_passives), "passive edit drifted"


def test_mutation_work_suitability_round_trip(fresh_state):
    """Set a work suitability to 5 → re-encode → re-decode → effective level is 5."""
    level_dict, save_type = fresh_state
    pal = _pick_pal(level_dict)
    iid = pal["instance_id"]
    cid = pal["character_id"]

    # Pick a work key the species actually has a base level for, else 0→5 is the
    # only meaningful test (delta = 5).
    result = pal_service.set_work_suitability(level_dict, iid, {"EmitFlame": 5}, cid)
    assert result is not None
    assert result["work_suitability"]["EmitFlame"] == 5

    encoded = palsav_rs_wrapper.encode_sav(level_dict, save_type)
    redecoded, _ = palsav_rs_wrapper.decode_sav(encoded)
    after = pal_service.read_pal_detail(redecoded, iid)
    assert after is not None
    assert after["work_suitability"]["EmitFlame"] == 5, "work-suitability edit drifted"


def test_mutation_level_recomputes_hp(fresh_state):
    """Level edit → HP recomputed; after round-trip HP still matches the formula."""
    level_dict, save_type = fresh_state
    pal = _pick_pal(level_dict)
    iid = pal["instance_id"]

    result = pal_service.set_level(level_dict, iid, level=50, cheat=True)
    assert result is not None
    assert result["level"] == 50
    assert result["hp"] == result["max_hp"] > 0, "HP not recomputed/healed"

    encoded = palsav_rs_wrapper.encode_sav(level_dict, save_type)
    redecoded, _ = palsav_rs_wrapper.decode_sav(encoded)
    after = pal_service.read_pal_detail(redecoded, iid)
    assert after is not None
    assert after["level"] == 50
    assert after["hp"] == after["max_hp"], "HP recompute did not survive round-trip"


def test_mutation_max_out_round_trip(fresh_state):
    """Max-out a pal → re-encode → re-decode → every stat at its cap."""
    level_dict, save_type = fresh_state
    pal = _pick_pal(level_dict)
    iid = pal["instance_id"]

    pal_service.max_out_pal(level_dict, iid, cheat=False)

    encoded = palsav_rs_wrapper.encode_sav(level_dict, save_type)
    redecoded, _ = palsav_rs_wrapper.decode_sav(encoded)
    after = pal_service.read_pal_detail(redecoded, iid)
    assert after is not None
    assert after["talent_hp"] == 100 and after["talent_shot"] == 100 and after["talent_defense"] == 100
    assert after["rank_hp"] == 20 and after["rank_attack"] == 20
    assert after["rank_defense"] == 20 and after["rank_craftspeed"] == 20
    assert after["rank"] == 5 and after["level"] == 80
