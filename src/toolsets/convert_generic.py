"""
convert_generic — Convert a single .sav <-> .json file (headless CLI).

Removed all PySide6/Qt dependencies.  Uses argparse for input selection and
logging for status output.  Business logic (convert_sav_to_json,
convert_json_to_sav) preserved as-is.
"""

import gc
import logging
import os
import sys

from import_libs import *
from loading_manager import run_with_loading, show_information
from palsav.commands.convert import main as convert_main

logger = logging.getLogger("pst.convert_generic")


# ============================================================================
# Conversion helpers (unchanged business logic)
# ============================================================================

def convert_sav_to_json(input_file, output_file):
    """Convert a .sav file to .json using ``palsav.commands.convert``."""
    old_argv = sys.argv
    try:
        sys.argv = ["convert", input_file, "--output", output_file, "--force"]
        convert_main()
    finally:
        sys.argv = old_argv


def convert_json_to_sav(input_file, output_file):
    """Convert a .json file to .sav using ``palsav.commands.convert``."""
    old_argv = sys.argv
    try:
        sys.argv = ["convert", input_file, "--output", output_file, "--force"]
        convert_main()
    finally:
        sys.argv = old_argv


# ============================================================================
# Main conversion function
# ============================================================================

def convert_generic(ext, input_file=None):
    """Perform a single conversion.

    Parameters
    ----------
    ext : str
        ``"sav"`` (convert .json -> .sav) or ``"json"`` (convert .sav -> .json).
    input_file : str or None
        Path to the input file.  If ``None``, the function prompts via stdin.

    Returns
    -------
    bool
        ``True`` on success, ``False`` otherwise.
    """
    if input_file is None:
        input_file = input(f"Enter path to the input .{ext} file: ").strip()
        if not input_file:
            logger.error("No input file provided.")
            return False

    if not os.path.exists(input_file):
        logger.error("Input file not found: %s", input_file)
        return False

    root, _ = os.path.splitext(input_file)
    output_path = root + (".sav" if ext == "sav" else ".json")

    if ext == "sav":
        # JSON -> SAV
        def task():
            convert_json_to_sav(input_file, output_path)
            gc.collect()
    else:
        # SAV -> JSON
        def task():
            convert_sav_to_json(input_file, output_path)
            gc.collect()

    # run_with_loading is headless — runs synchronously
    run_with_loading(None, task)

    logger.info("Converted %s -> %s", input_file, output_path)
    return True


# ============================================================================
# CLI entry point
# ============================================================================

def main():
    """CLI entry point.

    Usage::

        python convert_generic.py <sav|json> [input_file]

    If *input_file* is omitted the script prompts for it.
    """
    if len(sys.argv) < 2 or sys.argv[1] not in ("sav", "json"):
        print("Usage: convert_generic.py <sav|json> [input_file]", file=sys.stderr)
        sys.exit(1)

    ext = sys.argv[1]
    input_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not convert_generic(ext, input_file):
        sys.exit(1)


if __name__ == "__main__":
    main()
