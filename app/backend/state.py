"""In-memory save state with lazy section materialization.

Holds a parsed Palworld save behind a ``SaveHandle`` (Rust-side, cheap) and
exposes per-section Python dicts on demand. The handle is the source of
truth; ``level_dict`` is a cached materialization of the full save used for
backward compatibility with services that walk/mutate the entire tree.

Memory model
------------
A 2 MB world save expands to ~1M Python objects (~200 MB) when fully
materialized as a dict. Most endpoints touch only one or two
``worldSaveData`` sections (guilds, players, containers, …), so we keep the
parsed save in Rust memory and materialize Python dicts lazily:

* ``get_section("GroupSaveDataMap")`` — returns (and caches) just that
  section as a Python dict. ~1 MB for guilds vs ~200 MB for the full tree.
* ``level_dict`` — full materialization, cached after first access. Existing
  services that mutate the tree in place keep working unchanged.
* ``export()`` — if ``level_dict`` was never touched, encodes straight from
  the Rust handle (zero Python allocation). If it was materialized and
  mutated, encodes from the dict.

Single-user / local model: one save loaded at a time. A ``threading.RLock``
guards decode/encode/mutation paths since FastAPI serves requests on a
threadpool.

Player saves
------------
Per-player ``.sav`` files are NOT eagerly decoded at load. They are cached
on first access via ``get_player_sav(uid)`` and re-encoded individually on
mutation (``player_service._write_player_sav`` writes back to ``Players/``).
The raw bundle bytes (upload path) or ``Players/`` directory (path-load)
are kept so lazy decode can fetch any UID on demand.

Storage modes
-------------
``storage_mode`` controls where the decoded save lives after the cheap
Rust parse:

* ``"memory"`` (default) — the existing model. The Rust ``SaveHandle`` is
  the source of truth; Python dicts are materialized lazily per section
  (LRU-bounded) or fully on first mutation.
* ``"disk"`` — the full decoded JSON is written to a temp file
  (``disk_cache_path``) once at load. ``level_dict`` reads the file back
  on first access (one big allocation), after which it behaves exactly
  like the memory path. This trades disk space for a durable copy that
  survives process memory pressure and speeds up re-scan / re-write of
  huge saves. The temp file is unlinked on ``clear()``.

Disk mode covers the read side only in v1; mutations still materialize
the full dict in RAM (documented v2 follow-up).
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from app.backend.services.palsav_rs_wrapper import _PySaveHandle  # noqa: F401

logger = logging.getLogger(__name__)

StorageMode = Literal["memory", "disk"]

# LRU cap for materialized sections. Each section stays resident once
# touched; we evict oldest beyond this to bound memory. 8 covers the
# common working set (guilds + players + bases + containers + map + pals
# + game-time + work) without re-decoding on every request.
_SECTION_LRU_MAX = 8

# LRU cap for decoded player saves. On a server with 50+ players we don't
# want every player dict resident — decode-on-demand and evict.
_PLAYER_LRU_MAX = 16

# Prefix for disk-cache temp files. Used to sweep orphans on startup.
_DISK_CACHE_PREFIX = "pst-disk-cache-"


# -- disk-cache helpers -------------------------------------------------------


def _load_disk_json(path: Path) -> dict[str, Any]:
    """Read a JSON file with orjson (fast, shared import)."""
    import orjson
    return orjson.loads(path.read_bytes())


def _dumps_json(obj: dict) -> bytes:
    """Serialize a dict to JSON bytes with orjson."""
    import orjson
    return orjson.dumps(obj)


def _sweep_stale_cache_files() -> None:
    """Delete orphaned ``pst-disk-cache-*`` temp files from prior crashes.

    Runs once per process (on first ``LoadedSave.cleanup()`` or
    ``SaveState.clear()``). Best-effort: some files may be locked by
    another process, we skip those.
    """
    if getattr(_sweep_stale_cache_files, "_done", False):
        return
    _sweep_stale_cache_files._done = True  # type: ignore[attr-defined]
    try:
        tmp_dir = Path(tempfile.gettempdir())
        removed = 0
        for f in tmp_dir.glob(f"{_DISK_CACHE_PREFIX}*.json"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        if removed:
            logger.debug("Cleaned %d stale disk-cache file(s) from %s",
                         removed, tmp_dir)
    except Exception:
        logger.debug("Stale-cache sweep failed", exc_info=True)


@dataclass
class LoadedSave:
    filename: str
    save_dir: str
    players_dir: str
    save_type: int          # detected from magic bytes; reproduced on encode
    class_name: str         # derived from root.save_game_type (informational)
    file_size: int
    loaded_at: float
    guild_tail_shape: str = "PostUpdate"  # "PreUpdate" (legacy) or "PostUpdate" (latest)
    # Storage mode for this load. "memory" (default) keeps the existing
    # lazy-Rust-handle model; "disk" spills the full decoded JSON to a temp
    # file so RAM stays low on huge saves. Set by the load route from the
    # request's ``storage_mode`` param.
    storage_mode: StorageMode = "memory"
    # Temp file path holding the full decoded JSON when ``storage_mode ==
    # "disk"``. None in memory mode. Created at load, unlinked on clear.
    disk_cache_path: Path | None = None
    # Source of truth: the Rust-side parsed save handle (cheap to hold).
    # When the native module is absent this is a ``_PySaveHandle`` shim
    # wrapping the full decoded dict (no memory advantage, same API).
    handle: Any = None
    # Lazily-materialized full dict. None until first access via
    # :meth:`level_dict`; once materialized, services mutate it in place.
    _level_dict: dict[str, Any] | None = field(default=None, repr=False)
    # Section LRU cache: bare name → Python dict slice.
    _sections: OrderedDict = field(default_factory=OrderedDict, repr=False)
    # Pre-computed at load time from the Level.sav handle. Keys are cleaned
    # UIDs (lowercase, no hyphens).
    player_pal_counts: dict[str, int] = field(default_factory=dict)
    player_levels: dict[str, int] = field(default_factory=dict)
    # Fallback positions from LastJumpedLocation in CharacterSaveParameterMap.
    player_positions: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    # Decoded per-player .sav dicts, keyed by cleaned UID. Lazy: populated
    # on demand by :meth:`get_player_sav`.
    player_savs: OrderedDict = field(default_factory=OrderedDict)
    player_save_types: dict[str, int] = field(default_factory=dict)
    # Raw player .sav bytes for the bundle-upload path. Empty for the
    # path-load flow (which reads from ``players_dir`` on demand).
    # Keyed by cleaned UID.
    player_raw_bytes: dict[str, bytes] = field(default_factory=dict, repr=False)

    # -- world save access -------------------------------------------------

    @property
    def level_dict(self) -> dict[str, Any]:
        """Full decoded save dict (Rust uesave shape).

        Lazily materialized from the handle (or the disk cache) on first
        access and cached. Services that mutate the save in place do so on
        this dict; the cached sections (see :meth:`get_section`) are
        invalidated when a full dict is requested, since the dict becomes
        the source of truth.

        For endpoints that only need one section, prefer
        :meth:`get_section` — a guild lookup is ~1 MB versus ~200 MB for
        the full materialization on a 2 MB world save.

        In ``storage_mode == "disk"`` the dict is read back from
        :attr:`disk_cache_path` (written once at load) instead of decoded
        from the Rust handle. Same downstream shape, but the file is the
        durable copy.
        """
        if self._level_dict is None:
            if self.storage_mode == "disk" and self.disk_cache_path is not None:
                self._level_dict = self._load_dict_from_disk()
            else:
                from app.backend.services.palsav_rs_wrapper import handle_to_dict
                self._level_dict = handle_to_dict(self.handle)
            # The full dict subsumes any cached sections — drop them so
            # mutations are visible through both access paths.
            self._sections.clear()
            logger.debug("Materialized full level_dict (storage_mode=%s)",
                         self.storage_mode)
        return self._level_dict

    @property
    def has_materialized_level_dict(self) -> bool:
        """True if the full dict has been built (and possibly mutated)."""
        return self._level_dict is not None

    def get_section(self, name: str) -> dict[str, Any] | None:
        """Return one ``worldSaveData`` section as a Python dict.

        ``name`` is the bare property name (no ``_<idx>`` suffix), e.g.
        ``"GroupSaveDataMap"`` or ``"CharacterSaveParameterMap"``. The
        slice is cached in an LRU; repeated calls return the same dict
        object so mutations are preserved.

        Returns ``None`` if the section doesn't exist.

        If :attr:`level_dict` has already been materialized (e.g. by a
        legacy service doing a full walk), the section is sliced from the
        cached dict instead of re-decoding from the handle.
        """
        # Once the full dict is live, it's the source of truth — slice it.
        if self._level_dict is not None:
            return self._slice_from_full_dict(name)

        if name in self._sections:
            self._sections.move_to_end(name)
            return self._sections[name]

        from app.backend.services.palsav_rs_wrapper import section_to_dict
        value = section_to_dict(self.handle, name)
        if value is None:
            return None
        self._sections[name] = value
        self._sections.move_to_end(name)
        while len(self._sections) > _SECTION_LRU_MAX:
            evicted, _ = self._sections.popitem(last=False)
            logger.debug("Evicted section %r from LRU", evicted)
        return value

    def _slice_from_full_dict(self, name: str) -> dict[str, Any] | None:
        try:
            wsd = self._level_dict["root"]["properties"]["worldSaveData_0"]
        except KeyError:
            return None
        for key, value in wsd.items():
            bare = key.rsplit("_", 1)[0] if "_" in key else key
            if bare == name:
                return value
        return None

    def build_mini_wsd(self, *names: str) -> dict[str, Any]:
        """Build a minimal ``worldSaveData``-like dict containing only the
        requested sections.

        Services that take a ``wsd`` parameter (``list_guilds_from_wsd``,
        ``list_players_from_wsd``, …) work fine when handed a dict that
        contains just the keys they actually read. This lets list endpoints
        avoid materializing the full ~200 MB ``level_dict`` — they pull
        only the cheap sections they need (GroupSaveDataMap is ~1 MB,
        BaseCampSaveData is ~2 MB, GameTimeSaveData is tiny) and leave
        the heavy MapObjectSaveData / ItemContainerSaveData / pal maps
        untouched.

        ``mini_wsd = loaded.build_mini_wsd("GroupSaveDataMap", "GameTimeSaveData")``
        """
        # Late import to keep state.py importable without the wrapper.
        from app.backend.services.palsav_rs_wrapper import section_to_dict

        if self._level_dict is not None:
            # Full dict already live — slice from it.
            try:
                full_wsd = self._level_dict["root"]["properties"]["worldSaveData_0"]
            except KeyError:
                return {}
            mini: dict[str, Any] = {}
            for key, value in full_wsd.items():
                bare = key.rsplit("_", 1)[0] if "_" in key else key
                if bare in names:
                    mini[key] = value
            return mini

        # Pull each section lazily (cached via the LRU).
        mini = {}
        for name in names:
            section = self.get_section(name)
            if section is None:
                continue
            mini[f"{name}_0"] = section
        return mini

    def section_names(self) -> list[str]:
        """Bare section names under ``worldSaveData``."""
        if self._level_dict is not None:
            try:
                wsd = self._level_dict["root"]["properties"]["worldSaveData_0"]
            except KeyError:
                return []
            return [k.rsplit("_", 1)[0] if "_" in k else k for k in wsd]
        return list(self.handle.sections())

    # -- player save access -----------------------------------------------

    def get_player_sav(self, uid_clean: str) -> tuple[dict[str, Any], int] | None:
        """Return ``(decoded_player_dict, save_type)`` for one UID.

        Lazy: decodes on first request per UID and caches in an LRU. Reads
        from the bundle bytes (upload flow) or the ``Players/`` directory
        (path-load flow) via :func:`player_service._read_player_sav`.

        Returns ``None`` if the player save can't be found/decoded.
        """
        if uid_clean in self.player_savs:
            self.player_savs.move_to_end(uid_clean)
            st = self.player_save_types.get(uid_clean, 49)
            return self.player_savs[uid_clean], st

        from app.backend.services import player_service
        result = player_service._read_player_sav(
            self.players_dir, uid_clean, _raw_bytes=self.player_raw_bytes.get(uid_clean),
        )
        if result is None:
            return None
        player_dict, save_type = result
        # _read_player_sav back-fills the cache for us; just enforce LRU cap.
        while len(self.player_savs) > _PLAYER_LRU_MAX:
            evicted_uid, _ = self.player_savs.popitem(last=False)
            self.player_save_types.pop(evicted_uid, None)
            logger.debug("Evicted player save %r from LRU", evicted_uid)
        return player_dict, save_type

    # -- export -----------------------------------------------------------

    def encode_bytes(self) -> bytes:
        """Serialize the current state back into ``.sav`` bytes.

        If the full dict was materialized (and possibly mutated), encodes
        from it. Otherwise encodes straight from the Rust handle — zero
        Python dict allocation, fastest path for load-then-export workflows.

        In disk mode, if the dict hasn't been touched we still encode from
        the handle (the cache file is just a read-side durability copy; the
        Rust ``Save`` is always the encode source of truth until a mutation
        materializes the dict).
        """
        from app.backend.services.palsav_rs_wrapper import (
            encode_from_handle, encode_sav,
        )
        if self._level_dict is not None:
            return encode_sav(self._level_dict, self.save_type)
        return encode_from_handle(self.handle)

    # -- disk-backed mode --------------------------------------------------

    def dump_to_disk(self) -> Path | None:
        """Write the full decoded JSON to a temp file (disk mode only).

        Called once at load when ``storage_mode == "disk"``. Uses the Rust
        handle's ``to_json()`` *directly* — the JSON string is written to
        disk **without** materializing the full Python dict tree (which
        would bloat to ~1M+ Python objects for a 2 MB world save, and
        proportionally more for 80 MB+ saves).

        For the subprocess fallback (``_PySaveHandle``) this still goes
        through the full dict, but the native PyO3 path avoids the object
        tree entirely.

        Returns the temp file path, or ``None`` on failure. Idempotent.
        """
        if self.storage_mode != "disk":
            return None
        if self.disk_cache_path is not None and self.disk_cache_path.exists():
            return self.disk_cache_path

        # Get the JSON as a single Python *string* from the Rust handle.
        # We DO NOT call handle_to_dict() — that would parse the string
        # into ~1M+ Python objects (the bloat we're trying to avoid).
        # to_json() returns a string, which is one allocation.
        try:
            json_str = self.handle.to_json()
        except Exception:
            logger.exception("disk-mode dump failed: handle.to_json()")
            return None

        # Write the string directly to a temp file.
        fd, path_str = tempfile.mkstemp(
            prefix="pst-disk-cache-", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json_str)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(path_str)
            except OSError:
                pass
            logger.exception("disk-mode dump failed to write temp file")
            return None

        self.disk_cache_path = Path(path_str)
        logger.info("Disk cache written: %s (%d bytes, storage_mode=%s)",
                    self.disk_cache_path, len(json_str.encode("utf-8")),
                    self.storage_mode)
        return self.disk_cache_path

    def _load_dict_from_disk(self) -> dict[str, Any]:
        """Read the full dict back from :attr:`disk_cache_path`.

        Only called on the first access to :attr:`level_dict` in disk mode
        (typically triggered by a mutation). The file is parsed with
        ``orjson`` — still a large allocation, but at least it's deferred
        until the user actually edits, not paid at load.

        If the file is missing (deleted externally), falls back to decoding
        from the Rust handle (which does materialize the Python tree but
        still avoids re-parsing the SAV).
        """
        if self.disk_cache_path is not None and self.disk_cache_path.exists():
            return _load_disk_json(self.disk_cache_path)
        # File vanished — fall back to the handle (materializes Python tree).
        from app.backend.services.palsav_rs_wrapper import handle_to_dict
        return handle_to_dict(self.handle)

    def _sync_level_dict_to_disk(self) -> None:
        """Write the current :attr:`_level_dict` back to the disk cache.

        Called on ``SaveState.clear()`` to ensure the mutated dict is
        preserved in the temp file before cleanup. No-op if the dict
        hasn't been materialized or there's no disk cache path.
        """
        if self._level_dict is None or self.disk_cache_path is None:
            return
        try:
            payload = _dumps_json(self._level_dict)
            self.disk_cache_path.write_bytes(payload)
            logger.debug("Synced level_dict back to %s (%d bytes)",
                         self.disk_cache_path, len(payload))
        except Exception:
            logger.exception("Failed to sync level_dict back to disk cache")

    def cleanup(self) -> None:
        """Release disk-backed resources (temp cache file). Called on clear.

        Also sweeps any orphaned ``pst-disk-cache-*`` files in the OS temp
        dir that may have been left behind by a crashed session.
        """
        if self.disk_cache_path is not None:
            try:
                self.disk_cache_path.unlink()
                logger.debug("Removed disk cache: %s", self.disk_cache_path)
            except OSError:
                pass
            self.disk_cache_path = None

        # One-shot orphan sweep: clean temp files from prior crashes.
        # We sweep optimistically (best-effort) since some may be locked.
        _sweep_stale_cache_files()


class SaveState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._save: LoadedSave | None = None

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def is_loaded(self) -> bool:
        return self._save is not None

    def get(self) -> LoadedSave | None:
        return self._save

    def require(self) -> LoadedSave:
        if self._save is None:
            raise RuntimeError("No save loaded")
        return self._save

    def set(self, save: LoadedSave) -> None:
        with self._lock:
            # Replacing a loaded save: sync its level_dict back to the disk
            # cache (if any) and release resources before swapping.
            if self._save is not None and self._save is not save:
                self._save._sync_level_dict_to_disk()
                self._save.cleanup()
            self._save = save

    def clear(self) -> None:
        with self._lock:
            if self._save is not None:
                # Write back any mutated level_dict to the disk cache before
                # cleanup, so the temp file isn't orphaned with stale data.
                self._save._sync_level_dict_to_disk()
                self._save.cleanup()
            self._save = None


save_state = SaveState()
