"""Palworld breeding calculator engine.

Pure-Python, zero deps on ``palsav`` / Qt / save-decode code. Consumes plain
dicts/lists only, so it cannot regress the core save engine. Loaded by the
backend via ``importlib`` (mirroring how ``map_data_service`` is loaded — see
``app/backend/services/map_service.py``).

Public surface::

    from palworld_aio.breeding import (
        BreedingDB, BreedingSpec, Chain, DirectResult, Gender, PalRef,
        OwnedSource, SelectedSource, WildSource, CompositeSource,
        direct_child, direct_partners, direct_parents, solve,
    )

Typical use::

    db = BreedingDB.load(game_data_dir)
    child = direct_child(db, "WeaselDragon", "Gorilla")          # Direct Mode
    chains = solve(db, OwnedSource(pals), spec)                  # Save Mode
    chains = solve(db, SelectedSource(picks), spec)              # Selection Mode
"""

from __future__ import annotations

from .data import BreedingDB
from .direct import direct_child, direct_parents, direct_partners
from .graph import can_reach, min_steps
from .model import (
    BreedingSpec,
    BreedingStep,
    Chain,
    DirectResult,
    Gender,
    PalRef,
)
from .solver import solve
from .sources import (
    CompositeSource,
    OwnedSource,
    SelectedSource,
    SourceAdapter,
    WildSource,
)

__all__ = [
    "BreedingDB",
    "BreedingSpec",
    "BreedingStep",
    "Chain",
    "CompositeSource",
    "DirectResult",
    "Gender",
    "OwnedSource",
    "PalRef",
    "SelectedSource",
    "SourceAdapter",
    "WildSource",
    "can_reach",
    "direct_child",
    "direct_parents",
    "direct_partners",
    "min_steps",
    "solve",
]
