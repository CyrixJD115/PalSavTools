# AGENTS.md — PalworldSaveTools (PST)

## Quick start

```bash
start.cmd | start.sh | start.py          # root launchers → src/main.py
uv run src/main.py --web                 # launch WebUI (frontend + backend)
```

## Architecture

- **3-layer save pipeline**: SAV ↔ GVAS ↔ JSON via `palsav` engine (`src/palsav/`)
- **Global state**: `palworld_aio.constants` module globals; `GvasFileWrapper` wraps decoded save
- **All managers mutate in place** on `constants.loaded_level_json`
- **palsav is an installed workspace pkg** (`uv workspace`, editable). Do NOT import from `src/` directly
- **`web/frontend/` is the main GUI** — Svelte 5 + Tailwind SPA
- **`web/backend/` is the API layer** — thin FastAPI endpoints that call `src/` modules
- **`src/` is the source of truth** — all save-engine logic, managers, CLI tools, coord math; importable headlessly with zero Qt dependencies

## Critical gotchas

- **Triplicated reset block**: constants reset on load is copy-pasted in `src/palworld_aio/main.py` + `save_manager.py` + `reload_current_save`. Adding a global = edit all three.
- **CLI ≠ GUI decoding**: GUI uses `SKP_PALWORLD_CUSTOM_PROPERTIES` (6 no-op paths for speed). Full foliage/spawner edits require CLI.
- **Compression**: world saves → PLZ (double-zlib, type=50); others → PLM (Oodle, type=49). Checked via `'Pal.PalWorldSaveGame'` (note lowercase `w`).
- **Two save locations**: `constants.loaded_level_json` (Level.sav, deferred write) + per-player .sav files (written immediately).
- **i18n default**: `init_language()` falls back to `zh_CN`, not English.
- **`src/` NOT on `sys.path` in web context** — backend loads `map_data_service.py` via `importlib` to avoid shadowing the editable `palsav` install. `map_data_service.py` handles its own dependency imports (`coord`, `ContainerOwnership`) with try/except fallback.

## WebUI data model gotchas

- **StructProperty wrapper**: `BelongInfo`, `PlayerUId`, `GroupId`, and many other fields are wrapped in `{'struct_type': 'X', 'struct_id': UUID, 'id': None, 'value': ACTUAL_DATA, 'type': 'StructProperty'}`. The `_u()` helper auto-unwraps them via `len(cur) <= 5` check — **not** `<= 4`, because StructProperty dicts have 5 keys. Changing this threshold is the most common cause of "owner=None / guild=None" bugs.
- **`MapObjectId` location**: In `MapObjectSaveData` entries, the map object type identifier (`ItemChest_04`, `PalBooth`, etc.) is at the **top level**: `obj['MapObjectId']['value']`. NOT inside `Model.RawData.value`. Reading from the wrong path → all types show "Unknown".
- **Container key format**: `ItemContainerSaveData` entry keys are StructProperty dicts `{ID: {struct_type: 'Guid', value: UUID('...')}}`. Use `_extract_id()` (extracts UUID string) and `_s()` (normalizes for comparison) — never `str(dict)`.
- **Container BelongInfo access**: `BelongInfo` is a `PalItemContainerBelongInfo` StructProperty. The inner dict `value` contains `GroupId` and `PlayerUId` fields, which are themselves GUID StructProperty wrappers. Three levels of wrapping.
- **Save entries are heterogeneous**: The first ~500 `ItemContainerSaveData` entries are typically internal/engine containers (player inventories, guild chests). Map-object-backed containers (Booth, Chest, Mining Pit, etc.) start appearing at index 500+. Don't assume the start of the list is representative.
- **`_s()` vs `_extract_id()`**: `_s()` strips dashes and lowercases (for map-key comparison), `_extract_id()` preserves UUID format with dashes (for display/URL). A bug in one but not the other causes all types/locations to show "Unknown" despite matching correctly.
- **Container type classification**: `_classify_container()` handles 40+ map object types via case-insensitive substring matching. Falls back to "Unknown". The classification chain is: `MapObjectId` → `_classify_container()` → type badge in frontend.
- **Container list performance**: 10,000+ containers is common. The backend builds the map-object index + guild names in parallel threads (`ThreadPoolExecutor(max_workers=2)`), then slices `entries[offset:offset+limit]` so only the requested page is enriched. Never iterate all entries just to serve one page.
- **Pagination contract**: `GET /api/containers?offset=0&limit=1000` returns `{containers: [...], total: N, has_more: bool}`. Frontend loads in 1000-item chunks, appends to existing array. IntersectionObserver triggers auto-load 200px before bottom.

