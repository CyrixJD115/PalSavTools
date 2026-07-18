"""SAV <-> dict round-trip via the palsav-rs (Rust uesave) engine.

This is the sole serialization chokepoint for the WebUI backend. It delegates
to ``app/backend/services/palsav_rs_wrapper`` and returns plain ``dict`` values
in the Rust uesave JSON shape (for ``Level.sav``) or raw bytes (for per-player
``.sav`` files — lazy decoding happens on first access).

The Level.sav dict is the source of truth: callers read it (``world_service``
etc.), mutate it in place (``guild_service`` etc.), then hand it back here for
re-encoding. Player ``.sav`` files follow PSP Rust's lazy-loading philosophy:
raw bytes are stored at load time, decoded on first access.
"""

from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from app.backend.services.palsav_rs_wrapper import (
    PalsavRsError,
    decode_sav as _decode_sav,
    detect_save_type,
    encode_sav as _encode_sav,
)

logger = logging.getLogger(__name__)


class SaveDecodeError(Exception):
    """Raised when a .sav cannot be decompressed/parsed."""


# ---------------------------------------------------------------------------
# Level.sav decode
# ---------------------------------------------------------------------------

def decode_bytes(data: bytes) -> tuple[dict[str, Any], int]:
    """Decode raw SAV bytes into ``(level_dict, save_type)``.

    ``level_dict`` is the full Rust uesave shape (``{header, schemas, root,
    extra}``); ``save_type`` is detected from the magic bytes so the matching
    compression is reproduced on encode.
    """
    try:
        level_dict, save_type = _decode_sav(data)
    except PalsavRsError as exc:
        raise SaveDecodeError(str(exc)) from exc
    logger.info(
        "Decoded save: save_type=%d root.save_game_type=%s",
        save_type, _save_game_type(level_dict),
    )
    return level_dict, save_type


def decode_file(path: str | Path) -> tuple[dict[str, Any], int, int]:
    """Decode a .sav on disk into ``(level_dict, save_type, file_size)``."""
    p = Path(path)
    data = p.read_bytes()
    level_dict, save_type = decode_bytes(data)
    return level_dict, save_type, len(data)


# ---------------------------------------------------------------------------
# Player .sav — raw bytes only (lazy decode via LazyPlayerSavs)
# ---------------------------------------------------------------------------

def decode_player_savs(
    players_dir: str | Path,
) -> tuple[dict[str, bytes], dict[str, int]]:
    """Read every player ``.sav`` from ``Players/`` and return **raw bytes**.

    .. admonition:: Lazy-loading design

       Unlike the old code which batch-decoded every player through the Rust
       engine, this function only **reads** the raw bytes. Decoding is deferred
       until the first access via ``LazyPlayerSavs.get()``. This mirrors PSP
       Rust's ``PlayerFileData::Bytes`` pattern and avoids the cost of
       decoding *N* player files at load time.

    Returns ``(raw_bytes_by_uid, save_types_by_uid)`` keyed by cleaned UID
    (lowercase, no hyphens). ``_dps.sav`` companions are skipped — they are a
    separate data stream handled elsewhere.
    """
    players_path = Path(players_dir)
    raw: dict[str, bytes] = {}
    save_types: dict[str, int] = {}

    if not players_path.is_dir():
        return raw, save_types

    # Collect and read every .sav (skipping _dps).
    for entry in players_path.iterdir():
        if not entry.is_file() or entry.suffix.lower() != ".sav":
            continue
        stem = entry.stem
        if stem.endswith("_dps"):
            continue
        uid_clean = stem.replace("-", "").lower()
        if not uid_clean:
            continue
        try:
            data = entry.read_bytes()
            st = detect_save_type(data)
            raw[uid_clean] = data
            save_types[uid_clean] = st
        except OSError as exc:
            logger.warning("Failed to read player save %s: %s", entry.name, exc)

    logger.info(
        "Read %d player .sav files (raw bytes, not decoded) from %s",
        len(raw), players_path,
    )
    return raw, save_types


def decode_player_savs_from_bytes(
    player_files: dict[str, bytes],
) -> tuple[dict[str, bytes], dict[str, int]]:
    """Pass-through for bundle upload — returns raw bytes as-is.

    The bytes have already been read from the archive; no decoding occurs here.
    The ``LazyPlayerSavs`` will decode on first access.

    Returns ``(raw_bytes_by_uid, save_types_by_uid)`` matching the on-disk
    variant so the rest of the pipeline is identical.
    """
    raw: dict[str, bytes] = {}
    save_types: dict[str, int] = {}

    for uid_clean, data in player_files.items():
        try:
            st = detect_save_type(data)
            raw[uid_clean] = data
            save_types[uid_clean] = st
        except Exception as exc:
            logger.warning("Failed to detect save type for player %s: %s", uid_clean, exc)

    logger.info(
        "Staged %d bundled player .sav files (raw bytes, not decoded)",
        len(raw),
    )
    return raw, save_types


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------

def encode_bytes(level_dict: dict[str, Any], save_type: int) -> bytes:
    """Re-encode a ``level_dict`` back into SAV bytes."""
    try:
        return _encode_sav(level_dict, save_type)
    except PalsavRsError as exc:
        raise SaveDecodeError(str(exc)) from exc


def encode_to_stream(level_dict: dict[str, Any], save_type: int) -> io.BytesIO:
    """Encode and wrap in a seekable stream (for FastAPI StreamingResponse)."""
    return io.BytesIO(encode_bytes(level_dict, save_type))


def encode_from_save_handle(save_handle: Any, save_type: int) -> io.BytesIO:
    """Encode from a Rust ``SaveHandle`` (avoids round-tripping through Python dict).

    When the native module is available, this encodes directly from the Rust
    ``uesave::Save``, skipping the Python dict entirely. This is both faster
    and more memory-efficient.
    """
    try:
        raw = save_handle.encode(save_type)
    except Exception as exc:
        raise SaveDecodeError(str(exc)) from exc
    return io.BytesIO(raw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_game_type(level_dict: dict[str, Any]) -> str:
    """Read ``root.save_game_type`` (e.g. ``/Script/Pal.PalWorldSaveGame``)."""
    try:
        return str(level_dict["root"]["save_game_type"])
    except Exception:
        return ""


def class_name_of(level_dict: dict[str, Any]) -> str:
    """The save's class name, derived from ``root.save_game_type``.

    Replaces the legacy ``gvas.header.save_game_class_name``. Returns the
    short class (e.g. ``Pal.PalWorldSaveGame``) or ``""`` if absent.
    """
    sgt = _save_game_type(level_dict)
    if sgt.startswith("/Script/"):
        return sgt[len("/Script/"):]
    return sgt


def save_type_for_class(class_name: str) -> int:
    """Heuristic save_type from class name (fallback only; normally detected
    from magic bytes at decode time)."""
    cn = class_name or ""
    if "Pal.PalWorldSaveGame" in cn or "Pal.PalLocalWorldSaveGame" in cn:
        return 50  # PLZ — classic world saves
    return 49  # PLM — player saves
