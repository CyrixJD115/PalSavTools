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

Typed `fetch()` wrapper, base path `/api`. Methods (latest count ~40):
- System: `health()`, `languages()`, `i18n(lang)`, `saveState()`, `loadFromPath(path)`, `unload()`, `exportSave()`
- Players: `players()`, `playerDetail(uid)`, `renamePlayer(uid, name)`, `setPlayerLevel(uid, level)`, `setTechPoints(uid, tp)`, `setStats(uid, stats)`, `maxAbilities(body)`, `resetPlayerTimestamp(uid)`, `deletePlayer(uid)`
- Guilds: `guilds()`, `guildDetail(id)`, `renameGuild(id, name)`, `setGuildLevel(id, level)`, `setGuildLeader(id, player_uid)`, `removeGuildMember(id, player_uid)`, `deleteGuild(id)`
- Bases: `bases()`, `baseDetail(id)`, `deleteBase(id, delete_workers)`, `setBaseRadius(id, radius)`, `renameBaseGuild(id, name)`, `setBaseGuildLevel(id, level)`
- Containers: `containers(offset, limit)`, `containerDetail(id)`, `clearContainer(id)`, `expandContainer(id, body)`
- Other: `pals(limit)`, `mapData()`, `tools()`, toolConvert/ConvertIds/RestoreMap/SlotInject/FixHostSave

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

### Feature Components (`src/lib/components/{players,bases,guilds,containers}/`)

| Component | Route | Purpose |
|---|---|---|
| `players/PlayerDetailModal.svelte` | `/players` | Rename, set level/tech/stats, max abilities, reset timestamp, viewing cage, unlock techs, delete |
| `bases/BaseDetailModal.svelte` | `/bases` | Rename guild, set guild level, adjust area range, delete with/without workers |
| `guilds/GuildDetailModal.svelte` | `/guilds` | Member table with kick, rename, set level, promote leader, delete |
| `containers/ContainerDetailModal.svelte` | `/containers` | Item slot list with counts, clear all items, expand capacity |

**Detail modal pattern**: Each modal receives a `summary` object (from the table row), loads `detail` via API in `onMount`, then shows stats + action buttons. `onclose` / `onsaved` callbacks handle dismissal. The modal div uses `onclick={onclose}` on backdrop + `e.stopPropagation()` on inner panel. Keyboard `Escape` closes.

### Routes (`src/routes/`)

