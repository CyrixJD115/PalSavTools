"""Reporting schema for the round-trip validation suite.

Each test produces a structured record; the runner aggregates them into a
per-file report that surfaces parsing drift or serialization discrepancies
between implementations. Intended for ``pytest --tb=short`` consumption and
optional machine-readable export.

Record shape::

    {
      "file": "Level.sav",
      "category": "zero_change|mutation|parity|edge_case",
      "status": "pass|fail|skip",
      "oracle": "byte_exact|semantic|ground_truth",
      "detail": "...",                # human-readable on fail
      "drift": {                      # populated only on drift-detected fails
         "field": "...", "expected": "...", "actual": "..."
      },
      "duration_ms": 123,
    }

The runner prints a summary table; a JSON dump is written to
``tests/roundtrip/.last-report.json`` for CI artifacts.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

REPORT_PATH = Path(__file__).resolve().parent / ".last-report.json"


@dataclass
class Record:
    file: str
    category: str               # zero_change | mutation | parity | edge_case
    status: str                 # pass | fail | skip
    oracle: str = ""            # byte_exact | semantic | ground_truth
    detail: str = ""
    drift: dict = field(default_factory=dict)
    duration_ms: int = 0


class Report:
    """Accumulates records; call :meth:`write` at session end."""

    def __init__(self) -> None:
        self.records: list[Record] = []

    def add(self, **kw) -> None:
        self.records.append(Record(**kw))

    def write(self) -> Path:
        data = [asdict(r) for r in self.records]
        REPORT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return REPORT_PATH

    def summary(self) -> str:
        by_status: dict[str, int] = {}
        by_cat: dict[str, dict[str, int]] = {}
        for r in self.records:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            cat = by_cat.setdefault(r.category, {})
            cat[r.status] = cat.get(r.status, 0) + 1
        lines = ["round-trip report summary", "  by status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))]
        for cat, counts in sorted(by_cat.items()):
            lines.append(f"  {cat}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        # surface any failures with their drift detail
        fails = [r for r in self.records if r.status == "fail"]
        if fails:
            lines.append("  failures:")
            for f in fails:
                lines.append(f"    - {f.file} [{f.oracle}] {f.detail}")
        return "\n".join(lines)
