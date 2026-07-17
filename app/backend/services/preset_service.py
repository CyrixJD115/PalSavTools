"""JSON-file-backed pal preset storage.

Presets persist as one JSON file per preset under a user-config directory
(platform-appropriate), so they survive across repo checkouts and aren't
committed. ``PalPreset`` carries all-optional fields; ``None`` = "don't touch"
when applied (PSP semantics).

Apply logic lives here too: it delegates per-field writes to ``pal_service`` so
the same validation + HP recompute cascade runs whether you edit one pal by hand
or apply a preset to many.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Optional

from app.backend import paths
from app.backend.services import pal_service


def _presets_dir() -> Path:
    """User-config presets dir. Created on first use.

    Prefers ``~/.config/palworldsavetools/presets`` on POSIX (mirrors the XDG
    pattern); falls back to a local ``.palworldsavetools/presets`` in the user
    home on other platforms. Decoupled from the repo tree so presets persist
    across checkouts and are never committed.
    """
    home = Path.home()
    config_root = home / ".config" / "palworldsavetools"
    if not _is_writable(config_root.parent):
        config_root = home / ".palworldsavetools"
    presets = config_root / "presets"
    presets.mkdir(parents=True, exist_ok=True)
    return presets


def _is_writable(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p.exists() and p.is_dir()
    except OSError:
        return False


def _slugify(name: str) -> str:
    """URL/filename-safe slug, ensures uniqueness via a short uuid suffix."""
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-") or "preset"
    return f"{base}-{uuid.uuid4().hex[:8]}"


def list_presets() -> list[dict]:
    """All saved presets, sorted by name."""
    out: list[dict] = []
    for f in sorted(_presets_dir().glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("name"):
                out.append(data)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def get_preset(preset_id: str) -> Optional[dict]:
    p = _presets_dir() / f"{preset_id}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_preset(name: str, preset: dict, preset_id: Optional[str] = None) -> dict:
    """Create or overwrite a preset. Returns the stored dict (with id)."""
    pid = preset_id or _slugify(name)
    data = {**preset, "id": pid, "name": name}
    # Strip nested id/name from the incoming preset so ours wins.
    path = _presets_dir() / f"{pid}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def delete_preset(preset_id: str) -> bool:
    p = _presets_dir() / f"{preset_id}.json"
    if p.is_file():
        p.unlink()
        return True
    return False


def apply_preset(
    level_dict: dict, instance_ids: list[str], preset_id: str, cheat: bool = False,
) -> dict:
    """Apply a preset's non-None fields to each named pal.

    Returns ``{"applied": N, "failed": [...], "errors": {instance_id: msg}}``.
    """
    preset = get_preset(preset_id)
    if preset is None:
        return {"applied": 0, "failed": list(instance_ids), "errors": {"_": "preset not found"}}

    # Strip the id/name bookkeeping keys before applying.
    fields = {k: v for k, v in preset.items() if v is not None and k not in ("id", "name")}

    applied = 0
    failed: list[str] = []
    errors: dict[str, str] = {}
    for instance_id in instance_ids:
        try:
            result = pal_service.apply_preset_fields(level_dict, instance_id, fields, cheat=cheat)
            if result is None:
                failed.append(instance_id)
                errors[instance_id] = "pal not found"
            else:
                applied += 1
        except ValueError as e:
            failed.append(instance_id)
            errors[instance_id] = str(e)
    return {"applied": applied, "failed": failed, "errors": errors}
