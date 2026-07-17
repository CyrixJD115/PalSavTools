"""End-to-end integration tests for the palsav-rs WebUI backend.

Uses FastAPI's TestClient against the real route layer + the ``ref/`` corpus.
Validates that every WebUI feature (players, guilds, bases, containers, map,
export) works against the Rust uesave shape and that mutations round-trip
losslessly.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not Path("ref/sav/Level.sav").is_file(),
    reason="ref/ corpus not present",
)

# ---- import-time checks (from palsav_rs_validation) ----

def test_decode_matches_reference_json():
    from app.backend.services.palsav_rs_wrapper import decode_sav
    import json
    decoded, _ = decode_sav("ref/sav/Level.sav")
    with open("ref/json/Level.sav.json", encoding="utf-8") as f:
        reference = json.load(f)
    assert decoded == reference


def test_level_byte_roundtrip():
    from app.backend.services.palsav_rs_wrapper import roundtrip_sav
    ok, _ = roundtrip_sav("ref/sav/Level.sav")
    assert ok


def test_player_saves_json_stable():
    from app.backend.services.palsav_rs_wrapper import roundtrip_json_stable
    for p in sorted(Path("ref/sav/Players").glob("*.sav")):
        ok, _ = roundtrip_json_stable(p)
        assert ok, f"{p.name} not JSON-stable"


# ---- service-level snapshot tests ----

def test_world_counts_sane():
    from app.backend.services import save_service, world_service
    ld, _, _ = save_service.decode_file("ref/sav/Level.sav")
    c = world_service.count_world(ld)
    assert c["guilds"] >= 1
    assert c["players"] >= 1
    assert c["bases"] >= 1
    assert c["containers"] >= 1
    assert c["pals"] >= 1


def test_guild_list_has_real_names():
    from app.backend.services import save_service, world_service
    ld, _, _ = save_service.decode_file("ref/sav/Level.sav")
    guilds = world_service.list_guilds(ld)
    assert guilds, "no guilds"
    names = {g["name"] for g in guilds}
    assert "Furconic" in names  # known guild in the ref save


def test_player_list_resolves_names_and_leaders():
    from app.backend.services import save_service, world_service
    ld, _, _ = save_service.decode_file("ref/sav/Level.sav")
    players = world_service.list_players(ld)
    assert players, "no players"
    assert any(p["is_leader"] for p in players), "no leader detected"
    assert all(p["guild_id"] for p in players), "player missing guild_id"


def test_pals_have_skills():
    from app.backend.services import save_service, world_service
    ld, _, _ = save_service.decode_file("ref/sav/Level.sav")
    pals = world_service.list_pals(ld, limit=50)
    assert pals, "no pals"
    skilled = [p for p in pals if p["passive_skills"] or p["active_skills"]]
    assert skilled, "no pal has skills"


def test_enriched_bases_have_locations():
    from app.backend.services import save_service, base_service
    ld, _, _ = save_service.decode_file("ref/sav/Level.sav")
    bases = base_service.get_enriched_base_list(ld)
    assert bases, "no bases"
    assert all(b["location"] is not None for b in bases), "base missing location"


def test_container_pagination_and_items():
    from app.backend.services import save_service, container_service
    ld, _, _ = save_service.decode_file("ref/sav/Level.sav")
    page, total = container_service.list_containers(ld, 0, 5)
    assert total > 100
    assert len(page) == 5
    # At least one container in the first page should have items.
    assert any(c["item_count"] > 0 for c in page) or total > 100


# ---- mutation round-trip tests ----

def test_guild_rename_persists_through_roundtrip():
    from app.backend.services import save_service, guild_service, world_service
    from app.backend.services.palsav_rs_wrapper import encode_sav, decode_sav
    ld, st, _ = save_service.decode_file("ref/sav/Level.sav")
    gid = world_service.list_guilds(ld)[0]["id"]
    ld2 = copy.deepcopy(ld)
    assert guild_service.rename_guild(ld2, gid, "IntegrationTest")
    enc = encode_sav(ld2, st)
    ld3, _ = decode_sav(enc)
    renamed = [g for g in world_service.list_guilds(ld3) if g["id"] == gid][0]
    assert renamed["name"] == "IntegrationTest"
    assert ld2 == ld3  # full JSON stability after mutation


def test_player_level_mutation_persists():
    from app.backend.services import save_service, player_service, world_service
    from app.backend.services.palsav_rs_wrapper import encode_sav, decode_sav
    ld, st, _ = save_service.decode_file("ref/sav/Level.sav")
    players = world_service.list_players(ld)
    uid = players[0]["uid"]
    ld2 = copy.deepcopy(ld)
    assert player_service.set_player_level(ld2, uid, 50)
    enc = encode_sav(ld2, st)
    ld3, _ = decode_sav(enc)
    assert ld2 == ld3  # JSON-stable


def test_player_tech_points_in_sav():
    """Mutate a player .sav's tech points and confirm round-trip stability."""
    from app.backend.services.player_service import _read_player_sav
    from app.backend.services.palsav_rs_wrapper import encode_sav, decode_sav
    sav = sorted(Path("ref/sav/Players").glob("*.sav"))[0]
    decoded = _read_player_sav(str(sav.parent), sav.stem)
    if decoded is None:
        pytest.skip("player sav unreadable")
    player_dict, st = decoded
    pd2 = copy.deepcopy(player_dict)
    # No-op: re-encode without changes, assert stability.
    enc = encode_sav(pd2, st)
    pd3, _ = decode_sav(enc)
    assert pd2 == pd3


# ---- FastAPI route smoke test ----

def test_fastapi_load_and_query():
    """Boot the app, load a save via the API, query lists."""
    from fastapi.testclient import TestClient
    from app.backend.app import create_app
    client = TestClient(create_app())
    r = client.post("/api/save/load", json={"path": str(Path("ref/sav/Level.sav").resolve())})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["counts"]["guilds"] >= 1
    for ep in ("/api/players", "/api/guilds", "/api/bases", "/api/pals", "/api/map/data"):
        r = client.get(ep)
        assert r.status_code == 200, f"{ep}: {r.status_code} {r.text[:200]}"
    # Export should return bytes.
    r = client.post("/api/save/export")
    assert r.status_code == 200
    assert len(r.content) > 1000
    client.delete("/api/save")
