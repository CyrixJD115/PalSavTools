# palworld_aio Restructure Plan

## 1. Problem Statement

`palworld_aio/` is a kitchen sink: **20 loose `.py` files** at the top level mixing 5 different
concerns (app lifecycle, global state, 13 managers, pal editing engine, map generation) with no
boundaries between them. `ui/` has 21 files in a flat list. Only `widgets/` and `editors/` are
sub-packaged.

The result: opening the folder tells you nothing about what depends on what. Adding a new manager
means guessing where it belongs. The two giants (`edit_pals.py` 5454 LOC, `func_manager.py` 2657
LOC) sit alongside 86-line utility files with no visual hierarchy.

## 2. Constraints (verified from code, not assumed)

### Hard constraints — CANNOT change
1. **`constants.py` must stay at `palworld_aio.constants`** — 50 call sites across the ENTIRE
   codebase do `from palworld_aio import constants` (src/, tests/, scripts/, palworld_toolsets/).
   Moving it = 50-file diff for zero benefit.

2. **`utils.py` must stay at `palworld_aio.utils`** — externally imported by palworld_toolsets
   and tests. Too much churn to move.

3. **All imports are ABSOLUTE** (`from palworld_aio.X import Y`), never relative. Python resolves
   these naturally once `src/` is on `sys.path`. Moving a file only breaks its importers, never
   its own imports of other palworld_aio modules (those use absolute paths too).

4. **Tests use `import_from('palworld_aio.X')`** via the dynamic-import registry — NOT hardcoded
   imports. Updating a test's import = changing one string. The graph_validator SKIPS
   `dynamic_importer.py`, so `import_from()` calls are purity-check-exempt.

5. **graph_validator detects circular imports** via AST. Any restructure must not introduce new
   circular chains. Current codebase already uses lazy (in-function) imports to break cycles —
   those must be preserved.

6. **file_pairer matches by STEM, not path** — moving `save_manager.py` to `managers/save_manager.py`
   doesn't break test pairing (both have stem `save_manager`).

### Soft constraints — SHOULD preserve
7. External importers (palworld_toolsets, palsav/commands/backup.py, bootup.py) reference specific
   palworld_aio modules. Each moved file = updating those external imports.

8. The Nuitka build (`build_nuitka.py`) explicitly lists `--include-module` for palsav submodules
   but does NOT list individual palworld_aio modules — it relies on normal import resolution.
   Restructure won't break the build.

9. `import_libs.py` (src/) star-imports from palsav, NOT from palworld_aio. It does NOT re-export
   palworld_aio symbols. So palworld_aio restructure doesn't affect import_libs.

## 3. Current Structure (what we're fixing)

```
palworld_aio/                          # 20 loose files + 3 subdirs
├── __init__.py                        # empty
├── main.py               (275)        # app entry
├── constants.py          (86)         # global state hub — STAYS
├── utils.py              (279)        # shared helpers — STAYS
├── updater.py            (273)        # update checking
├── save_manager.py       (1018)       # SaveManager
├── player_manager.py     (324)        # player ops
├── guild_manager.py      (705)        # guild ops
├── base_manager.py       (533)        # base export/import/clone
├── data_manager.py       (876)        # read queries + deletes
├── func_manager.py       (2657)       # catch-all cleanup ← GIANT
├── zone_manager.py       (186)        # exclusion zones
├── backup_manager.py     (191)        # .pstbase/.pst7
├── inventory_manager.py  (523)        # ItemData, PlayerInventory
├── base_inventory_manager.py (1427)   # BaseInventoryManager
├── standardized_container.py (196)    # ContainerSlot, StandardizedContainer
├── dynamic_item_manager.py (218)      # DynamicItemManager
├── dynamic_item.py       (70)         # DynamicItem helpers
├── container_ownership.py (82)        # ContainerOwnership
├── edit_pals.py          (5454)       # pal editor ← GIANT
├── dialogs.py            (1181)       # input dialogs
├── map_generator.py      (207)        # map gen
├── editors/                           # only 1 file — odd
│   └── worldoption_editor.py (265)
├── ui/                                # 21 flat files
│   ├── main_window.py    (2144)       # ← god class
│   ├── *_tab.py (×6)
│   ├── map_view/markers/items/effects.py (×4)
│   ├── header/sidebar/results_widget.py (×3)
│   ├── *_dialog.py (×5)
│   ├── skill_picker.py, tab_guide_dialog.py
│   ├── styled_combo.py, styles.py, menus.py
│   └── __init__.py                    # exports MainWindow
└── widgets/                           # 9 reusable widgets — ALREADY CLEAN
    └── ...
```

