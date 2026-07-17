"""In-memory save state.

Holds the decoded Level.sav dict (in the Rust uesave JSON shape —
``{header, schemas, root, extra}``) plus the decoded per-player ``.sav``
dicts for the lifetime of the process. Level.sav is the single source of
truth for world state; ``player_savs`` holds the per-player SaveData dicts.
Read-only viewers query them, mutations edit in place, and
``save_service.encode_bytes`` / ``player_service._write_player_sav``
re-serialize them back to ``.sav``.

Single-user / local model: one save loaded at a time. A ``threading.RLock``
guards the heavy decode/encode paths since FastAPI serves requests on a
threadpool.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoadedSave:
    filename: str
    save_dir: str
    players_dir: str
    save_type: int          # detected from magic bytes; reproduced on encode
    class_name: str         # derived from root.save_game_type (informational)
    file_size: int
    loaded_at: float
    level_dict: dict[str, Any] = field(default_factory=dict)
    # Pre-computed at load time. Keys are cleaned UIDs (lowercase, no hyphens).
    player_pal_counts: dict[str, int] = field(default_factory=dict)
    player_levels: dict[str, int] = field(default_factory=dict)
    # Fallback positions from LastJumpedLocation in CharacterSaveParameterMap.
    # Used when Players/*.sav files aren't available (drag-drop upload).
    player_positions: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    # Decoded per-player .sav dicts, keyed by cleaned UID (lowercase, no hyphens).
    # Populated eagerly at load by walking Players/ through the Rust decode_sav
    # bridge. Every byte still goes through the Rust uesave parser — this cache
    # only holds the decoded dict so per-UID reads (tech points, relics, viewing
    # cage) don't re-decode on every request. ``player_save_types`` remembers the
    # per-file save_type (49=PlM/Oodle) so encode reproduces the right compression.
    player_savs: dict[str, dict[str, Any]] = field(default_factory=dict)
    player_save_types: dict[str, int] = field(default_factory=dict)


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
            self._save = save

    def clear(self) -> None:
        with self._lock:
            self._save = None


save_state = SaveState()
