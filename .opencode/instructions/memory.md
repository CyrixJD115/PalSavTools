<!--
  INSTRUCTIONS: how auto-load memory works
  ─────────────────────────────────────────
  This file is listed in .opencode/opencode.jsonc under "instructions".
  That means its content is injected into every agent session automatically —
  no need to @-mention or manually load it.

  To auto-load ADDITIONAL files, add paths to the "instructions" array:
    "instructions": [
      ".opencode/instructions/memory.md",
      ".opencode/instructions/rules.md",
      "docs/STYLEGUIDE.md"
    ]

  To use SKILLS (on-demand deep dives) instead:
  - Put SKILL.md in .opencode/skills/<name>/SKILL.md
  - Agents will see it listed and can load with skill({ name: "..." })

  Edit this file freely — changes apply next session.
-->

# PST (PalworldSaveTools) v2.0.0

## Project Purpose
Desktop GUI + CLI toolkit for editing, repairing, transferring, and converting Palworld save files. Operates on `Level.sav`, per-player `.sav`, and Xbox GamePass (UWP) containers.

## Tech Stack
- **Language:** Python >=3.11
- **GUI:** PySide6 (Qt6), frameless QMainWindow, Fusion style
- **Package mgr:** `uv` (workspace), pip fallback
- **Build:** Nuitka (primary, --onefile), cx_Freeze + Inno Setup (Win installer)
- **Serialization:** `palsav-flex` (custom fork of palworld-save-tools) — UE GVAS binary
- **Compression:** Oodle (Kraken) via `palooz` (C++ ext), zlib fallback
- **Testing:** pytest (dynamic-import registry), structural audit harness
- **CI:** GitHub Actions (5 workflows)
- **i18n:** Custom flat-dict, 8 languages, English fallback

## Key Architecture
- **3-layer save pipeline:** SAV bytes <-> GVAS (UE struct) <-> Python dict/JSON
- **Global state hub:** `palworld_aio.constants` module globals — no DI, mutated in place
- **13 manager modules:** SaveManager (QObject singleton), PlayerManager, GuildManager, etc.
- **God-class MainWindow:** 2144 lines, 4 main tabs + 5 tab classes
- **Two write strategies:** Level.sav deferred (in-memory → explicit Save), player .savs immediate
- **CLI ≠ GUI divergence:** GUI skips decode for 6 large opaque properties (foliage, map-object transforms)

## Pal Editor — Bulk & Mass Actions (Jun 17 session)
### Context Menu (`editor/edit_pals.py`, `ui/tabs/base_inventory_tab.py`)
- `build_pal_context_menu` → `ScrollableContextMenu` (scrollable, gradient bg, border-radius 6px, QGraphicsDropShadowEffect)
- Keys dispatched via string-key `popup.exec_()` → `elif` chain in `contextMenuEvent` + `_on_slot_right_clicked` / `_on_pal_right_clicked`

### Clone Pal (`_clone_pal` in `editor/edit_pals.py`)
- Uses `_generate_pal_save_param` skeleton (same as add pal) → fresh `InstanceId`, correct `OwnerPlayerUId`, guild registration
- Then copies ALL source fields into skeleton via `for field in source_raw:` (skips `SlotId`/`OwnerPlayerUId`)
- Guild lookup uses `self.player_uid`, not source pal's owner
- Base pals clone (`base_inventory_tab.py` `elif action == 'clone'`) uses `copy.deepcopy` directly

### Bulk Operations (`_bulk_rename_pal`, `_bulk_feed_pal`, `_bulk_heal_pal`)
- `_gather_same_species_items(sender)` collects all same-species pals (party + palbox) by `CharacterID` (strips `boss_` prefix)
- `FramelessDialog` + `QScrollArea` + checkbox list per pal
- `_bulk_feed_pal`: `FullStomach→max`, `SanityValue→100`, clears `WorkerSick`/`PhysicalHealth`/`HungerType`/`FoodWithStatusEffect`/`Tiemr_FoodWithStatusEffect`/`FoodRegeneEffectInfo`
- `_bulk_heal_pal`: same + HP restore to max (via `calculate_max_hp`)

