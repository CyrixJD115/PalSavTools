"""Pytest config + fixtures for the round-trip validation suite.

Corpus discovery
----------------
The suite auto-crawls ``ref/sav/`` (raw ``.sav`` files: the world ``Level.sav``
plus every per-player save, including ``_dps.sav`` dimensional-storage files).
Each discovered file becomes a parametrized test case, so adding saves to
``ref/sav/`` automatically extends coverage.

Oracles
-------
The SUT (system under test) is ``palsav_rs_wrapper.{decode_sav, encode_sav}``.
Three oracles are used, strongest first:

1. **Byte-exact round-trip** — ``encode(decode(raw)) == raw``. Verified to hold
   for this encoder on the reference corpus (the Rust uesave path is
   deterministic). This is the Zero-Change Pass gate.
2. **Ground-truth JSON** — ``ref/json/Level.sav.json`` is a prior decode of the
   same ``Level.sav``; we compare our fresh decode against it structurally. This
   is the cross-framework parity check (the reference JSON was produced by the
   same Rust decoder family, so drift here means our decode path diverged).
3. **Semantic re-read** — after a mutation, re-decode the encoded output and
   assert the edited fields changed and unedited fields didn't.

Performance note: ``Level.sav`` is ~3.2 MB and decodes in ~3 s; the full
``Level.sav.json`` is 318 MB, so parity comparisons stream rather than load it
whole into the assertion.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REF_SAV_DIR = REF_DIR = REPO_ROOT / "ref" / "sav"
REF_JSON_DIR = REPO_ROOT / "ref" / "json"


def _discover_sav_files() -> list[Path]:
    """Every .sav under ref/sav/ (Level.sav + Players/*.sav + *_dps.sav)."""
    if not REF_SAV_DIR.is_dir():
        return []
    return sorted(p.resolve() for p in REF_SAV_DIR.rglob("*.sav") if p.is_file())


SAV_FILES = _discover_sav_files()


def _sav_id(path: Path) -> str:
    """Readable test-id: path relative to ref/sav/, without the .sav suffix."""
    try:
        rel = path.relative_to(REF_SAV_DIR)
    except ValueError:
        rel = path
    return str(rel).replace(".sav", "").replace("/", "__")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def sav_corpus() -> list[Path]:
    """All discovered .sav files (empty list if ref/sav is absent)."""
    return SAV_FILES


@pytest.fixture(scope="session")
def level_sav_path() -> Path:
    p = REF_SAV_DIR / "Level.sav"
    if not p.is_file():
        pytest.skip("ref/sav/Level.sav not available — round-trip corpus missing")
    return p


@pytest.fixture(scope="session")
def level_ground_truth_json() -> Path:
    """Pre-baked decode of Level.sav (the parity oracle)."""
    p = REF_JSON_DIR / "Level.sav.json"
    if not p.is_file():
        pytest.skip("ref/json/Level.sav.json not available — parity oracle missing")
    return p


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_hex16(data: bytes) -> str:
    return sha256(data)[:16]


# Parametrize the Zero-Change + Re-Read passes over every .sav in the corpus.
def pytest_generate_tests(metafunc):
    if "sav_path" in metafunc.fixturenames:
        if not SAV_FILES:
            metafunc.parametrize("sav_path", [], ids=["no-corpus"])
        else:
            metafunc.parametrize("sav_path", SAV_FILES, ids=[_sav_id(p) for p in SAV_FILES])
