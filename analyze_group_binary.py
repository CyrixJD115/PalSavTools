import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import FArchiveReader

def print_bytes_hex(data, label, max_bytes=100):
    print(f"\n{label}:")
    print(f"  Length: {len(data)} bytes")
    print(f"  Hex (first {min(max_bytes, len(data))} bytes):")
    hex_str = ' '.join(f'{b:02x}' for b in data[:max_bytes])
    print(f"    {hex_str}")
    if len(data) > max_bytes:
        print(f"    ... ({len(data) - max_bytes} more bytes)")
    print(f"  ASCII (first {min(max_bytes, len(data))} bytes):")
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:max_bytes])
    print(f"    {ascii_str}")

def analyze_group_structure(group_bytes, label):
    print(f"\n{'='*80}")
    print(f"ANALYZING: {label}")
    print(f"{'='*80}")
    
    print_bytes_hex(group_bytes, f"Full Group Data")
    
    reader = FArchiveReader(bytes(group_bytes), debug=False)
    
    try:
        print(f"\n--- Standard Fields ---")
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
        
        remaining = reader.read_to_end()
        print_bytes_hex(remaining, "Remaining Data (admin_uid + players)", max_bytes=200)
        
        print(f"\n--- Analyzing Player Data Structure ---")
        r2 = FArchiveReader(remaining, debug=False)
        
        admin_uid = r2.guid()
        print(f"admin_player_uid: {admin_uid}")
        
        remaining_after_admin = r2.read_to_end()
        print(f"Remaining after admin UID: {len(remaining_after_admin)} bytes")
        
        if len(remaining_after_admin) >= 4:
            first_4 = remaining_after_admin[:4]
            print(f"First 4 bytes after admin UID: {[int(b) for b in first_4]}")
            
            if first_4 == b'\x00\x00\x00\x00':
                print("  -> This looks like NEW format (v1.0)")
                print("  Expected structure: unknown_guild_field + admin_uid + unknown_3 + unknown_4 + unknown_5 + unknown_6 + players")
                
                r3 = FArchiveReader(remaining, debug=False)
                _ = r3.guid()
                
                try:
                    unknown_guild_field = r3.byte_list(4)
                    print(f"  unknown_guild_field: {[int(b) for b in unknown_guild_field]}")
                except:
                    print("  No unknown_guild_field found")
                
                try:
                    admin_uid_2 = r3.guid()
                    print(f"  admin_player_uid (re-read): {admin_uid_2}")
                except:
                    print("  Cannot re-read admin UID")
                
                try:
                    unknown_3 = r3.i32()
                    print(f"  unknown_3: {unknown_3}")
                except:
                    print("  No unknown_3")
                
                try:
                    unknown_4 = r3.byte_list(4)
                    print(f"  unknown_4: {[int(b) for b in unknown_4]}")
                except:
                    print("  No unknown_4")
                
                try:
                    unknown_5 = r3.u16()
                    print(f"  unknown_5: {unknown_5}")
                except:
                    print("  No unknown_5")
                
                try:
                    unknown_6 = r3.i32()
                    print(f"  unknown_6: {unknown_6}")
                except:
                    print("  No unknown_6")
                
                player_raw = r3.read_to_end()
                print_bytes_hex(player_raw, "  Raw player data", max_bytes=150)
                
                try:
                    player_count = int.from_bytes(player_raw[:4], 'little')
                    print(f"  Player count (from manual encoding): {player_count}")
                except:
                    print("  Cannot read player count (might be old tarray format)")
                
            else:
                print("  -> This looks like OLD format (pre-v1.0)")
                print("  Expected structure: admin_uid + tarray(players) + trailing_bytes")
                
                r3 = FArchiveReader(remaining, debug=False)
                _ = r3.guid()
                
                try:
                    players_tarray = r3.tarray(lambda r: ({
                        'player_uid': r.guid(),
                        'last_online': r.i64(),
                        'player_name': r.fstring()
                    }))
                    print(f"  Players (tarray): {len(players_tarray)} entries")
                    for i, p in enumerate(players_tarray):
                        print(f"    Player {i}: {p['player_name']} ({p['player_uid']})")
                except Exception as e:
                    print(f"  Failed to parse as tarray: {e}")
                    print("  Trying to parse as manual format...")
                    
                    try:
                        r4 = FArchiveReader(remaining_after_admin, debug=False)
                        player_count = r4.i32()
                        print(f"  Player count (manual): {player_count}")
                        
                        for i in range(min(5, player_count)):
                            uid = r4.guid()
                            last_online = r4.i64()
                            name = r4.fstring()
                            print(f"    Player {i}: {name} ({uid})")
                    except Exception as e2:
                        print(f"  Failed to parse as manual format: {e2}")
    
    except Exception as e:
        print(f"\nERROR during parsing: {e}")
        import traceback
        traceback.print_exc()

print("="*80)
print("BINARY GROUP DATA ANALYZER")
print("="*80)

try:
    print("\nLoading PRE-v1.0 save (Pylar Save)...")
    raw_gvas_old = decompress_sav_to_gvas('Test_RoundTrip\\Pylar_Save_Original\\Level.sav')
    g_old = GvasFile.read(raw_gvas_old, PALWORLD_TYPE_HINTS, {}, allow_nan=True)
    
    world_save = g_old.properties.get('worldSaveData', {}).value.get('value', {})
    group_map = world_save.get('GroupSaveDataMap', {}).value.get('value', [])
    
    print(f"Found {len(group_map)} groups")
    
    for i, group in enumerate(group_map):
        group_type = group.get('value', {}).get('GroupType', {}).value.get('value', '')
        group_data = group.get('value', {}).get('RawData', {}).value.get('value', {})
        
        if group_type == 'EPalGroupType::Guild':
            raw_bytes = group_data
            analyze_group_structure(list(raw_bytes.values())[0] if isinstance(raw_bytes, dict) else raw_bytes, f"PRE-v1.0 Guild Group {i}")
            break
    else:
        print("No guild groups found in pre-v1.0 save")

except Exception as e:
    print(f"Error loading pre-v1.0 save: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\nLoading POST-v1.0 save (PylarSave)...")
    raw_gvas_new = decompress_sav_to_gvas('Test_RoundTrip\\Pylar_Save_v10_Original\\Level.sav')
    g_new = GvasFile.read(raw_gvas_new, PALWORLD_TYPE_HINTS, {}, allow_nan=True)
    
    world_save = g_new.properties.get('worldSaveData', {}).value.get('value', {})
    group_map = world_save.get('GroupSaveDataMap', {}).value.get('value', [])
    
    print(f"Found {len(group_map)} groups")
    
    for i, group in enumerate(group_map):
        group_type = group.get('value', {}).get('GroupType', {}).value.get('value', '')
        group_data = group.get('value', {}).get('RawData', {}).value.get('value', {})
        
        if group_type == 'EPalGroupType::Guild':
            raw_bytes = group_data
            analyze_group_structure(list(raw_bytes.values())[0] if isinstance(raw_bytes, dict) else raw_bytes, f"POST-v1.0 Guild Group {i}")
            break
    else:
        print("No guild groups found in post-v1.0 save")

except Exception as e:
    print(f"Error loading post-v1.0 save: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)