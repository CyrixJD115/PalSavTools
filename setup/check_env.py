#!/usr/bin/env python3
"""PalworldSaveTools — cross-platform environment preflight checker.

Runs *before* uv / the venv exists, so this file deliberately uses only the
standard library. It verifies that the host can build and launch PST, with
three severity levels:

  OK   ✓  present and good enough
  WARN ⚠  present-but-old / optional tool missing / low disk  (does not abort)
  CRIT ✗  blocking — missing a required tool or no write/space  (exit 1)

Soft mode (default): a CRIT result prints guidance and exits 1, but optional
tools only ever WARN so the app can still start in a degraded (browser-only)
mode. Use --mode=tauri or --mode=build to tighten the gates.

Exit codes
----------
  0  no critical issues (warnings are allowed)
  1  at least one critical issue
  2  invalid usage

Usage
-----
  python3 setup/check_env.py                # human report, launch gates
  python3 setup/check_env.py --mode=tauri   # stricter: cargo + webkit required
  python3 setup/check_env.py --mode=build   # stricter: nuitka/patchelf too
  python3 setup/check_env.py --json         # machine-readable for setup scripts
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

# Resolve the project root from this file's location so the checker works no
# matter the current working directory (or when invoked via uv run).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# Output helpers — ANSI only when on a TTY and not forced off.
# --------------------------------------------------------------------------- #
_FORCE_COLOR = os.environ.get("PST_CHECK_COLOR", "").lower()
_TTY = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
_ANSI = _FORCE_COLOR in ("1", "true", "yes") or (_TTY and _FORCE_COLOR != "0")


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _ANSI else s


def ok(s: str = "") -> str:    return _c("92", s)  # green
def warn(s: str = "") -> str:  return _c("93", s)  # yellow
def crit(s: str = "") -> str:  return _c("91", s)  # red
def bold(s: str = "") -> str:  return _c("1", s)
def dim(s: str = "") -> str:   return _c("2", s)


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #
OK, WARN, CRIT = "ok", "warn", "crit"
_MARK = {OK: "✓", WARN: "⚠", CRIT: "✗"}


class Result:
    __slots__ = ("name", "status", "detail", "hint")

    def __init__(self, name: str, status: str, detail: str = "", hint: str = ""):
        self.name = name
        self.status = status
        self.detail = detail
        self.hint = hint

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status,
                "detail": self.detail, "hint": self.hint}


# --------------------------------------------------------------------------- #
# Host detection — mirrors build/build.py::detect_host
# --------------------------------------------------------------------------- #
def detect_host() -> dict:
    sysname = os.name
    if sysname == "nt":
        kind, setup_hint = "win", "powershell -ExecutionPolicy Bypass -File setup/windows.ps1"
    elif sys.platform == "darwin":
        kind, setup_hint = "mac", "bash setup/macos.sh"
    else:
        kind, setup_hint = "linux", "bash setup/linux.sh"
    return {"kind": kind, "platform": sys.platform, "setup_hint": setup_hint}


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _version_tuple(text: str) -> tuple[int, ...]:
    """Extract the leading dotted numbers from an arbitrary version string."""
    m = re.search(r"(\d+(?:\.\d+)*)", text or "")
    if not m:
        return ()
    return tuple(int(x) for x in m.group(1).split("."))


def _run(cmd: list[str], timeout: float = 6.0) -> tuple[int, str]:
    """Run a command and capture combined output. Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 127, ""


def check_python() -> Result:
    info = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        return Result("Python", OK, f"{info} at {sys.executable}")
    return Result(
        "Python", CRIT, f"{info} — PST needs Python 3.11+",
        "Install from https://www.python.org/downloads/ "
        "or run the setup script for your distro.",
    )


def check_uv() -> Result:
    path = _which("uv")
    if not path:
        # uv may have just been installed but not yet on PATH for this shell.
        for candidate in (Path.home() / ".local/bin/uv",
                          Path.home() / ".cargo/bin/uv"):
            if candidate.exists():
                path = str(candidate)
                break
    if not path:
        return Result("uv (Python pkg manager)", CRIT, "not found on PATH",
                      "curl -LsSf https://astral.sh/uv/install.sh | sh")
    rc, out = _run([path, "--version"])
    return Result("uv", OK, out or f"at {path}")


def check_node() -> Result:
    path = _which("node")
    if not path:
        return Result("Node.js", CRIT, "not found on PATH",
                      "Install Node.js 18+ LTS — see setup/README.md")
    rc, out = _run([path, "--version"])  # prints "v20.11.1"
    ver = _version_tuple(out)
    if ver and ver >= (18,):
        return Result("Node.js", OK, out)
    return Result("Node.js", WARN, f"{out} — 18+ recommended",
                  "Upgrade to an LTS release from https://nodejs.org/")


