import sys, os, pickle
sys.path.insert(0, 'src')
from palworld_save_tools.palsav import decompress_sav_to_gvas, compress_gvas_to_sav
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.archive import UUID as PalUUID

def load_sav(p):
    with open(p,'rb') as f:
        raw,_ = decompress_sav_to_gvas(f.read())
    return GvasFile.read(raw, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)

def write_sav(gvas, path):
    data = gvas.write(PALWORLD_CUSTOM_PROPERTIES)
    t = 50 if 'Pal.PalworldSaveGame' in gvas.header.save_game_class_name or 'Pal.PalLocalWorldSaveGame' in gvas.header.save_game_class_name else 49
    with open(path, 'wb') as f:
        f.write(compress_gvas_to_sav(data, t))

def fast_deepcopy(obj):
    return pickle.loads(pickle.dumps(obj, -1))

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

def _bump_guid_str(s, used):
    t = str.maketrans('0123456789abcdef', '123456789abcdef0')
    bumped = s.translate(t)
    while bumped in used:
        bumped = bumped.translate(t)
    used.add(bumped)
    return bumped

def _collect_ids_from_pj(pj):
    sd = pj['SaveData']['value']
    ii = sd['InventoryInfo']['value']
    inv = {ii['CommonContainerId']['value']['ID']['value'], ii['EssentialContainerId']['value']['ID']['value'], ii['WeaponLoadOutContainerId']['value']['ID']['value'], ii['PlayerEquipArmorContainerId']['value']['ID']['value'], ii['FoodEquipContainerId']['value']['ID']['value']}
    char = {sd['PalStorageContainerId']['value']['ID']['value'], sd['OtomoCharacterContainerId']['value']['ID']['value']}
    return inv, char

src_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\PylarLatest_clean'
tgt_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\BetaTest_clean'
outdir = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\test_dynamics4'
os.makedirs(outdir + '/Players', exist_ok=True)

player_uids = [f.replace('.sav', '') for f in os.listdir(src_path + '/Players') if f.endswith('.sav') and not f.endswith('_dps.sav')]
print('PLAYERS:', player_uids)

src_gvas = load_sav(src_path + '/Level.sav')
src_wsd = src_gvas.properties['worldSaveData']['value']
tgt_gvas = load_sav(tgt_path + '/Level.sav')
tgt_wsd = tgt_gvas.properties['worldSaveData']['value']
targ_lvl = tgt_wsd

# Check target dynamics BEFORE transfer
orig_tgt_dyn_norms = {}
for dc in targ_lvl.get('DynamicItemSaveData', {}).get('value', {}).get('values', []):
    try:
        lid = dc['RawData']['value']['id']['local_id_in_created_world']
        norm = _normalize_lid(lid)
        if norm: orig_tgt_dyn_norms[norm] = True
    except: pass
print('Original target dynamics:', len(orig_tgt_dyn_norms))

modified_targets_data = {}
all_src_inv_ids = set()
all_src_char_ids = set()
all_tgt_inv_ids = set()
all_tgt_char_ids = set()

for i, uid in enumerate(player_uids):
    host_gvas = load_sav(os.path.join(src_path, 'Players', uid + '.sav'))
    host_json = host_gvas.properties
    host_sd = host_json['SaveData']['value']
    try:
        targ_gvas = load_sav(os.path.join(tgt_path, 'Players', uid + '.sav'))
        if targ_gvas is None: targ_gvas = fast_deepcopy(host_gvas)
    except:
        targ_gvas = fast_deepcopy(host_gvas)
    targ_json = targ_gvas.properties

    targ_lvl.setdefault('CharacterContainerSaveData', {'value': []})
    targ_lvl.setdefault('ItemContainerSaveData', {'value': []})

    src_inv = host_sd['InventoryInfo']['value']
    src_char_ids = {host_sd['PalStorageContainerId']['value']['ID']['value'], host_sd['OtomoCharacterContainerId']['value']['ID']['value']}
    src_item_ids = set()
    for k in ['CommonContainerId','EssentialContainerId','WeaponLoadOutContainerId','PlayerEquipArmorContainerId','FoodEquipContainerId']:
        src_item_ids.add(src_inv[k]['value']['ID']['value'])

    # Collect IDs for the check
    inv_ids, char_ids = _collect_ids_from_pj(host_json)
    all_src_inv_ids |= inv_ids
    all_src_char_ids |= char_ids
    inv_ids_t, char_ids_t = _collect_ids_from_pj(targ_json)
    all_tgt_inv_ids |= inv_ids_t
    all_tgt_char_ids |= char_ids_t

    for clist, ids in [('CharacterContainerSaveData', src_char_ids), ('ItemContainerSaveData', src_item_ids)]:
        existing = {c['key']['ID']['value'] for c in targ_lvl[clist]['value']}
        for c in src_wsd.get(clist, {}).get('value', []):
            cid = c['key']['ID']['value']
            if cid in ids and cid not in existing:
                targ_lvl[clist]['value'].append(fast_deepcopy(c))

    tgt_inv = targ_json['SaveData']['value']['InventoryInfo']['value']
    inv_lookup_src = {v: k for k, v in {k: src_inv[k]['value']['ID']['value'] for k in ['CommonContainerId','EssentialContainerId','WeaponLoadOutContainerId','PlayerEquipArmorContainerId','FoodEquipContainerId']}.items()}
    inv_lookup_tgt = {v: k for k, v in {k: tgt_inv[k]['value']['ID']['value'] for k in ['CommonContainerId','EssentialContainerId','WeaponLoadOutContainerId','PlayerEquipArmorContainerId','FoodEquipContainerId']}.items()}
    containers_src = {}
    containers_tgt = {}
    for c in src_wsd.get('ItemContainerSaveData', {}).get('value', []):
        cid = c['key']['ID']['value']
        if cid in inv_lookup_src:
            containers_src[inv_lookup_src[cid]] = c
    for c in targ_lvl.get('ItemContainerSaveData', {}).get('value', []):
        cid = c['key']['ID']['value']
        if cid in inv_lookup_tgt:
            containers_tgt[inv_lookup_tgt[cid]] = c
    for k in ['CommonContainerId','EssentialContainerId','WeaponLoadOutContainerId','PlayerEquipArmorContainerId','FoodEquipContainerId']:
        if k in containers_src and k not in containers_tgt:
            for sc in src_wsd.get('ItemContainerSaveData', {}).get('value', []):
                if sc['key']['ID']['value'] == inv_lookup_src.get(k, ''):
                    targ_lvl['ItemContainerSaveData']['value'].append(fast_deepcopy(sc))
                    containers_tgt[k] = targ_lvl['ItemContainerSaveData']['value'][-1]
                    break
        if k in containers_src and k in containers_tgt:
            containers_tgt[k]['value'] = fast_deepcopy(containers_src[k]['value'])

    modified_targets_data[uid] = (fast_deepcopy(targ_json), targ_gvas, uid)

