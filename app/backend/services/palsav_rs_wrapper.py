"""Python wrapper around the ``palsav-rs`` (uesave) Rust save engine.

Provides two backends:

1. **Native (PyO3)** — imports ``uesave_pyo3`` directly via FFI. No subprocess
   spawn, no temp files, no JSON round-trip over the filesystem. The Rust
   library handles all decompression, parsing, and serialization in-process.
   This is the primary path when available.

2. **Subprocess CLI bridge** — shells out to the ``uesave`` binary
   (``to-json --palworld`` / ``from-json [--compress-oodle]``). Used as a
   fallback when the native module is not installed.

Design
------
All SAV <-> dict conversion goes through here; the rest of the backend works
on the decoded ``dict`` (the *Rust* uesave JSON shape, NOT the legacy Python
``palsav`` shape). The dict is the source of truth: callers mutate it in place,
then hand it back for re-encoding.

The Rust JSON shape (what every service consumes)::

    {
      "header":   {magic, save_game_version, ...},
      "schemas":  {...},          # uesave internal schema cache
      "root":     {"save_game_type": "/Script/Pal.PalWorldSaveGame",
                   "properties": {"worldSaveData_0": {...}, ...}},
      "extra":    [0, 0, ...]
    }

Property keys carry an ``_<index>`` suffix; scalars are bare values; maps are
flat ``[{key, value}, ...]`` lists.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import struct
import subprocess
import tempfile
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Native (PyO3) backend
# ---------------------------------------------------------------------------

_HAS_NATIVE = False
try:
    import uesave_pyo3 as _native

    _HAS_NATIVE = True
    logger.info("Using native PyO3 uesave module (%s)", _native.__file__)
except ImportError:
    logger.info("Native PyO3 module not available, falling back to subprocess CLI")

# ---------------------------------------------------------------------------
# Paths / binary resolution (subprocess fallback only)
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
_PALSAV_RS_DIR: Path = _REPO_ROOT / "src" / "palsav-rs"
_BINARY_PATH: Path = _PALSAV_RS_DIR / "target" / "release" / "uesave"

# Compression save-type constants.
SAVE_TYPE_PLM = 49   # Oodle (PlM magic) — player saves
SAVE_TYPE_PLZ = 50   # double-zlib (PlZ magic) — classic world saves
SAVE_TYPE_CNK = 48   # nested chunk (Game Pass)
SAVE_TYPE_GVAS = 0   # uncompressed GVAS


class PalsavRsError(Exception):
    """Raised when the uesave binary is missing or returns an error."""


# ---------------------------------------------------------------------------
# Save-type detection
# ---------------------------------------------------------------------------

def detect_save_type(data: bytes) -> int:
    """Detect the save format from the first bytes.

    Returns one of :data:`SAVE_TYPE_PLM`, :data:`SAVE_TYPE_PLZ`,
    :data:`SAVE_TYPE_CNK`, or :data:`SAVE_TYPE_GVAS`.
    """
    if _HAS_NATIVE:
        return _native.detect_save_type(data)

    # Subprocess fallback: pure Python detection.
    if len(data) >= 4 and data[0:4] == b"GVAS":
        return SAVE_TYPE_GVAS
    if len(data) < 12:
        return SAVE_TYPE_GVAS

    if len(data) >= 24 and data[8:11] == b"CNK":
        magic = data[20:23]
    else:
        magic = data[8:11]

    if magic == b"PlM":
        return SAVE_TYPE_PLM
    if magic == b"PlZ":
        return SAVE_TYPE_PLZ
    return SAVE_TYPE_GVAS


# ---------------------------------------------------------------------------
# Binary resolution (subprocess fallback only)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _binary_path() -> Path:
    """Resolve the uesave binary, building it on first use if needed."""
    if _HAS_NATIVE:
        raise PalsavRsError("Native module is active; subprocess path should not be called")

    if _BINARY_PATH.exists():
        return _BINARY_PATH

    cargo = shutil.which("cargo")
    if cargo is None:
        raise PalsavRsError(
            f"uesave binary not found at {_BINARY_PATH} and `cargo` is not on "
            "PATH. Install Rust (https://rustup.rs) or build palsav-rs manually."
        )
    if not _PALSAV_RS_DIR.is_dir():
        raise PalsavRsError(
            f"palsav-rs submodule missing at {_PALSAV_RS_DIR}. "
            "Run: git submodule update --init src/palsav-rs"
        )

    logger.info("Building uesave (release, oodle) — first use only…")
    proc = subprocess.run(
        ["cargo", "build", "--release", "-p", "uesave_cli",
         "--features", "uesave/oodle"],
        cwd=str(_PALSAV_RS_DIR),
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0 or not _BINARY_PATH.exists():
        raise PalsavRsError(
            "Failed to build uesave.\n"
            f"stdout:\n{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-2000:]}"
        )
    logger.info("uesave built at %s", _BINARY_PATH)
    return _BINARY_PATH


# ---------------------------------------------------------------------------
# PLZ (double-zlib) — for subprocess fallback *and* native backend
# (uesave's from-json doesn't emit PlZ, so we wrap GVAS bytes here)
# ---------------------------------------------------------------------------

def _plz_compress(gvas: bytes) -> bytes:
    """Double-zlib compress GVAS bytes into a PlZ (type 0x32) SAV."""
    first = zlib.compress(gvas)
    second = zlib.compress(first)
    header = struct.pack(
        "<II", len(gvas), len(first),
    ) + b"PlZ" + bytes([0x32])
    return header + second


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a subprocess, raising PalsavRsError with stderr on failure."""
    proc = subprocess.run(
        cmd, capture_output=True, timeout=kw.pop("timeout", 180), **kw,
    )
    if proc.returncode != 0:
        raise PalsavRsError(
            f"`{' '.join(cmd[-6:])}` exited {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace')[-2000:]}"
        )
    return proc


