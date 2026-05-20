import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS
from palobject import SKP_PALWORLD_CUSTOM_PROPERTIES

print("Testing pre-v1.0 save load...")
raw_gvas = decompress_sav_to_gvas('Test_RoundTrip\\Pylar_Save_Original\\Level.sav')
g = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
print('SUCCESS: Loaded pre-v1.0 save successfully')

world_save_data = g.properties.get('worldSaveData', {}).value.get('value', {})
group_map = world_save_data.get('GroupSaveDataMap', {}).value.get('value', [])
print(f'Guild data found: {len(group_map)} groups')

for i, group in enumerate(group_map):
    group_type = group.get('value', {}).get('GroupType', {}).value.get('value', '')
    group_data = group.get('value', {}).get('RawData', {}).value.get('value', {})
    if 'admin_player_uid' in group_data:
        format_version = group_data.get('_format_version', 'unknown')
        print(f'  Group {i}: {group_type}, format={format_version}, admin={group_data["admin_player_uid"]}')
        players = group_data.get('players', [])
        print(f'    Players: {len(players)}')
        for player in players:
            print(f'      - {player.get("player_info", {}).get("player_name", "Unknown")} ({player.get("player_uid", "No UID")})')