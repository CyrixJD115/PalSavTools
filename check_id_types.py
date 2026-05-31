import sys, os
sys.path.insert(0, 'src')
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES
from palworld_save_tools.gvas import GvasFile

def load_sav(p):
    with open(p,'rb') as f:
        raw,_ = decompress_sav_to_gvas(f.read())
    return GvasFile.read(raw, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)

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

src_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\PylarLatest_clean\Level.sav'
gvas = load_sav(src_path)
wsd = gvas.properties['worldSaveData']['value']

# Print first 5 source dynamics
print('=== SOURCE DYNAMICS (first 10) ===')
for i, dc in enumerate(wsd.get('DynamicItemSaveData',{}).get('value',{}).get('values',[])):
    if i >= 10: break
    lid = dc['RawData']['value']['id']['local_id_in_created_world']
    print(f'  [{i}] type={type(lid).__name__}, norm={_normalize_lid(lid)[:24]}...')

# Print items in a player container that have dynamic IDs
print('\n=== SOURCE ITEM CONTAINER ITEMS WITH DYNAMIC IDs ===')
player_id = 'F8829FDD000000000000000000000000'
pl = load_sav(os.path.join(os.path.dirname(src_path), 'Players', player_id + '.sav'))
psd = pl.properties['SaveData']['value']
inv = psd['InventoryInfo']['value']
common_id = inv['CommonContainerId']['value']['ID']['value']

for c in wsd.get('ItemContainerSaveData', {}).get('value', []):
    if c['key']['ID']['value'] == common_id:
        slots = c.get('value', {}).get('Slots', {}).get('value', {}).get('values', [])
        count = 0
        for slot in slots:
            try:
                item = slot.get('RawData', {}).get('value', {}).get('item', {})
                if not isinstance(item, dict): continue
                dyn_id = item.get('dynamic_id', {})
                if not isinstance(dyn_id, dict) or not dyn_id: continue
                lid = dyn_id.get('local_id_in_created_world', '')
                norm = _normalize_lid(lid)
                if norm:
                    print(f'  slot: type={type(lid).__name__}, norm={norm[:24]}...')
                    count += 1
                    if count >= 5: break
            except: continue
        break
