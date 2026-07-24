# embed_python — Rust-embeds-CPython proof of concept

Minimal proof that a **native Rust binary** can embed CPython and execute a
Python module whose source lives **inside the binary** (no `.py` on disk),
without requiring the user to install Python.

Validates the hardest requirement from the architecture investigation:

> Can a Rust executable embed CPython and execute Python modules packaged
> inside the executable, without extracting source to disk, built for Win /
> Linux / macOS?

**Answer: yes** — for pure-Python source. The one universal carve-out: native
Python extensions (`.so`/`.pyd`/`.dylib`) cannot be imported from inside a
binary/zip on any platform (stock CPython `zipimport` forbids it; the OS
dynamic linker needs real files). They ship as real bundled resource files.

## What it proves

```
Rust binary
  └─ embeds CPython 3.13 (python-build-standalone — no system Python)
  └─ embeds pst_embed.py as bytes (include_str!)
  └─ registers an in-memory importlib finder at runtime
  └─ imports pst_embed → resolved by OUR finder, never from disk
  └─ calls pst_embed.add(10, 20) → 30 returned to Rust
```

Verified by `strace`:
- `pst_embed.py` opened from disk: **0 times**
- system Python consulted: **0** (only 2 failed `.pth` `ENOENT` probes)
- all libs + stdlib loaded from `./python/lib/...` (the bundled runtime)

## Run it

> Lives at `build/embed_python/`. The top-level orchestrator
> `python build/build.py --embed` builds and smoke-tests this in one step,
> auto-fetching the PBS runtime and picking the right target triple.

Requires: Rust toolchain, network to fetch python-build-standalone (~34 MB).

```sh
./scripts/fetch_pbs.sh            # downloads cpython-3.13.14 for host triple → ./python
export PYO3_PYTHON="$PWD/python/bin/python3"
export LD_LIBRARY_PATH="$PWD/python/lib:${LD_LIBRARY_PATH:-}"
export RUSTFLAGS="-L native=$PWD/python/lib"
cargo run                          # prints add(10,20)=30
```

## How it works

| File | Role |
|---|---|
| `python_src/finder_bootstrap.py` | ~40-line `importlib` meta_path finder. Pure-Python modules served straight from a bytes dict. Native exts deliberately unsupported. |
| `python_src/pst_embed.py` | The embedded test module (`add`, `whoami`). |
| `src/main.rs` | Sets `PYTHONHOME` → bundled runtime, `Python::attach` (PyO3 0.29), execs the bootstrap, registers modules, imports + calls. |

### Key PyO3 0.29 notes (API renamed since 0.21)

- `Python::with_gil` → **`Python::attach`**
- `py.allow_threads` → **`py.detach`**
- `bound_obj.call1(py, args)` → **`bound.call1(args)`** (no `py` on `Bound`)
- `bound_obj.getattr(py, n)` → **`bound.getattr(n)`**
- `obj.extract(py)` → **`bound.extract()`**
- `py.run` takes **`&CStr`** now, not `&str`
- `auto-initialize` feature makes `Python::attach` boot the interpreter

### Two non-obvious requirements

1. **`PYTHONHOME` must be set before init.** PBS compiles with
   `prefix=/install` (a build-time path that doesn't exist on the host); the
   embedded interpreter won't find its stdlib without it. In the real app,
   resolve the Tauri resource dir and set it there.
2. **Link path + rpath.** pyo3-build-config bakes `-L /install/lib`; the real
   `libpython3.13.so` is under `./python/lib`. POC uses
   `RUSTFLAGS="-L native=..."` + `LD_LIBRARY_PATH`. The real build bakes an
   rpath (`-C link-arg=-Wl,-rpath,$ORIGIN/python/lib`) so `LD_LIBRARY_PATH`
   isn't needed at runtime.

## Honest scope (what this does NOT prove yet)

- **Tauri integration** — resolve PBS dir via `app.path().resolve(.., Resource)`.
- **Native wheels** (py7zr, orjson, Pillow) — ship as real files in resource
  dir, add that dir to `sys.path`. Can't be in-binary.
- **macOS** — sign + notarize `libpython` and every native wheel; handle
  `__pycache__` writability (`PYTHONDONTWRITEBYTECODE=1`); no PBS universal2,
  ship per-arch.
- **Multiple targets** — swap the PBS tarball + link flags; all 5 target
  triples are published by PBS and have native GitHub Actions runners.
- **Plugin isolation** — a Python crash downs the host; sandboxing is a later
  concern (consider subprocess plugins if that matters).

`→ skipped: Tauri wiring + native-wheel packaging + signing; add when promoting into the app.`
