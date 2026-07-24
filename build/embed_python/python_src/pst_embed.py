"""Embedded module loaded directly from bytes inside the Rust binary — no .py file on disk."""


def add(a: int, b: int) -> int:
    return a + b


def whoami() -> str:
    # Proves this ran from inside the binary, not from a file on sys.path.
    import sys

    return f"pst_embed loaded in-memory; exec_prefix={sys.exec_prefix!r}"
