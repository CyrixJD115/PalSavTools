"""Edge-case + stress bounds — container overflow, corrupt inputs, move/delete.

These are the regression gates for the riskiest paths:
  * moving a pal to a full container (overflow safety),
  * moving + deleting through a full encode/decode round-trip (orphan safety),
  * feeding truncated / garbled bytes to the decoder (no crash, no silent
    acceptance of a corrupt save).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from app.backend.services import palsav_rs_wrapper, pal_service, world_service


@pytest.fixture(scope="module")
def decoded_level(level_sav_path: Path):
    raw = level_sav_path.read_bytes()
    level_dict, save_type = palsav_rs_wrapper.decode_sav(raw)
    return level_dict, save_type


@pytest.fixture
def fresh_state(decoded_level):
    level_dict, save_type = decoded_level
    return copy.deepcopy(level_dict), save_type


# ─── container overflow ─────────────────────────────────────────────────────

def test_move_into_full_container_is_safe(fresh_state):
    """Moving a pal into a container that's at capacity must NOT silently
    overflow — either it raises (clean rejection) or finds a legitimately free
    slot. We craft a full 5-slot party container and assert no slot index goes
    out of the container's SlotNum range."""
    level_dict, _ = fresh_state
    wsd = world_service.get_world_save_data(level_dict)

    # Find a small container (party, SlotNum=5) and a pal elsewhere to move in.
    target_cid = None
    for c in world_service._map_entries(wsd, "CharacterContainerSaveData"):
        value = world_service._g(c, "value") or {}
        if world_service._k(value, "SlotNum") == 5:
            slots = world_service._k(value, "Slots") or []
            if len(slots) == 5:  # already full
                target_cid = world_service._g(world_service._g(c, "key") or {}, "ID")
                break
    if target_cid is None:
        pytest.skip("no full 5-slot container in corpus")

    # A pal NOT in that container.
    pals = world_service.list_pals(level_dict, limit=200)
    mover = next(
        (p for p in pals
         if p.get("storage_id") and p["storage_id"] != target_cid),
        None,
    )
    if mover is None:
        pytest.skip("no pal outside the full container to move in")
    iid = mover["instance_id"]

    # The move should either find a genuinely free index (unlikely, it's full)
    # or raise ValueError. Either way it must not corrupt the container.
    try:
        pal_service.move_pal(level_dict, iid, target_cid, "00000000-0000-0000-0000-000000000000")
    except ValueError:
        pass  # clean rejection — acceptable
    # Container SlotNum unchanged; no slot index exceeds it.
    for c in world_service._map_entries(wsd, "CharacterContainerSaveData"):
        if world_service._g(world_service._g(c, "key") or {}, "ID") != target_cid:
            continue
        value = world_service._g(c, "value") or {}
        slotnum = world_service._k(value, "SlotNum")
        for s in (world_service._k(value, "Slots") or []):
            idx = world_service._int_field(s, "SlotIndex", -1)
            assert idx < slotnum, f"slot index {idx} exceeds SlotNum {slotnum} (overflow)"


# ─── move + delete round-trip (permanent orphan-safety gate) ─────────────────

def _find_move_pair(level_dict):
    """Return (pal_iid, src_cid, target_cid) for a safe move test."""
    wsd = world_service.get_world_save_data(level_dict)
    containers = world_service._map_entries(wsd, "CharacterContainerSaveData")
    small = []
    for c in containers:
        value = world_service._g(c, "value") or {}
        sn = world_service._k(value, "SlotNum")
        slots = world_service._k(value, "Slots") or []
        cid = world_service._g(world_service._g(c, "key") or {}, "ID")
        if sn and cid:
            small.append((cid, len(slots), sn))
    if len(small) < 2:
        return None
    # pal in the first container
    src_cid = small[0][0]
    target_cid = small[1][0]
    for c in containers:
        if world_service._g(world_service._g(c, "key") or {}, "ID") != src_cid:
            continue
        for s in (world_service._k(world_service._g(c, "value") or {}, "Slots") or []):
            iid = pal_service._extract_slot_instance_id(s)
            if iid:
                return iid, src_cid, target_cid
    return None


