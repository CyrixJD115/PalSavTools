"""Entry point for the PST WebUI backend.

Runs as a bare script path (``python /abs/path/app/backend/main.py``) or
as a module (``python -m app.backend.main``). The sys.path bootstrap below
handles the bare-script case.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

# Repo root = app/backend/main.py -> app/backend -> app -> <repo>
_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP_DIR = _REPO_ROOT / "app"
for p in (_REPO_ROOT, _APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import uvicorn

from app.backend.app import create_app
from app.backend.config import settings


class _AssetAccessFilter(logging.Filter):
    """Suppress 2xx access logs for the game-data-asset endpoint (too noisy)."""
    _ASSET_PATH = "/api/data/game-data-asset/"

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if self._ASSET_PATH not in msg:
            return True
        m = re.search(r'" (\d{3}) ', msg)
        return not (m and m.group(1).startswith("2"))


def main() -> None:
    logging.getLogger("uvicorn.access").addFilter(_AssetAccessFilter())
    app = create_app()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
