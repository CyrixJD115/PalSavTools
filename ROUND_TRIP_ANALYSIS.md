# Palworld Save Tool Round-Trip Issue Analysis

## Executive Summary
The round-trip issue where players cannot load their normal characters when using the latest PST version is caused by fundamental data structure incompatibilities in how guild player data is encoded and decoded between the old (76-line) and new (192-line) versions of `group.py`.

## Detailed Analysis

### 1. File Structure Comparison

**Pre-v1.0 Save** (`C:\Users\Administrator\Desktop\PST_v1.1.88\Pylar Save\`)
- Level.sav: 4,578,587 bytes
- Players directory with 4 files
- Headers indicate standard Palworld save format

**Post-v1.0 Save** (`C:\Users\Administrator\Desktop\PST_v1.1.88\PylarSave\`)
- Level.sav: 4,479,653 bytes (98,934 bytes smaller)
- Players directory with 4 files
- Some player files changed in size

### 2. Player File Changes

| File | Pre-v1.0 | Post-v1.0 | Difference |
|------|----------|-----------|------------|
| 2F2CA634000000000000000000000000.sav | 19,263 | 19,263 | 0 bytes |
| 4E6DACB6000000000000000000000000.sav | 21,358 | 21,347 | -11 bytes |
| 4E6DACB6000000000000000000000000_dps.sav | 140,973 | 140,973 | 0 bytes |
| 910CC8A7000000000000000000000000.sav | 18,007 | 18,147 | +140 bytes |

### 3. Code Changes in group.py

#### Old Version (76 lines) - `src/src/palworld_save_tools/rawdata/group.py`

**Key Player Parsing (Line 27):**
```python
guild: dict[str, Any] = {
    'admin_player_uid': reader.guid(),
    'players': reader.tarray(player_info_reader),
    'trailing_bytes': reader.byte_list(4)
}
```

**Player Info Reader (Line 4):**
```python
def player_info_reader(reader: FArchiveReader) -> dict[str, Any]:
    return {
        'player_uid': reader.guid(),
        'player_info': {
            'last_online_real_time': reader.i64(),
            'player_name': reader.fstring()
        }
    }
```

**Encoding (Line 73):**
```python
writer.tarray(player_info_writer, p['players'])
```

#### New Version (192 lines) - `src/palworld_save_tools/rawdata/group.py`

**New UUID Conversion Functions (Lines 10-23):**
```python
def fguid_to_uuid(a: int, b: int, c: int, d: int) -> _stdlib_uuid.UUID:
    time_low = a & 0xFFFFFFFF
    time_mid = (b >> 16) & 0xFFFF
    time_hi_version = b & 0xFFFF
    clock_seq_hi_variant = (c >> 24) & 0xFF
    clock_seq_low = (c >> 16) & 0xFF
    node = ((c & 0xFFFF) << 32) | (d & 0xFFFFFFFF)
    return _stdlib_uuid.UUID(fields=(time_low, time_mid, time_hi_version, clock_seq_hi_variant, clock_seq_low, node))

def uuid_to_fguid(uid: _stdlib_uuid.UUID) -> tuple[int, int, int, int]:
    a = uid.time_low & 0xFFFFFFFF
    b = ((uid.time_mid & 0xFFFF) << 16) | (uid.time_hi_version & 0xFFFF)
    c = ((uid.clock_seq_hi_variant & 0xFF) << 24) | ((uid.clock_seq_low & 0xFF) << 16) | ((uid.node >> 32) & 0xFFFF)
    d = uid.node & 0xFFFFFFFF
    return a, b, c, d
```

**Heuristic Player Extraction (Lines 34-63):**
```python
def _extract_players_from_unknown(unknown_bytes: list[int]) -> list[dict[str, Any]]:
    ub = bytes(unknown_bytes)
    players = []
    used = set()
    offset = 0
    while offset < len(ub) - 28:
        # Complex heuristic scanning for player data patterns
        str_len_bytes = ub[offset+24:offset+28]
        str_len = int.from_bytes(str_len_bytes, 'little', signed=False)
        if 2 <= str_len <= 100 and offset + 28 + str_len <= len(ub):
            try:
                name = ub[offset+28:offset+28+str_len].decode('utf-8').rstrip('\x00')
                if name.isprintable() and len(name) >= 1:
                    a = int.from_bytes(ub[offset:offset+4], 'little')
                    b = int.from_bytes(ub[offset+4:offset+8], 'little')
                    c = int.from_bytes(ub[offset+8:offset+12], 'little')
                    d = int.from_bytes(ub[offset+12:offset+16], 'little')
                    uid = fguid_to_uuid(a, b, c, d)
                    iv = int.from_bytes(ub[offset+16:offset+24], 'little', signed=True)
                    players.append({'player_uid': str(uid), 'player_info': {'last_online_real_time': iv, 'player_name': name}})
                    # ... continues
```

**Complex Guild Parsing (Lines 94-121):**
```python
def parse_guild(has_extra_field: bool) -> dict[str, Any]:
    r = FArchiveReader(remaining, debug=False)
    result: dict[str, Any] = {}
    if has_extra_field:
        result['unknown_guild_field'] = [int(b) for b in r.byte_list(4)]
    result['admin_player_uid'] = r.guid()
    result['unknown_3'] = r.i32()
    result['unknown_4'] = [int(b) for b in r.byte_list(4)]
    result['unknown_5'] = r.u16()
    result['unknown_6'] = r.i32()
    raw = r.read_to_end()
    players = _extract_players_from_unknown(raw)
    if not players:
        players = _extract_players_from_old_unknown(raw) or []
    result['players'] = players
    return result
```

**Manual Encoding (Lines 172-189):**
```python
players = p.get('players', [])
writer.i32(len(players))
for player in players:
    puid_str = player.get('player_uid', '')
    if isinstance(puid_str, str) and puid_str:
        puid = _stdlib_uuid.UUID(puid_str)
    elif isinstance(puid_str, _stdlib_uuid.UUID):
        puid = puid_str
    else:
        puid = _stdlib_uuid.UUID('00000000-0000-0000-0000-000000000000')
    writer.guid(puid)
    writer.i64(player['player_info']['last_online_real_time'])
    writer.fstring(player['player_info']['player_name'])
    if 'unknown_tail' in player:
        writer.write(bytes(player['unknown_tail']))
    else:
        writer.write(bytes(31))
```

### 4. Root Cause Analysis

#### **PRIMARY ISSUE: Binary Format Incompatibility**

The round-trip failure stems from incompatible binary encodings of guild player data:

1. **Old Encoding Format** (`tarray(player_info_writer, players)`):
   - Uses FArchive's structured array format
   - Internal array header with type information
   - Standard array serialization format

2. **New Encoding Format** (Manual loop):
   - Explicit `writer.i32(len(players))` count
   - Manual iteration: `guid()` + `i64()` + `fstring()` per player
   - Optional 31-byte tail per player

#### **SECONDARY ISSUE: Parsing Method Changes**

1. **Old Parsing**: Direct structured reading
   ```python
   'players': reader.tarray(player_info_reader)
   ```

2. **New Parsing**: Heuristic byte scanning
   ```python
   raw = r.read_to_end()
   players = _extract_players_from_unknown(raw)
   ```

The heuristics fail to correctly parse structured data from old saves, leading to:
- Missing player entries
- Incorrect player UIDs
- Corrupted guild data

#### **TERTIARY ISSUE: UUID Representation Changes**

1. **Old**: GUID objects read/written directly
2. **New**: String UUIDs with conversion functions

This changes the binary representation and can lead to UUID mismatches.

### 5. Round-Trip Failure Scenario

```
┌─────────────────────────────────────────────────────────────┐
│ SCENARIO: Old Save → New PST → New Save → Game Load         │
├─────────────────────────────────────────────────────────────┤
│ 1. Old Save contains structured player data (tarray format) │
│ 2. New PST tries to load using heuristic extraction         │
│ 3. Heuristics fail to correctly parse structured data       │
│ 4. Players are missing or have incorrect UIDs               │
│ 5. New PST saves with corrupted/missing player data         │
│ 6. Game cannot find valid player UIDs in guild              │
│ 7. Game forces new character creation instead of loading    │
└─────────────────────────────────────────────────────────────┘
```

### 6. Specific Code Locations Responsible

**Decoding Issues:**
- `src/palworld_save_tools/rawdata/group.py:94-121` - Complex guild parsing
- `src/palworld_save_tools/rawdata/group.py:34-63` - Heuristic player extraction
- `src/palworld_save_tools/rawdata/group.py:10-23` - UUID conversion

**Encoding Issues:**
- `src/palworld_save_tools/rawdata/group.py:172-189` - Manual player encoding
- `src/palworld_save_tools/rawdata/group.py:143-192` - Overall encode_bytes function

**Comparison:**
- `src/src/palworld_save_tools/rawdata/group.py:27` - Old structured parsing
- `src/src/palworld_save_tools/rawdata/group.py:73` - Old structured encoding

### 7. Impact on Game Loading

The game relies on guild player data to:
1. Map player UIDs to character data
2. Validate player permissions
3. Load character inventories and progress

When player UIDs are corrupted or missing:
- Game cannot find matching character data
- Assumes no valid character exists
- Forces new character creation

### 8. Recommendations for Fixing

#### **IMMEDIATE FIX (Backward Compatibility)**

1. **Detect old format during decoding:**
   ```python
   def decode_bytes(parent_reader, group_bytes, group_type):
       # ... existing code ...
       if group_type == 'EPalGroupType::Guild':
           # Try new parsing first
           try:
               parsed = parse_guild_new(...)
           except:
               # Fallback to old structured parsing
               parsed = parse_guild_old(...)
   ```

2. **Preserve original encoding format:**
   ```python
   def encode_bytes(p):
       if 'legacy_format' in p:
           # Use old tarray encoding
           writer.tarray(player_info_writer, p['players'])
       else:
           # Use new manual encoding
           # ... existing code ...
   ```

#### **LONG-TERM FIX (Unified Format)**

1. **Standardize on one binary format**
2. **Provide migration tool for old saves**
3. **Add format version detection**
4. **Implement comprehensive unit tests for round-trip scenarios**

#### **TESTING RECOMMENDATIONS**

1. Create test suite with known old-format saves
2. Verify round-trip: Old Load → New Save → Old Load
3. Verify round-trip: Old Load → New Save → New Load
4. Test with multiple player scenarios
5. Validate UUID preservation across conversions

### 9. Conclusion

The round-trip issue is caused by fundamental changes in how guild player data is encoded and decoded in the `group.py` file. The new version replaced structured array handling with heuristic parsing and manual encoding, creating binary incompatibility with old save formats. This prevents proper player data preservation and causes the game to force new character creation instead of loading existing characters.

The fix requires implementing backward compatibility by detecting and handling both old and new formats, or migrating all saves to a unified format.