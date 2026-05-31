import sys, os, pickle
sys.path.insert(0, 'src')
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES
from palworld_save_tools.gvas import GvasFile

def _normalize_lid(lid):
    if hasattr(lid, 'raw_bytes'):
        s = str(lid).lower()
        return '' if s.replace('-', '') == '00000000000000000000000000000000' else s
    if isinstance(lid, bytes):
        if lid == b'\x00' * 16: return ''
        from uuid import UUID
        try: return str(UUID(bytes=lid)).lower()
        except: return lid.hex().lower()
    if isinstance(lid, str):
        stripped = lid.replace('-', '').lower()
        return '' if stripped == '00000000000000000000000000000000' else lid.lower()
    return ''

unmapped_ids = [
    '82ddde5f-4c7a-66f7-9fda-4e4e62cc5bbc',
    'ac241e28-498a-5cba-6e22-167b6837a0cf',
    '866d203b-47e5-b24b-153c-6f0b98fe9dc4',
    'd194bc15-4e56-1c4d-d9c1-f2a083c198eb',
    '78aaeb15-490a-814d-084f-dc4d54f4e9e5',
    'f8d59977-4520-4126-760d-8e8664d62d94',
    'bbd73bd0-434c-1f62-1793-2b562587da21',
    'c4a5ed88-44f7-0c83-2547-09afd9a01e64',
    '43e132f0-4c5c-168d-7994-3a6c62ece23f',
    '98850738-4ee9-446b-023f-3f718b2bb200',
]

outdir = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\test_dynamics3'
check_lvl = load_sav(outdir + '/Level.sav')
c_wsd = check_lvl.properties['worldSaveData']['value']

# Search for these IDs in targ_lvl's DynamicItemSaveData
tgt_dyn_ids = set()
for dc in c_wsd.get('DynamicItemSaveData', {}).get('value', {}).get('values', []):
    try:
        lid = dc['RawData']['value']['id']['local_id_in_created_world']
        norm = _normalize_lid(lid)
        if norm: tgt_dyn_ids.add(norm)
    except: pass

print('Unmapped IDs that ARE in final dynamics list:')
found_in_dyn = 0
for uid in unmapped_ids:
    if uid in tgt_dyn_ids:
        found_in_dyn += 1
        print(f'  FOUND: {uid[:24]}...')
print(f'{found_in_dyn}/{len(unmapped_ids)} found in dynamics')

# Search these IDs in the original TARGET level
tgt_orig = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\BetaTest_clean\Level.sav'
orig_gvas = load_sav(tgt_orig)
orig_wsd = orig_gvas.properties['worldSaveData']['value']
orig_dyn_ids = set()
for dc in orig_wsd.get('DynamicItemSaveData', {}).get('value', {}).get('values', []):
    try:
        lid = dc['RawData']['value']['id']['local_id_in_created_world']
        norm = _normalize_lid(lid)
        if norm: orig_dyn_ids.add(norm)
    except: pass

print('\nUnmapped IDs that ARE in ORIGINAL target dynamics:')
found_orig = 0
for uid in unmapped_ids:
    if uid in orig_dyn_ids:
        found_orig += 1
        print(f'  ORIG: {uid[:24]}...')
print(f'{found_orig}/{len(unmapped_ids)} found in original target dynamics')

# Search in SOURCE dynamics
src_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\PylarLatest_clean\Level.sav'
src_gvas = load_sav(src_path)
src_wsd = src_gvas.properties['worldSaveData']['value']
src_dyn_ids = set()
for dc in src_wsd.get('DynamicItemSaveData', {}).get('value', {}).get('values', []):
    try:
        lid = dc['RawData']['value']['id']['local_id_in_created_world']
        norm = _normalize_lid(lid)
        if norm: src_dyn_ids.add(norm)
    except: pass

print('\nUnmapped IDs that ARE in SOURCE dynamics:')
found_src = 0
for uid in unmapped_ids:
    if uid in src_dyn_ids:
        found_src += 1
        print(f'  SRC: {uid[:24]}...')
print(f'{found_src}/{len(unmapped_ids)} found in source dynamics')
