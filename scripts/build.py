#!/usr/bin/env python3
"""Build PST Bootstrapper for one or all target platforms.

Usage:
    python build.py <ostype> [--skip-payload] [--skip-uv]

    <ostype> can be: linux, windows, mac, mac-arm, or all

Options:
    --skip-payload   Skip creating the source payload archive
    --skip-uv        Skip downloading uv binaries
"""

import os
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
os.chdir(ROOT_DIR)

PROJECT = "PST.Bootstrapper/PST.Bootstrapper.csproj"
DIST_DIR = "dist"
PAYLOAD_DIR = "PST.Bootstrapper/payload"
APPIMAGE_TOOL_URL = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

UV_RELEASES = {
    "win-x64": "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip",
    "linux-x64": "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz",
    "osx-x64": "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-apple-darwin.tar.gz",
    "osx-arm64": "https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz",
}

TARGETS = {
    "windows": {"rid": "win-x64", "name": "windows", "label": "Windows x64", "ext": "exe", "portable": False},
    "windows-portable": {"rid": "win-x64", "name": "windows-portable", "label": "Windows x64 (Portable)", "ext": "exe", "portable": True},
    "linux":   {"rid": "linux-x64", "name": "linux", "label": "Linux x64", "ext": "AppImage", "portable": False},
    "mac":     {"rid": "osx-x64", "name": "mac", "label": "macOS x64", "ext": "dmg", "portable": False},
    "mac-arm": {"rid": "osx-arm64", "name": "mac-arm", "label": "macOS ARM64", "ext": "dmg", "portable": False},
}

PAYLOAD_EXCLUDES = {
    "__pycache__", ".pyc", ".git", ".venv", "node_modules",
    ".DS_Store", "Thumbs.db", ".build", "uv.lock",
    "PST_standalone", "dist", "PST.Bootstrapper", "Backups", "Logs", "saves",
}

REQUIREMENTS_FILTER = {"cx-freeze"}

APP_NAME_MAC = "Palworld Save Tools"
APP_BUNDLE_ID = "com.palworldsavetools.bootstrapper"

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
GRAY = "\033[90m"

_use_ansi = sys.stdout.isatty()

ICNS_TYPE_MAP = {
    16: "icp4", 32: "icp5", 64: "icp6", 128: "ic07",
    256: "ic08", 512: "ic09", 1024: "ic10",
}

def _png_to_icns(png_path: str, icns_path: str) -> bool:
    try:
        import struct
        with open(png_path, "rb") as f:
            png_data = f.read()
        if not png_data.startswith(b"\x89PNG"):
            return False
        w = _png_width(png_data)
        entries = bytearray()
        for size in (128, 256, 512, 1024):
            tag = ICNS_TYPE_MAP.get(size, "ic08").encode("ascii")
            entry_len = 8 + len(png_data)
            entries += struct.pack(">4sI", tag, entry_len) + png_data
        file_len = 8 + len(entries)
        with open(icns_path, "wb") as f:
            f.write(struct.pack(">4sI", b"icns", file_len))
            f.write(entries)
        return True
    except Exception:
        return False

def _png_width(data: bytes) -> int:
    if len(data) > 24:
        import struct
        return struct.unpack(">I", data[16:20])[0]
    return 0

def _a(code: str) -> str:
    return code if _use_ansi else ""

def _visible_len(s: str) -> int:
    import re
    return len(re.sub(r"\033\[[0-9;]*m", "", s))

def _banner():
    print()
    print(f"{_a(BOLD)}{_a(CYAN)}  ___      _                _    _ ___              _____         _    {_a(RESET)}")
    print(f"{_a(BOLD)}{_a(CYAN)} | _ \\__ _| |_ __ _____ _ _| |__| / __| __ ___ ____|_   _|__  ___| |___{_a(RESET)}")
    print(f"{_a(BOLD)}{_a(CYAN)} |  _/ _` | \\ V  V / _ \\ '_| / _` \\__ \\/ _` \\ V / -_)| |/ _ \\/ _ \\(_-<{_a(RESET)}")
    print(f"{_a(BOLD)}{_a(CYAN)} |_| \\__,_|_|\\_/\\_/\\___/_| |_\\__,_|___/\\__,_|\\_/\\___||_|\\___/\\___/_/__/{_a(RESET)}")
    print(f"{_a(DIM)}{'':>16}Bootstrapper Build System v1.0{_a(RESET)}")
    print()