## Build

| Target | Command | Output |
|---|---|---|---|
| Standalone binary | `uv run python build/nuitka/build_nuitka.py --onefile` | `dist/` |
| Tauri desktop app | `python build/tauri/build_tauri.py` | `web/frontend/src-tauri/target/release/` |

CI (5 workflows) builds Nuitka binaries.

## OpenCode config (`.opencode/`)

- `instructions` (auto-loaded): `AGENTS.md` + `memory.md`
- Skills in `.opencode/skills/<name>/SKILL.md` — load via `skill({ name: "pst-*" })`
- Plugins in `.opencode/plugins/` — auto-discovered, no config entry needed
- Config is `.jsonc` (JSON with Comments); merges across global/project dirs

## Source layout

```
src/
  palsav/               # SERIALIZATION ENGINE (workspace pkg, editable)
  palworld_aio/         # Business logic: managers/, inventory/, map/, validation/
  coord/                # Coordinate transforms (was palworld_coord)
  toolsets/             # CLI tools (9) (was palworld_toolsets)
  xgp_import/           # Xbox Game Pass import pipeline (was palworld_xgp_import)
  main.py               # Bootstrap entry (venv + dep check + launch)
  boot_paths.py         # Path constants
  common.py             # Shared utilities
  path_setup.py         # Python path setup
  resource_resolver.py  # Asset path resolution
web/
  frontend/             # Svelte 5 + Tailwind SPA (:16920) — MAIN GUI
  backend/              # FastAPI API layer (:16921) — thin bridge to src/
  .web_ref/             # scraped Reflex app — VISUAL REFERENCE ONLY (do not copy logic)
```

## WebUI build contract

The web layer is **strictly decoupled**: `web/frontend` (Svelte 5 + Tailwind) is the **primary GUI**; `web/backend` (FastAPI) is a *thin API layer* that bridges to the core project. Rules (full detail: `pst-webui-build` skill; existing inventory: `pst-webui` skill):

- **Wrap, don't rewrite** — ALL real logic lives in `src/` (palsav, palworld_aio, coord, toolsets, xgp_import). Backend endpoints = validate → call `src/` → serialize; no domain math in `web/backend/`.
- **New capabilities → add to `src/` first**, then expose via one thin endpoint in `web/backend/`.
- **`web/backend/services/` loads `src/` modules via `importlib`** (not `sys.path`), because the editable `palsav` workspace install shadows `src/`. Service modules that need to be cross-loaded use try/except → `importlib` fallback (see `map_data_service.py`).
- **`web/frontend/` is the main GUI** — all user interaction happens here. The old PySide6 desktop GUI (`src/palworld_aio/ui/`) has been deleted.
- **REST + WebSocket boundary** — frontend only talks via `/api` and `/ws`; Pydantic schemas (`web/backend/schemas.py`) mirror TS types (`web/frontend/src/types`) — change both together.
- **Launchers**: `start.cmd` (Windows), `start.sh` (Unix), `start.py` (cross-platform) — all delegate to `src/main.py --web`.

## Repo exclusions

`.venv/`, `dist/`, `build/`, `Backups/`, `*.sav`, `*.savc`, `*.7z`, `uv.lock` — all gitignored.

## Reference projects (sibling repos — READ-ONLY inspiration)

These live **outside** PalSavTools and are used only as reference for features, bug fixes, and parsing approaches. They are NOT dependencies and should NOT be imported or copied wholesale — study them, then implement in PalSavTools' own architecture (`src/` first, thin `web/backend/` bridge, `web/frontend/` GUI).

| Project | Stack | Path | Use for |
|---|---|---|---|
| PalworldSaveTools (legacy) | Python + PySide6 | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PST/` | The original desktop GUI this project evolved from; Qt-based manager patterns |
| PalworldSavePals (Python) | Python + Svelte | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PSP/psp_python/` | Alt Python save tool; Python-side parsing/logic reference |
| PalworldSavePals (Rust) | Rust + Svelte | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PSP/psp_rust/` | Alt Rust save tool; fast parser reference, cross-check struct layouts |
| PalSav Parser | Python + Rust | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PalSav Parser/` | Standalone save parsers in both langs; ground truth for SAV/GVAS struct decoding |

**When referencing:** confirm struct layouts/offsets against PalSavTools' own `src/palsav/` engine before trusting external parsers — formats drift between projects.
