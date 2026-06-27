---
name: pst-webui-build
description: The architectural CONTRACT for building/extending the PST WebUI — decoupled Svelte 5 + Tailwind frontend with a lightweight Python (FastAPI) bridge, the wrap-don't-rewrite rule for reusing palsav/palworld_aio logic, the `.web_ref` visual-only reference rule, and the REST/WebSocket communication boundary. Load BEFORE planning or scoping any new WebUI screen, endpoint, or feature. For the inventory of what already exists in web/, load `pst-webui` instead.
---

# PST WebUI — Build Contract (Architectural Guardrails)

This skill is the **constitution** for WebUI work. It defines *how* the web layer must be built and what it may **not** do. It is deliberately distinct from the `pst-webui` skill, which inventories the code that already exists in `web/`.

> Read this when: scoping a new screen/route, adding an endpoint, porting a feature from the desktop app or from `.web_ref`, or deciding where logic should live. Switch to `pst-webui` once you need the concrete inventory of files/stores/routes.

## 1. Core architecture — strictly decoupled

```
web/frontend/   Svelte 5 + Tailwind CSS   (presentation, state, API client)
      ↕  REST (/api) + WebSocket (/ws)
web/backend/    FastAPI — thin bridge ONLY (parse, call core, serialize)
      ↕  imports
src/palsav, src/palworld_aio, src/palworld_toolsets  ← ALL real logic lives here
```

- **Frontend** is Svelte + Tailwind, full stop. No Python runs in the browser.
- **Backend is intentionally thin**: it validates requests, calls into the existing core project, and serializes responses. It must **not** grow domain logic.
- **Clean separation of concerns**: a UI concern never crosses into palsav, and a serialization concern never leaks into a Svelte component.

## 2. The wrap-don't-rewrite rule (non-negotiable)

All functional logic comes from the **existing** project scripts. Do **not** reinvent:

- Save pipeline → `src/palsav` (SAV↔GVAS↔JSON, compression, rawdata decoders)
- GUI-domain operations → `src/palworld_aio` (managers, editor, utils, game-data binding)
- CLI tools → `src/palworld_toolsets`, `palworld_xgp_import`, `palworld_coord`

The backend's job is to **wrap or interface** with these — import and call them. New "logic" in `web/backend/` should be limited to adaptation/glue (shaping a core result into a Pydantic schema, threading a long task, etc.). If you are about to implement save/parse/edit/stat logic inside `web/`, stop — it belongs in `src/`.

> **`src/` is NOT on `sys.path` in web context** — the editable `palsav` workspace install shadows `src/`. Services load `src/` modules via `importlib.util.spec_from_file_location` (not `sys.path`). See `map_data_service.py` for the established pattern (try/except → `sys.path.insert(0, src)` fallback for `palobject`).
> 
> Don't import from `palworld_aio` or `palworld_coord` directly — those packages pull in Qt/PySide6 or heavy init chains. Instead inline the specific function or use `importlib` for the narrow module you need.
> 
> Re-export hub reminder: `src/import_libs.py` (restored from git history but no longer imported) star-imports palsav — services import from the installed workspace packages directly.

## 3. `.web_ref` is VISUAL-ONLY

`web/.web_ref/` holds a scraped **Reflex** project. It is the canonical reference for **layout, UI components, color theme, and overall visual vibe** of the Svelte frontend.

### Extract freely (visual / structural inspiration)
- `pstmain/styles/colors.py` → palette sections (`bg`, `accent`, `status`, `text`, `border`, `gradient`, `header`, `alpha`)
- `pstmain/styles/tokens.py` → spacing, radii, shadows, transitions
- `pstmain/styles/typography.py`, `theme.py` → type scale + theme vibe
- `pstmain/components/layout/shell.py` → app shell composition: **header + sidebar + content + optional detail panel**
- `NAV_GROUPS` (in `core/constants.py`) → sidebar grouping/structure
- `pstmain/components/*` (base, common, editors, guild, inventory, map, pal, player, tools) → component layout, density, chip/badge styling
- `pstmain/pages/*` → which screens exist and how they compose
- Conventions: **dark theme only**, colors via tokens (never hardcoded), responsive grid `repeat(auto-fill, minmax(220px, 1fr))`

### NEVER copy from `.web_ref`
- **Any functional logic.** It is a Reflex app; its code is structurally incompatible with Svelte.
- The **Reflex Var system** and everything in `.web_ref/AGENTS.md` "Reflex Var System Rules" (`rx.cond`, `rx.foreach`, `.to_string()`, `.to(type)`, bracket-vs-get, etc.) — this is framework plumbing, not logic to port.
- `pstmain/states/*.py` — Reflex state classes. Svelte state lives in `web/frontend/src/stores/` (see `pst-webui`).
- `@rx.page` decorators, `shell()` implementation, `rx.menu.*` trees — reimplement in Svelte idiomatically; don't transliterate.
- `pstmain/toolsets/` — these are **duplicates** of core logic. Always use `src/` instead.

Treat `.web_ref` like a Figma file: look at it, match it, never ship its code.

## 4. Communication contract (frontend ↔ backend)

- **REST** over `/api/*` for request/response (typed via Pydantic schemas ↔ `web/frontend/src/types`).
- **WebSocket** over `/ws` for push (save state changes, long-running tool progress) — `WsManager` broadcasts; clients re-fetch on message.
- The frontend never touches the filesystem or core Python directly. Every capability is an endpoint.
- Vite proxies `/api` and `/ws` → backend in dev; backend serves the built SPA in production.

## 5. Hard rules (guardrails)

1. **Logic flows toward `src/`.** If a new capability needs real behavior, add it to the core project, then expose it via one thin endpoint — not the reverse.
2. **`.web_ref` = visual reference only.** Copying its Python/Reflex logic is a bug by definition.
3. **Backend stays lightweight.** Endpoints = validate → call core → serialize. No domain math in `web/backend/`.
4. **Types stay in sync.** Pydantic models (`web/backend/schemas.py`) mirror TS types (`web/frontend/src/types`); change both together.
5. **Svelte + Tailwind only** in the frontend; no other UI framework. Icons via `@iconify/svelte`.
6. **Match the existing vibe** (cyber-blue, dark-only, 2px borders, blocky chips) — see `pst-webui` styling section for the live token names.

## 6. Quick reference — where things live

| Concern | Location |
|---|---|
| Frontend SPA | `web/frontend/src/` (routes, stores, lib/components) |
| API client | `web/frontend/src/lib/api/client.ts` |
| Backend app | `web/backend/` (app.py, routes/, services/, schemas.py, state.py) |
| Launcher | `start.py --web` (frontend :16920, backend :16921) |
| Visual reference (LOOK ONLY) | `web/.web_ref/pstmain/` (styles/, components/, pages/) |
| Real logic (CALL THIS) | `src/palsav`, `src/palworld_aio`, `src/palworld_toolsets` |
| Existing-web inventory | load the **`pst-webui`** skill |

## 7. Definition of done for any new WebUI feature

- [ ] Logic added to `src/` (or already exists), not duplicated in `web/`.
- [ ] One thin backend endpoint wraps it; Pydantic schema + TS type both updated.
- [ ] Svelte component matches the cyber-blue/dark theme and reuses existing UI primitives (`Card`, `Button`, `Badge`, etc.) before introducing new ones.
- [ ] Visual styling cross-checked against `.web_ref`; no Reflex code copied.
- [ ] Save-gated screens wrapped in `<SaveGate>`.