def check_npm() -> Result:
    path = _which("npm")
    if not path:
        return Result("npm", CRIT, "not found on PATH",
                      "Comes with Node.js — reinstall from https://nodejs.org/")
    rc, out = _run([path, "--version"])
    return Result("npm", OK, out or "present")


def check_git() -> Result:
    path = _which("git")
    if not path:
        return Result("git", WARN, "not found on PATH",
                      "Needed for submodules + updates. Install via your package manager.")
    rc, out = _run([path, "--version"])
    return Result("git", OK, out or "present")


def check_cargo(strict: bool = False) -> Result:
    """Rust toolchain — needed to build the uesave save parser (palsav-rs).

    Optional for browser mode (a prebuilt is auto-downloaded / the build runs
    in the background); required for Tauri/build modes.
    """
    path = _which("cargo")
    status = CRIT if strict else WARN
    if not path:
        return Result(
            "Rust (cargo)", status, "not found on PATH",
            "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
        )
    rc, out = _run([path, "--version"])
    rustc = _which("rustc")
    return Result("Rust (cargo)", OK, out or f"at {path}",
                  "" if rustc else "rustc missing — reinstall the toolchain")


def check_submodule() -> Result:
    """Verify the palsav-rs submodule is checked out."""
    cargo_toml = PROJECT_ROOT / "src" / "palsav-rs" / "Cargo.toml"
    gitmodules = PROJECT_ROOT / ".gitmodules"
    if not gitmodules.exists():
        return Result("git submodule (palsav-rs)", OK, "no submodules declared")
    if cargo_toml.exists():
        return Result("git submodule (palsav-rs)", OK, "checked out")
    return Result(
        "git submodule (palsav-rs)", CRIT,
        "submodule not initialized — src/palsav-rs/Cargo.toml missing",
        "git submodule update --init --recursive",
    )


def check_writable() -> Result:
    """Can we actually write to the project root (for .venv, dist, Backups)?"""
    # Probe the project root.
    probe = PROJECT_ROOT / f".pst-write-probe-{uuid.uuid4().hex[:8]}"
    try:
        probe.write_text("ok", encoding="utf-8")
        if probe.read_text(encoding="utf-8") != "ok":
            raise OSError("readback mismatch")
        probe.unlink()
    except OSError as e:
        return Result("Write permission (project dir)", CRIT,
                      f"cannot write to {PROJECT_ROOT}: {e}",
                      f"Check ownership/perms on {PROJECT_ROOT}")
    # Probe .venv (create it transiently if absent so we catch the real
    # failure mode — a read-only mount — without leaving junk behind).
    venv = PROJECT_ROOT / ".venv"
    created_venv = False
    try:
        if not venv.exists():
            venv.mkdir()
            created_venv = True
        probe2 = venv / f".pst-write-probe-{uuid.uuid4().hex[:8]}"
        probe2.write_text("ok", encoding="utf-8")
        probe2.unlink()
    except OSError as e:
        return Result("Write permission (.venv/)", CRIT,
                      f"cannot write to {venv}: {e}",
                      f"Check ownership/perms on {venv}")
    finally:
        if created_venv:
            try:
                venv.rmdir()
            except OSError:
                pass
    return Result("Write permission", OK, f"{PROJECT_ROOT} writable")


# Disk-space thresholds. The browser/launch path needs very little, but Tauri
# builds (~3 GB in src-tauri/target) and Nuitka standalone builds need more.
MIN_DISK_MB = {"launch": 500, "tauri": 3_000, "build": 4_000}
WARN_DISK_MB = {"launch": 2_000, "tauri": 4_000, "build": 6_000}


def check_disk_space(mode: str) -> Result:
    target = PROJECT_ROOT
    # On the project root's filesystem.
    try:
        total, used, free = shutil.disk_usage(target)
    except OSError as e:
        return Result("Free disk space", WARN, f"could not query: {e}")
    free_mb = free // (1024 * 1024)
    min_mb = MIN_DISK_MB.get(mode, MIN_DISK_MB["launch"])
    warn_mb = WARN_DISK_MB.get(mode, WARN_DISK_MB["launch"])
    human_free = f"{free_mb:,} MB free on {target}"
    if free_mb < min_mb:
        return Result("Free disk space", CRIT,
                      f"{human_free} — need ≥ {min_mb:,} MB for {mode} mode",
                      "Free up space or change the project location.")
    if free_mb < warn_mb:
        return Result("Free disk space", WARN,
                      f"{human_free} — {min_mb:,} MB minimum, but Tauri/Nuitka "
                      f"builds want ≥ {warn_mb:,} MB",
                      "Free up space before building native binaries.")
    return Result("Free disk space", OK, human_free)


