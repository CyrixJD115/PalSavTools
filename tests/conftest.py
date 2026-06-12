from __future__ import annotations

import pytest
from pathlib import Path

from tests.test_registry import PROJECT_ROOT, get_all_parent_dirs, find_source_for_test


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    try:
        import palsav
        if getattr(palsav, '__file__', None) is not None:
            pass
    except Exception:
        pass

    for parent_dir in get_all_parent_dirs():
        parent_str = str(parent_dir)
        import sys
        if parent_str not in sys.path:
            sys.path.insert(0, parent_str)


@pytest.fixture
def project_dir() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def src_dir() -> Path:
    return PROJECT_ROOT / 'src'


@pytest.fixture
def sample_sav_path(tmp_path) -> Path:
    path = tmp_path / "test_level.sav"
    path.write_bytes(b"")
    return path


@pytest.fixture
def mock_gvas_data() -> dict:
    return {
        "save_game_data": {
            "value": {
                "GroupSaveDataMap": {"value": []},
                "CharacterSaveParameterMap": {"value": []},
                "MapObjectSaveData": {"value": []},
            }
        }
    }


@pytest.fixture
def resolve_source_target(request):
    test_stem = Path(request.fspath).stem
    return find_source_for_test(test_stem)


class Helpers:
    @staticmethod
    def make_sav_path(tmp_path: Path, name: str = "Level.sav") -> Path:
        p = tmp_path / name
        p.write_bytes(b"")
        return p


@pytest.fixture
def helpers() -> Helpers:
    return Helpers()
