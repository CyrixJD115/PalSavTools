"""Minimal WebSocket broadcast manager.

Clients connect to ``/ws`` and receive JSON messages broadcast by the backend
(save loaded / unloaded, future job logs). Stateless push-only for now.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class WsManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)

    async def broadcast(self, type_: str, payload: Any) -> None:
        msg = json.dumps({"type": type_, "payload": payload})
        dead: list[WebSocket] = []
        async with self._lock:
            targets = list(self._connections)
        for ws in targets:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def broadcast_load_progress(
        self,
        stage: str,
        current: int = 0,
        total: int = 0,
        section: str | None = None,
    ) -> None:
        """Broadcast a ``load_progress`` event to all connected clients.

        Used by the load route to surface staged progress (parse →
        precompute → optional pre-warm of each section → done) so the
        frontend can render a real progress bar instead of the default
        indeterminate spinner.

        ``stage`` is one of ``"parse"``, ``"precompute"``, ``"prewarm"``,
        ``"done"``. ``current``/``total`` describe the section-by-section
        position when ``stage == "prewarm"`` (1-indexed current).
        """
        await self.broadcast("load_progress", {
            "stage": stage,
            "current": current,
            "total": total,
            "section": section,
        })


manager = WsManager()
