import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from palworld_save_tools.archive import FArchiveReader

def analyze_raw_bytes(group_bytes, label):
    print(f"\n{'='*80}")
    print(f"ANALYZING: {label}")
    print(f"{'='*80}")
    
    print_bytes_hex(group_bytes, f"Full Group Data ({len(group_bytes)} bytes)")
    
    reader = FArchiveReader(bytes(group_bytes), debug=False)
    
    try:
        print(f"\n--- Standard Guild Fields ---")
        group_id = reader.guid()
        print(f"group_id: {group_id}")
        
        group_name = reader.fstring()
        print(f"group_name: {group_name}")
        
        char_handles = reader.tarray(lambda r: r.guid())
        print(f"individual_character_handle_ids: {len(char_handles)} entries")
        
        org_type = reader.byte()
        print(f"org_type: {org_type}")
        
        leading = reader.byte_list(4)
        print(f"leading_bytes: {[int(b) for b in leading]}")
        
        base_ids = reader.tarray(lambda r: r.guid())
        print(f"base_ids: {len(base_ids)} entries")
        
        unknown_1 = reader.i32()
        print(f"unknown_1: {unknown_1}")
        
        base_camp_level = reader.i32()
        print(f"base_camp_level: {base_camp_level}")
        
        map_objects = reader.tarray(lambda r: r.guid())
        print(f"map_object_instance_ids_base_camp_points: {len(map_objects)} entries")
        
        guild_name = reader.fstring()
        print(f"guild_name: {guild_name}")
        
        modifier_uid = reader.guid()
        print(f"last_guild_name_modifier_player_uid: {modifier_uid}")
        
        unknown_2 = reader.byte_list(4)
        print(f"unknown_2: {[int(b) for b in unknown_2]}")
        
        print(f"\n--- Player Data Section ---")
        remaining = reader.read_to_end()
        print(f"Remaining bytes after guild fields: {len(remaining)}")
        print_bytes_hex(remaining, "Raw player data section", max_bytes=150)
        
        r2 = FArchiveReader(remaining, debug=False)
        
        admin_uid = r2.guid()
        print(f"\nadmin_player_uid: {admin_uid}")
        
        remaining_after_admin = r2.read_to_end()
        print(f"Bytes after admin UID: {len(remaining_after_admin)}")
        
        if len(remaining_after_admin) >= 4:
            first_4 = remaining_after_admin[:4]
            print(f"\nFirst 4 bytes after admin UID: {[int(b) for b in first_4]} (hex: {' '.join(f'{b:02x}' for b in first_4)})")
            
            if first_4 == b'\x00\x00\x00\x00':
                print(">>> DETECTED: NEW FORMAT (v1.0) - has unknown_guild_field")
                print("Expected: unknown_guild_field + admin_uid + unknown_3 + unknown_4 + unknown_5 + unknown_6 + players")
                
                r3 = FArchiveReader(remaining, debug=False)
                _ = r3.guid()
                
                try:
                    unknown_guild_field = r3.byte_list(4)
                    print(f"unknown_guild_field: {[int(b) for b in unknown_guild_field]}")
                except Exception as e:
                    print(f"Cannot read unknown_guild_field: {e}")
                
                try:
                    admin_uid_2 = r3.guid()
                    print(f"admin_player_uid (2nd): {admin_uid_2}")
                except Exception as e:
                    print(f"Cannot read admin_uid_2: {e}")
                
                try:
                    unknown_3 = r3.i32()
                    print(f"unknown_3: {unknown_3}")
                except Exception as e:
                    print(f"Cannot read unknown_3: {e}")
                
                try:
                    unknown_4 = r3.byte_list(4)
                    print(f"unknown_4: {[int(b) for b in unknown_4]}")
                except Exception as e:
                    print(f"Cannot read unknown_4: {e}")
                
                try:
                    unknown_5 = r3.u16()
                    print(f"unknown_5: {unknown_5}")
                except Exception as e:
                    print(f"Cannot read unknown_5: {e}")
                
                try:
                    unknown_6 = r3.i32()
                    print(f"unknown_6: {unknown_6}")
                except Exception as e:
                    print(f"Cannot read unknown_6: {e}")
                
                player_raw = r3.read_to_end()
                print(f"\nRemaining for players: {len(player_raw)} bytes")
                print_bytes_hex(player_raw, "Player data (manual format)", max_bytes=150)
                
                if len(player_raw) >= 4:
                    player_count = int.from_bytes(player_raw[:4], 'little')
                    print(f"Player count (manual): {player_count}")
                    
                    r4 = FArchiveReader(player_raw, debug=False)
                    count = r4.i32()
                    print(f"Reading {count} players...")
                    for i in range(count):
                        try:
                            uid = r4.guid()
                            last_online = r4.i64()
                            name = r4.fstring()
                            print(f"  Player {i}: {name} ({uid})")
                            
                            pos = r4.tell()
                            remaining = r4.read_to_end()
                            if len(remaining) > 0:
                                print(f"    Has {len(remaining)} unknown bytes after player {i}")
                                print_bytes_hex(remaining[:31], f"    Player {i} tail", max_bytes=31)
                                r4.seek(pos + 31)
                        except Exception as e:
                            print(f"  Error reading player {i}: {e}")
                            break
            else:
                print(">>> DETECTED: OLD FORMAT (pre-v1.0) - no unknown_guild_field")
                print("Expected: admin_uid + tarray(players) + trailing_bytes")
                
                r3 = FArchiveReader(remaining, debug=False)
                _ = r3.guid()
                
                print("\nAttempting to parse as tarray (old format)...")
                try:
                    players_tarray = r3.tarray(lambda r: ({
                        'player_uid': r.guid(),
                        'last_online': r.i64(),
                        'player_name': r.fstring()
                    }))
                    print(f"Players (tarray): {len(players_tarray)} entries")
                    for i, p in enumerate(players_tarray):
                        print(f"  Player {i}: {p['player_name']} ({p['player_uid']})")
                    
                    if not r3.eof():
                        trailing = r3.byte_list(4)
                        print(f"trailing_bytes: {[int(b) for b in trailing]}")
                except Exception as e:
                    print(f"Failed to parse as tarray: {e}")
                    import traceback
                    traceback.print_exc()
    
    except Exception as e:
        print(f"\nERROR during parsing: {e}")
        import traceback
        traceback.print_exc()