def _decode_subprocess(data_bytes: bytes) -> tuple[dict[str, Any], int]:
    """Decode a .sav via the uesave CLI subprocess."""
    save_type = detect_save_type(data_bytes)
    binary = _binary_path()
    with tempfile.TemporaryDirectory(prefix="palsav-rs-dec-") as tmp:
        in_path = Path(tmp) / "in.sav"
        out_path = Path(tmp) / "out.json"
        in_path.write_bytes(data_bytes)
        _run([
            str(binary), "to-json", "--palworld", "--no-warn",
            "-i", str(in_path), "-o", str(out_path),
        ])
        with out_path.open("r", encoding="utf-8") as f:
            level_dict = json.load(f)
    return level_dict, save_type


def _encode_subprocess(level_dict: dict[str, Any], save_type: int) -> bytes:
    """Encode a level_dict via the uesave CLI subprocess."""
    binary = _binary_path()
    with tempfile.TemporaryDirectory(prefix="palsav-rs-enc-") as tmp:
        in_path = Path(tmp) / "in.json"
        out_path = Path(tmp) / "out.sav"
        in_path.write_text(
            json.dumps(level_dict), encoding="utf-8",
        )

        if save_type == SAVE_TYPE_PLM:
            _run([
                str(binary), "from-json", "--compress-oodle",
                "-i", str(in_path), "-o", str(out_path),
            ])
            return out_path.read_bytes()

        _run([
            str(binary), "from-json",
            "-i", str(in_path), "-o", str(out_path),
        ])
        gvas = out_path.read_bytes()

        if save_type == SAVE_TYPE_PLZ:
            return _plz_compress(gvas)
        return gvas


# ---------------------------------------------------------------------------
# Core decode / encode — unified API, chooses native or subprocess
# ---------------------------------------------------------------------------

def decode_sav(data: bytes | str | Path) -> tuple[dict[str, Any], int]:
    """Decode a ``.sav`` into ``(level_dict, save_type)``.

    Accepts raw bytes, a path to a ``.sav`` file, or a ``str`` path.
    The returned ``dict`` is the full Rust uesave shape (``{header, schemas,
    root, extra}``).

    When the native PyO3 module is available, this runs entirely in-process
    — no subprocess, no temp files, no JSON disk round-trip.
    """
    data_bytes, save_type = _as_bytes(data)

    if _HAS_NATIVE:
        json_str, save_type = _native.decode_sav(data_bytes)
        level_dict = json.loads(json_str)
        return level_dict, save_type

    return _decode_subprocess(data_bytes)


def encode_sav(level_dict: dict[str, Any], save_type: int) -> bytes:
    """Serialize a ``level_dict`` back into ``.sav`` bytes.

    When the native PyO3 module is available, this runs entirely in-process.
    """
    if _HAS_NATIVE:
        json_str = json.dumps(level_dict)
        raw = _native.encode_sav(json_str, save_type)
        if save_type == SAVE_TYPE_PLZ:
            return _plz_compress(raw)
        return raw

    return _encode_subprocess(level_dict, save_type)


def decode_player_sav(data: bytes | str | Path) -> tuple[dict[str, Any], int]:
    """Decode a per-player ``.sav`` (always PlM/Oodle)."""
    return decode_sav(data)


def encode_player_sav(player_dict: dict[str, Any], save_type: int) -> bytes:
    """Encode a per-player ``.sav`` back to bytes."""
    return encode_sav(player_dict, save_type)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_bytes(data: bytes | str | Path) -> tuple[bytes, int]:
    """Coerce input to (bytes, detected_save_type)."""
    if isinstance(data, (str, Path)):
        raw = Path(data).read_bytes()
    else:
        raw = bytes(data)
    return raw, detect_save_type(raw)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def roundtrip_sav(data: bytes | str | Path) -> tuple[bool, str]:
    """Decode → encode a ``.sav`` and report byte-faithfulness."""
    raw, save_type = _as_bytes(data)
    if save_type == SAVE_TYPE_CNK:
        return False, "CNK outer wrapper is not re-applied on encode"
    level_dict, _ = decode_sav(raw)
    encoded = encode_sav(level_dict, save_type)
    ok = encoded == raw
    detail = (
        "byte-identical" if ok
        else f"differs (orig {len(raw)}B → enc {len(encoded)}B)"
    )
    return ok, detail


def roundtrip_json_stable(data: bytes | str | Path) -> tuple[bool, str]:
    """Decode → encode → decode and assert the two dicts are equal."""
    raw, save_type = _as_bytes(data)
    d1, _ = decode_sav(raw)
    enc = encode_sav(d1, save_type)
    d2, _ = decode_sav(enc)
    ok = d1 == d2
    return ok, "JSON-stable" if ok else "decode→encode→decode diverged"


__all__ = [
    "PalsavRsError",
    "SAVE_TYPE_PLM", "SAVE_TYPE_PLZ", "SAVE_TYPE_CNK", "SAVE_TYPE_GVAS",
    "detect_save_type",
    "decode_sav", "encode_sav",
    "decode_player_sav", "encode_player_sav",
    "roundtrip_sav", "roundtrip_json_stable",
]
