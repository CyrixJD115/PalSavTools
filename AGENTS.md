# AGENTS.md — PalworldSaveTools (PST)

## Quick start

```bash
uv run start.py                          # app entry (bootstraps venv)
source .venv/bin/activate                # activate venv directly
```

## Commands

```bash
uv run start.py                          # app entry (bootstraps venv)
source .venv/bin/activate                # activate venv directly
```

## Architecture

- **3-layer save pipeline**: SAV ↔ GVAS ↔ JSON via `palsav` engine (`src/palsav/`)
- **Global state**: `palworld_aio.constants` module globals; `GvasFileWrapper` wraps decoded save
- **All managers mutate in place** on `constants.loaded_level_json`
- **palsav is an installed workspace pkg** (`uv workspace`, editable). Do NOT import from `src/` directly
- **10 flat files** in `src/` (boot, path, qt, i18n, etc.) + 6 packages

## Critical gotchas

- **Triplicated reset block**: constants reset on load is copy-pasted in `main.py` + `save_manager.py` + `reload_current_save`. Adding a global = edit all three.
- **CLI ≠ GUI decoding**: GUI uses `SKP_PALWORLD_CUSTOM_PROPERTIES` (6 no-op paths for speed). Full foliage/spawner edits require CLI.
- **Compression**: world saves → PLZ (double-zlib, type=50); others → PLM (Oodle, type=49). Checked via `'Pal.PalworldSaveGame'` (note lowercase `w`).
- **Two save locations**: `constants.loaded_level_json` (Level.sav, deferred write) + per-player .sav files (written immediately).
- **i18n default**: `init_language()` falls back to `zh_CN`, not English.
- **Re-export hub**: `import_libs.py` star-imports everything from palsav into namespace.

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
  palsav/               # SERIALIZATION ENGINE (workspace pkg)
  palworld_aio/         # GUI app (managers/, editor/, ui/)
  palworld_toolsets/    # CLI tools (9)
  palworld_xgp_import/  # Xbox Game Pass import pipeline
  palworld_coord/       # Coordinate transforms
  bootup.py             # Entry after start.py (splash + dep check)
  boot_paths.py         # Path constants
  import_libs.py        # Star-import re-export hub
web/
  frontend/             # Svelte 5 + Tailwind SPA (:16920)
  backend/              # FastAPI thin bridge (:16921)
  .web_ref/             # scraped Reflex app — VISUAL REFERENCE ONLY (do not copy logic)
```

## WebUI build contract

The web layer is **strictly decoupled**: Svelte 5 + Tailwind frontend, a *lightweight* FastAPI backend that only bridges to the core project. Rules (full detail: `pst-webui-build` skill; existing inventory: `pst-webui` skill):

- **Wrap, don't rewrite** — all real logic comes from `src/palsav`, `src/palworld_aio`, `src/palworld_toolsets`. Backend endpoints = validate → call core → serialize; no domain math in `web/backend/`.
- **`.web_ref` is visual-only** — match its layout/theme/components, but NEVER copy its Reflex/Python logic or `pstmain/states` (port to Svelte idiomatically, or call `src/`).
- **REST + WebSocket boundary** — frontend only talks via `/api` and `/ws`; Pydantic schemas (`web/backend/schemas.py`) mirror TS types (`web/frontend/src/types`) — change both together.
- Launcher: `start.py --web`. New capability → add to `src/` first, then expose via one thin endpoint.

## Repo exclusions

`.venv/`, `dist/`, `build/`, `Backups/`, `*.sav`, `*.savc`, `*.7z`, `uv.lock` — all gitignored.
