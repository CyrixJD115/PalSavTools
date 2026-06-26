"""SAV <-> GVAS <-> dict round-trip via the installed palsav engine.

Uses ``SKP_PALWORLD_CUSTOM_PROPERTIES`` (the GUI-grade property table with 6
heavy paths skipped as opaque blobs) for maximum compatibility. The save_type
reported by decompression is reused on encode for byte-faithful round-trips.
"""

from __future__ import annotations

import copy
import io
from pathlib import Path

from palsav.archive import FArchiveReader, FArchiveWriter
from palsav.core import compress_gvas_to_sav, decompress_sav_to_gvas
from palsav.gvas import GvasFile
from palsav.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS


def _skip_decode(
    reader: FArchiveReader, type_name: str, size: int, path: str
) -> dict:
    """Read property as raw bytes — skip complex sub-parsing."""
    if type_name == "ArrayProperty":
        array_type = reader.fstring()
        value = {
            "skip_type": type_name,
            "array_type": array_type,
            "id": reader.optional_guid(),
            "value": reader.read(size),
        }
    elif type_name == "MapProperty":
        key_type = reader.fstring()
        value_type = reader.fstring()
        _id = reader.optional_guid()
        value = {
            "skip_type": type_name,
            "key_type": key_type,
            "value_type": value_type,
            "id": _id,
            "value": reader.read(size),
        }
    elif type_name == "StructProperty":
        value = {
            "skip_type": type_name,
            "struct_type": reader.fstring(),
            "struct_id": reader.guid(),
            "id": reader.optional_guid(),
            "value": reader.read(size),
        }
    else:
        raise Exception(
            f"Expected ArrayProperty|MapProperty|StructProperty, got {type_name} in {path}"
        )
    return value


def _skip_encode(
    writer: FArchiveWriter, property_type: str, properties: dict
) -> int:
    """Write raw bytes that were stored by skip_decode."""
    if "skip_type" not in properties:
        return writer.property_inner(property_type, properties)

    del properties["custom_type"]
    del properties["skip_type"]

    if property_type == "ArrayProperty":
        writer.fstring(properties["array_type"])
        writer.optional_guid(properties.get("id"))
        writer.write(properties["value"])
        return len(properties["value"])
    if property_type == "MapProperty":
        writer.fstring(properties["key_type"])
        writer.fstring(properties["value_type"])
        writer.optional_guid(properties.get("id"))
        writer.write(properties["value"])
        return len(properties["value"])
    # StructProperty
    writer.fstring(properties["struct_type"])
    writer.guid(properties["struct_id"])
    writer.optional_guid(properties.get("id"))
    writer.write(properties["value"])
    return len(properties["value"])


_SKIP_PATHS = [
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldLocation",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldRotation",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldScale3D",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.Model.Value.EffectMap",
    ".worldSaveData.FoliageGridSaveDataMap",
    ".worldSaveData.MapObjectSpawnerInStageSaveData",
]

# Build the skip table: clone PALWORLD_CUSTOM_PROPERTIES and override 6 paths.
_CUSTOM_PROPS = copy.deepcopy(PALWORLD_CUSTOM_PROPERTIES)
for _p in _SKIP_PATHS:
    _CUSTOM_PROPS[_p] = (_skip_decode, _skip_encode)

_TYPE_HINTS = PALWORLD_TYPE_HINTS


class SaveDecodeError(Exception):
    """Raised when a .sav cannot be decompressed/parsed."""


def decode_bytes(data: bytes) -> tuple[GvasFile, int, dict]:
    """Decode raw SAV bytes into (gvas, save_type, level_dict).

    Raises ``SaveDecodeError`` on any palsav failure.
    """
    try:
        raw_gvas, save_type = decompress_sav_to_gvas(data)
        gvas = GvasFile.read(
            raw_gvas, _TYPE_HINTS, _CUSTOM_PROPS, allow_nan=True
        )
    except SaveDecodeError:
        raise
    except Exception as exc:  # palsav raises a variety of errors
        raise SaveDecodeError(f"Failed to decode save: {exc}") from exc
    level_dict = gvas.dump()
    return gvas, save_type, level_dict


def decode_file(path: str | Path) -> tuple[GvasFile, int, dict, int]:
    """Decode a .sav on disk. Returns (gvas, save_type, level_dict, file_size)."""
    p = Path(path)
    data = p.read_bytes()
    gvas, save_type, level_dict = decode_bytes(data)
    return gvas, save_type, level_dict, len(data)


def encode_bytes(gvas: GvasFile, save_type: int) -> bytes:
    """Re-encode a GvasFile back into SAV bytes using the original save_type."""
    try:
        return compress_gvas_to_sav(gvas.write(_CUSTOM_PROPS), save_type)
    except Exception as exc:
        raise SaveDecodeError(f"Failed to encode save: {exc}") from exc


def encode_to_stream(gvas: GvasFile, save_type: int) -> io.BytesIO:
    """Encode and wrap in a seekable stream (for StreamingResponse)."""
    return io.BytesIO(encode_bytes(gvas, save_type))


def save_type_for_class(class_name: str) -> int:
    """Heuristic save_type from the save-game class name (fallback only).

    World saves use PLZ (50); everything else PLM/Oodle (49). We prefer the
    save_type captured during decompression, which is always exact.
    """
    cn = class_name or ""
    if "Pal.PalworldSaveGame" in cn or "Pal.PalLocalWorldSaveGame" in cn:
        return 50
    return 49
