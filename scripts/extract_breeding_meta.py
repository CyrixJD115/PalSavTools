#!/usr/bin/env python3
"""One-off generator: build the slim breeding metadata files from palcalc's data.

Outputs two JSONs into ``src/_resources/game_data/``:

* ``breeding_meta.json``  — per-pal gender probability + breedable-gender class
  + localized display names. Keys are PST tribe names (the breeding combo
  identifier). Pals absent from palcalc fall back to ``{male:0.5,female:0.5}``
  and ``BOTH`` so the solver still runs.
* ``breeding_distance.json`` — palcalc's precomputed ``MinBreedingSteps``
  (shortest breeding chain length between any two pals). Powers the solver's
  reachability prune.

The combo table itself (``breeding.json``) is copied verbatim from the legacy
PST project — see ``copy_breeding_data`` below or just copy the file by hand.

Run::

    uv run python scripts/extract_breeding_meta.py

This script is idempotent; re-running regenerates the same output. It is NOT
imported at runtime — the backend just reads the emitted JSONs.

Manual alignment notes (verified once, July 2026):
  * PST pal_info has 304 tribes; palcalc has 299 ``InternalName``s.
  * 297 exact-match. 7 PST-only are newer pals absent from this palcalc
    snapshot (BlackFurDragon, CandleWitch, ElecLion, ...). 2 palcalc-only are
    spelling variants (BluePlatypus vs Blueplatypus) handled by the
    case-insensitive alias map below.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "src" / "_resources" / "game_data"

# External references — absolute paths from the workspace root.
PST_LEGACY = Path("/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PST")
PALCALC = Path("/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/Other Tools/palcalc")

PST_BREEDING = PST_LEGACY / "resources" / "game_data" / "breedingdata.json"
PALCALC_DB = PALCALC / "PalCalc.Model" / "db.json"
PALCALC_BREEDING = PALCALC / "PalCalc.Model" / "breeding.json"


def _load(path: Path) -> object:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_alias_map(pst_tribes: set[str], pcalc_names: set[str]) -> dict[str, str]:
    """Map a PST tribe -> the palcalc InternalName that refers to the same pal.

    Exact match first, then case-insensitive match for spelling-variant drift
    (e.g. ``Blueplatypus`` vs ``BluePlatypus``). Pals with no match are simply
    omitted — the loader falls back to defaults for them.
    """
    alias: dict[str, str] = {}
    lower = {n.lower(): n for n in pcalc_names}
    for tribe in pst_tribes:
        if tribe in pcalc_names:
            alias[tribe] = tribe
        elif tribe.lower() in lower:
            alias[tribe] = lower[tribe.lower()]
    return alias


def classify_breedable_gender(prob: dict[str, float]) -> str:
    """Collapse a gender-probability dict into a coarse class.

    ``MALE_ONLY`` / ``FEMALE_ONLY`` when the other gender has probability 0;
    otherwise ``BOTH``. (palcalc has no truly genderless breedable pal.)
    """
    male = prob.get("MALE", 0.0)
    female = prob.get("FEMALE", 0.0)
    if male <= 0 and female > 0:
        return "FEMALE_ONLY"
    if female <= 0 and male > 0:
        return "MALE_ONLY"
    return "BOTH"


def build_breeding_meta(
    pst_data: dict, db: dict, alias: dict[str, str]
) -> tuple[dict, list[str]]:
    """Emit ``breeding_meta.json`` content + a list of warnings."""
    pcalc_by_name = {p["InternalName"]: p for p in db["Pals"]}
    gender_prob_src = db["BreedingGenderProbability"]

    tribes = list(pst_data["pal_info"].keys())
    gender_prob: dict[str, dict[str, float]] = {}
    breedable_genders: dict[str, str] = {}
    display_names: dict[str, str] = {}
    warnings: list[str] = []

    for tribe in tribes:
        pc_name = alias.get(tribe)
        if pc_name is None or pc_name not in gender_prob_src:
            if pc_name is None:
                warnings.append(f"no palcalc match for tribe {tribe!r} — using default 50/50 gender")
            prob = {"male": 0.5, "female": 0.5}
        else:
            raw = gender_prob_src[pc_name]
            prob = {"male": float(raw.get("MALE", 0.0)), "female": float(raw.get("FEMALE", 0.0))}
        gender_prob[tribe] = prob
        breedable_genders[tribe] = classify_breedable_gender(
            {"MALE": prob["male"], "FEMALE": prob["female"]}
        )

        # Prefer palcalc's English localization (most up-to-date), fall back to
        # the name already baked into PST's pal_info.
        pal_obj = pcalc_by_name.get(pc_name) if pc_name else None
        loc = pal_obj.get("LocalizedNames") if pal_obj else None
        en = (loc or {}).get("en") if isinstance(loc, dict) else None
        display_names[tribe] = en or pst_data["pal_info"][tribe].get("name", tribe)

    return {
        "gender_prob": gender_prob,
        "breedable_genders": breedable_genders,
        "display_names": display_names,
    }, warnings


def build_breeding_distance(
    pst_data: dict, breeding: dict, alias: dict[str, str]
) -> tuple[dict, list[str]]:
    """Emit ``breeding_distance.json`` keyed by PST tribe names.

    The precomputed map from palcalc is keyed by palcalc ``InternalName``; we
    re-key both axes to PST tribes via the alias map. Any tribe without a
    palcalc counterpart is simply absent from the map (the solver treats
    unknown distances as "unreachable within budget" unless the start == target).
    """
    src = breeding["MinBreedingSteps"]
    out: dict[str, dict[str, int]] = {}
    warnings: list[str] = []

    # Build a reverse alias so we know which palcalc name maps back to a tribe.
    pc_to_tribe = {pc: tribe for tribe, pc in alias.items()}

    for tribe_a, pc_a in alias.items():
        row = src.get(pc_a)
        if not row:
            continue
        out_row: dict[str, int] = {}
        for pc_b, steps in row.items():
            tribe_b = pc_to_tribe.get(pc_b)
            if tribe_b is None:
                continue
            out_row[tribe_b] = int(steps)
        out[tribe_a] = out_row

    missing = sorted(set(pst_data["pal_info"]) - set(out))
    if missing:
        warnings.append(
            f"{len(missing)} tribes have no distance data (absent from palcalc): "
            + ", ".join(missing)
        )
    return out, warnings


def copy_breeding_data(pst_data: dict) -> None:
    """Write the slimmed ``breeding.json`` from the legacy PST source.

    Drops ``parent_to_children_formula`` (partial/buggy per the exploration
    report — only 44 of 304 parents indexed) and ``child_to_parents_ignore``
    (derivable at load time). Keeps the three authoritative sections.
    """
    slim = {
        "pal_info": pst_data["pal_info"],
        "unique_combos": pst_data["unique_combos"],
        "child_to_parents_formula": pst_data["child_to_parents_formula"],
        "child_to_parents_unique": pst_data.get("child_to_parents_unique", {}),
    }
    out_path = OUT_DIR / "breeding.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(slim, fh, ensure_ascii=False, separators=(",", ":"))
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  wrote {out_path.relative_to(REPO_ROOT)} ({size_mb:.1f} MB)")
    print(
        f"    pal_info={len(slim['pal_info'])}, "
        f"unique_combos={len(slim['unique_combos'])}, "
        f"formula_children={len(slim['child_to_parents_formula'])}, "
        f"unique_children={len(slim['child_to_parents_unique'])}"
    )


def main() -> int:
    print("Loading source data...")
    pst_data = _load(PST_BREEDING)
    db = _load(PALCALC_DB)
    breeding = _load(PALCALC_BREEDING)

    pst_tribes = set(pst_data["pal_info"].keys())
    pcalc_names = {p["InternalName"] for p in db["Pals"]}
    alias = build_alias_map(pst_tribes, pcalc_names)
    print(
        f"  alias map: {len(alias)}/{len(pst_tribes)} PST tribes matched to a "
        f"palcalc InternalName"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/3] breeding.json (from PST, slimmed)...")
    copy_breeding_data(pst_data)

    print("\n[2/3] breeding_meta.json (gender + names, from palcalc db.json)...")
    meta, meta_warns = build_breeding_meta(pst_data, db, alias)
    meta_path = OUT_DIR / "breeding_meta.json"
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, separators=(",", ":"))
    size_kb = meta_path.stat().st_size / 1024
    print(f"  wrote {meta_path.relative_to(REPO_ROOT)} ({size_kb:.1f} KB)")
    print(
        f"    gender_prob entries={len(meta['gender_prob'])}, "
        f"display_names={len(meta['display_names'])}"
    )
    for w in meta_warns:
        print(f"    [warn] {w}")

    print("\n[3/3] breeding_distance.json (MinBreedingSteps, from palcalc)...")
    dist, dist_warns = build_breeding_distance(pst_data, breeding, alias)
    dist_path = OUT_DIR / "breeding_distance.json"
    with dist_path.open("w", encoding="utf-8") as fh:
        json.dump(dist, fh, ensure_ascii=False, separators=(",", ":"))
    size_kb = dist_path.stat().st_size / 1024
    print(f"  wrote {dist_path.relative_to(REPO_ROOT)} ({size_kb:.1f} KB)")
    print(f"    tribes with distance data={len(dist)}")
    for w in dist_warns:
        print(f"    [warn] {w}")

    print("\nDone. 3 files written to", OUT_DIR.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
