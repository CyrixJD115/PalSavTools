# Todo — Architecture & Maintainability

Score: **7 / 10** &nbsp;|&nbsp; Tracked items below would move the needle to **8.5+**.

---

## Priority 1 — Do next (next 3 months)

### 1.1 Break up `tool_service.py` into a module

`app/backend/services/tool_service.py` (1,662 lines) wraps 10+ distinct tools in one file. Each tool
is a separate domain with its own schema, walk logic, and edge cases.

- [ ] Create `app/backend/services/tools/` directory
- [ ] Extract each tool into its own file (e.g. `tools/slot_injector.py`, `tools/fix_host_save.py`,
      `tools/character_transfer.py`, `tools/convert_generic.py`, `tools/convert_ids.py`, etc.)
- [ ] Keep existing function signatures as the public API so `routes/tools.py` doesn't change
- [ ] Verify all tool endpoints still work via integration tests

*ponytail:* Break at tool #11; one file per tool keeps the cost of adding a new tool at one file.

### 1.2 Remove / archive legacy dead code

`src/palworld_aio/` (~14,000 lines) is explicitly unused by the WebUI. Keeping it confuses
newcomers and wastes mental bandwidth.

- [ ] Decide: is the legacy CLI/headless path (`src/main.py` → `src/palworld_aio/`) still supported?
      - **If yes**: add a `DEPRECATED.md` notice to the directory and pin a removal version.
      - **If no**: move `src/palworld_aio/`, `src/palsav/` (the Python engine), `src/palobject.py`,
        `src/loading_manager.py`, `src/path_setup.py` to `archive/` at repo root, or delete outright.
- [ ] Remove `src/main.py` → `src/palworld_aio/` launcher bootstraps if unused
- [ ] Remove `src/palobject.py`, `src/loading_manager.py`, `src/path_setup.py` if nothing imports them

### 1.3 Add API versioning

Without a version prefix, a breaking backend change (newer uesave output shape, renamed fields)
silently breaks the frontend with no migration path.

- [ ] Move routes under `/api/v1/` (e.g. `/api/v1/save/state`)
- [ ] Keep `/api/...` as a deprecated alias or redirect
- [ ] Update `app/frontend/src/lib/api/client.ts` to target `/api/v1/`

*Minimum viable:* just the prefix. No content negotiation or header-based versioning.

### 1.4 Write integration tests for uncovered critical paths

The backend has 3 integration test files — the export, upload, disk-mode, and breeding-chain
paths have zero coverage.

- [ ] `tests/integration/test_export.py` — load a fixture save, export, verify roundtrip
- [ ] `tests/integration/test_upload.py` — bundle-upload flow with `.zip` and `.7z`
- [ ] `tests/integration/test_disk_mode.py` — load with `storage_mode="disk"`, verify temp file
- [ ] `tests/integration/test_prewarm.py` — load with `prewarm=True`, verify WS progress events
- [ ] `tests/integration/test_mutation.py` — edit a pal, export, verify byte-diff is sane

*ponytail:* Write these before the next Palworld update changes the save format again.

---

## Priority 2 — Do within the next 12 months

### 2.1 Split the largest service files along domain lines

| File | Lines | Suggested split |
|---|---|---|
| `pal_service.py` | 1,403 | `pal_reader.py` + `pal_editor.py` |
| `player_service.py` | 934 | `player_detail.py` + `player_editor.py` |
| `world_service.py` | 692 | `dict_helpers.py` + `world_queries.py` |

- [ ] Extract read-only query functions from `pal_service.py` into `pal_reader.py`
- [ ] Extract mutation + preset functions into `pal_editor.py`
- [ ] Same pattern for `player_service.py`
- [ ] Pull generic dict-navigation helpers (`_k`, `_g`, `_k_set`, `_map_entries`) from
      `world_service.py` into `dict_helpers.py`

### 2.2 Refactor `routes/save.py` — move internal helpers out

`save.py` (367 lines) contains internal helpers (`_build_loaded`, `_counts_from_handle`,
`_load_bundle`, progress callback builders) that blur the route/service boundary.

- [ ] Move `_build_loaded` → `services/save_service.py` or a new `services/load_service.py`
- [ ] Move `_counts_from_handle` → `services/world_service.py`
- [ ] Move `_load_bundle` → `services/archive_service.py`

### 2.3 Make mutation paths lazy

Every mutation currently materializes the full ~200 MB `level_dict`. For a load-edit-export
workflow this is wasted cost.

- [ ] Investigate: can `get_section()` support write-through that re-encodes only the changed
      section into the Rust handle?
- [ ] Investigate: alternative — mutations operate on an individual section dict, merged into the
      handle only at export time.
- [ ] Document the chosen path in `state.py` and `AGENTS.md`

*ponytail:* Implement when someone opens a performance bug on export time with 80 MB saves.

### 2.4 Clean up dual i18n

`src/_resources/i18n/` (desktop CLI, 1,927 strings) + `src/_resources/i18n_web/` (WebUI).
If the CLI path is dead, remove it.

- [ ] Confirm whether `src/_resources/i18n/` is imported by anything
- [ ] If unused: remove directory; update `paths.py` and `AGENTS.md`
- [ ] If still needed: add an `I18N_LEGACY_DIR` note to `paths.py` so the two are explicitly
      documented rather than silently coexisting

---

## Priority 3 — Stretch / watch

- [ ] **Benchmark the `5,237-line lib.rs`** — this is the vendored uesave library. If the project
      forks it (adds Palworld-specific patches), the surface area is risky. Monitor diff count per
      release.
- [ ] **Add a test template** — a `tests/integration/test_template.py` that a new developer can
      copy-paste when adding a new endpoint.
- [ ] **Deduplicate tool logic** — `app/backend/services/tool_service.py` and `src/toolsets/`
      appear to implement similar transformations. Validate they converge or pick one.
- [ ] **Remove `uv.lock` from `.gitignore`** — reproducible dependency resolution matters for
      CI and for contributors. Consider checking it in.

---

## Legend

- `ponytail:` = deliberate simplification with a documented ceiling. Add when conditions are met.
- `[ ]` = tracked task
- **Bold** = structural decision needed before work starts