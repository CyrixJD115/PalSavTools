"""SAV <-> dict round-trip via the palsav-rs (Rust uesave) engine.

This is the sole serialization chokepoint for the WebUI backend. It delegates
to ``app/backend/services/palsav_rs_wrapper`` (a subprocess bridge to the
``uesave`` binary) and returns plain ``dict`` values in the Rust uesave JSON shape.

The dict is the source of truth: callers read it (``world_service`` etc.),
mutate it in place (``guild_service`` etc.), then hand it back here for
re-encoding. There is no live object that can drift from the dict.
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



# Decode


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


def decode_player_savs(
    players_dir: str | Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Batch-decode every player ``.sav`` in ``Players/`` via the Rust engine.

    Walks ``players_dir`` for ``<UID>.sav`` files (skipping ``_dps.sav``
    companions, which are a separate stream), decodes each through
    ``decode_sav`` (Rust uesave — PlM/Oodle decompression is transparent),
    and returns two dicts keyed by cleaned UID (lowercase, no hyphens):

    * ``player_savs`` — ``{uid_clean: decoded_dict}``
    * ``player_save_types`` — ``{uid_clean: save_type}``

    Decode failures are logged and skipped (the player remains absent from
    the cache rather than aborting the whole load). Mirrors the proven
    pattern in both reference tools (``palworld-save-pal``'s
    ``extract_summaries`` and the Python tool's ``_count_pals_found``
    ThreadPoolExecutor scan).
    """
    players_path = Path(players_dir)
    player_savs: dict[str, dict[str, Any]] = {}
    player_save_types: dict[str, int] = {}

    if not players_path.is_dir():
        return player_savs, player_save_types

    # Collect candidate files first so the decode work can fan out to threads.
    # Stem is the raw UID (uppercase, no dashes) — normalized to cleaned form.
    candidates: list[tuple[str, Path]] = []
    for entry in players_path.iterdir():
        if not entry.is_file() or entry.suffix.lower() != ".sav":
            continue
        stem = entry.stem
        if stem.endswith("_dps"):  # dedicated player storage — separate stream
            continue
        uid_clean = stem.replace("-", "").lower()
        if not uid_clean:
            continue
        candidates.append((uid_clean, entry))

    if not candidates:
        return player_savs, player_save_types

    def _decode_one(item: tuple[str, Path]) -> tuple[str, dict[str, Any], int] | None:
        uid_clean, path = item
        try:
            data = path.read_bytes()
            decoded, save_type = _decode_sav(data)
            return uid_clean, decoded, save_type
        except (PalsavRsError, OSError) as exc:
            logger.warning("Failed to decode player save %s: %s", path.name, exc)
            return None

    workers = min(32, (len(candidates) or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(_decode_one, candidates):
            if result is None:
                continue
            uid_clean, decoded, save_type = result
            player_savs[uid_clean] = decoded
            player_save_types[uid_clean] = save_type

    logger.info(
        "Decoded %d/%d player .sav files from %s",
        len(player_savs), len(candidates), players_path,
    )
    return player_savs, player_save_types


def decode_player_savs_from_bytes(
    player_files: dict[str, bytes],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Batch-decode player ``.sav`` bytes via the Rust engine (no disk access).

    Sibling of :func:`decode_player_savs` for the in-memory bundle-upload
    path: ``player_files`` is ``{uid_clean: raw_sav_bytes}`` (as produced by
    ``archive_service.extract_save_bundle``). Every byte still goes through
    the Rust ``decode_sav`` engine — this only holds the decoded dicts.

    Returns ``(player_savs, player_save_types)`` keyed by cleaned UID, matching
    the on-disk variant so the rest of the pipeline is identical.
    """
    player_savs: dict[str, dict[str, Any]] = {}
    player_save_types: dict[str, int] = {}

    items = list(player_files.items())
    if not items:
        return player_savs, player_save_types

    def _decode_one(item: tuple[str, bytes]) -> tuple[str, dict[str, Any], int] | None:
        uid_clean, raw = item
        try:
            decoded, save_type = _decode_sav(raw)
            return uid_clean, decoded, save_type
        except PalsavRsError as exc:
            logger.warning("Failed to decode bundled player save %s: %s", uid_clean, exc)
            return None

    workers = min(32, len(items))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(_decode_one, items):
            if result is None:
                continue
            uid_clean, decoded, save_type = result
            player_savs[uid_clean] = decoded
            player_save_types[uid_clean] = save_type

    logger.info(
        "Decoded %d/%d bundled player .sav files", len(player_savs), len(items),
    )
    return player_savs, player_save_types



# Encode


def encode_bytes(level_dict: dict[str, Any], save_type: int) -> bytes:
    """Re-encode a ``level_dict`` back into SAV bytes."""
    try:
        return _encode_sav(level_dict, save_type)
    except PalsavRsError as exc:
        raise SaveDecodeError(str(exc)) from exc


def encode_to_stream(level_dict: dict[str, Any], save_type: int) -> io.BytesIO:
    """Encode and wrap in a seekable stream (for FastAPI StreamingResponse)."""
    return io.BytesIO(encode_bytes(level_dict, save_type))



# Helpers


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
    # root.save_game_type is "/Script/Pal.PalWorldSaveGame" -> "Pal.PalWorldSaveGame"
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
