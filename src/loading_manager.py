"""
Headless replacement for the GUI-based loading_manager.

Provides the same public API functions (show_information, show_warning,
show_critical, show_error_screen, run_with_loading, show_question) but
all implementations are logging- and console-based.  No Qt dependency.
"""

import logging
import threading
import traceback as tb_module
from typing import Any, Callable, Optional

logger = logging.getLogger("pst.loading_manager")

# ── Public API (same signatures as the original Qt version) ──────────────


def show_information(parent, title: str, text: str) -> None:
    """Log an info-level message."""
    logger.info("[%s] %s", title, text)


def show_warning(parent, title: str, text: str) -> None:
    """Log a warning-level message."""
    logger.warning("[%s] %s", title, text)


def show_critical(parent, title: str, text: str) -> None:
    """Log an error-level message (console output)."""
    logger.error("[%s] %s", title, text)
    print(f"[ERROR] {title}: {text}")


def show_error_screen(error_text: str) -> None:
    """Print error text to stderr."""
    import sys
    print("[FATAL ERROR]", file=sys.stderr)
    print(error_text, file=sys.stderr)


def show_question(parent, title: str, text: str) -> bool:
    """
    Console-based yes/no question.

    Returns True if the user answers 'y' or 'yes', False otherwise.
    """
    answer = input(f"{title}: {text} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def run_with_loading(
    callback: Optional[Callable[[Any], None]],
    func: Callable[..., Any],
    *args,
    parent=None,
    **kwargs,
) -> None:
    """
    Run *func(*args, **kwargs)* in a background thread and call
    *callback(result)* when done.

    This is a headless replacement for the original GUI version that
    showed an animated overlay.  Here we simply log progress and execute.
    """
    result_holder: dict[str, Any] = {"status": "running", "data": None}

    def task() -> None:
        try:
            result_holder["data"] = func(*args, **kwargs)
        except Exception:
            result_holder["data"] = tb_module.format_exc()
        result_holder["status"] = "finished"

    t = threading.Thread(target=task, daemon=True)
    t.start()
    t.join()  # block until finished (synchronous for simplicity)

    res = result_holder["data"]
    result_holder["status"] = "idle"

    if isinstance(res, str) and "Traceback" in res:
        logger.error("Task failed:\n%s", res)
    elif callback:
        callback(res)
