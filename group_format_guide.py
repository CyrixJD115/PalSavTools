"""
Binary Group Data Inspector
This script helps visualize the binary structure of guild player data
"""

def print_bytes_hex(data, label, max_bytes=200):
    print(f"\n{label}:")
    print(f"  Length: {len(data)} bytes")
    print(f"  Hex dump (first {min(max_bytes, len(data))} bytes):")
    for i in range(0, min(max_bytes, len(data)), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"    {i:04x}: {hex_str:<48} |{ascii_str}|")
    if len(data) > max_bytes:
        print(f"    ... ({len(data) - max_bytes} more bytes)")

def analyze_structure():
    print("="*80)
    print("GROUP BINARY FORMAT COMPARISON")
    print("="*80)
    
    print("\n" + "="*80)
    print("OLD FORMAT (pre-v1.0) - Using tarray()")
    print("="*80)
    print("\nStructure after guild_name_modifier_uid + unknown_2:")
    print("  admin_player_uid        : 16 bytes (GUID)")
    print("  players                 : tarray structured format")
    print("    - Array header        : varies (FArchive tarray overhead)")
    print("    - Element count       : 4 bytes (int32)")
    print("    - For each player:")
    print("      - player_uid        : 16 bytes (GUID)")
    print("      - last_online       : 8 bytes (int64)")
    print("      - player_name       : FString (4 bytes length + name bytes)")
    print("  trailing_bytes          : 4 bytes")
    
    print("\nBinary example:")
    print("  [admin_uid:16 bytes][tarray_header][count:4][player1...][player2...][trailing:4]")
    
    print("\n" + "="*80)
    print("NEW FORMAT (v1.0) - Using manual encoding")
    print("="*80)
    print("\nStructure after guild_name_modifier_uid + unknown_2:")
    print("  unknown_guild_field     : 4 bytes (optional, detected as 00 00 00 00)")
    print("  admin_player_uid        : 16 bytes (GUID)")
    print("  unknown_3               : 4 bytes (int32)")
    print("  unknown_4               : 4 bytes")
    print("  unknown_5               : 2 bytes (uint16)")
    print("  unknown_6               : 4 bytes (int32)")
    print("  players                 : manual encoding format")
    print("    - player_count        : 4 bytes (int32)")
    print("    - For each player:")
    print("      - player_uid        : 16 bytes (GUID)")
    print("      - last_online       : 8 bytes (int64)")
    print("      - player_name       : FString")
    print("      - unknown_tail      : 31 bytes (padding)")
    
    print("\nBinary example:")
    print("  [00:4][admin_uid:16][u3:4][u4:4][u5:2][u6:4][count:4][player1...][player2...]")
    
    print("\n" + "="*80)
    print("KEY DIFFERENCES")
    print("="*80)
    print("\n1. FORMAT DETECTION:")
    print("   - Check first 4 bytes after unknown_2")
    print("   - If == 00 00 00 00 -> NEW format (has unknown_guild_field)")
    print("   - Otherwise -> OLD format (no unknown_guild_field)")
    
    print("\n2. PLAYER ARRAY ENCODING:")
    print("   - OLD: FArchive.tarray() with internal structure")
    print("   - NEW: Manual count + loop with 31-byte tail per player")
    
    print("\n3. UNKNOWN FIELDS:")
    print("   - NEW has: unknown_3, unknown_4, unknown_5, unknown_6")
    print("   - NEW has: unknown_tail (31 bytes) per player")
    print("   - OLD has: trailing_bytes (4 bytes) after player array")
    
    print("\n" + "="*80)
    print("ROUND-TRIP ISSUE ROOT CAUSE")
    print("="*80)
    print("\nThe problem occurs when:")
    print("  1. OLD format save is loaded with NEW PST")
    print("  2. Heuristic parsing fails or corrupts data")
    print("  3. Data is saved back in NEW format")
    print("  4. Game cannot find valid player UIDs - forces new character")
    
    print("\nHEURISTIC PARSING FAILURES:")
    print("  - Scans raw bytes for patterns (name length, valid chars)")
    print("  - May miss players if pattern doesn't match")
    print("  - May incorrectly identify data as players")
    print("  - Converts GUID to string UUID (lossy)")
    print("  - Loses trailing_bytes and tarray structure")
    
    print("\n" + "="*80)
    print("SOLUTION APPROACH")
    print("="*80)
    print("\n1. PRESERVE RAW BYTES:")
    print("   - Store original player data bytes as _raw_player_bytes")
    print("   - Tag format as _format_version ('old' or 'new')")
    
    print("\n2. DETECT FORMAT ON LOAD:")
    print("   - Try NEW format parsing first")
    print("   - Fall back to OLD format if NEW fails")
    print("   - Store appropriate _format_version tag")
    
    print("\n3. ENCODE BACK IN SAME FORMAT:")
    print("   - If _format_version == 'old' and _raw_player_bytes exists:")
    print("     Write admin_uid + raw_player_bytes (preserve exact bytes)")
    print("   - Otherwise:")
    print("     Write in NEW format with manual encoding")
    
    print("\n" + "="*80)
    print("VERIFICATION CHECKLIST")
    print("="*80)
    print("\nTo verify the fix works:")
    print("  [ ] Load OLD format save")
    print("  [ ] Check players are parsed correctly")
    print("  [ ] Save without changes")
    print("  [ ] Reload and verify players still work")
    print("  [ ] Compare binary size before/after (should be identical)")
    print("  [ ] Test game can load the saved file")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    analyze_structure()