def _header(title: str):
    w = 60
    print(f"{_a(BOLD)}{_a(WHITE)}┌{'─' * w}┐{_a(RESET)}")
    print(f"{_a(BOLD)}{_a(WHITE)}│{_a(RESET)} {_a(BOLD)}{_a(CYAN)}{title:^{w - 1}}{_a(RESET)}{_a(BOLD)}{_a(WHITE)}│{_a(RESET)}")
    print(f"{_a(BOLD)}{_a(WHITE)}└{'─' * w}┘{_a(RESET)}")

def _section(title: str):
    print()
    print(f"  {_a(BOLD)}{_a(BLUE)}▸{_a(RESET)} {_a(BOLD)}{title}{_a(RESET)}")

def _step(label: str, detail: str = ""):
    if detail:
        print(f"    {_a(DIM)}│{_a(RESET)} {_a(GREEN)}✓{_a(RESET)} {label} {_a(DIM)}{detail}{_a(RESET)}")
    else:
        print(f"    {_a(DIM)}│{_a(RESET)} {_a(GREEN)}✓{_a(RESET)} {label}")

def _warn(msg: str):
    print(f"    {_a(DIM)}│{_a(RESET)} {_a(YELLOW)}⚠{_a(RESET)} {_a(YELLOW)}{msg}{_a(RESET)}")

def _fail(msg: str):
    print(f"    {_a(DIM)}│{_a(RESET)} {_a(RED)}✗{_a(RESET)} {_a(RED)}{msg}{_a(RESET)}")

def _size_label(path: str) -> str:
    mb = os.path.getsize(path) / 1024 / 1024
    return f"{mb:.1f} MB"