## 4. Proposed Structure

```
palworld_aio/
├── __init__.py
├── main.py                           # app entry — STAYS (bootstrap + run_aio)
├── constants.py                      # global state hub — STAYS (50 importers)
├── utils.py                          # shared helpers — STAYS (external importers)
├── updater.py                        # update checking — STAYS (self-contained, no deps on managers)
│
├── managers/                         # ★ business logic layer (operates on constants.loaded_level_json)
│   ├── __init__.py
│   ├── save_manager.py               #   SaveManager singleton
│   ├── player_manager.py             #   player ops
│   ├── guild_manager.py              #   guild ops
│   ├── base_manager.py               #   base export/import/clone
│   ├── data_manager.py               #   read queries + structural deletes
│   ├── func_manager.py               #   catch-all cleanup (2657 lines — future split candidate)
│   ├── zone_manager.py               #   exclusion zones
│   └── backup_manager.py             #   .pstbase/.pst7 compressed export/import
│
├── inventory/                        # ★ inventory + container subsystem (tightly coupled cluster)
│   ├── __init__.py
│   ├── inventory_manager.py          #   ItemData, PlayerInventory
│   ├── base_inventory_manager.py     #   BaseInventoryManager (thread-safe singleton)
│   ├── standardized_container.py     #   ContainerSlot, StandardizedContainer
│   ├── dynamic_item_manager.py       #   DynamicItemManager
│   ├── dynamic_item.py               #   DynamicItem helpers
│   └── container_ownership.py        #   ContainerOwnership (instance→container→owner resolver)
│
├── editor/                           # ★ pal + world editing
│   ├── __init__.py
│   ├── edit_pals.py                  #   PalEditorWidget (5454 lines — future split candidate)
│   ├── dialogs.py                    #   InputDialog, RadiusInputDialog, etc. (used by editor + managers + UI)
│   └── worldoption_editor.py         #   moved from editors/ (folding the singular editors/ dir)
│
├── map/                              # ★ map generation
│   ├── __init__.py
│   └── map_generator.py              #   generate_world_map
│
├── ui/                               # views (reorganized into sub-groups)
│   ├── __init__.py                   #   exports MainWindow (backward compat)
│   ├── main_window.py                #   QMainWindow god-class (2144 lines — future split candidate)
│   ├── tabs/                         #   ★ the 6 QStackedWidget pages
│   │   ├── __init__.py
│   │   ├── tools_tab.py
│   │   ├── base_inventory_tab.py
│   │   ├── inventory_tab.py
│   │   ├── pal_editor_tab.py
│   │   ├── map_tab.py
│   │   └── container_ids_tab.py
│   ├── dialogs/                      #   ★ UI dialogs (not editor dialogs)
│   │   ├── __init__.py
│   │   ├── container_selector_dialog.py
│   │   ├── player_item_dialog.py
│   │   ├── player_pal_dialog.py
│   │   ├── player_technology_dialog.py
│   │   ├── skill_picker.py
│   │   └── tab_guide_dialog.py
│   ├── chrome/                       #   ★ app-shell widgets (non-reusable, app-specific)
│   │   ├── __init__.py
│   │   ├── header_widget.py
│   │   ├── sidebar_widget.py
│   │   ├── results_widget.py
│   │   ├── styled_combo.py
│   │   ├── styles.py                 #   ThemeManager + CSS constants
│   │   └── menus.py                  #   MenuFactory, ContextMenuBuilder
│   └── map_view/                     #   ★ map rendering (QGraphicsView layer)
│       ├── __init__.py
│       ├── map_view.py               #   MapGraphicsView
│       ├── map_markers.py            #   BaseMarker, PlayerMarker
│       ├── map_items.py              #   BaseRadiusRing, ExclusionZoneItem
│       └── map_effects.py            #   EffectItem, DeleteEffect, ImportEffect
│
└── widgets/                          # reusable Qt widgets — UNCHANGED (already clean)
    ├── __init__.py
    ├── search_panel.py
    ├── stats_panel.py
    ├── menu_popup.py
    ├── scrollable_context_menu.py
    ├── base_hover_overlay.py
    ├── player_hover_overlay.py
    ├── collapsible_splitter.py
    ├── loading_popup.py
    └── tree_widgets.py
```

