"""Cache-invalidation helpers for mutation routes.

PSP Rust philosophy: after any mutation that changes world-tree state
(character maps, guild maps, containers), call ``invalidate_caches()``
on the current ``LoadedSave`` so lazy ``WorldCaches`` get rebuilt on
the next access.

Usage in a route handler::

    from app.backend.services.cache_invalidation import invalidate_caches
    invalidate_caches()
"""

from __future__ import annotations


def invalidate_caches() -> None:
    """Invalidate the current session's lazy performance caches.

    Safe to call when no save is loaded (no-op).
    """
    from app.backend.state import save_state
    loaded = save_state.get()
    if loaded is not None:
        loaded.invalidate_caches()
