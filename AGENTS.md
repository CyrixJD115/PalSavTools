# AGENTS.md — PalworldSaveTools (PST)

## Quick start

```bash
start.cmd | start.sh | start.py          # root launchers → src/main.py
uv run src/main.py --web                 # launch WebUI (frontend + backend)
```

## Architecture

### Save engine (Rust, `src/palsav-rs/`)

The **runtime parser is Rust** via the PyO3 module `uesave_pyo3` (`src/palsav-rs/uesave_pyo3/`). It provides a `SaveHandle` class that holds the decoded save **in Rust memory** — cheap to keep resident. Fallback: subprocess CLI (`src/palsav-rs/target/release/uesave`).

Key API on `SaveHandle`:
- `parse_save(data)` → `SaveHandle` — cheap, holds save in Rust memory
- `handle.to_json()` → `str` — full JSON string (one Python allocation, not the object tree)
- `handle.section_json(name)` → `str` — one `worldSaveData` section as JSON (lazy)
- `handle.sections()` → `list[str]` — bare section names
- `handle.encode()` → `bytes` — re-serialize without JSON roundtrip

The Python `src/palsav/` engine is **unused at runtime** in the WebUI; it exists only as an editable workspace package for the legacy CLI/headless path.

### WebUI backend (`app/backend/`)

**FastAPI + thin services** — no domain math lives here. Endpoints validate → call `app/backend/services/` → serialize. Services are **pure functions** taking a `level_dict` (or a `wsd` slice), never holding per-instance state.

### WebUI frontend (`app/frontend/`)

**Svelte 5 + Tailwind SPA** — the main GUI. Communicates with the backend via `/api` (REST) and `/ws` (WebSocket). Pydantic schemas (`app/backend/schemas.py`) mirror TS types (`app/frontend/src/types/index.ts`) — change both together.

### State model (`app/backend/state.py`)

A single `save_state` singleton wraps a `LoadedSave | None`. `LoadedSave` holds:

| Field | Role |
|---|---|
| `handle: SaveHandle` | **Source of truth** — Rust-side, cheap |
| `_level_dict` | Full Python dict (~200 MB for a 2 MB world save). **Never touched unless a mutation needs it.** |
| `_sections: OrderedDict` | LRU cache of materialized `worldSaveData` sections (cap `_SECTION_LRU_MAX = 8`). Evicted sections are freed; re-access re-decodes from the handle. |
| `player_savs: OrderedDict` | LRU cache of decoded per-player `.sav` dicts (cap `_PLAYER_LRU_MAX = 16`). |
| `player_pal_counts / player_levels / player_positions` | Pre-computed at load from `CharacterSaveParameterMap` only. |

**Critical rule: never access `loaded.level_dict` unless you need mutations.** Read-only endpoints use:
- `loaded.build_mini_wsd("SectionName", ...)` — builds a tiny `worldSaveData`-like dict containing only the requested sections (~3 MB vs ~200 MB).
- `loaded.get_section("SectionName")` — returns one section from the LRU cache.

**Violating this rule is the #1 cause of memory bloats and crashes.** See "Map & Breeding memory trap" below.

## Storage modes (`app/backend/state.py`)

`LoadedSave.storage_mode` controls where the decoded save data lives:

- **`"memory"` (default, recommended)** — The existing model. Rust `SaveHandle` + lazy LRU sections. Fastest performance for all save sizes. **Recommended even for very large saves** — the lazy architecture already bounds RAM.
- **`"disk"`** — On load, the full decoded JSON is written to a temp file (`pst-disk-cache-*.json` in the OS temp dir) via `handle.to_json()` **without materializing the Python dict tree**. The Rust handle is still used for reads (`section_json`). The full dict only materializes on first mutation. Intended as a low-memory fallback for ≤8 GB RAM machines.

Switch via Settings → Storage card, or via the large-save warning modal (triggered on browser uploads above `PST_WEB_LARGE_SAVE_MB`, default 50 MB). Configured server-side via env vars:
- `PST_WEB_STORAGE_MODE` — default `"memory"`
- `PST_WEB_LARGE_SAVE_MB` — default `50`

### Pre-warm (`app/backend/services/load_progress.py`)

Opt-in (Settings → "Pre-warm all sections at load"): sequentially materializes every `worldSaveData` section, runs `gc.collect()` between each, and reports stage progress over WS. Off by default — the existing lazy approach is preferred.