# Check: AFTER transfer, which items in retained target containers have dynamic IDs not in orig_tgt_dyn_norms?
all_container_ids = all_src_inv_ids | all_tgt_inv_ids | all_src_char_ids | all_tgt_char_ids
print('all_container_ids:', len(all_container_ids))

items_with_dyn_wrong = []
for ctype in ['ItemContainerSaveData']:
    for c in targ_lvl.get(ctype, {}).get('value', []):
        try:
            cid = c['key']['ID']['value']
            if cid not in all_container_ids:
                continue
        except:
            continue
        for slot in c.get('value', {}).get('Slots', {}).get('value', {}).get('values', []):
            try:
                raw = slot.get('RawData', {})
                if not isinstance(raw, dict): continue
                val = raw.get('value', {})
                if not isinstance(val, dict): continue
                item = val.get('item', {})
                if not isinstance(item, dict): continue
                dyn_id = item.get('dynamic_id', {})
                if not isinstance(dyn_id, dict): continue
                lid = dyn_id.get('local_id_in_created_world', '')
                norm = _normalize_lid(lid)
                if norm and norm not in orig_tgt_dyn_norms:
                    items_with_dyn_wrong.append(norm[:24])
            except:
                continue

print(f'Items with valid dyn IDs THAT ARE NOT in original target dynamics: {len(items_with_dyn_wrong)}')
if items_with_dyn_wrong:
    print('  These items have SOURCE dynamic IDs that need to be found in source dynamics')
    src_dyn_norms = {}
    for dc in src_wsd.get('DynamicItemSaveData', {}).get('value', {}).get('values', []):
        try:
            lid = dc['RawData']['value']['id']['local_id_in_created_world']
            norm = _normalize_lid(lid)
            if norm: src_dyn_norms[norm] = True
        except: pass
    print(f'  Source dynamics count: {len(src_dyn_norms)}')
    found_in_src = sum(1 for u in items_with_dyn_wrong[:50] if u in src_dyn_norms)
    print(f'  Found in source dynamics: {found_in_src}/{len(items_with_dyn_wrong)}')

# Also check: are any target dynamics missing from the output?
print('\nTarget dynamics that ARE in orig_tgt_dyn but NOT in items (all orphaned):')
# Scan ALL item containers in targ_lvl to collect all referenced dyn IDs
all_refed = set()
for ctype in ['ItemContainerSaveData', 'CharacterContainerSaveData']:
    for c in targ_lvl.get(ctype, {}).get('value', []):
        try:
            cid = c['key']['ID']['value']
        except: continue
        for slot in c.get('value', {}).get('Slots', {}).get('value', {}).get('values', []):
            try:
                raw = slot.get('RawData', {})
                if not isinstance(raw, dict): continue
                val = raw.get('value', {})
                if not isinstance(val, dict): continue
                item = val.get('item', {})
                if not isinstance(item, dict): continue
                dyn_id = item.get('dynamic_id', {})
                if not isinstance(dyn_id, dict): continue
                lid = dyn_id.get('local_id_in_created_world', '')
                norm = _normalize_lid(lid)
                if norm: all_refed.add(norm)
            except: continue

orphaned = orig_tgt_dyn_norms.keys() - all_refed
print(f'  Orphaned target dynamics (in orig but not referenced by any item): {len(orphaned)}')
print(f'  Total target dyn in orig: {len(orig_tgt_dyn_norms)}, Referenced by items: {len(all_refed)}')
