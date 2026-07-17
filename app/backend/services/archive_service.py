"""In-memory extraction of bundled save archives (``.zip`` / ``.7z``).

Used by the browser drag-drop upload path (``POST /save/upload``) so that a
user who isn't running the Tauri desktop window can still hand the backend a
*complete* save — ``Level.sav`` plus its sibling ``Players/`` folder — by
zipping/7z-ing the save directory first. This mirrors the ``load_zip_file``
flow in the reference Rust tool (``palworld-save-pal``).

Design notes
------------
* **Everything stays in memory.** Entries are read into ``bytes`` and handed
  to the Rust ``decode_sav`` engine; no temp directory is written to disk, so
  there is no temp-dir lifecycle to clean up on unload.
* **Layout resolution** follows the reference: a bundle is either *flat*
  (``Level.sav`` at the archive root) or *nested* under one top-level folder
  (``<save_id>/Level.sav``). Anything deeper is rejected.
* **Path-traversal safe**: archive members are never written to the
  filesystem, and any name with a ``..`` segment or an absolute path is
  rejected before its bytes are read.
* **Rust stays the single source of truth for parsing** — this module only
  extracts bytes; it never decodes ``.sav`` content itself.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

# Decompression-bomb guards (mirrors palworld-save-pal::save_file.rs:363-369).
_MAX_ENTRIES = 100_000
_MAX_ENTRY_BYTES = 1 << 30  # 1 GiB per decompressed member

_LEVEL_NAME = "Level.sav"
_PLAYERS_SEGMENT = "Players"


class BundleError(Exception):
    """Raised when a save bundle is malformed, unsafe, or incomplete.

    The string message is safe to return to the client as an HTTP 4xx body.
    """


@dataclass
class SaveBundle:
    """In-memory view of an extracted save archive."""

    level_bytes: bytes
    level_path: str                       # path of Level.sav inside the archive
    player_files: dict[str, bytes] = field(default_factory=dict)
    # Keys are cleaned UIDs (lowercase, no hyphens) -> raw player .sav bytes.
    source_filename: str = ""

    @property
    def player_count(self) -> int:
        return len(self.player_files)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_save_bundle(data: bytes, filename: str) -> SaveBundle:
    """Extract a ``.zip``/``.7z`` save bundle entirely into memory.

    Validates that the bundle contains ``Level.sav`` and a ``Players/`` folder,
    enforces decompression-bomb limits, and returns the level bytes plus a
    ``{uid_clean: player_sav_bytes}`` map. Raises :class:`BundleError` on any
    structural / safety problem.
    """
    name = (filename or "").lower()
    if name.endswith(".zip"):
        entries = _read_zip(data)
    elif name.endswith(".7z"):
        entries = _read_7z(data)
    else:
        raise BundleError(
            "Unsupported bundle format. Upload a .zip or .7z archive "
            "containing Level.sav and its Players/ folder."
        )

    if not entries:
        raise BundleError("Archive is empty.")

    if len(entries) > _MAX_ENTRIES:
        raise BundleError(
            f"Archive has too many entries ({len(entries)} > {_MAX_ENTRIES})."
        )

    # Level.sav: look for an entry whose basename is exactly "Level.sav".
    level_path = _find_level(entries)
    if level_path is None:
        raise BundleError(
            "Archive does not contain a 'Level.sav' file. Bundle your save "
            "directory (the one containing Level.sav and Players/) and re-upload."
        )

    # Players/: collect every *.sav under a Players/ path segment, keyed by
    # cleaned UID. Same filter rules as save_service.decode_player_savs:
    # skip _dps.sav companions, stems must look like a UID.
    player_files = _collect_players(entries, level_path)

    if not player_files:
        raise BundleError(
            "Archive does not contain any player save files under a Players/ "
            "folder. Bundle the directory that contains both Level.sav and Players/."
        )

    level_bytes = entries[level_path]
    bundle = SaveBundle(
        level_bytes=level_bytes,
        level_path=level_path,
        player_files=player_files,
        source_filename=filename or "",
    )
    logger.info(
        "Extracted save bundle %r: Level.sav=%d bytes, %d player .sav files",
        bundle.source_filename, len(level_bytes), bundle.player_count,
    )
    return bundle


# ---------------------------------------------------------------------------
# Readers — one per supported format
# ---------------------------------------------------------------------------

def _read_zip(data: bytes) -> dict[str, bytes]:
    """Read a Deflate zip into ``{member_path: bytes}`` (in memory)."""
    out: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # Iterate by index (preserves central-directory order, like the
            # reference impl) rather than via namelist() ordering.
            for info in zf.infolist():
                if info.is_dir():
                    continue
                _validate_member_name(info.filename)
                with zf.open(info, "r") as fh:
                    out[info.filename] = _read_capped(fh, info.filename)
    except zipfile.BadZipFile as exc:
        raise BundleError(f"Invalid or corrupted zip archive: {exc}") from exc
    except BundleError:
        raise
    except Exception as exc:  # decompression error, truncated stream, etc.
        raise BundleError(f"Failed to read zip archive: {exc}") from exc
    return out


def _read_7z(data: bytes) -> dict[str, bytes]:
    """Read a .7z archive into ``{member_path: bytes}`` (in memory).

    ``py7zr`` is a runtime dependency (declared in pyproject). Reads happen
    through an in-memory ``BytesIO``; no files touch disk.
    """
    try:
        import py7zr
    except ImportError as exc:  # pragma: no cover - pyproject guarantees it
        raise BundleError(
            "7z support requires the 'py7zr' package, which is not installed."
        ) from exc

    out: dict[str, bytes] = {}
    try:
        with py7zr.SevenZipFile(io.BytesIO(data), mode="r") as sz:
            names = sz.getnames()
            # readall() returns {name: BytesIO} for every member; directories
            # are skipped by py7zr. We read each stream under the byte cap.
            extracted = sz.readall()
            for name in names:
                if name is None:
                    continue
                # py7zr may emit directory entries ending with '/'.
                normalized = name.replace("\\", "/").rstrip("/")
                if not normalized:
                    continue
                _validate_member_name(normalized)
                stream = extracted.get(name)
                if stream is None:
                    continue
                out[normalized] = _read_capped(stream, normalized)
    except py7zr.Bad7zFile as exc:
        raise BundleError(f"Invalid or corrupted 7z archive: {exc}") from exc
    except BundleError:
        raise
    except Exception as exc:
        raise BundleError(f"Failed to read 7z archive: {exc}") from exc
    return out


# ---------------------------------------------------------------------------
# Layout resolution + player collection
# ---------------------------------------------------------------------------

def _find_level(entries: dict[str, bytes]) -> str | None:
    """Locate the ``Level.sav`` member, supporting flat and nested layouts.

    Flat:   ``Level.sav`` at the archive root.
    Nested: ``<save_id>/Level.sav`` under exactly one top-level folder.

    Deeper nesting (``a/b/Level.sav``) is rejected. Only the first match is
    returned; multiple matches are ambiguous and also rejected.
    """
    candidates = [p for p in entries if PurePosixPath(p).name == _LEVEL_NAME]
    if not candidates:
        return None
    if len(candidates) > 1:
        raise BundleError(
            "Archive contains multiple 'Level.sav' entries — expected exactly one."
        )
    path = candidates[0]
    parts = PurePosixPath(path).parts
    # Allowed: "Level.sav" (flat) or "<folder>/Level.sav" (nested, depth 2).
    if len(parts) <= 2:
        return path
    raise BundleError(
        f"'Level.sav' is nested too deeply in the archive ('{path}'). "
        "Bundle the save directory so Level.sav is at the top level."
    )


def _collect_players(entries: dict[str, bytes], level_path: str) -> dict[str, bytes]:
    """Collect every ``Players/*.sav`` member, keyed by cleaned UID.

    Resolves the ``Players/`` prefix from the Level.sav location so a nested
    bundle (``<save_id>/Players/...``) works. Mirrors the reference's substring
    match (``name.contains("Players")``) but keys by the cleaned UID stem so
    the result drops straight into ``decode_player_savs_from_bytes``.
    """
    # Derive the prefix the Players/ folder shares with Level.sav.
    level_parts = PurePosixPath(level_path).parts
    prefix = "/".join(level_parts[:-1])  # "" for flat, "<save_id>" for nested

    players: dict[str, bytes] = {}
    for path in entries:
        normalized = path.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        if _PLAYERS_SEGMENT not in parts:
            continue
        # If the bundle is nested, the Players segment must sit under the same
        # top-level folder as Level.sav. (Flat bundles have prefix == "".)
        if prefix and not normalized.startswith(prefix + "/"):
            continue
        if not normalized.lower().endswith(".sav"):
            continue
        stem = PurePosixPath(normalized).stem
        if stem.endswith("_dps"):
            continue  # dedicated player storage — separate stream
        uid_clean = stem.replace("-", "").lower()
        # Reject anything that doesn't look like a UID hex string.
        if not uid_clean or any(c not in "0123456789abcdef" for c in uid_clean):
            continue
        players[uid_clean] = entries[path]
    return players


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------

def _validate_member_name(name: str) -> None:
    """Reject path-traversal / absolute member names before reading bytes.

    Even though we never write to disk, enforcing this invariant keeps the
    in-memory ``{path: bytes}`` map well-formed and matches the reference's
    slash-free ``save_id`` guard.
    """
    if not name:
        raise BundleError("Archive contains an entry with an empty name.")
    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        raise BundleError(f"Archive entry has an absolute path: '{name}'.")
    parts = PurePosixPath(normalized).parts
    if any(part == ".." for part in parts):
        raise BundleError(f"Archive entry escapes the bundle root: '{name}'.")


def _read_capped(stream, name: str) -> bytes:
    """Read a stream up to ``_MAX_ENTRY_BYTES`` + 1 (decompression-bomb guard).

    If the declared/observed size exceeds the cap, raise immediately rather
    than materializing gigabytes of output.
    """
    data = stream.read(_MAX_ENTRY_BYTES + 1)
    if len(data) > _MAX_ENTRY_BYTES:
        raise BundleError(
            f"Archive entry '{name}' exceeds the {_MAX_ENTRY_BYTES // (1 << 30)} GiB limit."
        )
    return data