### Restore All / Max All Buttons
- **edit_pals.py**: Two buttons in palbox header (right of stretch, before ◀▶). Apply to party + current palbox page.
- **base_inventory_tab.py**: Two buttons in page_row (leftmost, before ◀▶). Apply to all base worker pals.
- Both methods clear selection highlight + show No Pal Data after operation.
- Button text refreshed via `refresh_labels()`.
- Visibility toggled in show/hide blocks.
- **Restore All**: HP/FullStomach/SanityValue restore + sickness cleanup.
- **Max All**: Talents(100)/Ranks(20)/Condenser(5)/Friendship(200k)/Awakening/Level 80/Work Suitabilities(10).
- Uses `_set_work_suitability` for work suitability maxing.

### i18n Key Pattern
- Bulk: `edit_pals.bulk_heal_desc`, `edit_pals.restore_all`/`_confirm`/`_success`, `edit_pals.max_all`/`_confirm`/`_success`
- Base: `base_inventory.restore_all`/`_confirm`/`_success`, `base_inventory.max_all`/`_confirm`/`_success`
- Script at `scripts/scrs/add_translation_keys.py` — add keys to `NEW_TRANSLATIONS` dict, then run

### Selection Highlight Gotchas
- `_BasePalIcon._build()` saves `was_selected = self.selected` at start, re-applies `slot_selected` at end if True
- Simply setting `_selected_idx = -1` does NOT clear the visual highlight
- Must call `widget.set_selected(False)` on the old widget BEFORE any `_rebuild()` or `update_display()`
- Same pattern in edit_pals.py: `_clear_party_highlight()` + `_clear_palbox_highlight()` before `set_clicked_pal(None)`

## Booth (ItemBooth / PalBooth) Inventory
- Booths stored in Level.sav `PalMapObjectConcreteModelSaveData`. ItemBooth → `RawData.trade_infos`, PalBooth → `CharacterContainerSaveData`.
- ItemBooth deletion: `_remove_item_from_slot` detects `booth_type` → `del` from `trade_infos` list ref (shared via removed `list()` copy in `get_booth_item_contents()`).
- PalBooth deletion: `_delete_base_pal` also cleans up the CharacterContainer slot by identity-matching `container_slot` in `values` list and `del`'ing it, then decrementing `SlotNum`.
- Booth pal entries carry `booth_char_container` dict ref from `get_booth_pal_contents()` for slot cleanup.
- `unlock_all_private_chests` zeros `private_lock_player_uid` on all booths (skip removed).

## Conventions
- PascalCase for tabs/dialogs, snake_case for modules/utilities
- `t('key', default=...)` for i18n; all UI widgets implement `refresh_labels()`
- `backup_whole_directory()` before every destructive operation
- UUID normalization: `str(uid).lower().replace('-', '')`
- Roundtrip fidelity: trailing/unknown bytes captured verbatim via `trailing_unknown_bytes`
- No DnD in pal editor (pal transfer = delete + create)
- Structural audit runs every pytest session (checks file pairing, import graph, resource paths)

## README Translation (`scripts/scrs/translate_readme.py`)
After editing `README.md` (esp. adding/renaming sections), **re-run** the script to regenerate all 7 translated files:
```
python scripts/scrs/translate_readme.py all
```
Key gotchas if translations appear broken:
- **Stale files, not script bug** — check if the source README changed before assuming the script is wrong. Regenerate first.
- **Logo/asset paths in `HEADER_SECTION`** — must be relative to `resources/readme/` (i.e. `../assets/branding/...`), not root-level. The English `README.md` lives at repo root and uses `resources/assets/branding/...`; the translated copies live one level deeper at `resources/readme/README.xx_XX.md`.
- **Team section content** — the script auto-translates the whole body, including The Palworld Team subheadings and bios. If they're in English, the translated files are just stale.
