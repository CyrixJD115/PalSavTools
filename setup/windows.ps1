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

Write-Step "1 - Git"
if (Test-Command git) {
    Write-Ok "git already present ($(git --version))"
} else {
    Install-Pkg $pm 'Git.Git' 'git' "Git install"
    Refresh-Path
    Verify-Tool git "Git install"
}

Write-Step "2 - Node.js LTS + npm"
if ((Test-Command node) -and (Test-Command npm)) {
    Write-Ok "node already present ($(node --version))"
} else {
    Install-Pkg $pm 'OpenJS.NodeJS.LTS' 'nodejs-lts' "Node.js install"
    Refresh-Path
    Verify-Tool node "Node.js install"
    Verify-Tool npm "npm install"
}

Write-Step "3 - Rust toolchain (cargo)"
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

Write-Step "4 - uv (Python package manager)"
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

Write-Step "5 - Visual C++ Redistributable (runtime)"
# Needed by the Nuitka-built standalone exe and by PyO3 extensions on Windows.
$vc = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64' -ErrorAction SilentlyContinue
if ($vc) {
    Write-Ok "VC++ Redistributable already installed"
} else {
    Install-Pkg $pm 'Microsoft.VCRedist.2015+.x64' 'vcredist140' "VC++ Redistributable install"
    Refresh-Path
    # Re-probe the registry to confirm it actually landed.
    $vc = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64' -ErrorAction SilentlyContinue
    if ($vc) {
        Write-Ok "VC++ Redistributable installed"
    } else {
        Write-Warn "VC++ Redistributable install was attempted but registry probe failed - verify manually."
    }
}

if ($IncludeBuildTools) {
    Write-Step "5b - Visual Studio Build Tools (C++ workload)"
    Write-Info "Needed for the native Nuitka standalone build path."
    Install-Pkg $pm 'Microsoft.VisualStudio.2022.BuildTools' 'visualstudio2022buildtools' "VS Build Tools install"
    Write-Ok "VS Build Tools install attempted (verify the 'Desktop development with C++' workload is checked)"
} else {
    Write-Host "`nSkipping VS Build Tools. Re-run with -IncludeBuildTools if you plan to" -ForegroundColor DarkGray
    Write-Host "build a standalone .exe with Nuitka.`n" -ForegroundColor DarkGray
}

Write-Step "6 - Verify"
Push-Location $Root
$py = if (Test-Command python) { 'python' } elseif (Test-Command python3) { 'python3' } else { $null }
if ($py) {
    Invoke-Native { & $py "$Here\check_env.py" --mode=launch } "Environment check"
    Write-Ok "environment check passed"
} else {
    Write-Crit "python not on PATH - cannot run check_env.py."
    Write-Hint "Install Python 3.11+ from https://python.org, then re-run this script."
    exit 1
}
Pop-Location

New-Terminal-Banner
Write-Host "`nDone. From $Root, **in a new terminal**, launch PST with:`n" -ForegroundColor White
Write-Host "    .\start.cmd            # native Tauri window" -ForegroundColor Cyan
Write-Host "    .\start.cmd --web      # browser mode (no native window)`n" -ForegroundColor Cyan
Write-Host "Re-run the environment check any time:" -ForegroundColor DarkGray
Write-Host "    python setup\check_env.py" -ForegroundColor DarkGray
