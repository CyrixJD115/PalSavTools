
from __future__ import annotations
from pathlib import Path
from app.backend.services.palsav_rs_wrapper import decode_sav, encode_sav
from .core import _g, _k, _k_set


# Restore Map (clear fog)


def restore_map_fog(path: str) -> dict:
    """Clear map-of-war fog from a ``LocalData.sav`` file.

    Returns ``{"file": ..., "world_map_cleared": bool, "hidden_locations_reset": int}``.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"LocalData.sav not found: {path}")

    data = p.read_bytes()
    level_dict, save_type = decode_sav(data)
    sd = _g(level_dict, "root", "properties", "SaveData") or {}

    world_map_cleared = False
    hidden_locations_reset = 0

    # WorldMapUISaveDataMap -> mask texture (a byte array in the Rust shape).
    wmap = _k(sd, "WorldMapUISaveDataMap")
    if isinstance(wmap, list):
        for entry in wmap:
            mask = _g(entry, "value", "MaskTextureData")
            mask_bytes = _k(mask, "Byte") if isinstance(mask, dict) else None
            if isinstance(mask_bytes, list) and mask_bytes:
                n = len(mask_bytes)
                _k_set(mask, "Byte", [0] * n)
                world_map_cleared = True
    elif isinstance(_k(sd, "WorldMapMaskTextureV4"), list):
        mask = _k(sd, "WorldMapMaskTextureV4")
        n = len(mask)
        _k_set(sd, "WorldMapMaskTextureV4", [0] * n)
        world_map_cleared = True

    # Hidden location flags.
    hl = _k(sd, "Local_HiddenLocationFlagMap")
    if isinstance(hl, list):
        for entry in hl:
            _k_set(entry.get("value", entry) if isinstance(entry, dict) else entry, "value", False)
        hidden_locations_reset = len(hl)

    p.write_bytes(encode_sav(level_dict, save_type))
    return {
        "file": str(p),
        "world_map_cleared": world_map_cleared,
        "hidden_locations_reset": hidden_locations_reset,
    }


