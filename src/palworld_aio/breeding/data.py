"""Loads and indexes the breeding data files.

Reads the three JSONs produced by ``scripts/extract_breeding_meta.py`` from
``src/_resources/game_data/`` and builds the lookup indexes the rest of the
engine needs. Pure data access — no solver logic, no I/O beyond the initial
load. Cached at module level so repeated solves don't re-parse.

Design note on the forward index: ``child_to_parents_formula`` is keyed
child→[parent pairs]. We invert it once into ``pair_to_child`` (a
``frozenset[a,b] → child`` map) for O(1) "A+B → ?" lookups, which both Direct
Mode and the solver need constantly. ``child_to_parents`` stays as-is for the
reverse Direct-Mode lookup.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Optional

from .model import DirectResult


class BreedingDB:
    """Indexed breeding data. Construct via :meth:`load` (cached)."""

    def __init__(
        self,
        pal_info: dict[str, dict],
        unique_combos: list[dict],
        child_to_parents_formula: dict[str, list[dict]],
        child_to_parents_unique: dict[str, list[dict]],
        gender_prob: dict[str, dict[str, float]],
        breedable_genders: dict[str, str],
        display_names: dict[str, str],
        min_steps: dict[str, dict[str, int]],
    ) -> None:
        self.pal_info = pal_info
        self.unique_combos = unique_combos
        self.child_to_parents_formula = child_to_parents_formula
        self.child_to_parents_unique = child_to_parents_unique
        self.gender_prob = gender_prob
        self.breedable_genders = breedable_genders
        self.display_names = display_names
        self.min_steps = min_steps

        # --- derived indexes (built once at load) ---
        # pair_to_child: frozenset{a,b} -> child tribe. Unique combos override
        # formula results (a given pair may appear in both; unique wins, mirroring
        # the game's DT_PalCombiUnique precedence).
        self.pair_to_child: dict[frozenset[str], str] = {}
        for child, pairs in child_to_parents_formula.items():
            for pair in pairs:
                self.pair_to_child[frozenset((pair["parent_a"], pair["parent_b"]))] = child
        for combo in unique_combos:
            self.pair_to_child[frozenset((combo["parent_a"], combo["parent_b"]))] = combo["child"]

        # child_to_parents: merged unique + formula + ignore, child -> list[(a,b)].
        # Built lazily — only Direct Mode reverse needs it.
        self._child_to_parents_merged: Optional[dict[str, list[tuple[str, str]]]] = None

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    @functools.lru_cache(maxsize=4)
    def load(cls, game_data_dir: str | Path) -> "BreedingDB":
        """Load the three breeding JSONs from ``game_data_dir``.

        Cached by directory path — safe to call repeatedly. Raises
        ``FileNotFoundError`` if any of the three files is missing.
        """
        gd = Path(game_data_dir)
        breeding = _read_json(gd / "breeding.json")
        meta = _read_json(gd / "breeding_meta.json")
        distance = _read_json(gd / "breeding_distance.json")
        return cls(
            pal_info=breeding["pal_info"],
            unique_combos=breeding["unique_combos"],
            child_to_parents_formula=breeding["child_to_parents_formula"],
            child_to_parents_unique=breeding.get("child_to_parents_unique", {}),
            gender_prob=meta.get("gender_prob", {}),
            breedable_genders=meta.get("breedable_genders", {}),
            display_names=meta.get("display_names", {}),
            min_steps=distance,
        )

    # ------------------------------------------------------------------
    # forward / reverse child lookups
    # ------------------------------------------------------------------
    def forward(self, parent_a: str, parent_b: str) -> Optional[str]:
        """A + B → child tribe, or ``None`` if the pair has no known child.

        Order-independent (the key is a frozenset). Same-species pairs resolve
        to themselves when present in the table (Alpaca+Alpaca→Alpaca).
        """
        return self.pair_to_child.get(frozenset((parent_a, parent_b)))

    def child_to_parents(self, child: str) -> list[tuple[str, str]]:
        """child → all parent pairs (unique + formula). Built once, cached."""
        if self._child_to_parents_merged is None:
            self._child_to_parents_merged = self._build_child_to_parents()
        return self._child_to_parents_merged.get(child, [])

    def _build_child_to_parents(self) -> dict[str, list[tuple[str, str]]]:
        merged: dict[str, list[tuple[str, str]]] = {}
        seen: dict[str, set[tuple[str, str]]] = {}
        # Unique combos first (so they appear ahead of formula results, matching
        # the legacy PST tab ordering that surfaced specials first).
        sources = [
            self.child_to_parents_unique,
            self.child_to_parents_formula,
        ]
        for src in sources:
            for child, pairs in src.items():
                bucket_seen = seen.setdefault(child, set())
                bucket = merged.setdefault(child, [])
                for pair in pairs:
                    key = tuple(sorted((pair["parent_a"], pair["parent_b"])))
                    if key in bucket_seen:
                        continue
                    bucket_seen.add(key)
                    bucket.append(key)
        return merged

    def reverse(self, parent_a: str, target_child: str) -> list[str]:
        """Given Parent A + target child, return candidate Parent B tribes.

        Projects the other side of every pair in ``child_to_parents(target)``
        where one parent matches ``parent_a``.
        """
        out: list[str] = []
        for a, b in self.child_to_parents(target_child):
            if a == parent_a:
                out.append(b)
            elif b == parent_a:
                out.append(a)
        return out

    # ------------------------------------------------------------------
    # reachability (distance map)
    # ------------------------------------------------------------------
    def reachable(self, start_pal: str, target_pal: str, budget: int) -> bool:
        """True if ``start_pal`` can reach ``target_pal`` in ≤ ``budget`` breeds.

        Same pal → 0 steps (always reachable with budget ≥ 0). Unknown pairs
        (absent from the distance map — newer pals not in palcalc's snapshot)
        are treated as unreachable unless start == target, which is the safe
        default: we'd rather under-report than fabricate a chain we can't verify.
        """
        if start_pal == target_pal:
            return budget >= 0
        row = self.min_steps.get(start_pal)
        if row is None:
            return False
        steps = row.get(target_pal)
        return steps is not None and steps <= budget

    # ------------------------------------------------------------------
    # metadata helpers
    # ------------------------------------------------------------------
    def display_name(self, tribe: str) -> str:
        """Localized display name, falling back to pal_info name then the tribe."""
        return (
            self.display_names.get(tribe)
            or self.pal_info.get(tribe, {}).get("name")
            or tribe
        )

    def icon_path(self, tribe: str) -> Optional[str]:
        return self.pal_info.get(tribe, {}).get("icon")

    def gender_probability(self, tribe: str) -> dict[str, float]:
        """``{"male": p, "female": q}``; defaults to 50/50 when unknown."""
        return self.gender_prob.get(tribe, {"male": 0.5, "female": 0.5})

    def breedable_gender(self, tribe: str) -> str:
        """``"BOTH" | "MALE_ONLY" | "FEMALE_ONLY"``; defaults to ``"BOTH"``."""
        return self.breedable_genders.get(tribe, "BOTH")

    def is_breedable(self, tribe: str) -> bool:
        """A pal is breedable if it appears in the combo table at all."""
        return tribe in self.pal_info

    def breedable_tribes(self) -> list[str]:
        """All tribes the UI picker should offer (sorted by display name)."""
        return sorted(self.pal_info.keys(), key=self.display_name)

    # ------------------------------------------------------------------
    # DirectResult factory — shared by direct.py forward + reverse
    # ------------------------------------------------------------------
    def direct_result(
        self,
        parent_a: str,
        parent_b: str,
        child: str,
        combo_type: str = "formula",
    ) -> DirectResult:
        return DirectResult(
            parent_a=parent_a,
            parent_b=parent_b,
            child=child,
            child_display=self.display_name(child),
            child_icon=self.icon_path(child),
            child_gender_prob=self.gender_probability(child),
            combo_type=combo_type,  # type: ignore[arg-type]
        )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing breeding data file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
