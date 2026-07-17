# Round-Trip Validation Suite

Rigorous, automated integrity tests for the `palworld-save-tools` backend's
read → modify → rewrite pipeline. Designed to catch data degradation,
structural mutation, and cross-framework parity drift before they reach a real
save file.

    uv run python -m pytest tests/roundtrip/ -v

## What it checks

### 1. Pre-Flight Structural Validation (`conftest.py`)
Auto-discovers the corpus: `ref/sav/Level.sav`, `LevelMeta.sav`, and every
`ref/sav/Players/*.sav` (+ `*_dps.sav` dimensional-storage files). Each file
becomes a parametrized case — drop a new save into `ref/sav/` and it's covered.

### 2. Zero-Change Pass (`test_zero_change.py`) — `decode → encode` integrity
The strictest gate, with a **two-tier oracle**:

- **Tier 1 — Byte-exact**: `encode(decode(raw)) == raw`, byte for byte. Holds
  for the world `Level.sav` (PLZ / double-zlib), which the Rust uesave encoder
  reproduces exactly. Passes → strongest possible result.
- **Tier 2 — Semantic-equivalence**: when the compressor is non-deterministic
  (player saves use PLM / Oodle, whose recompression differs byte-wise), we
  re-decode the output and assert `decode(encode(decode(raw))) == decode(raw)`.
  A byte-difference with identical content is **skipped with a clear reason**
  (visible, not hidden); only a content drift is a failure.

Plus `test_encode_is_deterministic` (two consecutive encodes produce identical
bytes given the same input dict) and `test_save_type_detected` (every file
resolves to a known compression type — no silent GVAS fallback).

### 3. Mutation Loop + Re-Read Validation (`test_mutation.py`)
The corruption gate for edits. Per mutation case:
1. Capture a baseline + **witnesses** (a second pal's stats, total pal count,
   container count, player count — fields that must NOT change).
2. Apply an edit via the real `pal_service` mutator (IV, skills, work
   suitability, level, max-out).
3. Re-encode the mutated state → re-decode the encoded bytes.
4. Assert (a) the edit survived exactly, (b) every witness is byte-identical.

### 4. Cross-Framework Parity (`test_parity.py`)
Compares our fresh decode of `Level.sav` against the pre-baked ground truth at
`ref/json/Level.sav.json` (a prior decode by the same Rust uesave family). Three
checks: top-level structure (`root.properties.worldSaveData`), pal-count parity,
and field-level parity for a 50-pal sample (`CharacterID`, `Level`, talents,
`Gender`, `OwnerPlayerUId`, and the three skill arrays). Drift here means our
decode path diverged from the reference.

### 5. Edge Cases & Stress Bounds (`test_edge_cases.py`)
- **Container overflow**: moving a pal into a full 5-slot party container must
  not produce an out-of-range `SlotIndex`.
- **Move round-trip (orphan safety)**: move → encode → re-decode → the pal is
  at the new container AND linked in its `Slots[]` via `instance_id`.
- **Delete round-trip (residue safety)**: delete → encode → re-decode → the pal
  is gone from `CharacterSaveParameterMap` AND no container slot references it.
- **Corrupt-input rejection**: truncated, garbled, and empty inputs must not be
  silently accepted as valid saves (run in a subprocess to isolate panics).

## Findings the suite produced

These are real issues the suite surfaced during development — the tests now
gate against regressions on each:

1. **Player saves are not byte-exact round-trippable** (PLM/Oodle). The encoder
   is deterministic given a decoded dict, but recompression differs from the
   original bytes. The content is provably equivalent (`decode(out) == decode(raw)`),
   so Tier-2 is the correct gate. The 8 skips in a green run are this.
2. **Truncated input triggers a Rust panic** (`PanicException` via PyO3) rather
   than a clean Python exception. The panic IS a rejection (corrupt input isn't
   accepted), but it's a rough edge. The corrupt-input tests run in a subprocess
   so the panic can't destabilize the test process; a future hardening would
   catch this in the wrapper and raise a typed `SaveDecodeError`.
3. **`move_pal` originally wrote malformed container slots** — the `RawData_0`
   blob lacked the pal's `instance_id`, which would orphan the moved pal. The
   move round-trip test caught this; the fix is in `pal_service._container_add_pal`.

## Reporting schema (`report.py`)

Each test can emit a structured `Record`:

```json
{
  "file": "Level.sav",
  "category": "zero_change | mutation | parity | edge_case",
  "status":  "pass | fail | skip",
  "oracle":  "byte_exact | semantic | ground_truth",
  "detail":  "...",
  "drift":   { "field": "...", "expected": "...", "actual": "..." },
  "duration_ms": 123
}
```

`Report.write()` dumps the session's records to `.last-report.json` for CI
artifacts; `Report.summary()` renders a by-status / by-category table with any
failures and their drift detail. (The fixtures above use plain pytest
assertions; the `Report` class is available for a future structured-runner
harness that wants machine-readable output.)

## Green-run expectations

- `Level.sav` + `LevelMeta.sav`: byte-exact Tier-1 pass.
- Most `Players/*.sav`: Tier-2 semantic pass (skipped, byte-differs, equivalent).
- All mutation, parity, edge-case tests: pass.
- Skips are documented (corpus-specific: no full container, no editable pal)
  and never mask a failure.
