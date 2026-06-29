---
name: pst-build-ci
description: The build system (Nuitka for standalone binaries → dist/, Tauri for WebUI desktop app), Inno Setup installer, GitHub Actions CI (5 workflows), standalone-mode signaling (runtime.cfg), verify_build checks, and utility scripts (update_game_data ETL, translation automation via Google Translate, theme linter, import validator). Load when building, releasing, or maintaining CI.
---

# PST Build System, CI, Scripts

## Build backends
**Nuitka** (build/nuitka/build_nuitka.py) = Primary. Entry src/palworld_aio/main.py. --onefile (default) or --standalone. Output dist/PalworldSaveTools-V{ver}-nk-{platform}. Forces palsav submodules via --include-module (21-39), excludes tkinter/unittest/numpy + ~20 Qt submodules (41-52). Bundles resources/ + src/data/ + games.json. macOS: --macos-create-app-bundle.

**Tauri** (build/tauri/build_tauri.py) = WebUI desktop app. Orchestrates: Svelte frontend build → Nuitka sidecar (web backend) → `npx tauri build`. Output at `web/frontend/src-tauri/target/release/`. See `build/tauri/build_nuitka_web.py` for the sidecar Nuitka config.

## Standalone-mode signaling
runtime.cfg flag: [build] standalone=true written before build, reset to false after. Read by common.is_standalone() (40-50). Consumers: updater (auto-download vs git-pull), main_window path resolution.

## verify_build.py (build/verify_build.py)
Post-build checks: binary exists+executable, size>1MiB, resources bundled, headless smoke test (exe Level.sav --logs --fix, 30s timeout), --version contains APP_VERSION.

## clean_code.py (build/clean_code.py — ONLY copy, NOT in scripts/scrs/)
AST-based docstring+comment+blank stripper. DESTRUCTIVE — rewrites source in place via ast.unparse. DocstringRemover(14).

## Inno Setup installer (build/installer/pst.windows.iss)
Packages PST_standalone/* (Nuitka output). AppId {B0E3F1A2-...}. Compression=lzma2/max SolidCompression=yes. PrivilegesRequired=lowest. Output: PalworldSaveTools-{ver}-windows-setup.exe. Desktop shortcut (checkedonce). Full clean uninstall.

## CI (5 workflows, all use checkout@v4 + setup-python@v5 3.12 + uv)
- **ci.yml** — push/PR gating. 3 parallel jobs (win/linux/mac), Nuitka build, upload artifacts. NO tests, NO release.
- **build-{windows,linux,mac}.yml** — workflow_dispatch only. Single-OS Nuitka build → draft+prerelease GH release.
- **build-all-and-release.yml** — workflow_dispatch with inputs (version, release_name, draft, prerelease). 5 jobs: prepare-source(tarball) + 3 builds + create-release(aggregates). THE canonical release pipeline.

## Utility scripts (scripts/scrs/)

### update_game_data.py (2362 lines) — game-data ETL
Ingests UE asset exports from Exports/Pal/Content/ → resources/game_data/. 21 sequential steps with spinner. Reads DT_*.json data tables + L10N + textures. Produces merged files: characters.json←{pals,npcs}, skills.json←{passives,skills,elements}, world.json←{structures,technology}, items.json←{items}. Then deletes per-entity files, cleans stale icons, PNG→WEBP via Pillow. Legacy fallback(129) maps old→merged names.

### Translation automation (deep-translator / Google Translate)
- **translate_readme.py** — README.md→7 locales. PlaceholderManager protects code/URLs/game terms. Parallel ThreadPoolExecutor.
- **translate_tab_guide.py** — tab_guide/en/*.html→7 locales. Protects HTML tags. Parallel max 10 workers.
- **update_translation_keys.py** — update EXISTING key text + re-translate all locales.
- **add_translation_keys.py** — add NEW keys + optionally prune OLD_KEYS.

### Validation
- **validate_imports.py** — smoke-test imports 16 core modules, asserts expected attrs. Exit 1 on failure.
- **check_theme_violations.py** (483) — linter enforcing centralized theming. Detects hardcoded hex/rgba (error), inline qss blocks ≥3 props (warning), hardcoded fonts (warning). Whitelist: styles.py, constants.py, edit_pals.py. Flags: --ruthless (no whitelist), --strict (warnings=fail).

### Other scripts
- **scan_ft_guids.py** — harvest fast-travel/area/unlock GUIDs from player .sav RecordData → reference_unlock_data.json (additive merge).
- **clear_fog.py** — dev utility, zeroes fog mask in a .sav.
- **auto_update.py** — 5-line shim → runpy palsav.commands.auto_update.
- **test_interactively.py** (348) — menu-driven pytest orchestrator. --quick=fast, --all=incl slow.

### .cmd launchers (scripts/tests/ + scripts/)
9 test .cmd runners (identical template: check uv→wipe venv→uv sync→run pytest target→del uv.lock→pause). Scripts/ has .cmd wrappers for each .py (uv venv bootstrap + run).

## GOTCHAS
- scripts/scrs/clean_code.py does NOT exist — only build/clean_code.py.
- setup_freeze.py:30 hardcodes version="2.0.0" (kept in sync only by build_cx.sync_version); .iss also hardcodes 2.0.0.
- ci.yml does NOT run pytest — test running is local-only (.cmd/test_interactively.py).
- palsav/palooz in frozen builds: Nuitka forces via --include-module for every submodule. Both inject src/+resources/ on sys.path.