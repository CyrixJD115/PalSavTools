---
name: pst-binary-schemas
description: Reverse-engineered binary schemas for Booth (ItemBooth/PalBooth) and Guild rawdata in palsav. Lock flags, V1_MARKER handling, _u8_flag semantics, and roundtrip rules. Load when touching map_concrete_model.py or group.py decoders, booth/guild lock features, or debugging roundtrip drift.
---

# PST Binary Schemas — Booth & Guild

## Booth Lock Schema (`src/palsav/palsav/rawdata/map_concrete_model.py`)

### ItemBooth `trailing_bytes` (20B) -> 3 fields
RE'd by comparing unlocked vs locked Level.sav byte diffs:
```
unlocked: 000000000000000000000000 00 0000000
locked:   000000000000000000000000 01 0000000
                                    ^^ byte[12]=1
```
- `unknown_before_lock` (12B): opaque prefix
- `is_private_lock` (1B u8): **0=unlocked, 1=locked** — THIS controls the lock state
- `unknown_after_lock` (7B): opaque suffix

### PalBooth `unknown_bytes` (236B) -> 3 fields
```
unlocked byte[224]: 00
locked   byte[224]: 01
```
- `unknown_prefix` (224B)
- `is_private_lock` (1B u8): 0=unlocked, 1=locked
- `unknown_suffix` (11B)

### KEY: `private_lock_player_uid` is identical (non-zero) in BOTH locked & unlocked. Lock state is NOT that GUID — it's `is_private_lock`.

### Unlock function (`func_manager.py:748-782`)
- `deep_unlock` SKIPS both booth types
- Sets `is_private_lock = 0` on booth RawData dicts directly
- Does NOT zero `private_lock_player_uid` on booths (game needs it non-zero)

## Guild Binary Format — V1_MARKER (`src/palsav/palsav/rawdata/group.py`)

### Problem: pre-V1 bytes
Newer Palworld versions prepend ~480 bytes BEFORE the known `V1_MARKER` (`02 00 00 00 02 03 00 00 00 00`) in the guild binary tail. Old code checked `post_unk2[:10] == V1_MARKER` — missed when marker not at offset 0. try/except silently set `players: []`.

### Fix (commit 667370dd)
- **Decode:** `post_unk2[:10] == V1_MARKER` -> `post_unk2.find(V1_MARKER) >= 0`
- Pre-marker bytes saved as `_pre_v1_bytes` for roundtrip
- `_raw_tail` fallback uses `original_tail` (unmodified)

### `_u8_flag` Bug (commit 343d5abb)
Decoder unconditionally read a `_u8_flag` byte after each player entry. In pre-V1 format these flag bytes don't exist — byte after each player's fstring is the FIRST byte of the next player's GUID. Caused 1-byte shift per player -> parser overran -> 0 players parsed.

**Fix:** Changed `if not sub.eof():` -> `if group_data.get('_has_v1_marker') and not sub.eof():`. Encoder already conditional (`if '_u8_flag' in p`).

### `_u8_flag` values
- `1` = guild master/admin
- `3` = regular member
- `2` = never observed

### Guild Move Bug (commit 343d5abb)
`move_player_to_guild()` left stale `_u8_flag=1` on moved players -> multiple admins. Fix: reset `found['_u8_flag'] = 3` after appending to target guild.

### `make_member_leader` (commit 36522918)
Iterates all guild players: `_u8_flag=1` on new leader, `3` on everyone else.

## Debug Pattern
To inspect guild binary tail: convert Level.sav to JSON, load with `json_tools.load()`, search for `V1_MARKER` in `_raw_tail` hex. If at offset > 0, guild format was extended.
