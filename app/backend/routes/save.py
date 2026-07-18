from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.backend.schemas import (
    LoadResponse, SaveStateResponse, SaveSummary, WorldCounts,
)
from app.backend.services import save_service, world_service
from app.backend.services.archive_service import BundleError, extract_save_bundle
from app.backend.state import LoadedSave, save_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/save")

_LEVEL_SUFFIX = "Level.sav"
_ARCHIVE_SUFFIXES = (".zip", ".7z")


class LoadPathRequest(BaseModel):
    path: str


def _build_loaded(
    level_dict: dict[str, Any],
    save_type: int,
    *,
    filename: str,
    save_dir: str,
    players_dir: str,
    file_size: int,
    player_raw: dict[str, bytes] | None = None,
    player_save_types: dict[str, int] | None = None,
    raw_sav_bytes: bytes | None = None,
) -> LoadedSave:
    """Shared constructor for ``LoadedSave`` across all load paths.

    Centralizes ``precompute_player_data``, position-index building, and
    summary-field wiring so the path-load, single-file upload, and bundle-
    upload flows stay consistent.

    When ``raw_sav_bytes`` is provided, a ``SaveHandle`` is created to keep
    the save in Rust memory (selective dynamic loading — PSP Rust philosophy).
    The Python ``level_dict`` is then lazily extracted from the handle on first
    access.
    """
    from app.backend.state import LazyPlayerSavs
    from app.backend.services.map_service import precompute_player_data

    pal_counts, levels, positions = precompute_player_data(level_dict)

    # Lazy player savs.
    lazy_savs = LazyPlayerSavs()
    if player_raw:
        st_map = player_save_types or {}
        for uid, raw_bytes in player_raw.items():
            lazy_savs.put_raw(uid, raw_bytes, st_map.get(uid, 49))

    # Position indexes.
    wsd = world_service.get_world_save_data(level_dict)
    char_entries = world_service._map_entries(wsd, "CharacterSaveParameterMap")
    ic_entries = world_service._map_entries(wsd, "ItemContainerSaveData")
    cc_entries = world_service._map_entries(wsd, "CharacterContainerSaveData")
    g_entries = world_service._map_entries(wsd, "GroupSaveDataMap")

    # Create Rust SaveHandle if raw bytes available (native module only).
    save_handle = None
    if raw_sav_bytes is not None:
        try:
            from app.backend.services.palsav_rs_wrapper import _native
            if hasattr(_native, "SaveHandle"):
                save_handle = _native.SaveHandle(raw_sav_bytes)
        except Exception:
            pass  # Fall back to pure-Python dict path

    return LoadedSave(
        filename=filename,
        save_dir=save_dir,
        players_dir=players_dir,
        save_type=save_type,
        class_name=save_service.class_name_of(level_dict),
        file_size=file_size,
        loaded_at=time.time(),
        save_handle=save_handle,
        _level_dict=level_dict,  # Initially populated from decode; invalidate_caches clears it
        player_pal_counts=pal_counts,
        player_levels=levels,
        player_positions=positions,
        player_savs=lazy_savs,
        player_save_types=player_save_types or {},
        character_index=world_service.build_index(char_entries, "InstanceId"),
        item_container_index=world_service.build_index(ic_entries, "ID"),
        char_container_index=world_service.build_index(cc_entries, "ID"),
        group_index=world_service.build_index(g_entries, None),
    )


def _summarize(level_dict: dict[str, Any], save_type: int, path: Path) -> LoadedSave:
    # Read every Players/*.sav as raw bytes (no decode). The LazyPlayerSavs
    # will decode on first access — mirrors PSP Rust's PlayerFileData::Bytes
    # pattern, avoiding the cost of decoding N players at load time.
    players_dir = path.parent / "Players"
    player_raw, player_save_types = save_service.decode_player_savs(players_dir)
    # Read the raw Level.sav bytes for the Rust SaveHandle.
    raw_sav_bytes = path.read_bytes()
    return _build_loaded(
        level_dict, save_type,
        filename=path.name, save_dir=str(path.parent),
        players_dir=str(players_dir), file_size=path.stat().st_size,
        player_raw=player_raw, player_save_types=player_save_types,
        raw_sav_bytes=raw_sav_bytes,
    )


@router.get("/state", response_model=SaveStateResponse)
async def get_state() -> SaveStateResponse:
    loaded = save_state.get()
    if loaded is None:
        return SaveStateResponse(loaded=False)
    summary = SaveSummary(
        filename=loaded.filename,
        save_dir=loaded.save_dir,
        players_dir=loaded.players_dir,
        class_name=loaded.class_name,
        save_type=loaded.save_type,
        file_size=loaded.file_size,
        loaded_at=loaded.loaded_at,
    )
    return SaveStateResponse(
        loaded=True, summary=summary,
        counts=WorldCounts(**world_service.count_world(loaded.level_dict)),
    )


