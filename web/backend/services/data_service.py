"""Static game-data and i18n serving.

Reads JSON straight from the main project's ``resources/`` tree. No Qt, no
dynamic imports. The character-name map keys on both the pal ``asset`` id and
its display ``name`` so save CharacterIDs resolve regardless of which form the
game used.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

from web.backend import paths

_LANGUAGE_LABELS = {
    "en_US": "English",
    "zh_CN": "中文",
    "ru_RU": "Русский",
    "fr_FR": "Français",
    "es_ES": "Español",
    "de_DE": "Deutsch",
    "ja_JP": "日本語",
    "ko_KR": "한국어",
}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@functools.lru_cache(maxsize=32)
def load_game_data(name: str) -> Any:
    """Load ``resources/game_data/<name>.json``. Raises KeyError if absent."""
    p = paths.GAME_DATA_DIR / f"{name}.json"
    if not p.is_file():
        raise KeyError(f"Unknown game-data resource: {name}")
    return _read_json(p)


def available_game_data() -> list[str]:
    return paths.game_data_files()


def _flatten(d: Any, prefix: str = "") -> dict[str, str]:
    """Recursively flatten nested dicts into dot-notation string values."""
    out: dict[str, str] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(_flatten(v, key))
            elif isinstance(v, str):
                out[key] = v
    return out


@functools.lru_cache(maxsize=16)
def load_i18n(lang: str) -> dict[str, str]:
    """Load ``resources/i18n/<lang>.json`` as a flat key->string dict."""
    p = paths.I18N_DIR / f"{lang}.json"
    if not p.is_file():
        raise KeyError(f"Unknown language: {lang}")
    return _flatten(_read_json(p))


@functools.lru_cache(maxsize=1)
def i18n_config() -> dict[str, Any]:
    p = paths.I18N_DIR / "config.json"
    if not p.is_file():
        return {}
    return _read_json(p)


@functools.lru_cache(maxsize=1)
def character_name_map() -> dict[str, str]:
    """Map lowercased pal asset/name -> display name."""
    out: dict[str, str] = {}
    try:
        data = load_game_data("characters")
    except KeyError:
        return out
    for pal in data.get("pals", []) if isinstance(data, dict) else []:
        display = pal.get("name")
        if not display:
            continue
        asset = pal.get("asset")
        if asset:
            out[str(asset).lower()] = display
        out[str(display).lower()] = display
    return out


def list_languages() -> tuple[str, str, list[dict]]:
    """Return (current, default, [{code,label},...])."""
    cfg = i18n_config()
    current = str(cfg.get("lang", "en_US"))
    codes = paths.i18n_languages() or ["en_US"]
    avail = [{"code": c, "label": _LANGUAGE_LABELS.get(c, c)} for c in codes]
    return current, "en_US", avail
