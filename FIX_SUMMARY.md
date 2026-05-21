# PST (Palworld Save Tools) Fix Summary

## Overview

Fixes for compatibility with the latest Palworld game patch (May 2026). The update changed several binary structures in `Level.sav`, breaking player detection in the "Search Players" tab and causing potential data corruption on save.

---

## Issue 1: Guild Player Parsing (`group.py`)

### Root Cause

The latest game patch (v1.0) changed the Guild `RawData` remaining-bytes structure. There are now **three distinct formats** depending on how the save was created:

| Feature | Pre-v1.0 (OldSave) | Upgraded pre-v1.0 (PylarSave) | Created on v1.0 (NewSave) |
|---------|-------------------|-------------------------------|---------------------------|
| 4-byte prefix `00000000` | No | **Yes** | **Yes** |
| Fields after admin_uid before player data | None (count follows immediately) | None (count follows immediately) | 26 bytes: u3(4)+u4(4)+u5(2)+u6(4)+u7(4)+u8(4)+u9(4) |
| Per-player UID in guild | Yes (16-byte GUID) | Yes (16-byte GUID) | **No** (stored only in `CharacterSaveParameterMap`) |
| Per-player tail | 4-byte trailing after all players | 31-byte tail | 31-byte tail per player |
| Total remaining bytes | 58 | 88–89 | 95 |

The **upgraded** format (PylarSave) was missed by the original fix: it has the v1.0 prefix but keeps OLD-style player entries with GUIDs, and uses 31-byte tails. The OLD format path was reading the prefix as part of the admin_uid, producing a wrong UID (e.g. `00000000-4e6d-acb6-...` instead of `4e6dacb6-...`) and count=0.

### Changes Made

**`src/palworld_save_tools/rawdata/group.py`:**

1. **Added 3 extra `i32` fields** (`unknown_7`, `unknown_8`, `unknown_9`) after `unknown_6` in both `decode_bytes` and `encode_bytes` — accounts for the 12 bytes between admin UID and player data in the v1.0 native format.

2. **Removed per-player GUID parsing in NEW path** — v1.0 native format stores `last_online_real_time(i64)` + `player_name(fstring)` + 31-byte tail per player, with no per-player GUID.

3. **Left `player_uid` as empty string `''`** in NEW path — PST's `_enrich_guild_player_uids()` (in `save_manager.py`) cross-references names against `CharacterSaveParameterMap` to fill in the real UID.

4. **Added prefix skipping to OLD format path** — checks for and reads the 4-byte `00000000` prefix before reading `admin_player_uid`, so it correctly handles upgraded pre-v1.0 saves.

5. **Try-new-format-first** — NEW format path runs first; if it fails, OLD (with prefix awareness) handles it; if both fail, `opaque_full` preserves raw bytes.

### File Changes

| File | Lines Changed | Description |
|------|-------------|-------------|
| `group.py` decode | 56-75 | NEW decode: 3 extra i32, empty player_uid, no per-player guid |
| `group.py` decode | 82-84 | OLD decode: skip 4-byte prefix before reading admin_uid |
| `group.py` encode | 197-205 | NEW encode: writes 3 extra i32, no per-player guid write |

---

## Issue 2: Character Data Parsing (`character.py`)

### Root Cause

The new patch format stores character properties inside `object.SaveParameter.value` the same way as before, so decoding works. However, `character.py` had a check that raised an exception on trailing bytes:

**`.bak` version (original):**
```python
if not reader.eof():
    raise Exception('Warning: EOF not reached')
```

**Current version (fixed):**
```python
if not reader.eof():
    char_data['unknown_bytes'] = [int(b) for b in reader.read_to_end()]
```

This prevents crashes when the new format has extra bytes after the expected fields.

### File Changes

| File | Lines Changed | Description |
|------|-------------|-------------|
| `character.py` | 14-15 | Silently absorb trailing bytes instead of raising exception |

---

## Issue 3: Double-Write Bugs (8 Encoder Files)

