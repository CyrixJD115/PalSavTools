# PalworldSaveTools - Windows setup (winget / Chocolatey).
#
# Installs every dependency needed to build and launch PST from source on
# Windows 10/11: Git, Node.js LTS, Rust (cargo), uv, plus the Visual C++
# Redistributable. The Tauri/Nuitka native build paths additionally need the
# Visual Studio Build Tools (C++ workload) - documented below, installed on
# request via the -IncludeBuildTools switch.
#
# Safe to re-run - every step is idempotent and verifies the tool actually
# works before moving on.
#
# Usage (PowerShell, as your normal user):
#   powershell -ExecutionPolicy Bypass -File setup\windows.ps1
#   powershell -ExecutionPolicy Bypass -File setup\windows.ps1 -IncludeBuildTools
#
# See setup/README.md for what each piece is for and troubleshooting.
[CmdletBinding()]
param(
    [switch] $IncludeBuildTools
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here

function Write-Step($m) { Write-Host "`n=== $m ===`n" -ForegroundColor White }
function Write-Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Warn($m) { Write-Host "[!!] $m" -ForegroundColor Yellow }
function Write-Info($m) { Write-Host "[..] $m" -ForegroundColor Cyan }
function Write-Crit($m) { Write-Host "[XX] $m" -ForegroundColor Red }
function Write-Hint($m) { Write-Host "     -> $m" -ForegroundColor DarkGray }

function Test-Command($n) {
    $null -ne (Get-Command $n -ErrorAction SilentlyContinue)
}

# Distinguish a REAL Python interpreter from the Windows Store stub.
# Windows ships a 0-byte `python.exe` in WindowsApps that, when run, opens the
# Microsoft Store instead of executing Python (exit 9009). Test-Command finds
# the stub and returns true, which misleads the rest of the script.
function Test-RealPython {
    foreach ($candidate in 'python', 'python3', 'py') {
        if (-not (Test-Command $candidate)) { continue }
        # Skip the WindowsApps stub by path — that's the Store redirector.
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd.Source -and ($cmd.Source -like '*\WindowsApps\*')) { continue }
        # Try to actually run it. A real Python prints its version; the stub
        # exits non-zero (9009) and may print the Store nag.
        $out = & $candidate --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$out" -match '^Python 3\.(\d+)') {
            return $candidate
        }
    }
    return $null
}

# Invoke a native command and abort with a clear message if it fails.
# $ErrorActionPreference='Stop' does NOT catch non-zero $LASTEXITCODE from
# native exes (winget, choco, rustup-init, python), so we must check it
# explicitly every time.
function Invoke-Native([scriptblock]$sb, $label) {
    & $sb
    if ($LASTEXITCODE -ne 0) {
        Write-Crit "$label FAILED (exit $LASTEXITCODE)"
        Write-Hint "See the output above; fix the issue and re-run this script."
        Write-Hint "If you just installed the tool in this terminal, OPEN A NEW TERMINAL so your PATH refreshes."
        exit 1
    }
}

# Verify a tool is on PATH after installing it. Hard-aborts on failure so the
# user knows exactly which step broke.
function Verify-Tool([string]$tool, [string]$label) {
    if (Test-Command $tool) {
        $ver = & $tool --version 2>&1 | Select-Object -First 1
        Write-Ok "$label ($ver)"
        return
    }
    Write-Crit "$label FAILED - '$tool' still not found on PATH"
    Write-Hint "Re-run this script, or install $tool manually and re-run."
    Write-Hint "If you just installed it in this terminal, OPEN A NEW TERMINAL so your PATH refreshes."
    exit 1
}

function New-Terminal-Banner {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  IMPORTANT: open a NEW terminal before running .\start.cmd" -ForegroundColor White
    Write-Host "  (so your shell picks up the tools we just installed)" -ForegroundColor DarkGray
    Write-Host "===========================================================" -ForegroundColor Cyan
}

