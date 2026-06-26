# PST (PalworldSaveTools) – Session Memory (condensed)

## Agent Rules
- Do NOT commit or push without explicit instruction.
- Ask before adding or removing files.
- Keep responses terse.
- Run `backup_whole_directory()` before any destructive operation.

## Project Snapshot
- **Purpose:** GUI + CLI tool for editing Palworld save files.
- **Tech:** Python ≥3.11, uv, pytest, PySide6, Nuitka.
- **Key Architecture:** 3‑layer pipeline (SAV↔GVAS↔JSON), globals in `palworld_aio.constants`, large `MainWindow` class.

## Gotchas & Conventions
- Selection highlight requires `widget.set_selected(False)` before rebuild.
- Booth lock uses `is_private_lock` byte.
- Guild `_u8_flag` only read when V1_MARKER present.
- Cross‑tab player sync guarded by `_syncing`.

## Skills (load on demand)
- `pst-codebase` – repo layout & entry points.
- `pst-save-pipeline` – save/round‑trip logic.
- `pst-pal-editor` – pal stats & editing.
- `pst-ui-tabs` – UI widgets and Qt styling.
- `pst-gui-architecture` – app structure.
- `pst-game-data` – JSON schemas & i18n.
- `pst-build-ci` – build system.
- `pst-stat-formula` – stat calculations.
- `pst-binary-schemas` – binary format details.
