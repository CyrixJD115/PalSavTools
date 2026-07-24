from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.backend.config import is_valid_storage_mode, settings
from app.backend.schemas import (
    LoadResponse, SaveStateResponse, SaveSummary, WorldCounts,
)
from app.backend.services import save_service, world_service
from app.backend.services.archive_service import BundleError, extract_save_bundle
from app.backend.services.load_progress import prewarm_sections
from app.backend.services.palsav_rs_wrapper import (
    parse_save, handle_to_dict, encode_from_handle,
)
from app.backend.state import LoadedSave, StorageMode, save_state
from app.backend.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/save")

_LEVEL_SUFFIX = "Level.sav"
_ARCHIVE_SUFFIXES = (".zip", ".7z")


class LoadPathRequest(BaseModel):
    path: str
    # ``"memory"`` (default) keeps the existing lazy-Rust-handle model;
    # ``"disk"`` spills the full decoded JSON to a temp file so RAM stays
    # low on huge saves. Mirrors the StorageMode Literal in state.py.
    storage_mode: Literal["memory", "disk"] = "memory"
    # Opt-in: sequentially materialize every section at load (with gc +
    # WS progress) instead of lazily on first access. Off by default.
    prewarm: bool = False


def _normalize_storage_mode(requested: str | None) -> StorageMode:
    """Resolve the effective storage mode.

    Per-request value wins if valid; otherwise fall back to the server
    default (``PST_WEB_STORAGE_MODE`` env var, exposed via settings).
    """
    if requested and is_valid_storage_mode(requested):
        return requested  # type: ignore[return-value]
    if is_valid_storage_mode(settings.storage_mode):
        return settings.storage_mode  # type: ignore[return-value]
    return "memory"


def _make_progress_callback(stage: str):
    """Build a sync progress callback that bridges to the async WS manager.

    ``prewarm_sections`` runs in a threadpool executor, but
    ``WsManager.broadcast`` is async. We bridge via
    ``asyncio.run_coroutine_threadsafe`` against the running loop so the
    frontend sees real staged progress mid-load.
    """
    loop = asyncio.get_event_loop()

    def _cb(current: int, total: int, section: str) -> None:
        if not ws_manager._connections:
            return  # no WS clients — skip the loop bridge
        try:
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast_load_progress(stage, current, total, section),
                loop,
            )
        except Exception:
            logger.debug("progress callback bridge failed", exc_info=True)

    return _cb


async def _run_prewarm(loaded: LoadedSave) -> None:
    """Run the chunked pre-warm in an executor so the WS loop can deliver."""
    cb = _make_progress_callback("prewarm")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, prewarm_sections, loaded, cb)


def _build_loaded(
    handle,
    *,
    filename: str,
    save_dir: str,
    players_dir: str,
    file_size: int,
    player_raw_bytes: dict[str, bytes] | None = None,
    storage_mode: StorageMode = "memory",
) -> LoadedSave:
    """Shared constructor for ``LoadedSave`` across all load paths.

    The handle is held as the source of truth (Rust-side, cheap). Player
    saves are NOT eagerly decoded — they're fetched on demand via
    ``LoadedSave.get_player_sav(uid)``.

    The only pre-computation done at load is the lightweight player summary
    (pal counts, levels, fallback positions) used by the overview and map
    endpoints. That scan needs only ``CharacterSaveParameterMap`` — fetched
    as a single ~30 MB section slice instead of materializing the full
    ~200 MB dict.

    When ``storage_mode == "disk"`` the full decoded JSON is also written
    to a temp file (``LoadedSave.dump_to_disk``) so reads come from a
    durable on-disk copy instead of staying in RAM.
    """
    from app.backend.services.map_service import precompute_player_data_from_section
    from app.backend.services.world_service import detect_guild_tail_shape

    # Slice just CharacterSaveParameterMap (~30 MB) for the precompute pass.
    # Avoids touching the heavy MapObjectSaveData / ItemContainerSaveData /
    # MapObjectSpawnerInStageSaveData sections (~800 MB combined).
    csp_json = handle.section_json("CharacterSaveParameterMap")
    csp_section = Any if csp_json is None else _loads(csp_json)
    pal_counts, levels, positions = precompute_player_data_from_section(csp_section)

    # Detect guild-tail shape from GroupSaveDataMap (one cheap section access
    # at load). Newer saves (PlM1 / V1) use PostUpdate; older saves use PreUpdate.
    import json as _json
    gsm_raw = handle.section_json("GroupSaveDataMap")
    gsm_section = _json.loads(gsm_raw) if gsm_raw is not None else []
    tail_shape = detect_guild_tail_shape({"GroupSaveDataMap_0": gsm_section})

    loaded = LoadedSave(
        filename=filename,
        save_dir=save_dir,
        players_dir=players_dir,
        save_type=handle.save_type,
        class_name=handle.save_game_type,
        file_size=file_size,
        loaded_at=time.time(),
        handle=handle,
        player_pal_counts=pal_counts,
        player_levels=levels,
        player_positions=positions,
        player_raw_bytes=player_raw_bytes or {},
        storage_mode=storage_mode,
        guild_tail_shape=tail_shape,
    )

    # Disk mode: spill the full decoded JSON to a temp file now so the
    # durable copy exists before the route returns. Reads will hit the
    # file instead of re-decoding from the Rust handle.
    if storage_mode == "disk":
        loaded.dump_to_disk()

    return loaded