def _run_quiet(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

def _run_show(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    label = os.path.basename(cmd[0])
    args = " ".join(cmd[1:])
    print(f"    {_a(DIM)}│{_a(RESET)} {_a(GRAY)}$ {label} {args}{_a(RESET)}")
    return subprocess.run(cmd, check=True, **kwargs)


def prepare_payload() -> dict:
    tar_path = os.path.join(PAYLOAD_DIR, "payload.tar")
    gz_path = os.path.join(PAYLOAD_DIR, "payload.tar.gz")
    os.makedirs(PAYLOAD_DIR, exist_ok=True)

    for p in (tar_path, gz_path):
        if os.path.exists(p):
            os.remove(p)

    _section("Payload Preparation")

    includes = ["src", "resources", "requirements.txt", "pyproject.toml", "license"]

    temp_req = os.path.join(ROOT_DIR, "requirements.txt")
    filtered_req_path = os.path.join(PAYLOAD_DIR, "_requirements_filtered.txt")
    if os.path.exists(temp_req):
        with open(temp_req, "r", encoding="utf-8") as f:
            lines = f.readlines()
        filtered = [l for l in lines if not any(flt in l.lower() for flt in REQUIREMENTS_FILTER)]
        with open(filtered_req_path, "w", encoding="utf-8") as f:
            f.writelines(filtered)
        _step("Filtered requirements", "(removed cx-freeze)")
    else:
        filtered_req_path = None

    with tarfile.open(tar_path, "w") as tar:
        for item in includes:
            full_path = os.path.join(ROOT_DIR, item)
            if not os.path.exists(full_path):
                continue
            if item == "requirements.txt" and filtered_req_path and os.path.exists(filtered_req_path):
                tar.add(filtered_req_path, arcname="requirements.txt")
            else:
                _add_to_tar(tar, full_path, item)

    if filtered_req_path and os.path.exists(filtered_req_path):
        os.remove(filtered_req_path)

    tar_mb = os.path.getsize(tar_path) / 1024 / 1024
    _step("Tar archive created", f"({tar_mb:.1f} MB)")

    import gzip
    with open(tar_path, "rb") as f_in, open(gz_path, "wb") as f_out:
        with gzip.GzipFile(fileobj=f_out, mode="wb", compresslevel=9) as gz:
            shutil.copyfileobj(f_in, gz)
    os.remove(tar_path)

    gz_mb = os.path.getsize(gz_path) / 1024 / 1024
    ratio = gz_mb / tar_mb * 100
    _step(f"gzip compressed", f"({gz_mb:.1f} MB, {ratio:.0f}% of tar)")

    return {"tar_mb": tar_mb, "gz_mb": gz_mb}


def _add_to_tar(tar: tarfile.TarFile, path: str, arcname: str) -> None:
    if os.path.isfile(path):
        tar.add(path, arcname=arcname)
        return
    for root, dirs, files in os.walk(path):
        rel_root = os.path.relpath(root, os.path.dirname(path))
        skip = False
        for part in rel_root.split(os.sep):
            if part in PAYLOAD_EXCLUDES or any(part.endswith(ext) for ext in [".pyc"]):
                skip = True
                break
        if skip:
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if d not in PAYLOAD_EXCLUDES]
        for f in files:
            if f in PAYLOAD_EXCLUDES or any(f.endswith(ext) for ext in [".pyc"]):
                continue
            full = os.path.join(root, f)
            arc = os.path.join(arcname, os.path.relpath(full, path))
            tar.add(full, arcname=arc)


def download_uv(rid: str) -> bool:
    if rid not in UV_RELEASES:
        return False

    rid_dir = os.path.join(PAYLOAD_DIR, rid)
    os.makedirs(rid_dir, exist_ok=True)

    uv_name = "uv.exe" if rid == "win-x64" else "uv"
    uv_path = os.path.join(rid_dir, uv_name)

    if os.path.exists(uv_path):
        _step(f"uv [{rid}]", "(cached)")
        return True

    url = UV_RELEASES[rid]
    ext = ".zip" if rid == "win-x64" else ".tar.gz"
    archive_path = os.path.join(PAYLOAD_DIR, f"uv-{rid}{ext}")

    try:
        urllib.request.urlretrieve(url, archive_path)
    except Exception as e:
        _fail(f"uv download failed: {e}")
        return False

    if rid == "win-x64":
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.namelist():
                if member.endswith("uv.exe"):
                    with zf.open(member) as src, open(uv_path, "wb") as dst:
                        dst.write(src.read())
                    break
    else:
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                if member.name.endswith("/uv") and not member.name.endswith("/uvx"):
                    member.name = "uv"
                    tf.extract(member, rid_dir)
                    break

    if os.path.exists(archive_path):
        os.remove(archive_path)

    if sys.platform != "win32":
        st = os.stat(uv_path)
        os.chmod(uv_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    _step(f"uv [{rid}]", _size_label(uv_path))
    return True


def publish(key: str) -> dict | None:
    info = TARGETS[key]
    rid = info["rid"]
    name = info["name"]
    label = info["label"]
    portable = info.get("portable", False)
    out_dir = os.path.join(DIST_DIR, name)

    _section(f"Publish {label}")

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    marker_path = os.path.join("PST.Bootstrapper", "portable.marker")
    if portable:
        with open(marker_path, "w") as f:
            f.write("")

    cmd = [
        "dotnet", "publish", PROJECT,
        "-c", "Release", "-r", rid,
        "--self-contained", "true",
        "-o", out_dir,
        "-p:DebugType=None",
        "-p:DebugSymbols=false",
        "-p:PublishSingleFile=true",
        "-p:IncludeNativeLibrariesForSelfExtract=true",
        "-p:EnableCompressionInSingleFile=true",
    ]

    if portable:
        cmd.append("-p:PortableBuild=true")

    result = _run_quiet(cmd)

    if portable and os.path.exists(marker_path):
        os.remove(marker_path)

    if result.returncode != 0:
        _fail("dotnet publish failed")
        for line in result.stderr.strip().splitlines():
            if "error" in line.lower():
                print(f"    {_a(DIM)}│{_a(RESET)}   {_a(RED)}{line.strip()}{_a(RESET)}")
        return None

    _step(".NET compiled", f"[{rid}]")

    result_info = {"key": key, "rid": rid, "name": name, "label": label}

    if key == "windows":
        exe_src = os.path.join(out_dir, "PST.Bootstrapper.exe")
        if os.path.exists(exe_src):
            result_info["exe_size"] = _size_label(exe_src)
            _step("Single-file exe", result_info["exe_size"])
        nsis_result = _build_nsis(out_dir, name)
        if nsis_result:
            result_info["installer"] = nsis_result

    if key == "windows-portable":
        exe_src = os.path.join(out_dir, "PST.Bootstrapper.exe")
        if os.path.exists(exe_src):
            portable_out = os.path.join(DIST_DIR, "PST-windows-x86_64-portable.exe")
            shutil.move(exe_src, portable_out)
            shutil.rmtree(out_dir, ignore_errors=True)
            result_info["exe_size"] = _size_label(portable_out)
            result_info["portable_path"] = portable_out
            _step("Portable exe", result_info["exe_size"])

    if key == "linux":
        appimg_result = _build_appimage(out_dir, name)
        if appimg_result:
            result_info["appimage"] = appimg_result

    if key in ("mac", "mac-arm"):
        dmg_result = _build_dmg(out_dir, name, rid)
        if dmg_result:
            result_info["dmg"] = dmg_result

    return result_info


def _build_dmg(publish_dir: str, name: str, rid: str) -> dict | None:
    arch = "arm64" if "arm" in rid else "x86_64"
    _step("Building .app bundle...", f"[{arch}]")

    app_bundle = os.path.join(DIST_DIR, f"{APP_NAME_MAC}.app")
    dmg_root = os.path.join(DIST_DIR, f"dmg-root-{name}")
    contents = os.path.join(app_bundle, "Contents")
    macos_dir = os.path.join(contents, "MacOS")
    resources_dir = os.path.join(contents, "Resources")

    for d in (app_bundle, dmg_root):
        if os.path.exists(d):
            shutil.rmtree(d)

    os.makedirs(macos_dir)
    os.makedirs(resources_dir)

    for item in os.listdir(publish_dir):
        s = os.path.join(publish_dir, item)
        d = os.path.join(macos_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d)

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>{APP_NAME_MAC}</string>
    <key>CFBundleDisplayName</key><string>{APP_NAME_MAC}</string>
    <key>CFBundleIdentifier</key><string>{APP_BUNDLE_ID}</string>
    <key>CFBundleVersion</key><string>1.0.0</string>
    <key>CFBundleShortVersionString</key><string>1.0.0</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleExecutable</key><string>PST.Bootstrapper</string>
    <key>LSMinimumSystemVersion</key><string>10.15</string>
    <key>NSHumanReadableCopyright</key><string>Copyright 2026 Pylar</string>
    <key>CFBundleIconFile</key><string>icon.icns</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>LSUIElement</key><false/>
</dict>
</plist>
"""
    with open(os.path.join(contents, "Info.plist"), "w", encoding="utf-8") as f:
        f.write(plist)
    with open(os.path.join(contents, "PkgInfo"), "w") as f:
        f.write("APPL????")

    _step("Info.plist generated")

    icon_src = os.path.join("PST.Bootstrapper", "assets", "icon.png")
    icns_dst = os.path.join(resources_dir, "icon.icns")
    icns_ok = False
    for tool in ["png2icns", "sips"]:
        try:
            if tool == "png2icns":
                subprocess.run([tool, icns_dst, icon_src], capture_output=True, check=True)
            else:
                subprocess.run([tool, "-s", "format", "icns", icon_src, "--out", icns_dst], capture_output=True, check=True)
            icns_ok = True
            break
        except Exception:
            pass
    if not icns_ok:
        if _png_to_icns(icon_src, icns_dst):
            _step("Icon converted", "(png → icns)")
        else:
            _warn("Could not convert icon to .icns")

    os.makedirs(dmg_root)
    shutil.copytree(app_bundle, os.path.join(dmg_root, f"{APP_NAME_MAC}.app"), symlinks=True)
    os.symlink("/Applications", os.path.join(dmg_root, "Applications"))

    dmg_path = os.path.join(DIST_DIR, f"PST-{name}-{arch}.dmg")

    xorriso = shutil.which("xorriso")
    genisoimage = shutil.which("genisoimage")
    tool_name = None

    if xorriso:
        tool_name = "xorriso"
        result = _run_quiet([
            xorriso, "-as", "mkisofs",
            "-V", "PST", "-D", "-R", "-J", "-hfsplus",
            "-o", dmg_path, dmg_root,
        ])
    elif genisoimage:
        tool_name = "genisoimage"
        result = _run_quiet([
            genisoimage, "-V", "PST", "-D", "-R", "-apple",
            "-no-pad", "-o", dmg_path, dmg_root,
        ])
    else:
        _warn("No DMG tool found, falling back to zip")
        _zip_fallback(dmg_root, name, rid)
        for d in (app_bundle, dmg_root):
            if os.path.exists(d):
                shutil.rmtree(d)
        return None

    for d in (app_bundle, dmg_root):
        if os.path.exists(d):
            shutil.rmtree(d)

    if os.path.exists(dmg_path):
        sz = _size_label(dmg_path)
        _step(f"DMG packaged", f"({sz}, {tool_name})")
        return {"path": dmg_path, "size": sz, "tool": tool_name}

    _fail("DMG not created")
    return None


def _zip_fallback(dmg_root: str, name: str, rid: str) -> None:
    arch = "arm64" if "arm" in rid else "x86_64"
    zip_path = os.path.join(DIST_DIR, f"PST-{name}-{arch}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(dmg_root):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, os.path.dirname(dmg_root))
                zf.write(filepath, arcname)
    _step("Zip fallback", _size_label(zip_path))


def _build_appimage(publish_dir: str, name: str) -> dict | None:
    _step("Building AppImage...")

    appdir = os.path.join(DIST_DIR, f"{name}.AppDir")
    usr_bin = os.path.join(appdir, "usr", "bin")

    if os.path.exists(appdir):
        shutil.rmtree(appdir)
    os.makedirs(usr_bin)

    for item in os.listdir(publish_dir):
        s = os.path.join(publish_dir, item)
        d = os.path.join(usr_bin, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d)

    icon_src = os.path.join("PST.Bootstrapper", "assets", "icon.png")
    icon_dst = os.path.join(appdir, "palworld-save-tools.png")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, icon_dst)

    with open(os.path.join(appdir, "palworld-save-tools.desktop"), "w") as f:
        f.write("[Desktop Entry]\nType=Application\nName=Palworld Save Tools\n")
        f.write("Comment=All-in-one tool for Palworld saves\nIcon=palworld-save-tools\n")
        f.write("Exec=PST.Bootstrapper\nCategories=Utility;\nTerminal=false\n")

    apprun = os.path.join(appdir, "AppRun")
    with open(apprun, "w") as f:
        f.write("#!/bin/bash\n")
        f.write('HERE="$(dirname "$(readlink -f "$0")")"\n')
        f.write('export PATH="$HERE/usr/bin:$PATH"\n')
        f.write('export LD_LIBRARY_PATH="$HERE/usr/bin:$LD_LIBRARY_PATH"\n')
        f.write('exec "$HERE/usr/bin/PST.Bootstrapper" "$@"\n')
    st = os.stat(apprun)
    os.chmod(apprun, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    appimagetool = shutil.which("appimagetool")
    if appimagetool is None:
        temp_tool = os.path.join(DIST_DIR, ".appimagetool")
        if not os.path.exists(temp_tool):
            try:
                urllib.request.urlretrieve(APPIMAGE_TOOL_URL, temp_tool)
                os.chmod(temp_tool, os.stat(temp_tool).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                _step("appimagetool downloaded")
            except Exception as e:
                _warn(f"Could not download appimagetool ({e})")
                _warn(f"AppDir at {appdir}")
                return None
        appimagetool = temp_tool

    output = os.path.join(DIST_DIR, f"PST-{name}-x86_64.AppImage")
    result = _run_quiet([appimagetool, appdir, output])

    if os.path.exists(appdir):
        shutil.rmtree(appdir)

    if os.path.exists(output):
        sz = _size_label(output)
        _step("AppImage packaged", f"({sz})")
        return {"path": output, "size": sz}

    _fail("AppImage not created")
    return None


def _build_nsis(publish_dir: str, name: str) -> dict | None:
    _step("Building NSIS installer...")

    makensis = shutil.which("makensis")
    if makensis is None:
        _warn("makensis not found, skipping installer")
        return None

    nsi_script = os.path.join(ROOT_DIR, "installer.nsi")
    if not os.path.exists(nsi_script):
        _warn("installer.nsi not found")
        return None

    result = _run_quiet([makensis, "-V2", nsi_script])
    if result.returncode != 0:
        _warn(f"NSIS failed (exit {result.returncode})")
        return None

    output = os.path.join(DIST_DIR, "PST-windows-x86_64-setup.exe")
    if os.path.exists(output):
        sz = _size_label(output)
        _step("Installer packaged", f"({sz})")
        return {"path": output, "size": sz}

    _warn("Installer output not found")
    return None


def _summary(results: list[dict], elapsed: float):
    print()

    def _row(content: str, width: int) -> str:
        vis = _visible_len(content)
        gap = max(width - vis, 0)
        return f"{content}{' ' * gap}"

    rows = []
    for r in results:
        label = r.get("label", r["name"])
        rid = r["rid"]
        rows.append((_a(BOLD) + f"  {label}" + _a(RESET) + "  " + _a(DIM) + f"[{rid}]" + _a(RESET), False))
        if "exe_size" in r:
            rows.append((f"    {_a(CYAN)}EXE{_a(RESET)}       {r['exe_size']:>8}", True))
        if "installer" in r:
            p = r["installer"]
            rows.append((f"    {_a(MAGENTA)}Installer{_a(RESET)}  {p['size']:>8}  {_a(DIM)}{p['path']}{_a(RESET)}", True))
        if "portable_path" in r:
            p = r["portable_path"]
            rows.append((f"    {_a(GREEN)}Portable{_a(RESET)}    {r['exe_size']:>8}  {_a(DIM)}{p}{_a(RESET)}", True))
        if "appimage" in r:
            p = r["appimage"]
            rows.append((f"    {_a(YELLOW)}AppImage{_a(RESET)}   {p['size']:>8}  {_a(DIM)}{p['path']}{_a(RESET)}", True))
        if "dmg" in r:
            p = r["dmg"]
            rows.append((f"    {_a(BLUE)}DMG{_a(RESET)}       {p['size']:>8}  {_a(DIM)}{p['path']}{_a(RESET)}", True))

    footer = f"  {_a(DIM)}Completed in {elapsed:.1f}s{_a(RESET)}"
    content_w = max(_visible_len(c) for c, _ in rows)
    content_w = max(content_w, _visible_len(footer))
    w = content_w + 2

    B = _a(BOLD) + _a(WHITE)
    R = _a(RESET)

    print(f"{B}┌{'─' * w}┐{R}")
    title = "Build Summary"
    print(f"{B}│{R} {title:^{content_w}} {B}│{R}")
    print(f"{B}├{'─' * w}┤{R}")
    for content, _ in rows:
        print(f"{B}│{R} {_row(content, content_w)} {B}│{R}")
    print(f"{B}├{'─' * w}┤{R}")
    print(f"{B}│{R} {_row(footer, content_w)} {B}│{R}")
    print(f"{B}└{'─' * w}┘{R}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Build PST Bootstrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Targets: linux, windows, windows-portable, mac, mac-arm, all",
    )
    parser.add_argument("target", help="Build target")
    parser.add_argument("--skip-payload", action="store_true", help="Skip payload creation")
    parser.add_argument("--skip-uv", action="store_true", help="Skip uv download")
    args = parser.parse_args()

    target = args.target.lower()
    os.makedirs(DIST_DIR, exist_ok=True)

    _banner()
    start = time.time()

    if not args.skip_payload:
        _header("PAYLOAD")
        prepare_payload()

    if target == "all":
        targets = list(TARGETS.keys())
    elif target in TARGETS:
        targets = [target]
    else:
        _fail(f"Unknown target: {target}")
        print(f"  Valid: {', '.join(TARGETS)} or 'all'")
        sys.exit(1)

    _header("BUILD")

    results = []
    for key in targets:
        rid = TARGETS[key]["rid"]
        if not args.skip_uv:
            download_uv(rid)
        r = publish(key)
        if r:
            results.append(r)

    elapsed = time.time() - start
    _summary(results, elapsed)

    if not results:
        sys.exit(1)


if __name__ == "__main__":
    main()