### Disk-cache cleanup

On every `SaveState.clear()` and `SaveState.set()`: `_sync_level_dict_to_disk` writes any mutated dict back to the temp file, then `cleanup()` unlinks it. On app startup, `_sweep_stale_cache_files()` removes orphaned `pst-disk-cache-*.json` files from the OS temp dir.

## WebSocket progress (`/ws`)

The `/ws` endpoint is wired in `app/backend/app.py`. The `WsManager` (`app/backend/ws_manager.py`) broadcasts JSON payloads:

| `type` | `payload` shape | When |
|---|---|---|
| `"save_state"` / `"save_update"` | `{}` | Save loaded/unloaded (triggers frontend to refetch `/api/save/state`) |
| `"load_progress"` | `{stage, current, total, section}` | During load: `parse` → `precompute` → optional `prewarm` → `done` |

The frontend `LoadingOverlay.svelte` displays a real progress bar + section name when `load_progress` events arrive; falls back to the indeterminate spinner otherwise.

## Critical gotchas

### Memory: the `loaded.level_dict` trap

**Calling `loaded.level_dict` materializes the full ~200 MB Python dict tree.** This is the #1 cause of OOM crashes. Always prefer:
- `loaded.build_mini_wsd("SectionName")` — for one or two sections
- `loaded.get_section("SectionName")` — for a single section
- `loaded.handle.section_json("Name")` — for a raw JSON string without Python object overhead

**Map & Breeding memory trap**: The map route and the breeding calculator (Save Mode) both historically called `loaded.level_dict`. Fixed — they now use `build_mini_wsd` with only the sections they need. Any new endpoint that touches the save should follow the same pattern.

### Directory naming

The WebUI lives in `app/`, not `web/` (the `web/` directories were renamed). All paths are `app/backend/...` and `app/frontend/...`.

### Rust parser vs Python palsav

The runtime parser is `uesave_pyo3` from `src/palsav-rs/` (Rust). The Python `src/palsav/` is **unused by the WebUI** — it's a workspace package for the legacy CLI/headless path. The AGENTS.md lines about "3-layer SAV ↔ GVAS ↔ JSON pipeline via palsav" describe the old Python path.

### Triplicated reset block (legacy CLI only)

Does **not** exist in the WebUI. The WebUI backend has a single `save_state` singleton with `clear()`. The triplication (`main.py` + `save_manager.py` + `reload_current_save`) is in the legacy `src/palworld_aio/` CLI path and does not affect `app/backend/`.

### Upload flow

