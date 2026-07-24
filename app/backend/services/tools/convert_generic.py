
from __future__ import annotations
import json
from pathlib import Path
from app.backend.services.palsav_rs_wrapper import decode_sav, encode_sav, detect_save_type



# Convert SAV <-> JSON


def convert_sav_json(
    input_path: str, output_path: str | None = None,
    direction: str = "sav2json",
) -> dict:
    """Convert a .sav file to/from .json using the palsav-rs uesave binary.

    ``direction`` is ``"sav2json"`` or ``"json2sav"``.
    Returns ``{"source": ..., "target": ..., "size": ...}``.
    """
    inp = Path(input_path).resolve()
    if not inp.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")
    out = Path(output_path) if output_path else inp.with_suffix(
        ".json" if direction == "sav2json" else ".sav",
    )
    out = out.resolve()

    if direction == "sav2json":
        level_dict, _ = decode_sav(inp)
        out.write_text(json.dumps(level_dict), encoding="utf-8")
    else:  # json2sav
        with inp.open("r", encoding="utf-8") as f:
            level_dict = json.load(f)
        # Infer the original save_type from the sibling .sav if present, else PLM.
        save_type = detect_save_type(Path(input_path).read_bytes()) if inp.suffix == ".json" and inp.with_suffix(".sav").exists() else 49
        out.write_bytes(encode_sav(level_dict, save_type))

    return {"source": str(inp), "target": str(out), "size": out.stat().st_size}




# Export loaded save as JSON


def export_loaded_save_json(level_dict: dict, output_path: str) -> dict:
    """Dump an already-loaded level_dict to pretty-printed JSON on disk."""
    Path(output_path).write_text(json.dumps(level_dict), encoding="utf-8")
    return {"output": output_path, "size": Path(output_path).stat().st_size}


