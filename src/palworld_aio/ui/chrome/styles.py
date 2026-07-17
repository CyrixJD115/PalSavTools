"""
Headless stub for palworld_aio.ui.chrome.styles.

In the original GUI version ThemeManager applied Qt stylesheets to widgets.
This stub provides the same public interface with no-ops.
"""

import logging

logger = logging.getLogger("pst.ui.chrome.styles")


class ThemeManager:
    """Stub that replaces the original Qt-based ThemeManager."""

    @staticmethod
    def apply_to_widget(widget) -> None:
        """No-op: widget theming not applicable in headless mode."""
        pass

    @staticmethod
    def get_theme() -> str:
        """Return a theme identifier string."""
        return "dark"

    @staticmethod
    def set_theme(name: str) -> None:
        """Set theme (stub — no visual effect)."""
        logger.debug("Theme set to %s (headless stub)", name)