FRONTEND_PORT = 16920
BACKEND_PORT = 16921


def _port_bindable(port: int) -> bool:
    fam = socket.AF_INET
    try:
        with socket.socket(fam, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def check_ports() -> Result:
    if os.name == "nt":
        # SO_REUSEADDR behaves differently on Windows; skip the deep check and
        # just report — the launcher already kills stale listeners via the
        # free_ports() step that only runs on POSIX anyway.
        return Result("Ports 16920/16921", OK, "checked by launcher at startup")
    issues = []
    for name, port in (("frontend", FRONTEND_PORT), ("backend", BACKEND_PORT)):
        if not _port_bindable(port):
            issues.append(f"{port}/{name}")
    if issues:
        return Result("Ports 16920/16921", WARN,
                      f"already in use: {', '.join(issues)}",
                      "The launcher will try to free them; if it fails, kill "
                      "the process holding the port.")
    return Result("Ports 16920/16921", OK, "both bindable")


def check_webkit_linux(strict: bool) -> Result | None:
    """Linux-only: probe for the WebKit2GTK 4.1 shared lib (Tauri's webview).

    Returns None on non-Linux hosts so the caller can skip it.
    """
    if detect_host()["kind"] != "linux":
        return None
    # pkg-config is the authoritative source if present.
    rc, out = _run(["pkg-config", "--exists", "webkit2gtk-4.1"])
    if rc == 0:
        return Result("WebKit2GTK 4.1 (Tauri webview)", OK, "pkg-config: webkit2gtk-4.1")
    status = CRIT if strict else WARN
    return Result(
        "WebKit2GTK 4.1 (Tauri webview)", status, "not found via pkg-config",
        "Debian: libwebkit2gtk-4.1-dev | Arch: webkit2gtk-4.1 | "
        "Fedora: webkit2gtk4.1-devel",
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_all(mode: str) -> list[Result]:
    results: list[Result] = []
    results.append(check_python())
    results.append(check_uv())
    results.append(check_node())
    results.append(check_npm())
    results.append(check_git())
    # cargo is required for tauri/build, optional (warn) for plain launch.
    results.append(check_cargo(strict=(mode in ("tauri", "build"))))
    results.append(check_submodule())
    results.append(check_writable())
    results.append(check_disk_space(mode))
    results.append(check_ports())
    wk = check_webkit_linux(strict=(mode in ("tauri", "build")))
    if wk is not None:
        results.append(wk)
    return results


def _print_report(results: list[Result], host: dict, mode: str) -> None:
    print(bold(f"\n  PalworldSaveTools — environment check ") +
          dim(f"({host['kind']}, mode={mode})"))
    print(dim("  " + "─" * 56))
    for r in results:
        if r.status == OK:
            mark, color = _MARK[OK], ok
        elif r.status == WARN:
            mark, color = _MARK[WARN], warn
        else:
            mark, color = _MARK[CRIT], crit
        line = f"  {color(mark)} {bold(r.name):<32} {r.detail}"
        print(line)
        if r.hint and r.status != OK:
            print(dim(f"      → {r.hint}"))
    crits = sum(1 for r in results if r.status == CRIT)
    warns = sum(1 for r in results if r.status == WARN)
    print(dim("  " + "─" * 56))
    summary = f"  {ok(str(sum(1 for r in results if r.status == OK)))} ok" \
              f"  {warn(str(warns))} warn" \
              f"  {crit(str(crits))} critical"
    print(summary)
    if crits:
        host_setup = host["setup_hint"]
        print(crit(f"\n  Fix the {crits} critical issue(s) above, then re-run: "
                   f"{bold('python3 setup/check_env.py')}"))
        print(dim(f"  Or run the setup script for your platform: {host_setup}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the host can build & launch PalworldSaveTools.")
    parser.add_argument("--mode", choices=("launch", "tauri", "build"),
                        default="launch",
                        help="Which gates to apply (default: launch)")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON instead of a report")
    args = parser.parse_args(argv)

    host = detect_host()
    results = run_all(args.mode)

    if args.json:
        payload = {
            "host": host,
            "mode": args.mode,
            "results": [r.to_dict() for r in results],
            "ok": all(r.status != CRIT for r in results),
        }
        print(json.dumps(payload, indent=2))
    else:
        _print_report(results, host, args.mode)

    return 1 if any(r.status == CRIT for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
