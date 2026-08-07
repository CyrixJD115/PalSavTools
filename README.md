> ## ⚠️ ARCHIVED — No Longer Maintained
>
> **PalworldSaveTools is no longer under active development.** The project has
> been merged into [**Palworld Save Pal (PSP)**](https://github.com/oMaN-Rod/palworld-save-pal) —
> the "one tool to rule them all." A large portion of PST's features are being
> folded into PSP, which is now the single place where all Palworld save tooling lives.
>
> **Please use [Palworld Save Pal](https://github.com/oMaN-Rod/palworld-save-pal) instead.**
>
> This repository is kept online for **historical reference only** — the code is
> incomplete and no longer maintained. Bugs will not be fixed and PRs will not
> be merged. Do not build new work on top of this codebase.

<div align="center">

<img src="https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/src/_resources/assets/branding/PST_Blue.png" alt="PalworldSaveTools" width="140" />

# PalworldSaveTools <sub>*(archived)*</sub>

**All-in-one save editor for Palworld — now a web app.**

A Rust-backed save engine, a thin FastAPI API layer, and a Svelte 5 + Tailwind UI. Load any Palworld save, edit it visually, and write it back byte-faithful — all from your browser or a native desktop window.

[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#installation)
[![Languages](https://img.shields.io/badge/UI%20languages-8-7DD3FC.svg)](#features)

[Installation](#installation) · [Features](#features) · [From Source](#from-source-all-platforms) · [Guides](#guides) · [Troubleshooting](#troubleshooting)

</div>

---

## Overview

> **This project is archived.** Development has moved to [**Palworld Save Pal (PSP)**](https://github.com/oMaN-Rod/palworld-save-pal). Everything below documents PST as it was — keep it as a historical reference, but use PSP for anything real.

PalworldSaveTools (PST) is a cross-platform save editor for Palworld. v2.0 is a complete rewrite of the original PySide6 desktop app as a **local-first web app**: a Rust parser does the byte-level work, FastAPI exposes it over a small REST + WebSocket surface, and a Svelte SPA is the UI. You run it on your machine; nothing leaves your computer.

**Why a web app?** The old Qt desktop app was hard to ship cross-platform and slow to iterate on. The new stack keeps the proven save logic, moves the heavy parsing into Rust (so even pre-V1 saves load cleanly without the old 4-byte header crashes), and puts a fast modern UI in front of it.

### Highlights

- **Rust save engine** — the parser lives in [`src/palsav-rs/`](src/palsav-rs/) via PyO3; decoded saves stay in Rust memory for cheap reads.
- **Byte-faithful round-trip** — re-encoding reuses the original compression and structure, so edited saves load back into the game cleanly.
- **Local-first** — runs on `127.0.0.1`; your save data never touches a third-party server.
- **Two UI modes** — native desktop window (Tauri) or plain browser mode (faster startup, no compile).
- **8 UI languages** — English, Deutsch, Español, Français, 日本語, 한국어, Русский, 简体中文.
- **Cross-platform** — Windows, Linux (Debian/Arch/Fedora), macOS.

---

## Features

The WebUI is organized into tabs. Each has in-app help — hover any control for detailed tooltips.

| Area | What you can do |
|---|---|
| **Players** | Browse/search players by name, level, pal count, UID, guild, last-seen. Edit stats, technology, quests/missions, abilities (effigies). |
| **Pal Editor** | View and edit every Pal's species, level, IVs, traits, skills, workspeed, gender, and more. |
| **Guilds** | Inspect guilds and members; rename, reassign players between guilds. |
| **Bases** | List all base camps with owner, pal count, location. **Right-click** to export / import / clone / adjust radius. |
| **Base Editor** | Detailed per-base property editing. |
| **Map** | Interactive world map with players, bases, fast-travel points, and pals plotted. Click to inspect; unlock all map/fast-travel. |
| **Inventory** | Player inventory viewer and editor. |
| **Base Inventory** | Per-base container contents. |
| **Containers** | Browse all `ItemContainerSaveData` entries (player boxes, base storage, dropped items). |
| **Breeding** | Calculate child from two parents, find partner pairs for a target child, compute parent trees, and chain planner. Works standalone or against your loaded save. |
| **Exclusions** | Manage breeding/list exclusions. |
| **Tools** | 12 utilities — see [Tools](#tools) below. |
| **Wiki** | Browse bundled game data (pals, items, breeding tree). |
| **Backups** | Create and restore timestamped backups of the save folder. |
| **Settings** | Storage mode (memory vs disk for large saves), pre-warm toggle, large-save threshold, language. |

### Tools

Single-purpose operations, each with its own form: **Convert** (SAV↔JSON), **Convert IDs** (Steam/NoSteam/UID), **Restore Map** (unlock map across all worlds at once), **Slot Injector**, **Fix Host Save** (host swap / migration), **Fix Guild**, **Character Transfer** (cross-save), **Player Migrate**, **Convert Export**, **Game Pass Fix**, and **XGP Extract**. Open the **Tools** tab for the live list with per-tool guidance.

---

## Installation

> **Prebuilt binaries aren't published yet** — PST currently ships as a **run-from-source** app. It's a one-time setup: a single command installs every dependency, then `./start.sh` boots the app. Pick your platform below.

> **Where does it install?** Into a new `PalSavTools/` folder **inside whatever directory your terminal is currently in**. So first `cd` to where you want it (e.g. `cd ~/projects`), then run the command. The installer prints the full path before it starts — no surprises. To override, pass `--dest <path>` (Linux/macOS) or `-Dest <path>` (Windows).

### Linux & macOS

**One-liner (easiest)** — clones, installs every system dependency, prints next steps. See [`get/README.md`](get/README.md):

```bash
curl -fsSL https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/get/get.sh | bash
```

**Manual setup** — if you already cloned, per-platform installers live in [`setup/`](setup/README.md):

```bash
bash setup/linux.sh        # Linux (auto-detects Arch / Debian / Fedora)
bash setup/macos.sh        # macOS
```

**Clone and run:**

```bash
git clone https://github.com/CyrixJD115/PalSavTools.git
cd PalworldSaveTools
./start.sh                 # native Tauri window
./start.sh --web           # browser mode (no native window)
```

### Windows

**One-liner (easiest)** — in PowerShell:

```powershell
irm https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/get/get.ps1 | iex
```

**Manual setup** — if you already cloned:

```powershell
powershell -ExecutionPolicy Bypass -File setup\windows.ps1
```

**Clone and run:**

```powershell
git clone https://github.com/CyrixJD115/PalSavTools.git
cd PalworldSaveTools
.\start.cmd                # native Tauri window
.\start.cmd --web          # browser mode (no native window)
```

### All Platforms

Verify the environment any time:

```bash
python3 setup/check_env.py              # colored report
python3 setup/check_env.py --mode=tauri # stricter gates for native builds
```

The launcher creates a `.venv`, runs a preflight check, installs Python deps via `uv sync`, and boots the app. Pass `--check` to run *only* the preflight, or `--skip-check` to bypass it.

> **Tip:** if you just ran a setup script and `./start.sh` says `uv not found`, **open a new terminal** so your shell refreshes its PATH (the launchers also probe `~/.local/bin` and `~/.cargo/bin` as a fallback).

---

## Quick Start

1. **Load Your Save** — click **Menu → Load Save** (or drag-and-drop a `.zip`/`.7z` bundle in browser mode, or pick a `Level.sav` in desktop mode). Navigate to your Palworld save folder and select `Level.sav`.
2. **Explore** — use the tabs (Map, Players, Pals, Guilds, Bases, Inventory, Breeding, Tools…) to inspect your data. The stats bar shows live counts.
3. **Edit** — left-click to select; right-click almost anything for contextual actions; double-click for quick-edit/delete.
4. **Save** — click **Menu → Save Changes**. Backups are created automatically.

> Each tab has a built-in help icon, and hovering any control reveals detailed tooltips. The in-app help is the most accurate reference for what every feature does.

---

## Guides

### Save File Locations

**Host / Co-op (Windows):**
```
%localappdata%\Pal\Saved\SaveGames\YOURID\RANDOMID\
```
**Dedicated Server:**
```
steamapps\common\Palworld\Pal\Saved\SaveGames\0\RANDOMSERVERID\
```

### Map Unlock

1. Load your save.
2. **Player Inventory** tab → **Unlock All Map + Fast Travel** (single player), **or**
3. **Tools** tab → **Restore Map** to apply unlocked map progress across *all* your worlds/servers at once.
4. Save. Automatic backups are created.

### Host → Server Transfer

<details><summary>Click to expand</summary>

1. Copy `Level.sav` and the `Players` folder from your host save.
2. Paste them into the dedicated server save folder.
3. Start the server, create a new character, and wait for an auto-save.
4. Close the server.
5. Use **Fix Host Save** to migrate the old character's GUID to the new one.
6. Copy files back and launch the server.

</details>

### Host Swap (Changing Host)

<details><summary>Click to expand</summary>

The host always uses the `0001.sav` slot. Each client gets a unique save (e.g. `123xxx.sav`). Both the old and new host must already have a regular save from joining + creating a character.

1. **Fix Host Save** → swap the old host's `0001.sav` to their regular save (moves their progress out of the host slot).
2. **Fix Host Save** → swap the new host's regular save into `0001.sav`.

The new host now occupies `0001.sav` with their own character and Pals; the old host becomes a client.

</details>

### Character Transfer (Cross-Save)

<details><summary>Click to expand</summary>

Transfer characters between worlds/servers preserving characters, Pals, inventory, and technology:

1. **Tools** tab → **Character Transfer**.
2. Select source save and target save.
3. Transfer a single player or all players.

</details>

### Base Export / Import / Clone

<details><summary>Click to expand</summary>

- **Export:** Bases tab (or Map) → right-click a base → **Export Base** → `.json` blueprint.
- **Import:** Right-click a target guild → **Import Base** (single) or **Import Bases (Multi-File)** → pick the `.json`.
- **Clone:** Right-click a base → **Clone Base** → pick target guild (clones with offset positioning).
- **Adjust radius:** Right-click a base → **Adjust Radius** (50%–1000%). Save and reload in-game for structures to reassign.

</details>

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `VCRUNTIME140.dll was not found` (Windows) | Install the [VC++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) (2015–2022). |
| `struct.error` when parsing a save | The save format is outdated. Load it in-game once (Solo/Co-op/Dedicated) to trigger an auto structure update, then retry. |
| GamePass converter not working | Fully close the GamePass Palworld, wait a few minutes for file handles to release, run the converter, then relaunch GamePass to verify. |
| Linux binary won't launch | `chmod +x PalworldSaveTools-*-linux`. |
| macOS binary blocked by Gatekeeper | Right-click → **Open**, or `xattr -d com.apple.quarantine /path/to/app`. |
| `uv not found` after `setup/*.sh` | **Open a new terminal** so PATH refreshes (the launchers also probe `~/.local/bin` and `~/.cargo/bin`). |
| `gio-2.0` / `webkit2gtk-4.1 not found` (Linux build) | Missing GTK/WebKit headers — re-run `setup/linux.sh`. Full table in [`setup/README.md`](setup/README.md). |
| Out of memory on huge saves | Settings → Storage → **Disk** mode (or lower the large-save threshold). See `AGENTS.md` for the memory model. |

> For from-source build issues, run `python3 setup/check_env.py` — it pinpoints what's missing.

---

## Architecture

```
src/palsav-rs/        Rust save engine (PyO3) — the actual parser, holds saves in Rust memory
app/backend/          FastAPI (:16921) — thin bridge: validate → service → serialize
  routes/             REST handlers (save, players, pals, guilds, bases, map, breeding, tools, …)
  services/           Pure-function domain logic (no per-instance state)
  state.py            LoadedSave singleton + lazy section cache (bounds memory on big saves)
app/frontend/         Svelte 5 + Tailwind SPA (:16920) — the main GUI
  routes/             One per tab (players, pals, bases, map, breeding, tools, …)
  lib/                api client, components, map engine, utils
setup/                Per-platform installers + check_env.py preflight
get/                  One-shot curl/iex installer
build/                Nuitka + Tauri build orchestrators
```

The frontend talks to the backend over `/api` (REST) and `/ws` (WebSocket push). Pydantic schemas mirror the TS types — change both together. See [`AGENTS.md`](AGENTS.md) for the full contract, the memory model (why we never touch `loaded.level_dict` unless mutating), and the critical gotchas.

---

## Building from Source

PST ships two build paths. Both need Python 3.11+ and `uv`; Nuitka standalone additionally needs `patchelf` (Linux) / VS Build Tools (Windows).

**Nuitka (standalone desktop binary)** — produces a single self-contained executable:

```bash
uv run python build/nuitka/build_nuitka.py --onefile   # Windows / Linux
uv run python build/nuitka/build_nuitka.py --onedir    # macOS (.app → .dmg)
```

Output → `dist/` (`PalworldSaveTools-*.exe` / `*-linux` / `.app`).

**Tauri (WebUI desktop app)** — bundles the Svelte frontend + FastAPI backend into a native window:

```bash
python build/tauri/build_tauri.py
```

CI (in `.github/workflows/`) builds the Nuitka binaries on every release.

---

## Contributing

> **This repository is archived** — PRs will not be merged. Please contribute to [**Palworld Save Pal**](https://github.com/oMaN-Rod/palworld-save-pal) instead.

The historical workflow (pre-archive):

1. Fork → branch (`git checkout -b feature/AmazingFeature`).
2. For new capabilities, add logic under `src/` first, then expose it via one thin endpoint in `app/backend/`, then the UI in `app/frontend/`. (See the "WebUI build contract" in [`AGENTS.md`](AGENTS.md).)
3. Commit → push → open a PR.

---

## The Palworld Team

> Development continues in [**Palworld Save Pal (PSP)**](https://github.com/oMaN-Rod/palworld-save-pal), where PST features are being merged.

### Active Maintainers

- **[Pylar](https://github.com/deafdudecomputers)** — Original author. Save engine, GUI, and the features you use every day.
- **[cyrix](https://github.com/CyrixJD115)** — Refactorer and sub-maintainer. Code quality, simplification, and the WebUI rewrite.

### Contributors

- **[dkoz](https://github.com/dkoz)** — Game-data IDs and the structural insight that keeps the tool accurate with every game update.
- **[oMaN-Rod](https://github.com/oMaN-Rod)** — Original save parser this project forked from; cracked the Palworld save format.
- **[Okaetsu](https://github.com/Okaetsu)** — Modding insights that made base import/export possible.

---

## Disclaimer

PalworldSaveTools is an unofficial, fan-made tool. It is not affiliated with, endorsed by, or connected to Pocketpair or any Palworld rights holder. "Palworld" is a trademark of its respective owner. Always back up your saves before editing — the tool creates automatic backups, but you are responsible for your data.

## License

[GNU General Public License v3.0](LICENSE) — © PalworldSaveTools contributors.

## Acknowledgments

Built on the shoulders of the Palworld save-editing community. Special thanks to everyone who contributes save-format research, reports bugs, and shares their saves for testing.
