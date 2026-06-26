"""SAV <-> GVAS <-> dict round-trip via the installed palsav engine.

Safety net: if a custom decode handler raises any exception, we discard its
result, rewind, and store the property as opaque bytes so the rest of the
file can parse.  Over-consumption (reading past the declared size) is NOT
corrected — the test save handles it fine, and the extra bytes belong to the
property's trailing alignment/padding.
"""

from __future__ import annotations

import copy
import io
import logging
from pathlib import Path

from palsav.archive import FArchiveReader, FArchiveWriter
from palsav.core import compress_gvas_to_sav, decompress_sav_to_gvas
from palsav.gvas import GvasFile
from palsav.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

logger = logging.getLogger(__name__)


def _skip_decode(
    reader: FArchiveReader, type_name: str, size: int, path: str
) -> dict:
    """Read property as raw bytes -- store metadata so encode can replay."""
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
            f"Expected ArrayProperty|MapProperty|StructProperty, "
            f"got {type_name} in {path}"
        )
    return value


def _skip_encode(
    writer: FArchiveWriter, property_type: str, properties: dict
) -> int:
    """Write raw bytes that were stored by skip_decode."""
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


class SaveDecodeError(Exception):
    """Raised when a .sav cannot be decompressed/parsed."""


# ---------------------------------------------------------------------------
# Safety net: catch exceptions from custom decode handlers, fall back to
# opaque bytes so the rest of the file parses.
# ---------------------------------------------------------------------------

def _make_read_safe(path: str, decode_fn: callable) -> callable:
    """Return a decode wrapper that catches exceptions."""
    def _safe(reader, type_name, size, path_):
        pos = reader.data.tell()
        try:
            result = decode_fn(reader, type_name, size, path_)
            result["__skip__"] = False
            return result
        except Exception as exc:
            logger.warning(
                "%s raised at '%s': %s; storing opaque bytes",
                decode_fn.__name__, path_, exc,
            )
            reader.data.seek(pos)
            result = _skip_decode(reader, type_name, size, path_)
            result["__skip__"] = True
            return result

    return _safe


def _make_write_safe(path: str, encode_fn: callable) -> callable:
    """Return an encode wrapper that handles skip-marked properties."""
    def _safe(writer, property_type: str, properties: dict) -> int:
        skip = properties.pop("__skip__", None)
        if skip:
            del properties["custom_type"]
            return _skip_encode(writer, property_type, properties)
        return encode_fn(writer, property_type, properties)

    return _safe


# Build the safe properties table.
_CUSTOM_PROPS: dict = {}
for _prop_path, (_decode_fn, _encode_fn) in PALWORLD_CUSTOM_PROPERTIES.items():
    _CUSTOM_PROPS[_prop_path] = (
        _make_read_safe(_prop_path, _decode_fn),
        _make_write_safe(_prop_path, _encode_fn),
    )

# 6 heavy-path skip overrides (byte-exact, no safety wrappers needed).
_SKIP_PATHS = [
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldLocation",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldRotation",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldScale3D",
    ".worldSaveData.MapObjectSaveData.MapObjectSaveData.Model.Value.EffectMap",
    ".worldSaveData.FoliageGridSaveDataMap",
    ".worldSaveData.MapObjectSpawnerInStageSaveData",
]
for _p in _SKIP_PATHS:
    _CUSTOM_PROPS[_p] = (_skip_decode, _skip_encode)

_TYPE_HINTS = PALWORLD_TYPE_HINTS


def decode_bytes(data: bytes) -> tuple[GvasFile, int, dict]:
    """Decode raw SAV bytes into (gvas, save_type, level_dict)."""
    try:
        raw_gvas, save_type = decompress_sav_to_gvas(data)

        reader = FArchiveReader(
            raw_gvas, type_hints=_TYPE_HINTS,
            custom_properties=_CUSTOM_PROPS, allow_nan=True,
        )
        reader.__enter__()
        try:
            from palsav.gvas import GvasHeader
            header = GvasHeader.read(reader)
            logger.info(
                "GVAS header OK: magic=%d version=%d class=%s",
                header.magic, header.save_game_version,
                header.save_game_class_name,
            )
            props = reader.properties_until_end()
            trailer = reader.read_to_end()
            gvas = GvasFile()
            gvas.header = header
            gvas.properties = props
            gvas.trailer = trailer
        finally:
            reader.__exit__(None, None, None)
    except SaveDecodeError:
        raise
    except Exception as exc:
        raise SaveDecodeError(f"Failed to decode save: {exc}") from exc
    level_dict = gvas.dump()
    return gvas, save_type, level_dict


def decode_file(path: str | Path) -> tuple[GvasFile, int, dict, int]:
    """Decode a .sav on disk."""
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
    """Encode and wrap in a seekable stream."""
    return io.BytesIO(encode_bytes(gvas, save_type))


def save_type_for_class(class_name: str) -> int:
    """Heuristic save_type from class name (fallback only)."""
    cn = class_name or ""
    if "Pal.PalworldSaveGame" in cn or "Pal.PalLocalWorldSaveGame" in cn:
        return 50
    return 49
