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

def _collect_container_ids(pj):
    ii = pj['SaveData']['value']['InventoryInfo']['value']
    return {ii['CommonContainerId']['value']['ID']['value'], ii['EssentialContainerId']['value']['ID']['value'], ii['WeaponLoadOutContainerId']['value']['ID']['value'], ii['PlayerEquipArmorContainerId']['value']['ID']['value'], ii['FoodEquipContainerId']['value']['ID']['value']}

def _collect_char_ids(pj):
    sd = pj['SaveData']['value']
    return {sd['PalStorageContainerId']['value']['ID']['value'], sd['OtomoCharacterContainerId']['value']['ID']['value']}

src_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\PylarLatest_clean'
tgt_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\BetaTest_clean'
outdir = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\test_dynamics3'
os.makedirs(outdir + '/Players', exist_ok=True)

player_uids = [f.replace('.sav', '') for f in os.listdir(src_path + '/Players') if f.endswith('.sav') and not f.endswith('_dps.sav')]
print('PLAYERS:', player_uids)

src_gvas = load_sav(src_path + '/Level.sav')
src_wsd = src_gvas.properties['worldSaveData']['value']
tgt_gvas = load_sav(tgt_path + '/Level.sav')
tgt_wsd = tgt_gvas.properties['worldSaveData']['value']
targ_lvl = tgt_wsd
modified_targets_data = {}

# --- SIMULATE BULK TRANSFER ---
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
    src_char_ids_set = {host_sd['PalStorageContainerId']['value']['ID']['value'], host_sd['OtomoCharacterContainerId']['value']['ID']['value']}
    src_item_ids_set = set()
    for k in ['CommonContainerId','EssentialContainerId','WeaponLoadOutContainerId','PlayerEquipArmorContainerId','FoodEquipContainerId']:
        src_item_ids_set.add(src_inv[k]['value']['ID']['value'])

    # transfer_character_only - copy containers
    for clist, ids in [('CharacterContainerSaveData', src_char_ids_set), ('ItemContainerSaveData', src_item_ids_set)]:
        existing = {c['key']['ID']['value'] for c in targ_lvl[clist]['value']}
        for c in src_wsd.get(clist, {}).get('value', []):
            cid = c['key']['ID']['value']
            if cid in ids and cid not in existing:
                targ_lvl[clist]['value'].append(fast_deepcopy(c))

    # transfer_inventory_only - replace container values
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

# --- DYNAMICS ---
print('\n=== DYNAMICS ===')
src_container_ids = _collect_container_ids(host_json)
tgt_container_ids = _collect_container_ids(targ_json)
src_char_ids = _collect_char_ids(host_json)
tgt_char_ids = _collect_char_ids(targ_json)
for _, (pj, _, _) in modified_targets_data.items():
    src_container_ids |= _collect_container_ids(pj)
    tgt_container_ids |= _collect_container_ids(pj)
    src_char_ids |= _collect_char_ids(pj)
    tgt_char_ids |= _collect_char_ids(pj)

needed = set()
for ctype in ['ItemContainerSaveData', 'CharacterContainerSaveData']:
    for c in src_wsd.get(ctype, {}).get('value', []):
        try:
            cid = c['key']['ID']['value']
            if cid not in src_container_ids and cid not in src_char_ids:
                continue
        except:
            continue
        for slot in c.get('value', {}).get('Slots', {}).get('value', {}).get('values', []):
            try:
                item = slot.get('RawData', {}).get('value', {}).get('item', {})
                if not isinstance(item, dict): continue
                dyn_id = item.get('dynamic_id', {})
                if not isinstance(dyn_id, dict): continue
                lid = dyn_id.get('local_id_in_created_world', '')
                norm = _normalize_lid(lid)
                if norm: needed.add(norm)
            except:
                continue

src_containers = src_wsd['DynamicItemSaveData']['value']['values']
tgt_containers = targ_lvl['DynamicItemSaveData']['value']['values']
print(f'SRC_DYN: {len(src_containers)}, TGT_DYN: {len(tgt_containers)}, NEEDED: {len(needed)}')

existing = set()
for dc in tgt_containers:
    try:
        norm = _normalize_lid(dc['RawData']['value']['id']['local_id_in_created_world'])
        if norm: existing.add(norm)
    except:
        continue

id_map = {}
tgt_dict = {}
for dc in src_containers:
    try:
        lid = dc['RawData']['value']['id']['local_id_in_created_world']
        if isinstance(lid, bytes) and lid == b'\x00' * 16: continue
        norm = _normalize_lid(lid)
        if not norm or norm not in needed: continue
    except:
        continue
    bumped = _bump_guid_str(norm, existing)
    copy = fast_deepcopy(dc)
    copy['RawData']['value']['id']['local_id_in_created_world'] = PalUUID.from_str(bumped)
    tgt_dict[bumped] = copy
    id_map[norm] = bumped

