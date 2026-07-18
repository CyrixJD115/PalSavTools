"""In-memory save state.

Holds the decoded Level.sav dict (in the Rust uesave JSON shape —
``{header, schemas, root, extra}``) plus lazy per-player ``.sav`` storage.
Level.sav is the single source of truth for world state; player ``.sav`` files
are decoded on first access and cached thereafter (PSP Rust lazy-loading
philosophy). ``save_service.encode_bytes`` / ``player_service._write_player_sav``
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


# ---------------------------------------------------------------------------
# Lazy per-player .sav storage (PSP Rust philosophy)
# ---------------------------------------------------------------------------


class LazyPlayerSavs:
    """Lazy-loaded per-player ``.sav`` storage.

    .. admonition:: Why this exists

       PSP Rust stores ``PlayerFileData::Bytes`` (raw bytes) at load time and
       only parses the GVAS tree on the first read (``ensure_player_loaded``).
       The decoded tree is then cached for subsequent accesses. This class
       mirrors that pattern — keeping the raw bytes avoids the cost of decoding
       *N* player files at load (a 100-player server can save 200+ MiB of
       Python dict allocations).

    Design
    ------
    * ``put_raw`` — store the raw ``.sav`` bytes at load time. No decode occurs.
    * ``get`` — return ``(decoded_dict, save_type)``, decoding from raw bytes on
      the first call. The decoded dict is then cached.
    * ``set`` — store an already-decoded dict (used after mutation/encode so the
      next read sees the latest state without re-reading).
    * ``discard`` — remove a player entirely (used by the delete-player path).

    Thread safety: the caller holds ``save_state.lock`` across all operations
    (the existing RLock guard on the route handlers).
    """

    def __init__(self) -> None:
        self._raw: dict[str, bytes] = {}
        self._save_types: dict[str, int] = {}
        self._decoded: dict[str, dict[str, Any]] = {}

    # ---- public API ---------------------------------------------------------

    def put_raw(self, uid_clean: str, raw_bytes: bytes, save_type: int) -> None:
        """Store raw ``.sav`` bytes for lazy decoding."""
        self._raw[uid_clean] = raw_bytes
        self._save_types[uid_clean] = save_type
        # If a stale decoded copy existed, evict it.
        self._decoded.pop(uid_clean, None)

    def get(self, uid_clean: str) -> tuple[dict[str, Any], int] | None:
        """Return ``(decoded_dict, save_type)``, lazy-decoding if needed."""
        # 1. Already decoded — fast path.
        cached = self._decoded.get(uid_clean)
        if cached is not None:
            st = self._save_types.get(uid_clean, 49)
            return cached, st

        # 2. Have raw bytes — decode on first access.
        raw = self._raw.get(uid_clean)
        if raw is not None:
            from app.backend.services.palsav_rs_wrapper import decode_sav as _ds
            decoded, save_type = _ds(raw)
            self._decoded[uid_clean] = decoded
            self._save_types[uid_clean] = save_type
            # Free the raw bytes now that we have the decoded dict.
            del self._raw[uid_clean]
            return decoded, save_type

        # 3. Not present at all.
        return None

    def set(self, uid_clean: str, player_dict: dict[str, Any], save_type: int) -> None:
        """Store a decoded player dict (post-mutation)."""
        self._decoded[uid_clean] = player_dict
        self._save_types[uid_clean] = save_type
        self._raw.pop(uid_clean, None)

    def discard(self, uid_clean: str) -> None:
        """Remove a player entirely from both raw and decoded storage."""
        self._raw.pop(uid_clean, None)
        self._decoded.pop(uid_clean, None)
        self._save_types.pop(uid_clean, None)

    def __contains__(self, uid_clean: str) -> bool:
        return uid_clean in self._raw or uid_clean in self._decoded

    def __len__(self) -> int:
        return len(self._raw) + len(self._decoded)

    @property
    def uids(self) -> set[str]:
        return set(self._raw.keys()) | set(self._decoded.keys())

    @property
    def save_types(self) -> dict[str, int]:
        """All known save types (from both raw and decoded storage)."""
        return dict(self._save_types)

    def keys(self) -> set[str]:
        return self.uids


# ---------------------------------------------------------------------------
# WorldCaches — lazy performance caches (PSP Rust WorldCaches pattern)
# ---------------------------------------------------------------------------

@dataclass
class WorldCaches:
    """Lazily built performance caches over ``LoadedSave.level_dict``.

    Every field starts ``None`` and is populated on first access. After any
    mutation that could change the cached values, call
    :meth:`LoadedSave.invalidate_caches` which resets every field back to
    ``None`` so the next access rebuilds from the current state.
    """

    pal_owner_counts: dict[str, int] | None = None
    """Cleaned UID → number of owned pals (from CharacterSaveParameterMap,
    counting non-player entries by OwnerPlayerUId)."""
    player_guild_map: dict[str, str] | None = None
    """Cleaned UID → guild ID (from GroupSaveDataMap guild tails)."""


@dataclass
class LoadedSave:
    filename: str
    save_dir: str
    players_dir: str
    save_type: int          # detected from magic bytes; reproduced on encode
    class_name: str         # derived from root.save_game_type (informational)
    file_size: int
    loaded_at: float

    # Rust-side save handle (keeps uesave::Save in Rust memory).
    # When set, ``get_level_dict()`` lazily extracts worldSaveData from it.
    save_handle: Any | None = None

    # Python-side level_dict (full decoded dict).
    # Populated lazily from ``save_handle`` on first access, or set directly
    # for the legacy subprocess path. ``None`` when not yet materialized.
    # Only the ``worldSaveData`` subtree is stored (header/schemas/extra
    # are kept in Rust memory only).
    _level_dict: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def level_dict(self) -> dict[str, Any]:
        """Lazily materialized world save data.

        When ``save_handle`` is available, extracts only the ``worldSaveData``
        subtree from Rust memory (skipping ``header``, ``schemas``, ``extra``
        — saving ~30% memory). Caches the result so subsequent accesses are
        instant.

        When ``save_handle`` is ``None`` (legacy subprocess path), returns
        the pre-populated ``_level_dict``.
        """
        if self._level_dict is not None:
            return self._level_dict

        if self.save_handle is not None:
            import json
            wsd_json = self.save_handle.get_world_save_data_json()
            if wsd_json:
                wsd = json.loads(wsd_json)
                self._level_dict = {
                    "root": {
                        "properties": {
                            "worldSaveData": wsd,
                        }
                    }
                }
                return self._level_dict

        # Fallback: return empty dict
        return {}

    def sync_from_level_dict(self) -> None:
        """After mutating ``level_dict`` in Python, sync back to Rust.

        Serializes the Python ``level_dict`` to JSON and calls
        ``save_handle.put_full_json()`` to update the Rust-side save.
        Only needed when ``save_handle`` is available and mutations were
        done through the Python dict.
        """
        if self.save_handle is None or self._level_dict is None:
            return
        import json
        # We only have worldSaveData in _level_dict. Need the full save.
        # The full save was never materialized — we reconstruct it.
        # Get the full JSON from save_handle and merge our changes.
        current_full = json.loads(self.save_handle.get_full_json())
        # Replace worldSaveData in the full tree with our mutated version
        wsd = self._level_dict.get("root", {}).get("properties", {}).get("worldSaveData", {})
        if wsd:
            root_props = current_full.get("root", {}).get("properties", {})
            # Find the worldSaveData key (has _0 suffix)
            for key in list(root_props.keys()):
                if key.startswith("worldSaveData") or key == "worldSaveData":
                    root_props[key] = {"Struct": {"Struct": wsd}}
                    break
        self.save_handle.put_full_json(json.dumps(current_full))

    def invalidate_caches(self) -> None:
        """Reset all lazy performance caches. Call after any mutation."""
        self.caches = WorldCaches()
        # Also clear the Python-level dict so the next access re-extracts
        # from the Rust save handle.
        self._level_dict = None

    # Pre-computed at load time. Keys are cleaned UIDs (lowercase, no hyphens).
    player_pal_counts: dict[str, int] = field(default_factory=dict)
    player_levels: dict[str, int] = field(default_factory=dict)
    # Fallback positions from LastJumpedLocation in CharacterSaveParameterMap.
    # Used when Players/*.sav files aren't available (drag-drop upload).
    player_positions: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    # Lazy per-player .sav storage — raw bytes at load, decoded on first access.
    # Replaces the old eager ``player_savs: dict[str, dict]``.
    player_savs: LazyPlayerSavs = field(default_factory=LazyPlayerSavs)
    player_save_types: dict[str, int] = field(default_factory=dict)

    # Position indexes (built at load, PSP Rust philosophy).
    # Maps UUID (lowercase, no dashes) → position in the corresponding map.
    character_index: dict[str, int] = field(default_factory=dict)
    item_container_index: dict[str, int] = field(default_factory=dict)
    char_container_index: dict[str, int] = field(default_factory=dict)
    group_index: dict[str, int] = field(default_factory=dict)

    # Lazy performance caches (PSP Rust WorldCaches pattern).
    # Built on first access, invalidated on mutation via invalidate_caches().
    caches: WorldCaches = field(default_factory=WorldCaches)

    def invalidate_caches(self) -> None:
        """Reset all lazy performance caches. Call after any mutation."""
        self.caches = WorldCaches()


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
