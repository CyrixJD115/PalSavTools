"""Regression tests for the quest ("mission") and relic-ability endpoints.

Exercises the two feature sets ported from PST Python:

1. **Quests** — ``GET/PUT /players/{uid}/quests`` reads/writes the two
   ``*_QuestArray_FullRelease`` arrays on the player ``.sav``. Complete →
   reset must be idempotent and survive a real Rust ``encode_sav`` round-trip.
2. **Abilities** — ``GET/PUT /players/{uid}/abilities`` reads/writes the
   relic ``RelicPossessNumMap`` on the player ``.sav`` and the derived ranks
   in the world ``CharacterSaveParameterMap.GotStatusPointList``. A write must
   keep count, scalar and rank in sync.

Both run against the ``ref/`` corpus and are skipped when it's absent
(same gate as ``test_player_endpoints`` and ``test_palsav_rs_integration``).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not Path("ref/sav/Level.sav").is_file(),
    reason="ref/ corpus not present",
)

_REF_LEVEL = Path("ref/sav/Level.sav").resolve()
_REF_PLAYERS = Path("ref/sav/Players")


def _first_player_uid(client) -> str:
    r = client.get("/api/players")
    assert r.status_code == 200, r.text
    players = r.json()["players"]
    assert players, "no players in roster"
    return players[0]["uid"]


def _load(client) -> None:
    r = client.post("/api/save/load", json={"path": str(_REF_LEVEL)})
    assert r.status_code == 200, r.text


# ---- quests (missions) ------------------------------------------------------

def test_quests_read_returns_catalog():
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    client = TestClient(create_app())
    _load(client)
    uid = _first_player_uid(client)

    r = client.get(f"/api/players/{uid}/quests")
    assert r.status_code == 200, f"quests read {r.status_code}: {r.text}"
    body = r.json()
    assert body["supported"] is True, "player .sav should decode"
    quests = body["quests"]
    assert len(quests) >= 100, f"expected full catalog (~120), got {len(quests)}"
    # Status values are constrained to the derived set.
    assert all(q["status"] in {"completed", "active", "not_started"} for q in quests)
    # Every entry has the QuestDef fields.
    assert all({"id", "type", "name", "status"} <= set(q) for q in quests)

    client.delete("/api/save")


def test_quest_complete_then_reset_roundtrip():
    """Complete a quest, assert it's completed; reset it, assert it's not.

    The mutation persists through a real Rust encode_sav round-trip
    (``_write_player_sav`` re-encodes the player .sav), so this is the
    load-bearing guard against silent uesave schema failures on the
    ``*_QuestArray_FullRelease`` arrays.
    """
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    client = TestClient(create_app())
    _load(client)
    uid = _first_player_uid(client)

    # Pick a Main quest that is currently not completed.
    r = client.get(f"/api/players/{uid}/quests")
    assert r.status_code == 200, r.text
    before = {q["id"]: q["status"] for q in r.json()["quests"]}
    candidate = next(
        (qid for qid, st in before.items()
         if qid.startswith("Main_") and st != "completed"),
        None,
    )
    if candidate is None:
        pytest.skip("no completable Main quest in the ref save")

    # Complete it.
    r = client.put(f"/api/players/{uid}/quests", json={"complete": [candidate]})
    assert r.status_code == 200, f"quests complete {r.status_code}: {r.text}"

    r = client.get(f"/api/players/{uid}/quests")
    after = {q["id"]: q["status"] for q in r.json()["quests"]}
    assert after[candidate] == "completed", (
        f"{candidate} should be completed after PUT complete"
    )

    # Reset it.
    r = client.put(f"/api/players/{uid}/quests", json={"reset": [candidate]})
    assert r.status_code == 200, f"quests reset {r.status_code}: {r.text}"

    r = client.get(f"/api/players/{uid}/quests")
    final = {q["id"]: q["status"] for q in r.json()["quests"]}
    assert final[candidate] != "completed", (
        f"{candidate} should not be completed after PUT reset"
    )

    client.delete("/api/save")


# ---- abilities (Lifmunk Effigies / relic boosts) ----------------------------

def test_abilities_read_returns_all_relic_types():
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    client = TestClient(create_app())
    _load(client)
    uid = _first_player_uid(client)

    r = client.get(f"/api/players/{uid}/abilities")
    assert r.status_code == 200, f"abilities read {r.status_code}: {r.text}"
    body = r.json()
    relics = body["relics"]
    types = {r["type"] for r in relics}
    # All 13 relic types must be present (CapturePower + 12 boosts).
    assert "EPalRelicType::CapturePower" in types
    assert "EPalRelicType::HungerReduction" in types  # the "hunger" boost
    assert "EPalRelicType::MoveSpeed" in types         # the "speed" boost
    assert len(relics) == 13, f"expected 13 relic types, got {len(relics)}"
    # Each entry carries the metadata fields the UI needs.
    for entry in relics:
        assert {"type", "label", "count", "cumulative_max", "max_rank", "rank"} <= set(entry)
        assert 0 <= entry["count"] <= entry["cumulative_max"]
        assert 0 <= entry["rank"] <= entry["max_rank"]

    client.delete("/api/save")


def test_ability_write_keeps_count_scalar_and_rank_in_sync():
    """Setting a CapturePower count must update the derived rank and keep the
    world-side GotStatusPointList in sync — the core correctness invariant.

    On saves whose schema includes ``RelicPossessNumMap`` this verifies the
    full count→scalar→rank write. On older saves without the map schema, the
    write is a graceful no-op (same contract as ``max_all_abilities``) and the
    test asserts that instead — both paths must pass.

    Persists through a real Rust encode_sav round-trip.
    """
    from fastapi.testclient import TestClient
    from app.backend.app import create_app
    from app.backend.services import player_service as ps

    client = TestClient(create_app())
    _load(client)
    uid = _first_player_uid(client)

    CP = "EPalRelicType::CapturePower"

    # Detect whether this save supports per-type relic maps.
    decoded = ps._read_player_sav(str(_REF_PLAYERS.parent), uid)
    supports_map = False
    if decoded is not None:
        pdict = decoded[0]
        sprops = pdict.get("schemas", {}).get("schemas", {})
        supports_map = "SaveData.RecordData.RelicPossessNumMap" in sprops

    r = client.get(f"/api/players/{uid}/abilities")
    assert r.status_code == 200, r.text
    relics = {x["type"]: x for x in r.json()["relics"]}
    cp = relics[CP]
    target_count = min(10, cp["cumulative_max"]) or 10

    r = client.put(
        f"/api/players/{uid}/abilities",
        json={"values": {CP: target_count}},
    )
    assert r.status_code == 200, f"abilities write {r.status_code}: {r.text}"

    r = client.get(f"/api/players/{uid}/abilities")
    assert r.status_code == 200, r.text
    after = {x["type"]: x for x in r.json()["relics"]}[CP]

    relic_data, _ = ps._relic_meta()
    per_rank = relic_data[CP]["per_rank"]
    expected_rank = ps.relic_rank_for_count(per_rank, target_count)

    if supports_map:
        # Full invariant: count propagated, rank derived, world-side row updated.
        assert after["count"] == target_count, (
            f"CapturePower count should be {target_count}, got {after['count']}"
        )
        assert after["rank"] == expected_rank, (
            f"CapturePower rank should be {expected_rank}, got {after['rank']}"
        )
        from app.backend.state import save_state
        level_dict = save_state.require().level_dict
        ranks = ps._world_relic_ranks(uid)
        assert ranks.get(CP) == expected_rank, (
            f"world GotStatusPointList rank for CapturePower should be "
            f"{expected_rank}, got {ranks.get(CP)}"
        )
        # The Japanese capture-rate glyph must be in GotStatusPointList now.
        sp = ps._find_player_sp(level_dict, uid)
        items = sp.get("GotStatusPointList_0", sp.get("GotStatusPointList")) if sp else None
        names = {
            (i.get("StatusName_0") or i.get("StatusName"))
            for i in (items or [])
            if isinstance(i, dict)
        }
        assert ps.RELIC_TO_STATUS[CP] in names, (
            f"GotStatusPointList should contain '{ps.RELIC_TO_STATUS[CP]}'"
        )
    else:
        # Older save without RelicPossessNumMap: write is a graceful no-op.
        # The endpoint must still return 200 (not error), and the count stays 0.
        assert after["count"] == 0, (
            "CapturePower count should remain 0 on a map-less save"
        )

    client.delete("/api/save")