preserved = {}
for dc in tgt_containers:
    try:
        norm = _normalize_lid(dc['RawData']['value']['id']['local_id_in_created_world'])
        if norm and norm not in needed: preserved[norm] = dc
    except:
        continue
tgt_dict.update(preserved)
print(f'ID_MAP: {len(id_map)}, TGT_DICT: {len(tgt_dict)}')

# REMAP
all_ids = src_container_ids | tgt_container_ids | src_char_ids | tgt_char_ids
remapped = 0
unmapped = []
skip_no_item = 0
skip_no_dyn = 0
skip_empty_norm = 0
processed_slots = 0
total_items_in_scope = 0

for ctype in ['ItemContainerSaveData', 'CharacterContainerSaveData']:
    for c in targ_lvl.get(ctype, {}).get('value', []):
        try:
            cid = c['key']['ID']['value']
            if cid not in all_ids: continue
        except:
            continue
        slot_list = c.get('value', {}).get('Slots', {}).get('value', {}).get('values', [])
        for slot in slot_list:
            processed_slots += 1
            try:
                raw = slot.get('RawData', {})
                if not isinstance(raw, dict): continue
                val = raw.get('value', {})
                if not isinstance(val, dict): continue
                if 'item' not in val:
                    skip_no_item += 1
                    continue
                total_items_in_scope += 1
                item = val.get('item', {})
                if not isinstance(item, dict): continue
                dyn_id = item.get('dynamic_id', {})
                if not isinstance(dyn_id, dict) or not dyn_id:
                    skip_no_dyn += 1
                    continue
                lid = dyn_id.get('local_id_in_created_world', '')
                norm = _normalize_lid(lid)
                if not norm:
                    skip_empty_norm += 1
                    continue
                if norm in id_map:
                    dyn_id['local_id_in_created_world'] = PalUUID.from_str(id_map[norm])
                    remapped += 1
                elif norm not in tgt_dict:
                    unmapped.append(norm[:24])
            except:
                continue

print(f'SLOTS: {processed_slots}, ITEMS: {total_items_in_scope}')
print(f'NO_ITEM: {skip_no_item}, NO_DYN: {skip_no_dyn}, EMPTY_NORM: {skip_empty_norm}')
print(f'REMAPPED: {remapped}, UNMAPPED: {len(unmapped)}')
for u in unmapped[:10]:
    print(f'  UNMAPPED: {u}..')

# Check what dynamic IDs are in the source items but NOT in needed
src_dyn_ids_in_items = set()
for ctype in ['ItemContainerSaveData', 'CharacterContainerSaveData']:
    for c in src_wsd.get(ctype, {}).get('value', []):
        try:
            cid = c['key']['ID']['value']
            if cid not in src_container_ids and cid not in src_char_ids: continue
        except: continue
        for slot in c.get('value', {}).get('Slots', {}).get('value', {}).get('values', []):
            try:
                item = slot.get('RawData', {}).get('value', {}).get('item', {})
                if not isinstance(item, dict): continue
                dyn_id = item.get('dynamic_id', {})
                if not isinstance(dyn_id, dict): continue
                lid = dyn_id.get('local_id_in_created_world', '')
                norm = _normalize_lid(lid)
                if norm: src_dyn_ids_in_items.add(norm)
            except: continue

print(f'SRC_ITEM_DYN_IDS: {len(src_dyn_ids_in_items)}, IN_NEEDED: {len(src_dyn_ids_in_items & needed)}')
missing_from_needed = src_dyn_ids_in_items - needed
if missing_from_needed:
    print(f'  {len(missing_from_needed)} source item dyn IDs NOT in needed')
    for m in list(missing_from_needed)[:5]:
        print(f'    MISSING: {m[:24]}..')

# Check if ALL all_ids containers actually exist in targ_lvl
found_ids = set()
for ctype in ['ItemContainerSaveData', 'CharacterContainerSaveData']:
    for c in targ_lvl.get(ctype, {}).get('value', []):
        try: found_ids.add(c['key']['ID']['value'])
        except: pass
missing_containers = all_ids - found_ids
if missing_containers:
    print(f'MISSING_CONTAINERS (in all_ids but not in targ_lvl): {len(missing_containers)}')

targ_lvl['DynamicItemSaveData']['value']['values'] = list(tgt_dict.values())
write_sav(tgt_gvas, outdir + '/Level.sav')
for uid, (_, gvas_obj, _) in modified_targets_data.items():
    write_sav(gvas_obj, os.path.join(outdir, 'Players', uid + '.sav'))
print('\nDONE')
