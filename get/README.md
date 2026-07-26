# One-shot installer

The fastest way to get PalworldSaveTools running from source. Each one-liner
clones the repo, installs every system dependency, and prints the exact launch
command — no manual steps in between.

> Prefer a pre-built binary? Grab one from
> [GitHub Releases](https://github.com/CyrixJD115/PalSavTools/releases/latest)
> instead — no setup needed.

---

## Linux / macOS

> **Where does it install?** Into a new `PalSavTools/` folder **inside whatever directory your terminal is currently in**. So first `cd` to where you want it (e.g. `cd ~/projects`), then run the command. The script prints the full install path (e.g. `/home/you/projects/PalSavTools`) before it starts cloning — no surprises. To install elsewhere without `cd`-ing, pass `--dest <path>`.

```bash
curl -fsSL https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/get/get.sh | bash
```

That's it. It will:

1. **Print the install path**, then **clone** PalworldSaveTools (with submodules) into `<current dir>/PalSavTools`.
2. **Detect your OS + distro** and run the matching [`setup/`](../setup/) installer
   — installs Rust, Node.js, uv, and (on Linux) the GTK/WebKit headers Tauri needs.
3. **Print the launch command** to run next.

### Options

Pass them after `bash -s --`:

```bash
curl -fsSL .../get/get.sh | bash -s -- --dest ~/projects/pst --branch dev
```

| Flag | Default | Purpose |
|---|---|---|
| `--dest <dir>` | `./PalSavTools` | Where to clone |
| `--branch <name>` | `master` | Branch/tag to check out |
| `--repo <url>` | public GitHub | Override the git remote (useful for forks) |
| `--no-clone` | — | Skip cloning; run `setup/` against the current directory |

---

## Windows (PowerShell)

> **Where does it install?** Into a new `PalSavTools\` folder **inside whatever directory your PowerShell prompt is currently in**. So first `cd` to where you want it (e.g. `cd C:\projects`), then run the command. The script prints the full install path (e.g. `C:\projects\PalSavTools`) before it starts cloning — no surprises. To install elsewhere without `cd`-ing, pass `-Dest <path>`.

```powershell
irm https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/get/get.ps1 | iex
```

Same flow: print install path → clone → install Git/Node/Rust/uv/VC++ Redist → print next steps.

### Options (download the file first)

The `irm | iex` one-liner above can't take arguments (PowerShell's `Invoke-Expression` doesn't forward them). To pass any of the flags below, download the script and run it with `-File`:

```powershell
irm https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/get/get.ps1 -OutFile get.ps1
powershell -ExecutionPolicy Bypass -File get.ps1 -Dest C:\projects\pst -Branch dev -IncludeBuildTools
```

| Flag | Default | Purpose |
|---|---|---|
| `-Dest <dir>` | `.\PalSavTools` | Where to clone |
| `-Branch <name>` | `master` | Branch/tag to check out |
| `-Repo <url>` | public GitHub | Override the git remote |
| `-NoClone` | — | Skip cloning; run `setup\` against `$PWD` |

(`-IncludeBuildTools` is passed through to `setup/windows.ps1` to add the
Visual Studio Build Tools for the Nuitka standalone-build path.)

---

## After it finishes

**Open a new terminal** (so your shell picks up the freshly-installed tools),
then from the cloned dir:

**Linux / macOS:**

```bash
./start.sh            # native Tauri window
./start.sh --web      # browser mode (no native window)
```

**Windows:**

```powershell
.\start.cmd           # native Tauri window
.\start.cmd --web     # browser mode (no native window)
```

You can verify the environment any time with the standalone checker:

```bash
python3 setup/check_env.py
```

---

## What if it fails?

- **Cloning failed** → check your network, or pass `--repo` / `-Repo` to point at a fork.
- **A package install failed** → the error message names the tool. Re-run the matching `setup/*.sh` (or `setup\windows.ps1`) directly — they're idempotent.
- **`./start.sh` says `uv not found` after setup** → you didn't open a new terminal. Close the current one and open a fresh terminal, then retry. (The launchers also probe `~/.local/bin` and `~/.cargo/bin` as a fallback, but a fresh shell is the reliable fix.)

See [`setup/README.md`](../setup/README.md) for the full troubleshooting table.