- **Browser**: only `.zip`/`.7z` bundles (bare `Level.sav` rejected — can't carry the `Players/` folder via browser upload).
- **Tauri/desktop**: only `Level.sav` paths (archives rejected — Tauri provides OS-level file paths, not bytes).
- Both paths accept `storage_mode` + `prewarm` params (FormData for upload, JSON body for path-load).

### Container list architecture

- `GET /api/containers?offset=0&limit=1000` returns paginated results. Frontend loads in 1000-item chunks via IntersectionObserver (200px preload margin).
- ThreadPoolExecutor(max_workers=2) builds map-object index + guild names in parallel, then slices for the requested page.
- The first ~500 `ItemContainerSaveData` entries are internal/engine containers; map-object-backed containers start at index 500+.

### Storage-mode warning modal

On browser uploads, if `file.size > largeThresholdMb` (default 50), a `StorageModeWarning.svelte` modal appears recommending In-Memory mode. Disk mode is available as a fallback. The user's preference is persisted in localStorage (`stores/settings.ts`, key `pst:settings`) and visible in Settings → Storage.

### Settings persistence

Frontend settings (storage mode, prewarm toggle, threshold) are persisted in `localStorage` via `app/frontend/src/stores/settings.ts`. No backend settings endpoint — localStorage is sufficient.

### i18n

Flat dot-notation keys in `src/_resources/i18n_web/en_US.json`. The catalog is seeded at build time into the `i18n` store to prevent FOUC. Language selection persists via `localStorage` under `pst-lang`.

### WS-manager state

The `/ws` endpoint is a simple push-only channel. No client→server messages are processed (the backend only calls `receive_text()` to keep the connection open). All state mutations go through REST endpoints.

## Build

| Target | Command | Output |
|---|---|---|
| Standalone binary | `uv run python build/nuitka/build_nuitka.py --onefile` | `dist/` |
| Tauri desktop app | `python build/tauri/build_tauri.py` | `app/frontend/src-tauri/target/release/` |

CI (5 workflows) builds Nuitka binaries.

## Source layout

```
src/
  palsav/               # SERIALIZATION ENGINE (workspace pkg, editable; UNUSED by WebUI)
  palsav-rs/            # ACTUAL RUNTIME PARSER — Rust (uesave + PyO3)
  palworld_aio/         # Legacy CLI/headless path (managers/, inventory/, map/, validation/)
  coord/                # Coordinate transforms (was palworld_coord)
  toolsets/             # CLI tools (9) (was palworld_toolsets)
  xgp_import/           # Xbox Game Pass import pipeline
  main.py               # Bootstrap entry (venv + dep check + launch)
  boot_paths.py, common.py, path_setup.py, resource_resolver.py
app/
  backend/              # FastAPI API layer (:16921) — thin bridge to src/
    routes/             #   FastAPI route handlers
    services/           #   Pure-function service modules (no per-instance state)
    app.py              #   Application factory
    state.py            #   LoadedSave + SaveState (singleton save state)
    config.py           #   Env-var-based settings (PST_WEB_*)
    schemas.py          #   Pydantic models (mirrors app/frontend/src/types/index.ts)
    ws_manager.py       #   WebSocket broadcast manager
  frontend/             # Svelte 5 + Tailwind SPA (:16920) — MAIN GUI
    src/
      routes/           #   SvelteKit page routes
      stores/           #   Svelte stores (saveState, settings, zones, mapStore, …)
      lib/
        api/            #     client.ts — typed fetch wrapper
        components/     #     Svelte components (ui/, layout/, map/, load/, …)
        map/            #     MapCanvas, MapEngine, MapConfig
        utils/          #     infiniteScroll.ts, …
      types/            #   TS interfaces mirroring backend schemas
  .web_ref/             # Scraped Reflex app — VISUAL REFERENCE ONLY (do not copy)
```

## WebUI build contract

The web layer is **strictly decoupled**: `app/frontend` (Svelte 5 + Tailwind) is the **primary GUI**; `app/backend` (FastAPI) is a *thin API layer* that bridges to the core project.

- **Wrap, don't rewrite** — ALL real logic lives in `src/` (palsav-rs, palworld_aio, coord, toolsets, xgp_import). Backend endpoints = validate → call `app/backend/services/` → serialize; no domain math in `app/backend/`.
- **New capabilities → add to `src/` first**, then expose via one thin endpoint in `app/backend/`.
- **`app/backend/services/` loads `src/` modules via `importlib`** where needed (e.g., `map_data_service.py`, `breeding_service.py`), because the editable `palsav` workspace install shadows `src/`.
- **REST + WebSocket boundary** — frontend only talks via `/api` and `/ws`; Pydantic schemas mirror TS types — change both together.
- **Memory-efficient reads** — always use `build_mini_wsd()` or `get_section()` over `loaded.level_dict` (see Memory trap above).

## Repo exclusions

`.venv/`, `dist/`, `build/`, `Backups/`, `*.sav`, `*.savc`, `*.7z`, `uv.lock` — all gitignored.

## Reference projects (sibling repos — READ-ONLY inspiration)

These live **outside** PalSavTools and are used only as reference for features, bug fixes, and parsing approaches. They are NOT dependencies and should NOT be imported or copied wholesale — study them, then implement in PalSavTools' own architecture (`src/` first, thin `app/backend/` bridge, `app/frontend/` GUI).

| Project | Stack | Path | Use for |
|---|---|---|---|
| PalworldSaveTools (legacy) | Python + PySide6 | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PST/` | The original desktop GUI this project evolved from; Qt-based manager patterns |
| PalworldSavePals (Python) | Python + Svelte | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PSP/psp_python/` | Alt Python save tool; Python-side parsing/logic reference |
| PalworldSavePals (Rust) | Rust + Svelte | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PSP/psp_rust/` | Alt Rust save tool; fast parser reference, cross-check struct layouts |
| PalSav Parser | Python + Rust | `/mnt/dev/Dev/Coding_Projects/PalworldSaveTools/PalSav Parser/` | Standalone save parsers in both langs; ground truth for SAV/GVAS struct decoding |

**When referencing:** confirm struct layouts/offsets against PalSavTools' own `src/palsav-rs/` engine before trusting external parsers — formats drift between projects.
