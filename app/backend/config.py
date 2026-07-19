"""Runtime configuration for the WebUI backend.

All values are overridable via environment variables so the same code runs in
dev (separate Vite + uvicorn processes) and production (single process serving
the built SPA).
"""

from __future__ import annotations

import os
from pathlib import Path

from app.backend import paths


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Networking
    host: str = os.environ.get("PST_WEB_HOST", "127.0.0.1")
    port: int = int(os.environ.get("PST_WEB_PORT", "16921"))

    # When False the SPA static mount is skipped (dev mode uses Vite directly).
    serve_frontend: bool = _env_bool("PST_WEB_SERVE_FRONTEND", True)

    # Allow overriding the frontend build location for frozen/packaged builds.
    frontend_build_dir: Path = Path(
        os.environ.get("PST_WEB_FRONTEND_BUILD", str(paths.FRONTEND_BUILD_DIR))
    )

    # CORS: open in local-single-user mode; tighten for a real deployment.
    cors_origins: list[str] = ["*"]

    # Default storage mode for a loaded save. ``"memory"`` keeps the decoded
    # save in RAM (current behavior); ``"disk"`` spills the full decoded JSON
    # to a temp file so RAM stays low on huge saves. Per-request overrides
    # come from the load endpoints' ``storage_mode`` param.
    storage_mode: str = os.environ.get("PST_WEB_STORAGE_MODE", "memory")

    # Files above this size (in MB) trigger the frontend's storage-mode
    # warning modal on upload. Mirrored to the client via /api/health so both
    # sides share the same threshold.
    large_save_threshold_mb: int = int(
        os.environ.get("PST_WEB_LARGE_SAVE_MB", "50")
    )


settings = Settings()


def is_valid_storage_mode(mode: str) -> bool:
    """True if ``mode`` is one of the supported storage modes."""
    return mode in {"memory", "disk"}
