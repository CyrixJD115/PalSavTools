# PalworldSaveTools - Windows setup (winget / Chocolatey).
#
# Installs every dependency needed to build and launch PST from source on
# Windows 10/11: Git, Node.js LTS, Rust (cargo), uv, plus the Visual C++
# Redistributable. The Tauri/Nuitka native build paths additionally need the
# Visual Studio Build Tools (C++ workload) - documented below, installed on
# request via the -IncludeBuildTools switch.
#
# Safe to re-run - every step is idempotent.
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

function Test-Command($n) {
    $null -ne (Get-Command $n -ErrorAction SilentlyContinue)
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

function Install-Pkg([string]$pm, [string]$wingetId, [string]$chocoId) {
    if ($pm -eq 'winget') {
        winget install --id $wingetId --silent --accept-package-agreements --accept-source-agreements --disable-interactivity `
            | Out-Null
    } else {
        choco install $chocoId -y | Out-Null
    }
}

$pm = Ensure-PackageManager

Write-Step "1 - Git"
if (Test-Command git) {
    Write-Ok "git already present ($(git --version))"
} else {
    Install-Pkg $pm 'Git.Git' 'git'
    # Refresh PATH for this session so subsequent steps see git.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + `
                [Environment]::GetEnvironmentVariable('Path', 'User')
    if (Test-Command git) { Write-Ok "git installed" } else { Write-Warn "git install failed" }
}

Write-Step "2 - Node.js LTS + npm"
if ((Test-Command node) -and (Test-Command npm)) {
    Write-Ok "node already present ($(node --version))"
} else {
    Install-Pkg $pm 'OpenJS.NodeJS.LTS' 'nodejs-lts'
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + `
                [Environment]::GetEnvironmentVariable('Path', 'User')
    if (Test-Command node) { Write-Ok "node installed ($(node --version))" } else { Write-Warn "node install failed" }
}

Write-Step "3 - Rust toolchain (cargo)"
if (Test-Command cargo) {
    Write-Ok "cargo already present ($(cargo --version))"
} else {
    Write-Info "installing rustup (rustup.rs)"
    # rustup-init is not in winget/choco reliably; use the official installer.
    Invoke-WebRequest -UseBasicParsing 'https://win.rustup.rs/x86_64' -OutFile "$env:TEMP\rustup-init.exe"
    & "$env:TEMP\rustup-init.exe" -y --profile minimal
    Remove-Item "$env:TEMP\rustup-init.exe" -Force
    $env:Path += ";$env:USERPROFILE\.cargo\bin"
    if (Test-Command cargo) { Write-Ok "cargo installed" } else { Write-Warn "cargo install failed" }
}

Write-Step "4 - uv (Python package manager)"
if (Test-Command uv) {
    Write-Ok "uv already present ($(uv --version))"
} else {
    Install-Pkg $pm 'astral-sh.uv' 'uv'
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + `
                [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not (Test-Command uv)) {
        Write-Info "package-manager uv failed - trying astral.sh PowerShell installer"
        powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
        $env:Path += ";$env:USERPROFILE\.local\bin"
    }
    if (Test-Command uv) { Write-Ok "uv installed ($(uv --version))" } else { Write-Warn "uv install failed" }
}

Write-Step "5 - Visual C++ Redistributable (runtime)"
# Needed by the Nuitka-built standalone exe and by PyO3 extensions on Windows.
$vc = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64' -ErrorAction SilentlyContinue
if ($vc) {
    Write-Ok "VC++ Redistributable already installed"
} else {
    Install-Pkg $pm 'Microsoft.VCRedist.2015+.x64' 'vcredist140'
    Write-Ok "VC++ Redistributable install attempted"
}

if ($IncludeBuildTools) {
    Write-Step "5b - Visual Studio Build Tools (C++ workload)"
    Write-Info "Needed for the native Nuitka standalone build path."
    Install-Pkg $pm 'Microsoft.VisualStudio.2022.BuildTools' 'visualstudio2022buildtools'
    Write-Ok "VS Build Tools install attempted (verify the 'Desktop development with C++' workload is checked)"
} else {
    Write-Host "`nSkipping VS Build Tools. Re-run with -IncludeBuildTools if you plan to"
    Write-Host "build a standalone .exe with Nuitka.`n" -ForegroundColor DarkGray
}

Write-Step "6 - Verify"
Push-Location $Root
$py = if (Test-Command python) { 'python' } elseif (Test-Command python3) { 'python3' } else { $null }
if ($py) {
    & $py "$Here\check_env.py" --mode=launch
} else {
    Write-Warn "python not on PATH - cannot run check_env.py. Install Python 3.11+ from python.org."
}
Pop-Location

Write-Host "`nDone. From $Root, launch PST with:`n" -ForegroundColor White
Write-Host "    .\start.cmd            # native Tauri window" -ForegroundColor Cyan
Write-Host "    .\start.cmd --web      # browser mode (no native window)`n" -ForegroundColor Cyan
Write-Host "If check_env reported warnings, re-run it any time:" -ForegroundColor DarkGray
Write-Host "    python setup\check_env.py" -ForegroundColor DarkGray
