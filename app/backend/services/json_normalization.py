"""Python ``json`` vs Rust ``serde_json`` — differences & normalization.

This module documents every concrete difference between the legacy Python
``palsav`` JSON output (the shape the original WebUI services consumed) and the
Rust ``uesave``/``serde_json`` output (the shape the palsav-rs integration
uses), and provides normalization helpers for the rare cases where a value
must cross the boundary (e.g. comparing against legacy reference dumps).

Background
----------
The WebUI backend used to decode saves with the Python ``palsav`` package and
operated on its JSON dict shape. palsav-rs (Rust ``uesave`` via
``palsav_rs_wrapper``) is now the sole decoder; it emits a *different* JSON
shape. Rather than translate at the boundary (fragile, two-way), **the services
were rewritten to consume the Rust shape natively.** This file exists so the
differences are explicit and any future cross-format comparison is correct.

The authoritative ground-truth for the Rust shape is ``ref/json/`` (generated
by the same ``uesave`` binary the wrapper shells out to). ``decode_sav`` output
is byte-identical to those files.
"""

from __future__ import annotations

import base64
from typing import Any

__all__ = ["normalize_for_python_json", "bytes_to_int_array", "int_array_to_bytes"]


DIFFERENCES = """
# Python palsav  →  Rust uesave JSON: full difference table

| Aspect              | Python palsav                                  | Rust uesave (palsav-rs)                                  |
|---------------------|------------------------------------------------|----------------------------------------------------------|
| Top-level keys      | `{header, properties, trailer}`                | `{header, schemas, root:{save_game_type, properties}, extra}` |
| Property key names  | `worldSaveData` (bare)                         | `worldSaveData_0` (name + `_` + zero-based index)        |
| Scalar value        | `{"id":null,"value":100,"type":"IntProperty"}` | bare `100`                                               |
| Bool                | `{"value":true,"type":"BoolProperty"}`         | bare `true`                                              |
| String              | `{"value":"x","type":"StrProperty"}`           | bare `"x"`                                               |
| Enum                | `{"value":{"type":"T","value":"T::V"}}`        | bare `"T::V"`                                            |
| StructProperty      | `{struct_type,struct_id,id,value,type}` (5 keys)| inner struct fields are direct dict members (no wrapper)|
| MapProperty         | `{key_type,value_type,...,value:[...],type}`   | flat `[{key:{...}, value:{...}}, ...]` list              |
| SetProperty         | `{set_type,...,value:[...],type}`              | flat `[...]` list                                        |
| ArrayProperty       | `{array_type,...,value:{values:[...]},type}`   | flat `[...]` list                                        |
| RawData blob        | decoded to `{...,"custom_type":"<path>"}`      | decoded to typed struct (e.g. `PalGuildGroup`), or `{Byte:[...]}` if unparsed |
| bytes               | `{"~b":"<base64>"}` (via json_tools tag)       | `[0,0,0,...]` (flat int array)                           |
| UUID/Guid           | mixed-endian hex string (palsav UUID.__str__)  | canonical lowercase `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`|
| DateTime / u64      | Python int                                     | JSON number (Python int on load)                         |
| Float NaN/Inf       | orjson `OPT_SERIALIZE_NUMPY` or `None` (sanitize)| serde_json emits string `"NaN"`/`"Infinity"`/`"-NaN"`    |
| Float precision     | orjson `float_roundtree` off by default        | serde_json built with `float_roundtree` (full round-trip)|
| Property ordering   | insertion order (Python dict)                  | insertion order (indexmap preserves it)                  |
| Trailing bytes      | often discarded or in `trailer` (base64)       | preserved as `trailing_bytes:[...]` int arrays on typed structs |
| Header class name   | `header.save_game_class_name`                  | `root.save_game_type` (a path like `/Script/Pal.PalWorldSaveGame`) |

## Why we consume the Rust shape directly (no normalization at runtime)

A bidirectional translator (Rust→Python on read, Python→Rust before every
write) would be large and error-prone because the shapes differ in *structure*,
not just formatting. The Rust shape is also the only one that round-trips
cleanly through palsav-rs (decode → mutate → encode). So the services
(`world_service`, `base_service`, `guild_service`, `container_service`,
`player_service`, `tool_service`) were rewritten to read the Rust shape. The
helpers below are only needed when comparing against legacy Python dumps.

## Key conventions the services rely on

- `_k(node, name)` resolves `node[name_0]` falling back to `node[name]` — every
  property key may carry the `_0` index suffix.
- `_g(node, *names)` chains `_k` accesses defensively (returns `None` on any
  miss, never raises).
- Scalars are bare: `int`, `float`, `str`, `bool` directly — no `.value` unwrap.
- Maps/arrays are flat lists — iterate directly, no `.value.values` dig.
- UUIDs are canonical lowercase strings; normalize with `_s()` (strip dashes,
  lowercase) for comparison.
- `trailing_bytes` / `unknown_bytes` / `trailing_unparsed_data` arrays on typed
  structs must be preserved verbatim (they're unmapped tails); never strip them.
"""


def bytes_to_int_array(b: bytes) -> list[int]:
    """Rust represents raw byte blobs as a flat int list; convert from bytes."""
    return list(b)


def int_array_to_bytes(arr: list[int]) -> bytes:
    """Inverse of :func:`bytes_to_int_array`."""
    return bytes(int(x) & 0xFF for x in arr)


def normalize_for_python_json(rust_value: Any) -> Any:
    """Best-effort normalization of a Rust-shape value toward the legacy Python
    palsav shape, for *comparison only* against old reference dumps.

    .. warning::
        This is NOT used at runtime by the services (they consume the Rust
        shape natively). It exists purely so legacy JSON dumps can be
        diffed. It does not attempt to reconstruct the `{value,type}` scalar
        wrappers — only structurally obvious cases (byte arrays, NaN strings).

    - `[0,0,0,...]` int arrays that look like raw bytes → ``{"~b": <base64>}``
    - `"NaN"`/`"Infinity"`/`"-NaN"` strings in float position → Python float
      (Python's ``json`` cannot serialize these without ``allow_nan``).
    """
    if isinstance(rust_value, list):
        # Heuristic: an all-uint8 list likely represents a raw byte blob.
        if rust_value and all(isinstance(x, int) and 0 <= x <= 255 for x in rust_value):
            return {"~b": base64.b64encode(bytes(rust_value)).decode("ascii")}
        return [normalize_for_python_json(x) for x in rust_value]
    if isinstance(rust_value, dict):
        return {k: normalize_for_python_json(v) for k, v in rust_value.items()}
    if rust_value in ("NaN", "Infinity", "-NaN", "-Infinity"):
        import math
        mapping = {"NaN": math.nan, "Infinity": math.inf,
                   "-Infinity": -math.inf, "-NaN": -math.nan}
        return mapping[rust_value]
    return rust_value


if __doc__:  # expose the docstring table for tooling
    DIFFERENCES = DIFFERENCES  # noqa: PLW0127