### Root Cause

Eight rawdata encoder files wrote `trailing_bytes` or `unknown_bytes` twice — once in an explicit `writer.write(bytes(p['trailing_bytes']))` call and again in a generic `if 'trailing_bytes' in p: writer.write(...)` check at the bottom of the encoding function. This doubled the data on every save, corrupting the file.

### Files Fixed

| File | Pattern Removed |
|------|----------------|
| `character.py` | Generic trailing_bytes/unknown_bytes re-check at bottom of `encode_bytes` |
| `item_container_slots.py` | Same |
| `base_camp.py` | Same |
| `work_collection.py` | Same |
| `worker_director.py` | Same |
| `dynamic_item.py` | Same |
| `foliage_model.py` | Same |
| `build_process.py` | Same |

These files had the explicit write removed to eliminate the duplication, keeping only the generic bottom-of-function check (or vice versa, depending on the file).

### Files Verified Clean (No Change Needed)

| File | Reason |
|------|--------|
| `connector.py` | Already clean — no duplicate pattern |
| `foliage_model_instance.py` | Already clean |
| `guild_item_storage.py` | Already clean |
| `guild_lab.py` | Already clean |
| `item_container.py` | Already clean |
| `map_concrete_model.py` | Already clean |

---

## Detailed Binary Structure Reference

### Pre-v1.0 (OldSave) — 58 bytes
```
[admin_player_uid: 16 bytes]     e.g. {4e6dacb6-0000-0000-0000-000000000000}
[player_count: i32 (4 bytes)]
For each player:
  [player_uid: 16 bytes GUID]    e.g. {4e6dacb6-0000-0000-0000-000000000000}
  [last_online_real_time: i64]
  [player_name: fstring]
[trailing: 4 bytes]
```

### Upgraded pre-v1.0 (PylarSave) — 88–89 bytes
```
[unknown_guild_field: 4 bytes]   ← 00 00 00 00 (v1.0 prefix)
[admin_player_uid: 16 bytes]     e.g. {4e6dacb6-0000-0000-0000-000000000000}
[player_count: i32 (4 bytes)]
For each player:
  [player_uid: 16 bytes GUID]    e.g. {4e6dacb6-0000-0000-0000-000000000000}
  [last_online_real_time: i64]
  [player_name: fstring]
[31-byte tail (opaque)]          ← instead of 4-byte trailing
```

### Created on v1.0 (NewSave) — 95 bytes
```
[unknown_guild_field: 4 bytes]   ← 00 00 00 00 (v1.0 prefix)
[admin_player_uid: 16 bytes]     e.g. {00000002-0000-0302-0000-000000000000}
[unknown_3: i32]                 0
[unknown_4: byte[4]]             [0, 1, 0, 0]
[unknown_5: u16]                 1
[unknown_6: i32]                 0
[unknown_7: i32]                 0
[unknown_8: i32]                 0
[unknown_9: i32]                 0
[player_count: i32]              1
For each player:
  [12 bytes unknown zeros]
  [last_online_real_time: i64]
  [player_name: fstring]
  [31-byte tail (opaque)]
```

---

## Verification

| Test | OldSave | PylarSave (upgraded) | NewSave (v1.0 native) |
|------|---------|---------------------|----------------------|
| Parse → guild shows correct players | ✅ (Pylar, Roxx) | ✅ (Pylar, Roxx) | ✅ (Pylar) |
| Parse → correct player UIDs | ✅ | ✅ (matches .sav filenames) | ✅ (enriched from char map) |
| Parse → player levels | ✅ | ✅ (Pylar=64, Roxx=56, Azurai=60) | ✅ (Pylar=80) |
| Parse → pal counts | ✅ | ✅ | ✅ (943) |
| Round-trip (read → encode → read) | ✅ | ✅ | ✅ |
| Full compressed `.sav` round-trip | ✅ | ✅ | ✅ |
| UID matches player .sav filename | ✅ | ✅ | N/A (enriched) |