def print_bytes_hex(data, label, max_bytes=150):
    print(f"\n{label}:")
    print(f"  Length: {len(data)} bytes")
    print(f"  Hex (first {min(max_bytes, len(data))} bytes):")
    for i in range(0, min(max_bytes, len(data)), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"    {i:04x}: {hex_str:<48} |{ascii_str}|")
    
    if len(data) > max_bytes:
        print(f"    ... ({len(data) - max_bytes} more bytes)")

print("="*80)
print("GROUP BINARY DATA ANALYZER")
print("="*80)

test_data = [
    {
        'name': 'PRE-v1.0 Format (Old)',
        'bytes': [
            0x4e, 0x6d, 0xac, 0xb6, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00, 0x54,
            0x65, 0x73, 0x74, 0x47, 0x75, 0x69, 0x6c, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ],
        'admin_uid': '4e6dacb6000000000000000000000000',
        'players': [
            {'name': 'Player1', 'uid': '00000000000000000000000000000001', 'last_online': 1234567890},
            {'name': 'Player2', 'uid': '00000000000000000000000000000002', 'last_online': 1234567891},
        ]
    }
]

print("\nExample OLD format structure (pre-v1.0):")
print("After guild_name_modifier_uid + unknown_2:")
print("  admin_player_uid (16 bytes GUID)")
print("  players (tarray format):")
print("    - Array header")
print("    - Player count")
print("    - For each player:")
print("      - player_uid (16 bytes GUID)")
print("      - last_online_real_time (8 bytes int64)")
print("      - player_name ( FString)")
print("  trailing_bytes (4 bytes)")

print("\nExample NEW format structure (v1.0):")
print("After guild_name_modifier_uid + unknown_2:")
print("  unknown_guild_field (4 bytes, optional)")
print("  admin_player_uid (16 bytes GUID)")
print("  unknown_3 (4 bytes int32)")
print("  unknown_4 (4 bytes)")
print("  unknown_5 (2 bytes uint16)")
print("  unknown_6 (4 bytes int32)")
print("  players (manual format):")
print("    - player_count (4 bytes int32)")
print("    - For each player:")
print("      - player_uid (16 bytes GUID)")
print("      - last_online_real_time (8 bytes int64)")
print("      - player_name (FString)")
print("      - unknown_tail (31 bytes)")

print("\n" + "="*80)
print("Run this with actual save data to see real format")
print("="*80)