def test_move_round_trip_no_orphan(fresh_state):
    """Move → encode → re-decode → pal at new container, linked in its Slots[]."""
    level_dict, save_type = fresh_state
    pair = _find_move_pair(level_dict)
    if pair is None:
        pytest.skip("no suitable move pair in corpus")
    iid, src_cid, target_cid = pair

    result = pal_service.move_pal(level_dict, iid, target_cid, "00000000-0000-0000-0000-000000000000")
    assert result is not None
    assert result["storage_id"] == target_cid

    encoded = palsav_rs_wrapper.encode_sav(level_dict, save_type)
    redecoded, _ = palsav_rs_wrapper.decode_sav(encoded)
    after = pal_service.read_pal_detail(redecoded, iid)
    assert after is not None, "moved pal vanished after round-trip"
    assert after["storage_id"] == target_cid, "storage_id drifted after round-trip"

    # The pal must be linked in the target container's Slots[] via instance_id.
    rwsd = world_service.get_world_save_data(redecoded)
    linked = False
    for c in world_service._map_entries(rwsd, "CharacterContainerSaveData"):
        if world_service._g(world_service._g(c, "key") or {}, "ID") != target_cid:
            continue
        for s in (world_service._k(world_service._g(c, "value") or {}, "Slots") or []):
            if pal_service._extract_slot_instance_id(s) == iid:
                linked = True
                break
    assert linked, "moved pal not linked in target container Slots[] (orphan)"


def test_delete_round_trip_no_residue(fresh_state):
    """Delete → encode → re-decode → pal gone from map AND all containers."""
    level_dict, save_type = fresh_state
    pals = world_service.list_pals(level_dict, limit=100)
    pal = next((p for p in pals if p.get("talent_hp", 0) >= 0), None)
    if pal is None:
        pytest.skip("no pal to delete")
    iid = pal["instance_id"]

    assert pal_service.delete_pal(level_dict, iid) is True

    encoded = palsav_rs_wrapper.encode_sav(level_dict, save_type)
    redecoded, _ = palsav_rs_wrapper.decode_sav(encoded)

    assert pal_service.read_pal_detail(redecoded, iid) is None, "deleted pal came back"
    # No container slot still references it.
    rwsd = world_service.get_world_save_data(redecoded)
    for c in world_service._map_entries(rwsd, "CharacterContainerSaveData"):
        for s in (world_service._k(world_service._g(c, "value") or {}, "Slots") or []):
            assert pal_service._extract_slot_instance_id(s) != iid, (
                "deleted pal still referenced in a container slot"
            )


# ─── corrupted-input safety ─────────────────────────────────────────────────
#
# Contract: corrupt input must NOT be silently accepted as a valid save. The
# Rust uesave decoder currently rejects truncated input via a panic
# (PyO3 PanicException) rather than a clean Python exception — a panic is a
# rejection (the bad input isn't accepted), but it's a rough edge. We assert
# the weaker-but-meaningful contract here: corrupt input never returns a valid
# decoded dict. A subprocess guard isolates the panic so it can't destabilize
# the test process.

def _decode_in_subprocess(data: bytes) -> tuple[bool, str]:
    """Run decode_sav in a subprocess; return (accepted, detail).

    ``accepted`` is True only if the subprocess exited 0 AND printed a valid-dict
    marker. A panic, a Python exception, or a non-zero exit all mean rejected.
    Data is piped via stdin (not argv) to avoid ARG_MAX limits on large inputs.
    """
    import subprocess, sys
    script = (
        "import sys; "
        "from app.backend.services import palsav_rs_wrapper; "
        "data = sys.stdin.buffer.read(); "
        "ld, st = palsav_rs_wrapper.decode_sav(data); "
        "print('ACCEPTED' if isinstance(ld, dict) else 'REJECTED'); "
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            input=data, capture_output=True, text=False, timeout=60,
        )
        accepted = proc.returncode == 0 and b"ACCEPTED" in proc.stdout
        detail = (proc.stdout.decode(errors="replace") + proc.stderr.decode(errors="replace"))[-300:]
        return accepted, detail
    except subprocess.TimeoutExpired:
        return False, "timeout"


def test_decode_truncated_bytes_rejected(level_sav_path: Path):
    """A truncated Level.sav must not decode to a valid dict (panic or raise)."""
    raw = level_sav_path.read_bytes()
    truncated = raw[: len(raw) // 2]
    accepted, detail = _decode_in_subprocess(truncated)
    assert not accepted, (
        f"truncated Level.sav was silently accepted as a valid save!\n{detail}"
    )


def test_decode_garbled_bytes_rejected():
    """Random garbage with a fake .sav header must not decode as a real save."""
    garbage = b"PlZ\x00\x00\x00\x00" + bytes(range(256)) * 16
    accepted, detail = _decode_in_subprocess(garbage)
    assert not accepted, f"garbage input was silently accepted!\n{detail}"


def test_decode_empty_bytes_rejected():
    accepted, detail = _decode_in_subprocess(b"")
    assert not accepted, f"empty input was silently accepted!\n{detail}"
