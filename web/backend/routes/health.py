from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter

from web.backend.schemas import HealthResponse
from web.backend.state import save_state

router = APIRouter()

# Read versions from the project's source of truth (src/common.py)
_COMMON_PY = Path(__file__).resolve().parent.parent.parent.parent / "src" / "common.py"
_APP_VERSION = "?"
_GAME_VERSION = "?"
try:
    _src = _COMMON_PY.read_text()
    _m = re.search(r'^APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', _src, re.M)
    if _m:
        _APP_VERSION = _m.group(1)
    _m = re.search(r'^GAME_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', _src, re.M)
    if _m:
        _GAME_VERSION = _m.group(1)
except Exception:
    pass


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="0.1.0",
        app_version=_APP_VERSION,
        game_version=_GAME_VERSION,
        save_loaded=save_state.is_loaded(),
    )