| Route | Page | Guard |
|---|---|---|
| `/` | Overview — Load/Export/Unload buttons, 5 stat count cards, file details | None |
| `/players` | Sortable player table (name/UID/guild/level/status) | SaveGate |
| `/guilds` | Grid/list toggle, sortable table, card grid | SaveGate |
| `/bases` | Sortable base table (guild badge, coords, workers) | SaveGate |
| `/containers` | Infinite-scroll container table with type/location/guild; scroll-aware row range | SaveGate |
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
app.include_router(players.router)     # /api/players/*
app.include_router(guilds.router)      # /api/guilds/*
app.include_router(bases.router)       # /api/bases/*
app.include_router(containers.router)  # /api/containers/*
app.include_router(tools.router)       # /api/tools*
```

### Endpoints

#### World (read-only aggregators — `world.py`)

| Route | Methods | Returns |
|---|---|---|
| `/api/players` | GET | `PlayerListResponse` — all players with guild info, last-seen |
| `/api/guilds` | GET | `GuildListResponse` — guild summaries with member/base counts |
| `/api/bases` | GET | `BaseListResponse` — base summaries (guild name attached post-hoc) |
| `/api/containers` | GET | (redirected to containers router) |
| `/api/pals` | GET | `PalListResponse` — pal list with IVs/skills/level |
| `/api/pals/stats` | GET | aggregate pal statistics (avg level, gender ratio, talent avg, top skills) |
| `/api/map/data` | GET | `MapDataResponse` — bases + players with coord transforms |

#### Players (`routes/players.py`)

| Route | Methods | Purpose |
|---|---|---|
| `/api/players/{uid}` | GET | `PlayerDetail` — full player detail |
| `/api/players/{uid}/name` | PUT | Rename player |
| `/api/players/{uid}/level` | PUT | Set player level |
| `/api/players/{uid}/tech-points` | PUT | Set technology points (both normal + boss) |
| `/api/players/{uid}/stats` | PUT | Set stats (HP/SP/ATK/Weight/CaptureRate/WorkSpeed) |
| `/api/players/{uid}/max-abilities` | POST | Max all abilities (HP/ATK/DEF/WorkSpeed) |
| `/api/players/{uid}/reset-timestamp` | POST | Reset player last-online timestamp |
| `/api/players/{uid}/viewing-cage` | POST | Add viewing cage unlock |
| `/api/players/{uid}/unlock-techs` | POST | Unlock all technologies |
| `/api/players/{uid}` | DELETE | Delete player from save |

#### Bases (`routes/bases.py`)

| Route | Methods | Purpose |
|---|---|---|
| `/api/bases/{base_id}` | GET | `BaseDetail` — full base with guild/members/location |
| `/api/bases/{base_id}` | DELETE | Delete base (optionally delete workers) |
| `/api/bases/{base_id}/radius` | PUT | Set area range |
| `/api/bases/{base_id}/guild/name` | PUT | Rename the guild that owns this base |
| `/api/bases/{base_id}/guild/level` | PUT | Set the guild level |

#### Guilds (`routes/guilds.py`)

| Route | Methods | Purpose |
|---|---|---|
| `/api/guilds/{guild_id}` | GET | `GuildDetail` — members, bases, admin |
| `/api/guilds/{guild_id}/name` | PUT | Rename guild |
| `/api/guilds/{guild_id}/level` | PUT | Set guild level |
| `/api/guilds/{guild_id}/leader` | PUT | Promote member to leader |
| `/api/guilds/{guild_id}/members/{player_uid}` | DELETE | Remove member from guild |
| `/api/guilds/{guild_id}` | DELETE | Delete guild entirely |

#### Containers (`routes/containers.py`)

| Route | Methods | Purpose |
|---|---|---|
| `/api/containers?offset={n}&limit={n}` | GET | `ContainerListResponse` — paginated enriched container list with type/location/guild, computed from MapObjectSaveData cross-reference |
| `/api/containers/{id}` | GET | `ContainerDetail` — full item slot list |
| `/api/containers/{id}/clear` | POST | Remove all items from container |
| `/api/containers/{id}/expand` | PUT | Expand container slot capacity |

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
| `world_service.py` | Read-only dict queries: `count_world()`, `list_players/guilds/bases/containers/pals()`, `get_current_stats()`. **Contains the critical `_u()` helper** — auto-unwraps property wrappers by checking `len(cur) <= 5` (not `<= 4`) to handle StructProperty dicts (5 keys). |
| `data_service.py` | Static JSON loader for game_data + i18n; `character_name_map()` builds display name lookup; `list_languages()` |
| `base_service.py` | Base/guild mutation helpers: `_s()` (UUID normalization — strips dashes + lowercases), `_extract_id()` (preserves UUID format with dashes for display/URL), `_find_base_entry()`, `_find_guild_by_base()`, delete base with worker handling |
| `guild_service.py` | Guild mutations: get detail, rename, set level, promote leader, remove member, delete. Operates on `GroupSaveDataMap` entries |
| `player_service.py` | Player mutations: get detail, rename, set level/tech/stats, max abilities, reset timestamp, delete. Player `.sav` mutations (viewing cage, unlock techs) use `save_service.decode/encode` |
| `container_service.py` | Container operations: **list_containers** builds map-object index + guild names in parallel threads (`ThreadPoolExecutor(max_workers=2)`), then slices `entries[offset:offset+limit]` and enriches each entry. `_build_map_object_index()` cross-references `MapObjectSaveData.ConcreteModel.ModuleMap` for `target_container_id`. `_classify_container()` handles 40+ types. `_belong_inner()` extracts the inner `value` dict from the `PalItemContainerBelongInfo` StructProperty. Detail/clear/expand operate on individual containers. |
| `map_data_service.py` | Map data queries: inlines `sav_to_gvasfile` to avoid `palworld_aio.__init__` import chain; loads coord transforms via importlib |
| `tool_service.py` | Headless tool wrappers: re-invokes palsav CLI for convert, cityhash64 for convert_ids, clears WorldMapUISaveDataMap for restore_map, modifies CharacterContainerSaveData for slot_injector |

### Data Model Gotchas

- **StructProperty wrapper**: `BelongInfo`, `PlayerUId`, `GroupId`, and many other fields are wrapped in `{'struct_type': 'X', 'struct_id': UUID, 'id': None, 'value': ACTUAL_DATA, 'type': 'StructProperty'}`. The `_u()` helper auto-unwraps via `len(cur) <= 5` — never change this to `<= 4` (StructProperty dicts have 5 keys).
- **`MapObjectId` location**: In `MapObjectSaveData` entries, the type identifier (`ItemChest_04`, `PalBooth`) is at the **top level**: `obj['MapObjectId']['value']`. NOT inside `Model.RawData.value`. Use `_u(obj, "MapObjectId")`.
- **Container key format**: `ItemContainerSaveData` entry keys are StructProperty dicts `{ID: {struct_type: 'Guid', value: UUID('...')}}`. Use `_extract_id()` for display, `_s()` for comparison.
- **Container BelongInfo**: Three levels of wrapping: `BelongInfo` is a `PalItemContainerBelongInfo` StructProperty → `.value` → contains `GroupId` and `PlayerUId` fields, each of which are themselves GUID StructProperty wrappers.
- **Container list is heterogeneous**: First ~500 entries are internal/engine containers. Map-object-backed containers (Booth, Chest) start appearing at index 500+. Never assume start-of-list is representative.
- **`_s()` vs `_extract_id()`**: `_s()` normalizes (lowercase, no dashes) for dict-key comparison; `_extract_id()` preserves UUID format with dashes for display/URLs. A mismatch between the two causes all types/locations to show "Unknown".
- **Container classification**: `_classify_container()` handles 40+ map object types via case-insensitive substring matching. Falls back to "Unknown". Common types: Chest, Booth, Mining Pit, Feed Box, Factory, Campfire, Container, Medicine Facility, Kitchen, Blast Furnace, Egg Incubator, Workbench, Ice Crusher, Oil Pump, Crusher, Refrigerator, BreedFarm, Logging Site.
- **Pagination contract**: `GET /api/containers?offset=0&limit=1000` → `{containers: [...], total: N, has_more: bool}`. Frontend loads 1000 at a time, appends to array, uses IntersectionObserver sentinel for auto-load.

### Container Service Internals (`container_service.py`)

```
list_containers(level_dict, offset, limit)
  │
  ├── ThreadPoolExecutor(max_workers=2)      ← parallel
  │   ├── _build_map_index(wsd)              ← iterates MapObjectSaveData (6k entries)
  │   │   └── For each: ConcreteModel.ModuleMap → EPalMapObjectConcreteModelModuleType::ItemContainer
  │   │       → _s(target_container_id) → map key
  │   └── _build_guild_names(wsd)            ← iterates GroupSaveDataMap
  │
  ├── entries = wsd["ItemContainerSaveData"]["value"]
  ├── page = entries[offset : offset+limit]   ← slice, no iteration wasted
  └── for each entry:
        _enrich_container()                   ← type from map_index, guild from names, item count from Slots
