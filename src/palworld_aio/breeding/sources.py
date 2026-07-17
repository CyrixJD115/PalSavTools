"""Source adapters — how the solver gets its initial breeding pool.

The key palcalc insight reproduced here: Save Mode and Selection Mode are the
*same solver* with different initial pools. Each adapter just produces a list
of :class:`PalRef` leaves; the solver never knows which mode it's in.

* :class:`OwnedSource`    — Save Mode. Wraps the ``PalSummary`` dicts that
  ``GET /api/pals`` already returns (gender, passives, character_id, ...).
  One ref per owned pal, carrying its real gender + passives + provenance.
* :class:`SelectedSource` — Selection Mode. User's theoretical picks
  (``{species, gender?, passives?}``). Gender defaults to WILDCARD so the solver
  treats them as flexible.
* :class:`WildSource`     — optional. Adds one WILDCARD ref per breedable
  species not otherwise present, representing "go catch one". Composable with
  the above via :class:`CompositeSource`.

All adapters are pure — no I/O, no save parsing. ``OwnedSource`` accepts the
exact shape ``world_service.list_pals`` emits; no mapping layer needed.
"""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from .data import BreedingDB
from .model import Gender, PalRef


@runtime_checkable
class SourceAdapter(Protocol):
    """Produces the initial ``PalRef`` leaves for the solver."""

    def initial_refs(self, db: BreedingDB) -> list[PalRef]: ...


# ----------------------------------------------------------------------
# OwnedSource — Save Mode
# ----------------------------------------------------------------------
class OwnedSource:
    """Wraps owned-pal dicts (the ``PalSummary`` shape from ``GET /api/pals``).

    Accepts the raw dicts straight from ``world_service.list_pals`` — keys:
    ``character_id`` (species), ``gender`` ("Male"/"Female"/"Unknown"),
    ``passive_skills`` ([str, ...]), plus optional provenance
    (``instance_id``, ``nickname``, ``level``, ``owner_uid``, ...).
    """

    def __init__(self, pals: Iterable[dict]) -> None:
        self._pals = list(pals)

    def initial_refs(self, db: BreedingDB) -> list[PalRef]:
        refs: list[PalRef] = []
        for pal in self._pals:
            species = _normalize_species(pal.get("character_id"))
            if not species or not db.is_breedable(species):
                # Skip unbreedable entries (bosses, players, pals not in the
                # combo table — e.g. raid/predator pals with no breeding data).
                continue
            cid = pal.get("character_id", "")
            refs.append(
                PalRef(
                    species=species,
                    gender=Gender.coerce(pal.get("gender")),
                    passives=frozenset(_clean_passives(pal.get("passive_skills"))),
                    generation=0,
                    origin="owned",
                    provenance={
                        k: pal[k]
                        for k in ("instance_id", "nickname", "level", "owner_uid")
                        if pal.get(k) is not None
                    } | {"raw_character_id": cid},
                )
            )
        return refs


# ----------------------------------------------------------------------
# SelectedSource — Selection Mode
# ----------------------------------------------------------------------
class SelectedSource:
    """User-selected theoretical pals (``{species, gender?, passives?}``).

    ``gender`` omitted → WILDCARD (the solver may use the pal as either parent).
    Unbreedable species are dropped with a warning returned via ``.warnings``.
    """

    def __init__(self, selected: Iterable[dict]) -> None:
        self._selected = list(selected)
        self.warnings: list[str] = []

    def initial_refs(self, db: BreedingDB) -> list[PalRef]:
        refs: list[PalRef] = []
        for entry in self._selected:
            species = _normalize_species(entry.get("species"))
            if not species:
                continue
            if not db.is_breedable(species):
                self.warnings.append(f"{species!r} is not in the breeding table; skipped")
                continue
            refs.append(
                PalRef(
                    species=species,
                    gender=Gender.coerce(entry.get("gender")) if entry.get("gender") else Gender.WILDCARD,
                    passives=frozenset(_clean_passives(entry.get("passives"))),
                    generation=0,
                    origin="selected",
                )
            )
        return refs


# ----------------------------------------------------------------------
# WildSource — "go catch one" fallback
# ----------------------------------------------------------------------
class WildSource:
    """One WILDCARD ref per breedable species not already in the pool.

    Represents wild-caught pals. Optional — disabled by default (the user opts
    in). Cheap because wild refs have no passives, so they collapse into one
    group-key per species.
    """

    def __init__(self, *, exclude: Iterable[str] = ()) -> None:
        self._exclude = set(exclude)

    def initial_refs(self, db: BreedingDB) -> list[PalRef]:
        refs: list[PalRef] = []
        for tribe in db.breedable_tribes():
            if tribe in self._exclude:
                continue
            refs.append(
                PalRef(
                    species=tribe,
                    gender=Gender.WILDCARD,
                    passives=frozenset(),
                    generation=0,
                    origin="wild",
                )
            )
        return refs


# ----------------------------------------------------------------------
# CompositeSource — combine adapters (e.g. OwnedSource + WildSource)
# ----------------------------------------------------------------------
class CompositeSource:
    """Merge multiple adapters' refs. De-duplicates identical group keys."""

    def __init__(self, *adapters: SourceAdapter) -> None:
        self._adapters = adapters

    def initial_refs(self, db: BreedingDB) -> list[PalRef]:
        out: list[PalRef] = []
        seen: set[tuple] = set()
        for adapter in self._adapters:
            for ref in adapter.initial_refs(db):
                if ref.group_key() in seen:
                    continue
                seen.add(ref.group_key())
                out.append(ref)
        return out


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _normalize_species(raw: object) -> str:
    """Strip boss/predator prefixes so a save's CharacterID maps to its tribe.

    Saves encode boss pals as ``BOSS_Anubis``; the breeding table keys on the
    bare tribe ``Anubis``. Also trims whitespace. Returns "" for falsy input.
    """
    if not raw:
        return ""
    s = str(raw).strip()
    for prefix in ("BOSS_", "B_O_S_S_"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s


def _clean_passives(raw: object) -> list[str]:
    """Coerce a passive-skills field into a clean ``[str, ...]`` list."""
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(p).strip() for p in raw if p and str(p).strip()]
