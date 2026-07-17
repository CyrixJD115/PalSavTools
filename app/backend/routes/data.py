from __future__ import annotations

import mimetypes
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.backend import paths
from app.backend.schemas import (
    GameDataResponse, I18nResponse, LanguagesResponse, LanguageInfo,
)
from app.backend.services import data_service

router = APIRouter(prefix="/data")


@router.get("/game-data")
async def list_game_data() -> dict:
    return {"resources": data_service.available_game_data()}


@router.get("/game-data/{name}", response_model=GameDataResponse)
async def get_game_data(name: str) -> GameDataResponse:
    try:
        return GameDataResponse(name=name, data=data_service.load_game_data(name))
    except KeyError:
        raise HTTPException(404, f"Unknown game-data resource: {name}")


@router.get("/i18n/{lang}", response_model=I18nResponse)
async def get_i18n(lang: str) -> I18nResponse:
    try:
        return I18nResponse(lang=lang, keys=data_service.load_i18n(lang))
    except KeyError:
        raise HTTPException(404, f"Unknown language: {lang}")


@router.get("/languages", response_model=LanguagesResponse)
async def get_languages() -> LanguagesResponse:
    current, default, avail = data_service.list_languages()
    return LanguagesResponse(
        current=current, default=default,
        available=[LanguageInfo(**a) for a in avail],
    )


_GAME_DATA_DIR = paths.GAME_DATA_DIR.resolve()

_FALLBACK_NAME = "icons/T_icon_unknown.webp"


@lru_cache(maxsize=1)
def _fallback_path() -> str | None:
    p = _GAME_DATA_DIR / _FALLBACK_NAME
    return str(p) if p.is_file() else None


def _media_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".gif": "image/gif",
    }.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


_cache_forever = {"Cache-Control": "public, max-age=31536000, immutable"}
_cache_short = {"Cache-Control": "public, max-age=300"}


@router.get("/game-data-asset/{path:path}")
async def get_game_data_asset(path: str) -> FileResponse:
    resolved = (_GAME_DATA_DIR / path).resolve()
    try:
        resolved.relative_to(_GAME_DATA_DIR)
    except ValueError:
        raise HTTPException(403, "Path traversal denied")

    if resolved.is_file():
        return FileResponse(
            str(resolved),
            media_type=_media_type(path),
            headers=_cache_forever,
        )

    fallback = _fallback_path()
    if fallback:
        return FileResponse(fallback, media_type="image/webp", headers=_cache_short)

    raise HTTPException(404, f"Asset not found: {path}")
