"""Core data types for the breeding engine.

Everything here is a plain dataclass / string enum — no I/O, no save deps, no
``palsav``. The solver, direct-mode lookups, and source adapters all exchange
these types. Kept deliberately tiny so the wire format (Pydantic in the backend,
TS in the frontend) can mirror it 1:1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class Gender(str, Enum):
    """Pal gender. ``WILDCARD`` means "could be either" — bred children start
    here until (optionally) forced to a concrete gender by a target spec."""

    MALE = "Male"
    FEMALE = "Female"
    WILDCARD = "Wildcard"  # bred children; also used for unspecified selected pals
    UNKNOWN = "Unknown"    # couldn't be read from save / not in gender data

    @classmethod
    def coerce(cls, raw: Optional[str]) -> "Gender":
        if not raw:
            return cls.UNKNOWN
        r = str(raw).strip().lower()
        if r in ("male", "m", "epalgendertype::male"):
            return cls.MALE
        if r in ("female", "f", "epalgendertype::female"):
            return cls.FEMALE
        if r in ("wildcard", "any", "both"):
            return cls.WILDCARD
        return cls.UNKNOWN


@dataclass(frozen=True)
class PalRef:
    """A pal participating in a breeding chain.

    Immutable so it can be hashed/grouped in the solver's working set. The
    ``parents`` tuple makes a ``PalRef`` a node in a DAG: owned/selected/wild
    sources are leaves (``parents=None``); bred children carry two parent refs.

    ``origin`` records *why* this pal exists in the chain so we can render
    source badges (owned / selected / wild / bred) without re-deriving it.
    """

    species: str                       # internal asset/tribe name (e.g. "WeaselDragon")
    gender: Gender = Gender.WILDCARD
    passives: frozenset[str] = field(default_factory=frozenset)
    generation: int = 0                # 0 = source pal, 1 = first bred gen, ...
    parents: Optional[tuple["PalRef", "PalRef"]] = None
    origin: Literal["owned", "selected", "wild", "bred"] = "bred"
    # Free-form provenance for owned pals (carried through to the UI badge),
    # e.g. {"nickname": "...", "level": 42, "instance_id": "..."}. Unused by
    # the solver; harmless on selected/wild refs.
    provenance: dict = field(default_factory=dict)

    @property
    def is_source(self) -> bool:
        return self.parents is None

    def group_key(self) -> tuple[str, Gender, frozenset[str]]:
        """Identity used to dedupe refs in the working set.

        Two refs with the same species + gender + passive set are
        interchangeable for breeding purposes; we keep only the cheapest
        (fewest generations) one.
        """
        return (self.species, self.gender, self.passives)


@dataclass(frozen=True)
class BreedingStep:
    """One A+B→child edge inside a chain, flattened for serialization."""

    parent_a: str
    parent_b: str
    child: str
    inherited_passives: tuple[str, ...] = ()
    gender_feasible: bool = True


@dataclass
class Chain:
    """A complete breeding plan from sources to a target.

    ``steps`` is a flat, topologically-ordered list (parents before children)
    rather than a nested tree — easier to serialize and render. ``sources``
    lists the leaf pals the chain consumes, tagged by origin.
    """

    target: str
    generations: int
    steps: list[BreedingStep]
    final_passives: list[str]
    sources: list[dict]            # [{type, pal, ...provenance}]
    gender_feasible: bool
    # The passive set the target ended up with that matches the required set.
    matched_passives: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BreedingSpec:
    """What the solver is asked to produce."""

    target_pal: str
    required_passives: tuple[str, ...] = ()   # must be subset of the child's passives
    target_gender: Optional[Gender] = None
    max_generations: int = 5
    max_results: int = 5


@dataclass(frozen=True)
class DirectResult:
    """One row of a Direct-Mode answer (forward or reverse)."""

    parent_a: str
    parent_b: str
    child: str
    child_display: Optional[str] = None
    child_icon: Optional[str] = None
    child_gender_prob: Optional[dict] = None  # {"male": 0.4, "female": 0.6}
    combo_type: Literal["formula", "unique"] = "formula"