```

### Schemas (`web/backend/schemas.py`)

~40 Pydantic models. Key groups: Health/Languages/Save lifecycle, Player/Guild/Base/Container summaries and details, mutation request schemas, map data, tools. **Mirror frontend `types/index.ts`** — add fields to both files together.

## Key Conventions

- All icon imports use `@iconify/svelte` with `"lucide:name"` strings (never `@lucide/svelte`)
- Build: `npm --prefix web/frontend run build`
- `npm` resolved via `shutil.which('npm')` (not `shell=True`)
- Vite stdout `"Local:"` line detection (not HTTP polling) for browser auto-open
- Icon buttons in header use `width: 33px; height: 33px; box-sizing: border-box` (matching version chip 33px height)
- Routes requiring a save wrap content in `<SaveGate>`
- Header version chips show GitHub commit version and Palworld game version
- Detail modals follow a consistent pattern: load detail in `onMount`, show stats grid + action buttons, `doAction()` wrapper for loading/error state, `onclick={onclose}` backdrop + `e.stopPropagation()` inner panel
- Paginated tables use IntersectionObserver sentinel for infinite scroll + scroll position tracking for "Row X–Y" range display
- All backend endpoints are async FastAPI handlers; services are synchronous Python — FastAPI's thread pool handles the blocking calls
