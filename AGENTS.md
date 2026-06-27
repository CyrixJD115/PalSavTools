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
- **Compression**: world saves → PLZ (double-zlib, type=50); others → PLM (Oodle, type=49). Checked via `'Pal.PalworldSaveGame'` (note lowercase `w`).
- **Two save locations**: `constants.loaded_level_json` (Level.sav, deferred write) + per-player .sav files (written immediately).
- **i18n default**: `init_language()` falls back to `zh_CN`, not English.
- **`src/` NOT on `sys.path` in web context** — backend loads `map_data_service.py` via `importlib` to avoid shadowing the editable `palsav` install. `map_data_service.py` handles its own dependency imports (`coord`, `ContainerOwnership`) with try/except fallback.

## Build

| Target | Command | Output |
|---|---|---|
| Release binary | `uv run python build/nuitka/build_nuitka.py --onefile` | `dist/` |
| Windows installer | `uv run python build/cx_freeze/build_cx.py` | `PST_standalone/` |

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