@router.post("/load", response_model=LoadResponse)
async def load_from_path(body: LoadPathRequest) -> LoadResponse:
    p = Path(body.path).expanduser()
    if not p.name.endswith(_LEVEL_SUFFIX):
        raise HTTPException(400, f"Path must point to a {_LEVEL_SUFFIX} file")
    if not p.is_file():
        raise HTTPException(404, f"File not found: {p}")
    players = p.parent / "Players"
    if not players.is_dir():
        raise HTTPException(400, "Expected a 'Players' folder next to Level.sav")
    with save_state.lock:
        try:
            level_dict, save_type, size = save_service.decode_file(p)
        except save_service.SaveDecodeError as exc:
            raise HTTPException(422, str(exc))
        save_state.set(_summarize(level_dict, save_type, p))
    return LoadResponse(
        summary=SaveSummary(
            filename=p.name, save_dir=str(p.parent), players_dir=str(players),
            class_name=save_service.class_name_of(level_dict), save_type=save_type,
            file_size=size, loaded_at=time.time(),
        ),
        counts=WorldCounts(**world_service.count_world(level_dict)),
    )


@router.post("/upload", response_model=LoadResponse)
async def upload_save(file: UploadFile = File(...)) -> LoadResponse:
    """Browser drag-drop upload — **archives only** (``.zip`` / ``.7z``).

    The browser can only send file bytes, never the sibling ``Players/`` folder,
    so a bare ``Level.sav`` upload would silently omit every player save and
    break all player-``.sav`` endpoints. To match the proven PSP UX contract,
    the browser path requires a bundled archive containing the full save
    directory (``Level.sav`` + ``Players/``). Loading a lone ``Level.sav`` is a
    desktop/Tauri concern — use ``POST /save/load`` with the OS path instead.
    """
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty upload")
    filename = file.filename or ""
    name_lower = filename.lower()

    if name_lower.endswith(_LEVEL_SUFFIX.lower()):
        raise HTTPException(
            400,
            "Browser upload requires a .zip or .7z bundle containing Level.sav "
            "and its Players/ folder (a lone Level.sav can't carry player "
            "saves). Drop the bundle here, or use the desktop app / Load Save "
            "by path to open Level.sav directly.",
        )
    if not name_lower.endswith(_ARCHIVE_SUFFIXES):
        raise HTTPException(
            400,
            "Upload a .zip or .7z bundle containing Level.sav and its Players/ "
            "folder.",
        )

    with save_state.lock:
        loaded = _load_bundle(data, filename)
        save_state.set(loaded)
    return LoadResponse(
        summary=SaveSummary(
            filename=loaded.filename, save_dir=loaded.save_dir,
            players_dir=loaded.players_dir, class_name=loaded.class_name,
            save_type=loaded.save_type, file_size=loaded.file_size,
            loaded_at=loaded.loaded_at,
        ),
        counts=WorldCounts(**world_service.count_world(loaded.level_dict)),
    )


def _load_bundle(data: bytes, filename: str) -> LoadedSave:
    """Extract + decode a .zip/.7z save bundle (Level.sav + Players/).

    Extraction stays in memory; every player .sav byte still goes through the
    Rust ``decode_sav`` engine. Mirrors palworld-save-pal's ``load_zip_file``.
    """
    try:
        bundle = extract_save_bundle(data, filename)
    except BundleError as exc:
        raise HTTPException(400, str(exc))

    try:
        level_dict, save_type = save_service.decode_bytes(bundle.level_bytes)
    except save_service.SaveDecodeError as exc:
        raise HTTPException(422, str(exc))

    player_raw, player_save_types = save_service.decode_player_savs_from_bytes(
        bundle.player_files
    )
    return _build_loaded(
        level_dict, save_type,
        filename=filename,
        save_dir=f"(bundle: {filename})",
        players_dir=f"(bundle: {filename})",
        file_size=len(data),
        player_raw=player_raw, player_save_types=player_save_types,
        raw_sav_bytes=bundle.level_bytes,
    )


@router.post("/export", response_class=StreamingResponse)
async def export_save() -> StreamingResponse:
    loaded = save_state.require()
    with save_state.lock:
        try:
            # Use SaveHandle encode when available (avoids Python dict round-trip).
            if loaded.save_handle is not None:
                stream = save_service.encode_from_save_handle(
                    loaded.save_handle, loaded.save_type,
                )
            else:
                stream = save_service.encode_to_stream(
                    loaded.level_dict, loaded.save_type,
                )
        except save_service.SaveDecodeError as exc:
            raise HTTPException(500, str(exc))
    size = len(stream.getvalue())
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{loaded.filename}"',
            "X-Export-Size": str(size),
        },
    )


@router.delete("", response_model=SaveStateResponse)
async def unload() -> SaveStateResponse:
    save_state.clear()
    return SaveStateResponse(loaded=False)