### What changed (summary)

| Action | Files | Reason |
|--------|-------|--------|
| **STAY** | main.py, constants.py, utils.py, updater.py | Root-level public API, too many external importers |
| **NEW DIR: managers/** | 8 files moved from root | Business logic that mutates `constants.loaded_level_json` |
| **NEW DIR: inventory/** | 6 files moved from root | Tightly coupled container/item cluster |
| **NEW DIR: editor/** | edit_pals.py + dialogs.py moved; worldoption_editor.py folded from editors/ | Editing engine + its dialogs |
| **NEW DIR: map/** | map_generator.py moved | Isolated map generation |
| **RENAME: editors/ → folded into editor/** | worldoption_editor.py | Singular-dir eliminated |
| **REORGANIZE ui/** | 21 files → 4 subdirs (tabs/, dialogs/, chrome/, map_view/) + main_window.py at root | Flat → grouped by role |
| **UNCHANGED** | widgets/ (9 files) | Already clean |

### Root file count: 20 loose files → 4 loose files

## 5. Import Rewriting Strategy

Every moved file triggers import-path updates. Here's the complete rewrite map.

### 5.1. Internal imports (palworld_aio → palworld_aio)

Each old import path → new path. The codebase uses `from palworld_aio.X import Y` exclusively.

**managers/ moves:**
```
from palworld_aio.save_manager       → from palworld_aio.managers.save_manager
from palworld_aio.player_manager     → from palworld_aio.managers.player_manager
from palworld_aio.guild_manager      → from palworld_aio.managers.guild_manager
from palworld_aio.base_manager       → from palworld_aio.managers.base_manager
from palworld_aio.data_manager       → from palworld_aio.managers.data_manager
from palworld_aio.func_manager       → from palworld_aio.managers.func_manager
from palworld_aio.zone_manager       → from palworld_aio.managers.zone_manager
from palworld_aio.backup_manager     → from palworld_aio.managers.backup_manager
```

**inventory/ moves:**
```
from palworld_aio.inventory_manager         → from palworld_aio.inventory.inventory_manager
from palworld_aio.base_inventory_manager    → from palworld_aio.inventory.base_inventory_manager
from palworld_aio.standardized_container    → from palworld_aio.inventory.standardized_container
from palworld_aio.dynamic_item_manager      → from palworld_aio.inventory.dynamic_item_manager
from palworld_aio.dynamic_item              → from palworld_aio.inventory.dynamic_item
from palworld_aio.container_ownership       → from palworld_aio.inventory.container_ownership
```

**editor/ moves:**
```
from palworld_aio.edit_pals                 → from palworld_aio.editor.edit_pals
from palworld_aio.dialogs                   → from palworld_aio.editor.dialogs
from palworld_aio.editors.worldoption_editor → from palworld_aio.editor.worldoption_editor
```

**map/ moves:**
```
from palworld_aio.map_generator             → from palworld_aio.map.map_generator
```

**ui/ reorganization:**
```
from palworld_aio.ui.tools_tab              → from palworld_aio.ui.tabs.tools_tab
from palworld_aio.ui.base_inventory_tab     → from palworld_aio.ui.tabs.base_inventory_tab
from palworld_aio.ui.inventory_tab          → from palworld_aio.ui.tabs.inventory_tab
from palworld_aio.ui.pal_editor_tab         → from palworld_aio.ui.tabs.pal_editor_tab
from palworld_aio.ui.map_tab                → from palworld_aio.ui.tabs.map_tab
from palworld_aio.ui.container_ids_tab      → from palworld_aio.ui.tabs.container_ids_tab

from palworld_aio.ui.container_selector_dialog → from palworld_aio.ui.dialogs.container_selector_dialog
from palworld_aio.ui.player_item_dialog        → from palworld_aio.ui.dialogs.player_item_dialog
from palworld_aio.ui.player_pal_dialog         → from palworld_aio.ui.dialogs.player_pal_dialog
from palworld_aio.ui.player_technology_dialog  → from palworld_aio.ui.dialogs.player_technology_dialog
from palworld_aio.ui.skill_picker              → from palworld_aio.ui.dialogs.skill_picker
from palworld_aio.ui.tab_guide_dialog          → from palworld_aio.ui.dialogs.tab_guide_dialog

from palworld_aio.ui.header_widget          → from palworld_aio.ui.chrome.header_widget
from palworld_aio.ui.sidebar_widget         → from palworld_aio.ui.chrome.sidebar_widget
from palworld_aio.ui.results_widget         → from palworld_aio.ui.chrome.results_widget
from palworld_aio.ui.styled_combo           → from palworld_aio.ui.chrome.styled_combo
from palworld_aio.ui.styles                 → from palworld_aio.ui.chrome.styles
from palworld_aio.ui.menus                  → from palworld_aio.ui.chrome.menus

from palworld_aio.ui.map_view               → from palworld_aio.ui.map_view.map_view (stays)
from palworld_aio.ui.map_markers            → from palworld_aio.ui.map_view.map_markers
from palworld_aio.ui.map_items              → from palworld_aio.ui.map_view.map_items
from palworld_aio.ui.map_effects            → from palworld_aio.ui.map_view.map_effects
```

**NOTE:** `from palworld_aio.ui.styles import X` is used in ~10 files (edit_pals, dialogs,
inventory_tab, etc.). This becomes `from palworld_aio.ui.chrome.styles import X`. Similarly
`from palworld_aio.ui.sidebar_widget import NerdBtn` (used by edit_pals, widgets/stats_panel)
becomes `from palworld_aio.ui.chrome.sidebar_widget import NerdBtn`.

### 5.2. External imports (outside palworld_aio)

These files import palworld_aio modules and need updating:

| External file | Old import | New import |
|---|---|---|
| `palworld_toolsets/character_transfer.py` | `from palworld_aio.container_ownership import ContainerOwnership` | `from palworld_aio.inventory.container_ownership import ContainerOwnership` |
| `palworld_toolsets/character_transfer.py` | `from palworld_aio.edit_pals import ...` | `from palworld_aio.editor.edit_pals import ...` |
| `palworld_toolsets/character_transfer.py` | `from palworld_aio.inventory_manager import ...` | `from palworld_aio.inventory.inventory_manager import ...` |
| `palworld_toolsets/fix_host_save.py` | `from palworld_aio.container_ownership import ...` | `from palworld_aio.inventory.container_ownership import ...` |
| `palworld_toolsets/game_pass_save_fix.py` | `from palworld_aio.utils import ...` | UNCHANGED (utils stays at root) |
| `palsav/commands/backup.py` | `from palworld_aio.backup_manager import ...` | `from palworld_aio.managers.backup_manager import ...` |

`from palworld_aio import constants` — **UNCHANGED everywhere** (constants stays at root).

### 5.3. Test imports

Tests use `import_from('palworld_aio.X')`. Update the string:

| Test file | Old | New |
|---|---|---|
| `test_constants.py` | `import_from('palworld_aio.constants')` | UNCHANGED |
| `test_utils.py` | `import_from('palworld_aio.utils')` | UNCHANGED |
| `test_imports.py` | (checks palworld_aio imports) | Verify/update as needed |

### 5.4. `from palworld_aio.ui import MainWindow`

This is used by `main.py` and resolved through `ui/__init__.py`. The `ui/__init__.py` currently
exports `MainWindow`. After restructure, `ui/__init__.py` must continue to export `MainWindow`
from its new location (`ui/main_window.py` stays at `ui/` root, so this is UNCHANGED).

## 6. Execution Plan (step-by-step)

### Phase 1: Create directory structure + __init__.py files
- Create: `managers/`, `inventory/`, `editor/`, `map/`, `ui/tabs/`, `ui/dialogs/`, `ui/chrome/`, `ui/map_view/`
- Create `__init__.py` in each new directory
- `ui/__init__.py` already exists and exports MainWindow — keep it, update if needed

### Phase 2: Move files (git mv for clean history)
- Move 8 files → `managers/`
- Move 6 files → `inventory/`
- Move 3 files → `editor/` (edit_pals, dialogs, worldoption_editor from editors/)
- Move 1 file → `map/`
- Move 6 files → `ui/tabs/`
- Move 6 files → `ui/dialogs/`
- Move 6 files → `ui/chrome/`
- Move 4 files → `ui/map_view/`
- Delete now-empty `editors/` directory
- `ui/main_window.py` STAYS at `ui/` root

### Phase 3: Rewrite all import statements
- Use `execute_code` to systematically find-and-replace all import paths across:
  - `src/palworld_aio/**/*.py` (internal)
  - `src/palworld_toolsets/**/*.py` (external)
  - `src/palsav/palsav/commands/backup.py` (external)
  - `tests/**/*.py` (test import_from strings)
- Each rewrite is a simple string substitution (old dotted path → new dotted path)

### Phase 4: Verify
1. **Compile check**: `python -m compileall src/palworld_aio` — catches syntax errors
2. **Import smoke test**: `python scripts/scrs/validate_imports.py` — imports 16 core modules
3. **Pytest fast suite**: `pytest` — runs 186 tests + structural audit (circular import detection,
   file pairing, import graph purity)
4. **Pytest slow suite**: `pytest -m slow` — save file roundtrip (verifies palsav still works)
5. **LSP check** (if available): pyright/pylsp to catch any missed import errors that runtime
   might not exercise (lazy imports, conditional imports)

### Phase 5: Update skills
- Patch `pst-gui-architecture`, `pst-ui-tabs`, `pst-pal-editor` skills with new paths
- Patch `pst-codebase` layout map

## 7. Risk Assessment

### Low risk
- **File moves**: mechanical, git mv preserves history
- **Import rewrites**: string substitution, no logic changes
- **Test stability**: tests use import_from() (string update only), file_pairer matches by stem

### Medium risk
- **Circular imports**: the graph_validator will catch these. Current code uses lazy imports
  (in-function) to break cycles — e.g. `edit_pals.py` imports from `dialogs.py` at line 3700
  (inside a function), not at module level. These lazy patterns MUST be preserved. The validator
  runs automatically at pytest session start.
- **styles.py / sidebar_widget.py consumers**: `from palworld_aio.ui.styles import X` is used by
  ~10 files. All must be updated to `ui.chrome.styles`. Missing one = ImportError at runtime.

### What this plan does NOT do (intentionally)
- Does NOT split `edit_pals.py` (5454 lines) or `func_manager.py` (2657 lines) into smaller files.
  That's a logic refactor, not a structure refactor. Flagged as "future split candidate."
- Does NOT split `main_window.py` (2144 lines) god-class. Same reason.
- Does NOT change the constants.py global-state pattern. That's an architecture decision, not
  a folder-organization task.
- Does NOT introduce backward-compat shims (re-export files at old paths). Clean break only.
- Does NOT touch `widgets/`, `palsav/`, `palworld_toolsets/`, `palworld_coord/`,
  `palworld_xgp_import/`, or anything outside `palworld_aio/` (except updating their import
  statements that reference moved palworld_aio modules).

## 8. Verification Checklist

Before marking complete, ALL of these must pass:

- [ ] `python -m compileall src/palworld_aio` — zero errors
- [ ] `python -m compileall src/palworld_toolsets` — zero errors
- [ ] `python -m compileall src/palsav/palsav/commands` — zero errors
- [ ] `python scripts/scrs/validate_imports.py` — exit 0
- [ ] `pytest` — 186 passed, 0 failed, structural audit clean
- [ ] `pytest -m slow` — save roundtrip passes
- [ ] `pytest --dump-structural` — no circular imports, no purity violations
- [ ] No remaining references to old import paths (grep verified)
- [ ] Skills updated with new paths

## 9. Decision Points for cyrix

1. **ui/ sub-organization depth**: I proposed 4 subdirs (tabs/dialogs/chrome/map_view). Alternative:
   keep ui/ flat (just move files into managers/inventory/editor/). My recommendation: sub-organize
   — 21 files in a flat dir is the same kitchen-sink problem.

2. **dialogs.py placement**: I put it in `editor/` because it's primarily consumed by edit_pals +
   func_manager + UI. Alternative: put in `ui/dialogs/` since it's UI. My recommendation: `editor/`
   — it's more of a shared business-logic helper (InputDialog, RadiusInputDialog) than a pure
   view widget.

3. **LSP tool**: I'll use pyright if available (npm), otherwise fall back to compileall + pytest
   structural audit. Do you have a preference?

4. **Commit strategy**: Single commit for the whole restructure, or phased commits (dirs → moves
   → imports)? My recommendation: single commit — it's atomic, and partial states would be broken.
