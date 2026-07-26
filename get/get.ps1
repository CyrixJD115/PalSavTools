# PalworldSaveTools - one-shot installer for Windows.
#
# Clones the repo (with submodules), then runs setup\windows.ps1 to install all
# system dependencies (Git, Node.js, Rust, uv, VC++ Redist). Does NOT auto-
# launch - prints the exact command to run next.
#
# Usage (PowerShell, irm | iex):
#   irm https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/get/get.ps1 | iex
#
# Or, with options (download the file first):
#   powershell -ExecutionPolicy Bypass -File get.ps1 -Dest C:\path\to\clone -Branch dev
#
# Options (passed after the iex, or as named args via -File):
#   -Dest <dir>      Where to clone (default: .\PalSavTools under $PWD)
#   -Branch <name>   Branch/tag to check out (default: master)
#   -Repo <url>      Override the git remote
#   -NoClone         Skip cloning - assume $PWD is already the repo root (run setup only)
#   -IncludeBuildTools  Add VS Build Tools (for the Nuitka standalone path)
#
# NOTE: this script is deliberately written to be `irm | iex`-safe. That means:
#   - No param() block (iex doesn't honor it as script parameters).
#   - No here-strings (@"..."@) — their `"@ terminator breaks iex re-parsing.
# We parse $args manually and build multi-line strings via array-join instead.
$ErrorActionPreference = 'Stop'

# --- parse $args manually (iex-safe; works for both -File and iex) ----------
function Get-Arg([string[]]$a, [string]$name, $default) {
    $idx = [array]::IndexOf($a, $name)
    if ($idx -ge 0 -and $idx -lt $a.Length - 1) { return $a[$idx + 1] }
    return $default
}
function Has-Arg([string[]]$a, [string]$name) {
    [array]::IndexOf($a, $name) -ge 0
}

$Repo    = Get-Arg $args '-Repo'    'https://github.com/CyrixJD115/PalSavTools.git'
$Branch  = Get-Arg $args '-Branch'  'master'
$Dest    = Get-Arg $args '-Dest'    (Join-Path $PWD 'PalSavTools')
$NoClone = Has-Arg $args '-NoClone'

# --- helpers (no here-strings; multi-line via array-join) -------------------
function Write-Step($m) { Write-Host ("`n=== $m ===`n") -ForegroundColor White }
function Write-Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Info($m) { Write-Host "[..] $m" -ForegroundColor Cyan }
function Write-Crit($m) { Write-Host "[XX] $m" -ForegroundColor Red }
function Write-Hint($m) { Write-Host "     -> $m" -ForegroundColor DarkGray }

function Invoke-Native([scriptblock]$sb, $label) {
    & $sb
    if ($LASTEXITCODE -ne 0) {
        Write-Crit "$label FAILED (exit $LASTEXITCODE)"
        Write-Hint "See the output above; fix the issue and re-run."
        exit 1
    }
}

# ASCII logo as an array of lines, joined with newlines — iex-safe.
$LogoLines = @(
    '  ___      _                _    _ ___              _____         _    ',
    ' | _ \__ _| |_ __ _____ _ _| |__| / __| __ ___ ____|_   _|__  ___| |___',
    ' |  _/ _` | \ V V / _ \ ''_| / _` \__ \/ _` \ V / -_)| |/ _ \/ _ \(_-<',
    ' |_| \__,_|_|\_/\_/\___/_| |_\__,_|___/\__,_|\_/\___||_|\___/\___/_/__/'
)
$Banner = $LogoLines -join "`n"

$CloneDir = if ($NoClone) { $PWD } else { $Dest }

try {
    Write-Host $Banner -ForegroundColor Cyan
    Write-Host ""

    # Announce the install destination loudly and FIRST, so there's no surprise
    # about where the project is going. The default is $PWD\PalSavTools.
    if (-not $NoClone) {
        Write-Host "Installing to: " -NoNewline -ForegroundColor White
        Write-Host "$CloneDir" -ForegroundColor Cyan
        $defaultPath = Join-Path $PWD 'PalSavTools'
        if ($CloneDir -eq $defaultPath) {
            Write-Hint "That's a new 'PalSavTools' folder inside your current directory ($PWD)."
            Write-Hint "To install somewhere else, cancel now and re-run with: -Dest C:\your\path"
        }
    }

    # --- step 1: clone ----------------------------------------------------
    if ($NoClone) {
        Write-Step "1/3  Using current directory (skipping clone)"
        Write-Ok "$CloneDir"
    } else {
        Write-Step "1/3  Clone PalSavTools"
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Crit "git is required to clone the repo but isn't installed."
            Write-Hint "Install Git from https://git-scm.com, then re-run."
            exit 1
        }
        if (Test-Path $CloneDir) {
            Write-Crit "Destination already exists: $CloneDir"
            Write-Hint "Pick a different location with -Dest <dir>, or remove the existing dir."
            exit 1
        }
        Write-Info "git clone --recurse-submodules --branch $Branch $Repo -> $CloneDir"
        Invoke-Native { git clone --recurse-submodules --branch $Branch $Repo $CloneDir } "Clone"
        Write-Ok "cloned to $CloneDir"
    }

    # --- step 2: run the per-platform setup script ------------------------
    Write-Step "2/3  Install system dependencies"
    $SetupScript = Join-Path $CloneDir 'setup\windows.ps1'
    if (-not (Test-Path $SetupScript)) {
        Write-Crit "setup\windows.ps1 not found at $SetupScript"
        Write-Hint "The clone may be incomplete or from a very old branch."
        exit 1
    }
    # Forward -IncludeBuildTools if the user passed it.
    $setupArgs = @('-ExecutionPolicy', 'Bypass', '-File', $SetupScript)
    if (Has-Arg $args '-IncludeBuildTools') { $setupArgs += '-IncludeBuildTools' }
    Write-Info "Running setup\windows.ps1"
    Invoke-Native { powershell @setupArgs } "Setup"

    # --- step 3: next steps -----------------------------------------------
    Write-Step "3/3  Next steps"
    Write-Host ""
    Write-Host ("Done! The project is set up at: " + $CloneDir) -ForegroundColor White
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  IMPORTANT: open a NEW terminal, then run:" -ForegroundColor White
    Write-Host ""
    Write-Host ("    cd " + $CloneDir) -ForegroundColor White
    Write-Host "    .\start.cmd            # native Tauri window" -ForegroundColor Cyan
    Write-Host "    .\start.cmd --web      # browser mode (no native window)" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "A new terminal is needed so your shell picks up the tools we just installed." -ForegroundColor DarkGray
}
catch {
    Write-Crit "Install failed: $_"
    Write-Hint "Review the output above for the exact error."
    if (-not $NoClone -and (Test-Path $CloneDir)) {
        Write-Hint "Removing partial clone at $CloneDir..."
        Remove-Item -Recurse -Force $CloneDir -ErrorAction SilentlyContinue
    }
    exit 1
}
