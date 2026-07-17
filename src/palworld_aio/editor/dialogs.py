"""
Headless replacement for editor/dialogs.py.

Provides GameDaysInputDialog.get_days() as a console-based prompt.
"""

import logging

logger = logging.getLogger("pst.editor.dialogs")


class GameDaysInputDialog:
    """Console-based replacement for the Qt GameDaysInputDialog."""

    @staticmethod
    def get_days(title: str, prompt: str, parent=None, current_days: int = 0) -> int | None:
        """
        Prompt the user to enter a number of game days via console.

        Returns the entered integer, or None if cancelled/empty.
        """
        print(f"\n=== {title} ===")
        print(prompt)
        try:
            raw = input(f"  Current: {current_days}. New value (or press Enter to cancel): ").strip()
            if not raw:
                return None
            val = int(raw)
            if val < 0:
                logger.warning("Negative value entered, ignoring")
                return None
            return val
        except (ValueError, EOFError, KeyboardInterrupt):
            return None
