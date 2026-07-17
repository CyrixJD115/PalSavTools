"""Pytest config + fixtures for the breeding engine tests.

The engine lives under ``src/palworld_aio/breeding/`` but its parent package
(``palworld_aio``) eagerly imports ``main`` which pulls Qt/i18n deps that aren't
available in a headless test environment. So we load the breeding subpackage via
``importlib`` (the same pattern the backend uses for ``map_data_service``) rather
than a normal ``import`` — this exercises the engine in true isolation.

The :func:`breeding` fixture exposes the loaded module; :func:`db` exposes a
``BreedingDB`` built from the real generated data files.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GAME_DATA = _REPO_ROOT / "src" / "_resources" / "game_data"
_PKG_PATH = _REPO_ROOT / "src" / "palworld_aio" / "breeding" / "__init__.py"


@pytest.fixture(scope="session")
def breeding():
    """Load the breeding engine as an isolated module (no parent-package import)."""
    # Use a unique name so repeated sessions don't collide in sys.modules.
    mod_name = "pst_breeding_test"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name, _PKG_PATH, submodule_search_locations=[str(_PKG_PATH.parent)]
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def db(breeding):
    """A ``BreedingDB`` loaded from the real game-data files."""
    # Clear the lru_cache so each test session sees the current files.
    breeding.BreedingDB.load.cache_clear()
    return breeding.BreedingDB.load(_GAME_DATA)
