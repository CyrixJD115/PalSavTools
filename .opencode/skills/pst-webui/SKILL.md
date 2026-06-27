---
name: pst-webui
description: The PST WebUI layer — FastAPI backend (web/backend/), Svelte 5 + Tailwind SPA frontend (web/frontend/), CLI launcher (start.py --web), theme system, Iconify icons, modals, stores, and API client. Load when editing web/, start.py WebUI code, or the frontend/backend architecture.
---

# PST WebUI — Frontend + Backend

Ports: frontend **16920**, backend **16921**. Vite proxies `/api` and `/ws` to backend.

## Launcher (`start.py --web`)

- Creates venv + `uv sync`; checks `npm` via `shutil.which('npm')` (no `shell=True`)
- Runs `npm --prefix web/frontend run dev -- --host 127.0.0.1 --port 16920`
- Runs `uv run python -m web.backend.main`
- Stdout pipes prefixed `[frontend]` / `[backend]`
- **Browser auto-open**: `threading.Event` + thread reading Vite stdout for `"Local:"` line; falls back to printing URL if `webbrowser.open()` returns `False`

## Frontend — Svelte 5 + Tailwind (dark-only)

### Icons — `@iconify/svelte` (NOT `@lucide/svelte`)

```svelte
<script lang="ts">
  import Icon from '@iconify/svelte';
</script>
<Icon icon="lucide:info" width={16} />
```

All Lucide imports migrated to `@iconify/svelte`. Icon string format: `"lucide:name"` or `"simple-icons:name"`. The `<Icon>` component renders an SVG; `width` controls both dimensions for square icons.

### Stores (`src/stores/`)

| Store file | Exports |
|---|---|
| `index.ts` | `health`, `isHealthy`, `wsConnected`, `languages`, `currentLang`, `i18n`, `saveState`, `saveLoaded`, `saveSummary`, `saveCounts`, `loadingSave`, `loadError`, `t()`, `resetSaveData()` |
| `toast.ts` | `pushToast()`, `dismissToast()`, toast kind: `info/success/warning/error` |
| `toolStore.ts` | `tools`, `currentTool`, `isModalOpen`, `isRunning`, `output`, `error`, `openTool()`, `closeModal()`, `resetState()` |

### API Client (`src/lib/api/client.ts`)

Typed `fetch()` wrapper, base path `/api`. 15 methods: `health()`, `languages()`, `i18n(lang)`, `saveState()`, `loadFromPath(path)`, `unload()`, `exportSave()`, `players()`, `guilds()`, `bases()`, `containers(limit)`, `pals(limit)`, `tools()`, toolConvert/ConvertIds/RestoreMap/SlotInject/FixHostSave.

### Layout Components (`src/lib/components/layout/`)

| Component | Purpose |
|---|---|
| `Header.svelte` | Version chips (GitHub + save version), info/warn/toolbox icon buttons, Discord link, save status badge, backend health dot, file size/counts |
| `Sidebar.svelte` | 4 nav groups (Tools/Editors/Utilities), active-page detection from `$page.url.pathname`, grays out save-required links |
| `LoadSaveModal.svelte` | File path input dialog, Enter-to-load, error display |
| `AboutModal.svelte` | App version, feature list, GitHub link, copyright |
| `WarningModal.svelte` | 3 warning cards (backups, patches, errors) |

### UI Components (`src/lib/components/ui/`)

| Component | Purpose |
|---|---|
| `Card.svelte` | Reusable card with optional title/hover/class |
| `Button.svelte` | Variants: primary/secondary/ghost/danger, loading spinner |
| `Badge.svelte` | Tones: neutral/accent/success/warning/error/amber |
| `Spinner.svelte` | CSS rotation spinner |
| `EmptyState.svelte` | Centered icon + title + description slot |
| `SaveGate.svelte` | Conditional wrapper — renders content only if `$saveLoaded` |
| `ComingSoon.svelte` | Phase-2 placeholder with icon + title + description |
| `ToastContainer.svelte` | Fixed bottom-right toast stack, auto-dismiss (4s/8s) |

### Tool Components (`src/lib/components/tools/`)

| Component | Purpose |
|---|---|
| `ToolCard.svelte` | Card button with category color, icon map, windows-only badge |
| `ToolGrid.svelte` | Grid grouped by Converting/Management/Utility |
| `ToolModal.svelte` | Tool-runner modal with 5 tool-specific forms |

### Routes (`src/routes/`)

