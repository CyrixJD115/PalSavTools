# First-time setup

One-time installers for each platform, plus a cross-platform environment checker
that the launcher also runs before booting the app.

> **Prefer a pre-built binary?** Grab one from
> [GitHub Releases](https://github.com/CyrixJD115/PalSavTools/releases/latest) —
> no setup needed. The scripts here are only for **building from source**.

> **Want the one-liner?** See [`get/README.md`](../get/README.md) —
> `curl -fsSL .../get/get.sh | bash` clones + sets up everything in one shot.

---

## Which script do I run?

```
What OS are you on?                Run this
─────────────────────────────────  ────────────────────────────────────────
Linux (any distro)                 bash setup/linux.sh        ← auto-detects
  └ Arch / Manjaro / EndeavourOS     bash setup/linux-arch.sh    (or the dispatcher picks it)
  └ Debian / Ubuntu / Mint / Pop!    bash setup/linux-debian.sh
  └ Fedora / Rocky / Alma            bash setup/linux-fedora.sh
macOS                              bash setup/macos.sh
Windows  (PowerShell)              powershell -ExecutionPolicy Bypass -File setup\windows.ps1
```

Then launch from the repo root:

```bash
./start.sh            # macOS / Linux — native Tauri window
./start.sh --web      #               — browser mode (no native window)
.\start.cmd           # Windows       — native Tauri window
.\start.cmd --web     #               — browser mode
```

Every script is **idempotent** — safe to re-run any time. They end by invoking
the environment checker (`check_env.py`) so you get a green report before you
launch.

---

## check_env.py — the environment checker

A standalone, stdlib-only script that verifies the host can build & launch PST.
It runs automatically at launch, but you can invoke it directly:

```bash
python3 setup/check_env.py                 # human report, launch gates
python3 setup/check_env.py --mode=tauri    # stricter: cargo + webkit required
python3 setup/check_env.py --mode=build    # stricter: nuitka/patchelf too
python3 setup/check_env.py --json          # machine-readable (for CI / scripts)
```

### What it checks

| Check | Severity if missing | Why |
|---|---|---|
| Python ≥ 3.11 | ✗ critical | Runtime interpreter |
| uv | ✗ critical | Python dependency management |
| Node.js ≥ 18 + npm | ✗ critical (node) / ✗ critical (npm) | Frontend dev server / Tauri |
| git | ⚠ warn | Submodules + updates (app still runs without it) |
| Rust (cargo) | ⚠ warn (launch) / ✗ crit (tauri, build) | Builds the `uesave` save parser |
| git submodule (`src/palsav-rs`) | ✗ critical | The actual save parser source |
| Write permission (project + `.venv/`) | ✗ critical | Must be able to create venv, write dist/Backups |
| Free disk space | ✗ crit (<500 MB) / ⚠ warn (<2 GB) | Tauri builds want ~3 GB, Nuitka ~4 GB |
| Ports 16920 / 16921 | ⚠ warn | Frontend + backend; launcher tries to free them |
| WebKit2GTK 4.1 *(Linux only)* | ⚠ warn (launch) / ✗ crit (tauri) | Tauri's webview engine on Linux |

**Soft mode (default):** warnings never abort — the app boots in browser mode
with just Python + uv + Node. Use `--mode=tauri` or `--mode=build` to tighten
the gates for those workflows.

---

## What each system package is for

### Linux (Debian family)

| Package | Why |
|---|---|
| `build-essential` | gcc, g++, make — needed by Cargo/Rust build scripts |
| `pkg-config` | Rust `-sys` crates use pkg-config to find system libraries |
| `ca-certificates` | TLS roots for the curl/rustup/uv downloads |
| `git` | Clone the repo + submodules |
| `curl`, `wget` | Used by rustup / uv / NodeSource installers |
| `file` | MIME detection — used by upload handling |
| `python3`, `python3-dev` | Runtime + C headers (needed by PyO3/Nuitka) |
| `python3-venv` | Python virtual environments |
| `libssl-dev` | OpenSSL headers — reqwest/rustls + Python cryptography |
| `libglib2.0-dev` | GLib 2.0 headers — Tauri dependency (gio-sys, glib-sys) |
| `libgtk-3-dev` | GTK 3 headers — required by Tauri (gdk-sys, pango-sys, cairo-sys) |
| `libwebkit2gtk-4.1-dev` | WebKit2GTK headers — Tauri's webview engine on Linux |
| `libayatana-appindicator3-dev` | System tray support (Tauri tray plugin) |
| `librsvg2-dev` | SVG rendering — Tauri app icon support |
| `patchelf` | Nuitka standalone binary builds (ELF patching) |

### Linux (Arch)

| pacman package | Debian equivalent |
|---|---|
| `base-devel` | `build-essential` + `pkg-config` |
| `pkgconf` | `pkg-config` |
| `python`, `python-pip`, `python-virtualenv` | `python3`, `python3-dev`, `python3-venv` |
| `openssl` | `libssl-dev` |
| `glib2` | `libglib2.0-dev` |
| `gtk3` | `libgtk-3-dev` |
| `webkit2gtk-4.1` | `libwebkit2gtk-4.1-dev` |
| `libayatana-appindicator` | `libayatana-appindicator3-dev` |
| `librsvg` | `librsvg2-dev` |
| `patchelf` | `patchelf` |

### Linux (Fedora)

| dnf package | Debian equivalent |
|---|---|
| `gcc-c++`, `make` | `build-essential` |
| `pkgconf-pkg-config` | `pkg-config` |
| `python3`, `python3-devel`, `python3-virtualenv` | `python3`, `python3-dev`, `python3-venv` |
| `openssl-devel` | `libssl-dev` |
| `glib2-devel` | `libglib2.0-dev` |
| `gtk3-devel` | `libgtk-3-dev` |
| `webkit2gtk4.1-devel` | `libwebkit2gtk-4.1-dev` |
| `libappindicator-gtk3-devel` | `libayatana-appindicator3-dev` |
| `librsvg2-devel` | `librsvg2-dev` |
| `patchelf` | `patchelf` |

### macOS

macOS needs **no** GTK/WebKit dev packages — Tauri uses the WebKit Apple ships
with the OS. Setup just installs: Xcode Command Line Tools, Homebrew, Node.js,
Rust (cargo), uv.

### Windows

Everything comes via winget (or Chocolatey fallback): Git, Node.js LTS, Rust
(cargo), uv, VC++ Redistributable. The optional `-IncludeBuildTools` switch
adds the Visual Studio Build Tools (C++ workload) for the Nuitka standalone
`.exe` build path.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `gio-2.0 not found` / `gdk-3.0 not found` | Missing `libgtk-3-dev` + `libglib2.0-dev` (Debian) / `gtk3` + `glib2` (Arch) / `gtk3-devel` + `glib2-devel` (Fedora) — re-run the setup script |
| `webkit2gtk-4.1 not found` | Missing WebKit dev headers — see the per-distro row above |
| `No space left on device` (Tauri) | `rm -rf app/frontend/src-tauri/target/` to reclaim ~2.6 GB, then retry |
| `cargo: command not found` | `source "$HOME/.cargo/env"` (or open a new terminal) |
| `uv: command not found` | `source "$HOME/.local/bin/env"` or add `~/.local/bin` to PATH |
| PyO3 / maturin build fails | Ensure `python3-dev` (Debian) / `python` (Arch) / `python3-devel` (Fedora) is installed |
| `VCRUNTIME140.dll was not found` (Windows) | Install the [VC++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) (re-run `setup/windows.ps1`) |
| Gatekeeper blocks the app (macOS) | Right-click → **Open** the first time, or `xattr -d com.apple.quarantine /path/to/app` |

---

## Files in this folder

| File | Purpose |
|---|---|
| `check_env.py` | Cross-platform preflight checker (stdlib-only; runs before uv exists) |
| `linux.sh` | Dispatcher — detects apt/pacman/dnf and execs the matching script |
| `linux-debian.sh` | Ubuntu / Debian / Mint / Pop! installer (apt) |
| `linux-arch.sh` | Arch / Manjaro / EndeavourOS installer (pacman) |
| `linux-fedora.sh` | Fedora / Rocky / Alma installer (dnf) |
| `macos.sh` | macOS installer (Homebrew) |
| `windows.ps1` | Windows installer (winget / Chocolatey) |
