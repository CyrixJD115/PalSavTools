"""Chunked / incremental section pre-warm.

The Rust parse is already cheap and lives in Rust memory; Python only
materializes ``worldSaveData`` sections on demand via an 8-slot LRU
(``LoadedSave.get_section``). That keeps steady-state RAM low but means
the first navigation into a heavy section (e.g. ``MapObjectSaveData``)
incurs a decode spike on first access.

:func:`prewarm_sections` is an opt-in "load bit by bit" pass: it walks
every section in order, materializes it (so the decode happens here,
under the loading overlay, not mid-navigation), runs ``gc.collect()``
between sections to drop intermediate parse buffers, and reports
progress via a callback so the UI can render real staged progress.

It bounds peak RAM to the LRU cap in memory mode (eviction still
applies), and in disk mode it also spills to the JSON cache so the
durability benefit compounds. It is **not** run by default — the load
route calls it only when the request opts in via ``prewarm=True``.
"""

from __future__ import annotations

import gc
import logging
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.backend.state import LoadedSave

logger = logging.getLogger(__name__)

# Progress callback signature: (current_1_indexed, total, section_name).
# Callers wire this to ``WsManager.broadcast_load_progress("prewarm", ...)``.
ProgressCallback = Callable[[int, int, str], Any]


def prewarm_sections(loaded: "LoadedSave", on_progress: ProgressCallback | None = None) -> int:
    """Materialize every ``worldSaveData`` section sequentially.

    Iterates ``loaded.section_names()``, calls ``loaded.get_section(name)``
    on each (which populates the LRU / disk cache), then forces a garbage
    collection so transient decode buffers are released before the next
    section. Reports progress via ``on_progress(current, total, name)``
    after each section.

    Returns the number of sections successfully materialized. Sections
    that return ``None`` (absent in this save) are counted as skipped but
    still progress the counter.

    Safe to call on either storage mode. In disk mode the section is
    served from the loaded full dict (or spills into the cache); in memory
    mode the LRU still bounds residency, so this is a "touch each once"
    warmup rather than a "keep all resident" operation.
    """
    try:
        names = loaded.section_names()
    except Exception:
        logger.exception("prewarm: failed to enumerate sections")
        return 0

    total = len(names)
    if total == 0:
        logger.debug("prewarm: no sections to materialize")
        return 0

    materialized = 0
    for idx, name in enumerate(names, start=1):
        try:
            section = loaded.get_section(name)
        except Exception:
            logger.exception("prewarm: failed to materialize %r", name)
            section = None
        if section is not None:
            materialized += 1

        # Drop transient parse state between sections to keep peak RAM low.
        gc.collect()

        if on_progress is not None:
            try:
                on_progress(idx, total, name)
            except Exception:
                logger.debug("prewarm: progress callback raised", exc_info=True)

    logger.info("prewarm: materialized %d/%d sections (storage_mode=%s)",
                materialized, total, loaded.storage_mode)
    return materialized
