import sys, os; sys.path.insert(0,'src')
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS
from palobject import SKP_PALWORLD_CUSTOM_PROPERTIES

base = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(base, 'WtfTestFix', 'Level.sav')
with open(p,'rb') as f: data = f.read()
rg, st = decompress_sav_to_gvas(data)
g = GvasFile.read(rg, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
wsd = g.properties['worldSaveData']['value']

print("=== WtfTestFix Guilds ===")
for x in wsd['GroupSaveDataMap']['value']:
    if x['value']['GroupType']['value']['value'] != 'EPalGroupType::Guild': continue
    r = x['value']['RawData']['value']
    fmt = r.get('_format_version', '?')
    adm = str(r.get('admin_player_uid', '?'))
    gname = r.get('guild_name', '?')
    has_v1 = '_v1_header' in r
    has_op = '_opaque_raw' in r
    for p in r.get('players', []):
        puid = str(p.get('player_uid', '???'))
        pname = p.get('player_info', {}).get('player_name', '???')
        print(f"  [{fmt}] '{gname}' UID={puid[:40]} Name={pname} admin={adm[:35]} v1={has_v1} op_raw={has_op}")

print("\n=== CharacterSaveParameterMap ===")
for c in wsd['CharacterSaveParameterMap']['value']:
    try:
        sp = c['value']['RawData']['value']['object']['SaveParameter']
        if not sp['value'].get('IsPlayer', {}).get('value', False): continue
        uid = str(c['key']['PlayerUId']['value'])
        nick = sp['value'].get('NickName', {}).get('value', '?')
        lvl = sp['value'].get('Level', {}).get('value', '?')
        print(f"  UID={uid} Name={nick} Level={lvl}")
    except: continue