| Route | Page | Guard |
|---|---|---|
| `/` | Overview — Load/Export/Unload buttons, 5 stat count cards, file details | None |
| `/players` | Player table (name/UID/guild filter) | SaveGate |
| `/guilds` | Guild cards (members/bases) | SaveGate |
| `/bases` | Base table (guild badge, coords) | SaveGate |
| `/containers` | Container table (slots, owner) | SaveGate |
| `/pal-editor` | Pal card grid (level, rank, IVs, skills, search) | SaveGate |
| `/map` | Coordinate plot (-440k..440k normalised 0-100%) | SaveGate |
| `/inventory` | **ComingSoon** | — |
| `/base-inventory` | **ComingSoon** | — |
| `/backups` | **ComingSoon** | — |
| `/exclusions` | **ComingSoon** | — |
| `/settings` | Language selector, backend info, about | None |
| `/tools` | ToolGrid + ToolModal orchestration | None |

### Styling

**Tailwind config** (`tailwind.config.js`): dark-only (`class` strategy). Custom tokens:
- Background: `bg-base` (#0A0E1A), `bg-deep`, `bg-surface`, `bg-hover`, `bg-elevated`, `bg-card`
- Accent: `accent` (#3B8ED0), `accent-cyan` (#00BCD4), `accent-electric` (#00E5FF)
- Ink: `ink-primary` through `ink-dim`
- Pal: `pal-sky`, `pal-electric`, `pal-yellow`, `pal-amber`, `pal-glow`
- Status: `status-success`/`warning`/`error`/`info`/`amber`
- Glow shadows: `glow`, `glow-strong`, `glow-cyan`, `glow-electric`, `glow-amber`
- Gradients: `surface-gradient`, `header-gradient`, `nav-gradient`, `card-gradient`, `accent-gradient`, `cyber-gradient`, `amber-glow`
- Animations: `float`, `shimmer`, `breathe`, `drift`, `borderGlow`, `gradientShift`, `fadeInUp`, `pulseDot`, `slideUp`, `pulseGlow`
- Border: all weights, `border-4` token
- Fonts: `system-ui` sans, `Hack Nerd Font` mono

**Component CSS** (`app.css`): reusable classes — `.card`, `.btn` (primary/secondary/ghost/danger/warning), `.input`, `.badge`, `.chip` (blue/amber/green), `.block-chip`, `.nav-link` (active/inactive with animated left-border), `.glow-border`, `.pulse-dot`, custom scrollbar, drifting grid background animation.

**Theme**: Cyber-blue with blocky futuristic elements — 2px borders, `rounded-6`, solid color-block chips, 4px nav-link indicator. Animated drifting grid background via `body::before`.

### Vite Config (`vite.config.ts`)

```ts
server: {
  port: 16920,
  proxy: { '/api': 'http://127.0.0.1:16921', '/ws': 'ws://127.0.0.1:16921' },
  watch: { usePolling: true, interval: 300 }
}
```

Build: `@sveltejs/adapter-static`, SPA fallback via `index.html`. Output to `build/`. Aliases: `$lib` → `src/lib`, `$components` → `src/lib/components`, `$stores` → `src/stores`, `$types` → `src/types`.

## Backend — FastAPI

### Entry (`web/backend/main.py`)

Bootstraps `sys.path` to include `src/`, calls `app.create_app()`, runs `uvicorn` on `PST_WEB_HOST:PST_WEB_PORT` (default `127.0.0.1:16921`). No reload (Vite handles HMR).

### Resource path resolution (`paths.py`)

`RESOURCES_DIR = REPO_ROOT / "src" / "_resources"` (the old `resources/` was renamed to `src/_resources/`). Serves `game_data/` and `i18n/` from there. See `pst-codebase` for the resource layout.

### Key fixes / gotchas

- **`map_data_service.py` (lines 513–531)**: `list_map_players()` inlines `sav_to_gvasfile` directly instead of importing from `palworld_aio.utils`. Reason: `palworld_aio.__init__` imports `main.py` which pulls in deleted/renamed modules (`i18n` → `_i18n`, `import_libs`). The inlined version only imports `palsav` (installed workspace pkg) and `palobject` (via try/except + `sys.path.insert(0, src)` fallback).
- **`palobject.py`**: replaced `from import_libs import *` with explicit imports (`ctypes`, `FArchiveReader`, `FArchiveWriter`, etc.). `import_libs.py` was deleted during the refactor.
- **`paths.py`**: `RESOURCES_DIR` points to `REPO_ROOT / "src" / "_resources"` now, not `"resources"` (the dir was renamed).
- **`start.py`**: `KeyboardInterrupt` caught around `subprocess.call` to avoid traceback on Ctrl+C.

### App Factory (`web/backend/app.py`)

```python
app = FastAPI(title="PST WebUI")
app.add_middleware(CORSMiddleware, ...)
app.mount("/ws", ws_app)  # WebSocket
app.include_router(health.router)      # /api/health
app.include_router(save.router)        # /api/save/*
app.include_router(data.router)        # /api/data/*
app.include_router(world.router)       # /api/players, /guilds, /bases, etc.
app.include_router(tools.router)       # /api/tools*
# Static SPA fallback for production builds
```

### Endpoints

| Route | Methods | Module |
|---|---|---|
| `/api/health` | GET | `health.py` — regex-parses `APP_VERSION`/`GAME_VERSION` from `src/common.py` |
| `/api/save/state` | GET | `save.py` — returns current save state |
| `/api/save/load` | POST | `save.py` — load from path, payload `{path}` |
| `/api/save/upload` | POST | `save.py` — upload .sav file, parse |
| `/api/save/export` | POST | `save.py` — stream re-encoded .sav |
| `/api/save` | DELETE | `save.py` — unload |
| `/api/data/game-data` | GET | `data.py` — list all game data names |
| `/api/data/game-data/{name}` | GET | `data.py` — specific JSON |
| `/api/data/i18n/{lang}` | GET | `data.py` — locale strings |
| `/api/data/languages` | GET | `data.py` — available languages |
| `/api/players` | GET | `world.py` — player summaries |
| `/api/guilds` | GET | `world.py` — guild summaries |
| `/api/bases` | GET | `world.py` — base summaries |
| `/api/containers` | GET | `world.py` — container summaries |
| `/api/pals` | GET | `world.py` — pal summaries |
| `/api/pals/stats` | GET | `world.py` — aggregate pal stats |
| `/api/tools` | GET | `tools.py` — 11 tool definitions |
| `/api/tools/convert` | POST | `tools.py` — SAV↔JSON |
| `/api/tools/convert-ids` | POST | `tools.py` — Steam↔PalworldID |
| `/api/tools/restore-map` | POST | `tools.py` — clear fog of war |
| `/api/tools/slot-injector` | POST | `tools.py` — container slot count |
| `/api/tools/fix-host-save` | POST | `tools.py` — host save fix |

### Config (`web/backend/config.py`)

```python
PST_WEB_HOST = os.getenv("PST_WEB_HOST", "127.0.0.1")
PST_WEB_PORT = int(os.getenv("PST_WEB_PORT", "16921"))
SERVE_FRONTEND = strtobool(os.getenv("PST_SERVE_FRONTEND", "true"))
CORS_ORIGINS = ["http://127.0.0.1:16920", "http://localhost:16920"]
```

### State (`web/backend/state.py`)

`SaveState` singleton with `threading.RLock`. Holds `LoadedSave` dataclass:
```python
@dataclass
class LoadedSave:
    filename, save_dir, players_dir, save_type, class_name, file_size, loaded_at
    gvas: GvasFile           # for re-encode
    level_dict: dict         # for queries
```

### WebSocket (`web/backend/ws_manager.py`)

Clients connect to `/ws`. `WsManager` broadcasts `save_state` / `save_update` JSON messages to all clients on load/unload. Frontend re-fetches `api.saveState()` on WS message.

### Services (`web/backend/services/`)

| Service | Role |
|---|---|
| `save_service.py` | SAV↔GVAS↔dict decode/encode via palsav; safety net catches custom property decoder failures and stores them as opaque bytes; 6 skip-path overrides for heavy foliage/spawner properties |
| `world_service.py` | Read-only dict queries: `count_world()`, `list_players/guilds/bases/containers/pals()`, `get_current_stats()` |
| `data_service.py` | Static JSON loader for game_data + i18n; `character_name_map()` builds display name lookup; `list_languages()` |
| `tool_service.py` | Headless tool wrappers: re-invokes palsav CLI for convert, cityhash64 for convert_ids, clears WorldMapUISaveDataMap for restore_map, modifies CharacterContainerSaveData for slot_injector |

### Schemas (`web/backend/schemas.py`)

26 Pydantic models mirroring frontend `types/index.ts` — `HealthResponse`, `LanguagesResponse`, `SaveStateResponse`, `SaveSummary`, `WorldCounts`, `PlayerSummary`, `GuildSummary`, `BaseSummary`, `ContainerSummary`, `PalSummary`, `ToolInfo`, `ConvertRequest/Response`, `ConvertIdsRequest/Response`, `SlotInjectRequest/Response`, `FixHostSaveRequest/Response`.

## Key Conventions

- All icon imports use `@iconify/svelte` with `"lucide:name"` strings (never `@lucide/svelte`)
- Build: `npm --prefix web/frontend run build`
- `npm` resolved via `shutil.which('npm')` (not `shell=True`)
- Vite stdout `"Local:"` line detection (not HTTP polling) for browser auto-open
- Icon buttons in header use `width: 33px; height: 33px; box-sizing: border-box` (matching version chip 33px height)
- Routes requiring a save wrap content in `<SaveGate>`
- Header version chips show GitHub commit version and Palworld game version
