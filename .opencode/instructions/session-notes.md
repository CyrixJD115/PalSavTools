# PST Session Notes (Detailed Work Logs)

<!--
  NOT auto-loaded. Reference-only archive of detailed session work logs.
  These are historical records of specific debugging/feature sessions.
  If you need details on a specific feature/fix, search this file.
-->

## Pal Editor — Bulk & Mass Actions (Jun 17)
- `build_pal_context_menu` -> `ScrollableContextMenu` (scrollable, gradient bg, shadow)
- Clone Pal: uses `_generate_pal_save_param` skeleton -> fresh InstanceId, copies all source fields
- Bulk ops: `_gather_same_species_items` collects same-species by CharacterID (strips boss_)
- `_bulk_feed_pal`: FullStomach->max, SanityValue->100, clears sicknesses
- `_bulk_heal_pal`: same + HP restore via `calculate_max_hp`
- Restore All / Max All buttons in palbox header (all 960 slots, not current page)
- Max All: two-phase — max stats first, then restore (HP recalc uses maxed stats)

## Game Data ETL (Jun 20)
- `scripts/scrs/update_game_data.py`: structure descs from DT_BuildObjectDescText_Common.json
- Structure icon CI fallback: case-insensitive lookup
- Tech desc CI fallback maps: tech_desc_l10n_ci, build_desc_l10n_ci, item_desc_l10n_ci
- Grenade fix: EPalItemTypeB::WeaponThrowObject exempt from SINGLETON_TYPE_A; equip slots show "Edit Quantity" for food+weapon

## NPC Work Suitabilities (Jun 20)
- `update_npc_data()` now loads DT_PalHumanParameter.json (433 entries, 13 WS fields + stats)
- `update_pal_descriptions()` merges WS/stats into elementless pals[] entries (369/384)
- `_load_pal_base_data()` caches npcs[] as fallback

## Key Items — Double-Click Delete Fix (Jun 23)
- Problem: `get_items()`/`get_slot_at()` omitted container_type -> `_delete_item_direct` used wrong container
- Fix: InventoryContainer accepts container_type param, get_items/get_slot_at include it
- `_delete_item_direct` checks is_bounty first -> remove_bounty_item()

## Level.sav Debug — Orphaned BossReward Containers (Jun 23)
- CLI: `uv run python -m palsav.cli convert --to-json --output out.json in.sav`
- ViperGeek save: placeholder admin UID (all zeros+1), zero BossDefeatReward items
- Legacy container 419aef792ddd: world container, 200 slots, 4 old bugged items from v1.1.88

## Bounty Tokens & Boss Defeat Flags (Jun 22)
- Stored in player .sav only: RecordData.NormalBossDefeatFlag (MapProperty), BossDefeatExpBonusTableIndex, bossTechnologyPoint
- Boss mapping: boss_mapping.json from two-phase approach (UI/DT_BossSpawnerLocationData + Spawner/DT_PalWildSpawner)
- Shared key issue: worldtree_9_55_WorldTreeAura shared by Warsect + Relaxaurus_Electric
- API: add_item early-returns for BossDefeatReward_*, remove_item cleans boss flags
- Known game bug: may regenerate/wipe NormalBossDefeatFlag if detects inconsistency
- CLI fix: os.execv -> subprocess.run fallback for non-Unix

## Base Inventory — Structure Filter (Jun 23)
- Item filter vs Structure filter: mutually exclusive
- Container-type structures (ItemChest_04, Fridge, Booth): load containers, filter by map_object_id
- Non-container structures: show instance entries via add_structure_entry()
- `find_structure_locations_efficient(asset)` iterates MapObjectSaveData.values

## Booth Inventory UI (Jun 23)
- Booths in Level.sav PalMapObjectConcreteModelSaveData
- ItemBooth deletion: del from trade_infos list ref
- PalBooth deletion: _delete_base_pal cleans CharacterContainer slot
- Clear button fix: _clear_container checks booth_type, calls booth-specific clear

## Cross-Tab Player Selection Sync (Jun 22)
- select_player/clear_player on PalEditorTab + PlayerInventoryTab
- _syncing bool prevents re-entrant cross-calls
- refresh() saves prev_uid, re-selects if player still exists

## README Translation
- `scripts/scrs/translate_readme.py all` regenerates 7 translated files
- Logo paths in HEADER_SECTION relative to resources/readme/ (../assets/branding/...)
- Stale files are usually the issue, not the script — regenerate first
