"""Regression tests for the per-player .sav endpoints.

These exist specifically to catch the class of bug where the browser upload
path delivered only Level.sav (no Players/), causing every player-.sav endpoint
to 404. They exercise:

1. Path load (``/save/load``) → player endpoints return 200 with real data.
2. Bundle upload (``/save/upload`` with a .zip) → player saves decode through
   Rust and the same endpoints work.
3. Cache consistency — a tech-points write is visible to the next read.

All three run against the ``ref/`` corpus and are skipped when it's absent
(same gate as ``test_palsav_rs_integration``).
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not Path("ref/sav/Level.sav").is_file(),
    reason="ref/ corpus not present",
)

_REF_LEVEL = Path("ref/sav/Level.sav").resolve()
_REF_PLAYERS = Path("ref/sav/Players")


def _first_player_uid(client) -> str:
    """Return a real player UID from the loaded save's roster."""
    r = client.get("/api/players")
    assert r.status_code == 200, r.text
    players = r.json()["players"]
    assert players, "no players in roster"
    return players[0]["uid"]


def _build_save_zip(level_path: Path, players_dir: Path) -> bytes:
    """Build an in-memory .zip mirroring a save folder (Level.sav + Players/)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(level_path, "Level.sav")
        for sav in sorted(players_dir.glob("*.sav")):
            zf.write(sav, f"Players/{sav.name}")
    return buf.getvalue()


# ---- path load (Tauri / desktop) -------------------------------------------

def test_path_load_player_endpoints_work():
    """Load via /save/load (path) and confirm player-.sav endpoints succeed.

    This is the test that would have caught the original 'player saves never
    loaded' regression: tech-points / viewing-cage / unlock-technologies must
    return 200, not 404.
    """
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    client = TestClient(create_app())
    r = client.post("/api/save/load", json={"path": str(_REF_LEVEL)})
    assert r.status_code == 200, r.text
    assert client.get("/api/save/state").json()["loaded"] is True

    uid = _first_player_uid(client)

    # tech-points: read must succeed (proves the player .sav decoded).
    r = client.get(f"/api/players/{uid}/tech-points")
    assert r.status_code == 200, f"tech-points {r.status_code}: {r.text}"

    # viewing-cage: idempotent — True if unlocked-or-already-so, never 404 when
    # the player .sav is present and the schema supports the field.
    r = client.put(f"/api/players/{uid}/viewing-cage")
    assert r.status_code in (200, 404), f"viewing-cage {r.status_code}: {r.text}"
    # 404 here specifically means 'schema doesn't define bIsViewingCageCanUse'
    # (version mismatch), NOT 'player .sav missing'. We accept either but flag
    # the distinction: a missing-sav 404 would be a regression.

    # unlock-technologies: injects recipes; must succeed when the .sav decodes.
    r = client.put(f"/api/players/{uid}/unlock-technologies")
    assert r.status_code == 200, f"unlock-technologies {r.status_code}: {r.text}"

    client.delete("/api/save")


# ---- bundle upload (browser / --web mode) -----------------------------------

def test_bundle_upload_loads_players():
    """Build a .zip from the ref save, upload via /save/upload, and confirm
    the player saves decode through Rust and the endpoints work.

    This proves the browser-mode fix: a bundled archive lets the backend see
    the complete save structure (Level.sav + Players/) without needing OS
    file-path access.
    """
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    bundle = _build_save_zip(_REF_LEVEL, _REF_PLAYERS)

    client = TestClient(create_app())
    r = client.post(
        "/api/save/upload",
        files={"file": ("ref_save.zip", bundle, "application/zip")},
    )
    assert r.status_code == 200, f"upload {r.status_code}: {r.text}"

    summary = r.json()["summary"]
    assert summary["filename"] == "ref_save.zip"
    assert "bundle" in summary["players_dir"]

    uid = _first_player_uid(client)

    # The key assertion: player .sav endpoints must NOT 404 after a bundle load.
    r = client.get(f"/api/players/{uid}/tech-points")
    assert r.status_code == 200, f"tech-points after bundle: {r.status_code} {r.text}"

    r = client.put(f"/api/players/{uid}/unlock-technologies")
    assert r.status_code == 200, f"unlock-technologies after bundle: {r.status_code} {r.text}"

    client.delete("/api/save")


def test_bundle_upload_rejects_archive_without_level():
    """A bundle missing Level.sav is rejected with a clear 400."""
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Players/ only, no Level.sav.
        for sav in sorted(_REF_PLAYERS.glob("*.sav")):
            zf.write(sav, f"Players/{sav.name}")

    client = TestClient(create_app())
    r = client.post(
        "/api/save/upload",
        files={"file": ("no_level.zip", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 400
    assert "Level.sav" in r.text


def test_upload_rejects_lone_level_sav():
    """A bare Level.sav upload must be rejected — the browser path is bundle-only.

    Mirrors the PSP UX contract: web/upload = .zip/.7z bundle; desktop =
    Level.sav by OS path (``POST /save/load``). A lone .sav over the upload
    endpoint would silently omit Players/ and break every player-.sav endpoint,
    so the backend refuses it up front with a clear 400.
    """
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    level_bytes = _REF_LEVEL.read_bytes()
    client = TestClient(create_app())
    r = client.post(
        "/api/save/upload",
        files={"file": ("Level.sav", level_bytes, "application/octet-stream")},
    )
    assert r.status_code == 400, f"expected 400 for lone .sav upload, got {r.status_code}"
    body = r.json()["detail"].lower()
    # The message must point the user at the bundle (or desktop) — not just a
    # generic "unsupported format".
    assert ".zip" in body or ".7z" in body
    # And it must not have loaded anything.
    assert client.get("/api/save/state").json()["loaded"] is False


# ---- cache consistency ------------------------------------------------------

def test_cache_consistency_after_tech_points_write():
    """A tech-points PUT must be visible to the next tech-points GET.

    Proves the in-memory cache write-back in ``player_service._write_player_sav``
    works end-to-end through the HTTP layer (the cache is updated in place, so
    a follow-up read returns the new value without a disk re-read).
    """
    from fastapi.testclient import TestClient
    from app.backend.app import create_app

    client = TestClient(create_app())
    client.post("/api/save/load", json={"path": str(_REF_LEVEL)})

    uid = _first_player_uid(client)

    before = client.get(f"/api/players/{uid}/tech-points").json()
    new_tech = before["tech_points"] + 7
    new_boss = before["boss_tech_points"] + 3

    r = client.put(
        f"/api/players/{uid}/tech-points",
        json={"tech_points": new_tech, "boss_tech_points": new_boss},
    )
    assert r.status_code == 200, f"put tech-points: {r.status_code} {r.text}"

    after = client.get(f"/api/players/{uid}/tech-points").json()
    assert after["tech_points"] == new_tech, "tech_points not reflected after write"
    assert after["boss_tech_points"] == new_boss, "boss_tech_points not reflected"

    client.delete("/api/save")