# Reload PATH from the registry into the current process (winget/choco write
# to the Machine/User PATH, which the current process won't see otherwise).
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + `
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

# winget ships with modern Windows 11; on older installs it comes from the
# App Installer Store package. If absent, fall back to Chocolatey.
function Ensure-PackageManager {
    if (Test-Command winget) { return 'winget' }
    Write-Info "winget not found - installing Chocolatey"
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol =
        [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString(
        'https://community.chocolatey.org/install.ps1'))
    if (Test-Command choco) { return 'choco' }
    throw "Could not find or install a package manager (winget or choco)."
}

function Install-Pkg([string]$pm, [string]$wingetId, [string]$chocoId, [string]$label) {
    if ($pm -eq 'winget') {
        Invoke-Native { winget install --id $wingetId --silent --accept-package-agreements --accept-source-agreements --disable-interactivity } $label
    } else {
        Invoke-Native { choco install $chocoId -y } $label
    }
}

$pm = Ensure-PackageManager

Write-Step "1 - Python 3.12 (runtime)"
# PST requires Python >=3.11. On a clean Windows box Python is almost never
# present, and the `python` stub in WindowsApps opens the Store instead of
# running — so we install the real thing via winget/choco.
$pyExe = Test-RealPython
if ($pyExe) {
    Write-Ok "python already present ($(& $pyExe --version 2>&1))"
} else {
    Install-Pkg $pm 'Python.Python.3.12' 'python --version=3.12.7' "Python 3.12 install"
    Refresh-Path
    $pyExe = Test-RealPython
    if (-not $pyExe) {
        Write-Crit "Python install failed or only the Windows Store stub is on PATH."
        Write-Hint "Disable the 'App Installer' python alias at:"
        Write-Hint "  Settings -> Apps -> Advanced app settings -> App execution aliases"
        Write-Hint "Or install Python 3.11+ manually from https://python.org, then re-run."
        exit 1
    }
    Write-Ok "python installed ($(& $pyExe --version 2>&1))"
}

Write-Step "2 - Git"
if (Test-Command git) {
    Write-Ok "git already present ($(git --version))"
} else {
    Install-Pkg $pm 'Git.Git' 'git' "Git install"
    Refresh-Path
    Verify-Tool git "Git install"
}

Write-Step "3 - Node.js LTS + npm"
if ((Test-Command node) -and (Test-Command npm)) {
    Write-Ok "node already present ($(node --version))"
} else {
    Install-Pkg $pm 'OpenJS.NodeJS.LTS' 'nodejs-lts' "Node.js install"
    Refresh-Path
    Verify-Tool node "Node.js install"
    Verify-Tool npm "npm install"
}

Write-Step "4 - Rust toolchain (cargo)"
if (Test-Command cargo) {
    Write-Ok "cargo already present ($(cargo --version))"
} else {
    Write-Info "installing rustup (rustup.rs)"
    # rustup-init is not in winget/choco reliably; use the official installer.
    Invoke-WebRequest -UseBasicParsing 'https://win.rustup.rs/x86_64' -OutFile "$env:TEMP\rustup-init.exe"
    Invoke-Native { & "$env:TEMP\rustup-init.exe" -y --profile minimal } "Rust install"
    Remove-Item "$env:TEMP\rustup-init.exe" -Force
    $env:Path += ";$env:USERPROFILE\.cargo\bin"
    Verify-Tool cargo "Rust install"
}

Write-Step "5 - uv (Python package manager)"
if (Test-Command uv) {
    Write-Ok "uv already present ($(uv --version))"
} else {
    try {
        Install-Pkg $pm 'astral-sh.uv' 'uv' "uv install"
        Refresh-Path
    } catch {
        Write-Info "package-manager uv failed - trying astral.sh PowerShell installer"
        Invoke-Native { powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex" } "uv install"
        $env:Path += ";$env:USERPROFILE\.local\bin"
    }
    Verify-Tool uv "uv install"
}

Write-Step "6 - Visual C++ Redistributable (runtime)"
# Needed by the Nuitka-built standalone exe and by PyO3 extensions on Windows.
# Probe multiple known registry locations — winget/choco installs land in
# different keys depending on version, bitness, and WOW64 redirection.
function Test-VCRedist {
    $keys = @(
        'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64',
        'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64'
    )
    foreach ($k in $keys) {
        if (Get-ItemProperty $k -ErrorAction SilentlyContinue) { return $true }
    }
    # Fall back to the Uninstall key by display-name match.
    $uninst = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
              'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
    foreach ($root in $uninst) {
        Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
            $name = (Get-ItemProperty $_.PSPath -Name DisplayName -ErrorAction SilentlyContinue).DisplayName
            if ($name -like '*Visual C++*Redistributable*x64*') { return $true }
        }
        if ($?) { }  # no-op to suppress pipeline errors
    }
    return $false
}
if (Test-VCRedist) {
    Write-Ok "VC++ Redistributable already installed"
} else {
    Install-Pkg $pm 'Microsoft.VCRedist.2015+.x64' 'vcredist140' "VC++ Redistributable install"
    Refresh-Path
    if (Test-VCRedist) {
        Write-Ok "VC++ Redistributable installed"
    } else {
        Write-Warn "VC++ Redistributable install was attempted but registry probe failed - verify manually."
    }
}

if ($IncludeBuildTools) {
    Write-Step "6b - Visual Studio Build Tools (C++ workload)"
    Write-Info "Needed for the native Nuitka standalone build path."
    Install-Pkg $pm 'Microsoft.VisualStudio.2022.BuildTools' 'visualstudio2022buildtools' "VS Build Tools install"
    Write-Ok "VS Build Tools install attempted (verify the 'Desktop development with C++' workload is checked)"
} else {
    Write-Host "`nSkipping VS Build Tools. Re-run with -IncludeBuildTools if you plan to" -ForegroundColor DarkGray
    Write-Host "build a standalone .exe with Nuitka.`n" -ForegroundColor DarkGray
}

Write-Step "7 - Verify"
Push-Location $Root
# Use the stub-aware resolver — Test-Command python would find the WindowsApps
# stub and trigger the Microsoft Store redirect (exit 9009).
$py = Test-RealPython
if ($py) {
    Invoke-Native { & $py "$Here\check_env.py" --mode=launch } "Environment check"
    Write-Ok "environment check passed"
} else {
    Write-Crit "python not on PATH (or only the Windows Store stub is present)."
    Write-Hint "Install Python 3.11+ from https://python.org, or disable the python"
    Write-Hint "alias under Settings -> Apps -> Advanced app settings -> App execution aliases."
    exit 1
}
Pop-Location

New-Terminal-Banner

# When invoked by get.ps1 (one-shot installer), skip this summary — get.ps1
# prints its own, clearer final instructions. This block only runs when the
# user called setup\windows.ps1 directly.
if (-not $env:PST_GET_INVOKED) {
    Write-Host "`nSetup complete. To launch PST (in a NEW terminal so your PATH is refreshed):`n" -ForegroundColor White
    Write-Host "    cd $Root" -ForegroundColor White
    Write-Host "    .\start.cmd --web      # browser mode - fastest, no compile (recommended first run)" -ForegroundColor Cyan
    Write-Host "    .\start.cmd            # native Tauri desktop window (slower first launch:" -ForegroundColor Cyan
    Write-Host "                          #   compiles ~487 Rust crates, needs ~3 GB disk)`n" -ForegroundColor Cyan
    Write-Host "Re-run the environment check any time:" -ForegroundColor DarkGray
    Write-Host "    python setup\check_env.py" -ForegroundColor DarkGray
}