def _loads(s: str):
    import json
    return json.loads(s)


def _counts_from_handle(handle) -> dict:
    """Compute world counts lazily from sections (no full materialization).

    ``count_world`` walks four sections (GroupSaveDataMap,
    CharacterSaveParameterMap, BaseCampSaveData, ItemContainerSaveData);
    we materialize each as a slice just for the count, then let them go.
    """
    import json
    counts = {"guilds": 0, "players": 0, "bases": 0, "containers": 0, "characters": 0, "pals": 0}

    def _section(name: str):
        sj = handle.section_json(name)
        return json.loads(sj) if sj is not None else []

    guilds_raw = _section("GroupSaveDataMap")
    counts["guilds"] = sum(
        1 for g in guilds_raw
        if world_service._group_type(g) == "EPalGroupType::Guild"
    )
    counts["players"] = sum(
        len(world_service._gplayers(g)) for g in guilds_raw
        if world_service._group_type(g) == "EPalGroupType::Guild"
    )
    del guilds_raw

    chars = _section("CharacterSaveParameterMap")
    counts["characters"] = len(chars)
    counts["pals"] = sum(1 for c in chars if world_service._is_pal_entry(c))
    del chars

    counts["bases"] = len(_section("BaseCampSaveData"))
    counts["containers"] = len(_section("ItemContainerSaveData"))
    return counts


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
        guild_tail_shape=loaded.guild_tail_shape,
    )
    # Use lazy counts — only materialize the four cheap count sections
    # instead of the full ~200 MB level_dict.
    counts = _counts_from_handle(loaded.handle) if not loaded.has_materialized_level_dict \
        else world_service.count_world(loaded.level_dict)
    return SaveStateResponse(loaded=True, summary=summary, counts=WorldCounts(**counts))


@router.post("/load", response_model=LoadResponse)
async def load_from_path(body: LoadPathRequest) -> LoadResponse:
    storage_mode = _normalize_storage_mode(body.storage_mode)
    p = Path(body.path).expanduser()
    if not p.name.endswith(_LEVEL_SUFFIX):
        raise HTTPException(400, f"Path must point to a {_LEVEL_SUFFIX} file")
    if not p.is_file():
        raise HTTPException(404, f"File not found: {p}")
    players = p.parent / "Players"
    if not players.is_dir():
        raise HTTPException(400, "Expected a 'Players' folder next to Level.sav")
    await ws_manager.broadcast_load_progress("parse")
    with save_state.lock:
        try:
            data = p.read_bytes()
            handle = parse_save(data)
        except save_service.SaveDecodeError as exc:
            raise HTTPException(422, str(exc))
        await ws_manager.broadcast_load_progress("precompute")
        loaded = _build_loaded(
            handle,
            filename=p.name, save_dir=str(p.parent),
            players_dir=str(players), file_size=len(data),
            storage_mode=storage_mode,
        )
        if body.prewarm:
            await _run_prewarm(loaded)
        save_state.set(loaded)
    await ws_manager.broadcast_load_progress("done")
    counts = _counts_from_handle(handle)
    return LoadResponse(
        summary=SaveSummary(
            filename=p.name, save_dir=str(p.parent), players_dir=str(players),
            class_name=loaded.class_name, save_type=handle.save_type,
            file_size=len(data), loaded_at=time.time(),
            guild_tail_shape=loaded.guild_tail_shape,
        ),
        counts=WorldCounts(**counts),
    )


@router.post("/upload", response_model=LoadResponse)
async def upload_save(
    file: UploadFile = File(...),
    storage_mode: str = Form("memory"),
    prewarm: bool = Form(False),
) -> LoadResponse:
    """Browser drag-drop upload — **archives only** (``.zip`` / ``.7z``).

    The browser can only send file bytes, never the sibling ``Players/`` folder,
    so a bare ``Level.sav`` upload would silently omit every player save and
    break all player-``.sav`` endpoints. To match the proven PSP UX contract,
    the browser path requires a bundled archive containing the full save
    directory (``Level.sav`` + ``Players/``). Loading a lone ``Level.sav`` is a
    desktop/Tauri concern — use ``POST /save/load`` with the OS path instead.

    ``storage_mode`` (``"memory"`` or ``"disk"``) and ``prewarm`` come in as
    multipart form fields alongside ``file`` so the frontend can pass the
    user's choice from the storage-mode warning modal.
    """
    effective_mode = _normalize_storage_mode(storage_mode)
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

    await ws_manager.broadcast_load_progress("parse")
    with save_state.lock:
        loaded = _load_bundle(data, filename, storage_mode=effective_mode)
        if prewarm:
            await _run_prewarm(loaded)
        save_state.set(loaded)
    await ws_manager.broadcast_load_progress("done")
    counts = _counts_from_handle(loaded.handle)
    return LoadResponse(
        summary=SaveSummary(
            filename=loaded.filename, save_dir=loaded.save_dir,
            players_dir=loaded.players_dir, class_name=loaded.class_name,
            save_type=loaded.save_type, file_size=loaded.file_size,
            loaded_at=loaded.loaded_at,
            guild_tail_shape=loaded.guild_tail_shape,
        ),
        counts=WorldCounts(**counts),
    )


def _load_bundle(
    data: bytes, filename: str, storage_mode: StorageMode = "memory",
) -> LoadedSave:
    """Extract + parse a .zip/.7z save bundle (Level.sav + Players/).

    Extraction stays in memory; the Level.sav is parsed into a Rust handle
    and the bundle's per-player raw bytes are kept so lazy decode can fetch
    any UID on demand (no eager batch decode of every Players/*.sav).
    """
    try:
        bundle = extract_save_bundle(data, filename)
    except BundleError as exc:
        raise HTTPException(400, str(exc))

    try:
        handle = parse_save(bundle.level_bytes)
    except save_service.SaveDecodeError as exc:
        raise HTTPException(422, str(exc))

    return _build_loaded(
        handle,
        filename=filename,
        save_dir=f"(bundle: {filename})",
        players_dir=f"(bundle: {filename})",
        file_size=len(data),
        player_raw_bytes=bundle.player_files,
        storage_mode=storage_mode,
    )


@router.post("/export", response_class=StreamingResponse)
async def export_save() -> StreamingResponse:
    """Export the full save folder as a ZIP archive.

    Includes ``Level.sav``, every ``Players/<uid>.sav`` (plus ``_dps.sav``
    companions), and ``WorldOption.sav`` if present — matching the standard
    Palworld save folder layout. This replaces the old single-file export so
    the download is a drop-in replacement for the on-disk save folder.
    """
    import io
    import zipfile
    from pathlib import Path

    from app.backend.services.player_service import _is_disk_players_dir, _player_sav_path

    loaded = save_state.require()
    with save_state.lock:
        try:
            level_bytes = loaded.encode_bytes()
        except save_service.SaveDecodeError as exc:
            raise HTTPException(500, str(exc))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Level.sav at root.
        zf.writestr("Level.sav", level_bytes)

        # Players/ — iterate known UIDs from the handle's CharacterSaveParameterMap.
        player_paths: dict[str, bytes] = {}
        if _is_disk_players_dir(loaded.players_dir):
            # Path-load flow: read *.sav files directly from disk.
            pdir = Path(loaded.players_dir)
            if pdir.is_dir():
                for f in sorted(pdir.iterdir()):
                    if f.suffix.lower() == ".sav" and f.stem:
                        player_paths[f.stem] = f.read_bytes()
        else:
            # Bundle-upload flow: use the raw bytes kept in memory.
            for uid_clean, raw in (loaded.player_raw_bytes or {}).items():
                player_paths[uid_clean.upper()] = raw

        for stem, raw_bytes in sorted(player_paths.items()):
            zf.writestr(f"Players/{stem}.sav", raw_bytes)

        # WorldOption.sav — present in dedicated-server saves.
        if _is_disk_players_dir(loaded.players_dir):
            wo_path = Path(loaded.save_dir) / "WorldOption.sav"
            if wo_path.is_file():
                zf.writestr("WorldOption.sav", wo_path.read_bytes())

    zip_bytes = buf.getvalue()
    # Use the original filename stem for a meaningful archive name.
    base = Path(loaded.filename).stem
    zip_filename = f"{base}_{int(time.time())}.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "X-Export-Size": str(len(zip_bytes)),
        },
    )


@router.delete("", response_model=SaveStateResponse)
async def unload() -> SaveStateResponse:
    save_state.clear()
    return SaveStateResponse(loaded=False)
