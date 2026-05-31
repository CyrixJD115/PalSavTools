import sys, os, pickle
sys.path.insert(0, 'src')
from palworld_save_tools.palsav import decompress_sav_to_gvas, compress_gvas_to_sav
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES
from palworld_save_tools.gvas import GvasFile

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
        if lid == b'\x00' * 16:
            return ''
        from uuid import UUID
        try:
            return str(UUID(bytes=lid)).lower()
        except:
            return lid.hex().lower()
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

def _collect_container_ids(player_json):
    ii = player_json['SaveData']['value']['InventoryInfo']['value']
    return {ii['CommonContainerId']['value']['ID']['value'], ii['EssentialContainerId']['value']['ID']['value'], ii['WeaponLoadOutContainerId']['value']['ID']['value'], ii['PlayerEquipArmorContainerId']['value']['ID']['value'], ii['FoodEquipContainerId']['value']['ID']['value']}

src_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\PylarLatest_clean'
tgt_path = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\BetaTest_clean'
outdir = r'C:\Users\Administrator\Desktop\PST_v2.0.0\TestSaves\CharacterTransfer\test_dynamics_check'
os.makedirs(outdir + '/Players', exist_ok=True)

player_uids = [f.replace('.sav', '') for f in os.listdir(src_path + '/Players') if f.endswith('.sav') and not f.endswith('_dps.sav')]
print('Players:', player_uids)

src_gvas = load_sav(src_path + '/Level.sav')
src_wsd = src_gvas.properties['worldSaveData']['value']
tgt_gvas = load_sav(tgt_path + '/Level.sav')
tgt_wsd = tgt_gvas.properties['worldSaveData']['value']

print('=== PRE-TRANSFER DYNAMIC CONTAINERS IN TARGET ===')
tgt_dyns = tgt_wsd.get('DynamicItemSaveData',{}).get('value',{}).get('values',[])
print(f'Target has {len(tgt_dyns)} dynamic containers')
for i, dc in enumerate(tgt_dyns[:5]):
    lid = dc['RawData']['value']['id']['local_id_in_created_world']
    norm = _normalize_lid(lid)
    print(f'  [{i}] {norm[:20]}...')

# Simulate bulk + dynamics
targ_lvl = tgt_wsd
modified_targets_data = {}

for i, uid in enumerate(player_uids):
    host_gvas = load_sav(os.path.join(src_path, 'Players', uid + '.sav'))
    host_json = host_gvas.properties
    host_sd = host_json['SaveData']['value']

    # Load target .sav (or deepcopy source)
    try:
        targ_gvas = load_sav(os.path.join(tgt_path, 'Players', uid + '.sav'))
        if targ_gvas is None:
            targ_gvas = fast_deepcopy(host_gvas)
    except:
        targ_gvas = fast_deepcopy(host_gvas)
    targ_json = targ_gvas.properties
    targ_sd = targ_json['SaveData']['value']

    targ_lvl.setdefault('CharacterContainerSaveData', {'value': []})
    targ_lvl.setdefault('ItemContainerSaveData', {'value': []})

    src_inv = host_sd['InventoryInfo']['value']
    src_char_ids = {host_sd['PalStorageContainerId']['value']['ID']['value'], host_sd['OtomoCharacterContainerId']['value']['ID']['value']}
    src_item_ids = {v for v in [
        src_inv['CommonContainerId']['value']['ID']['value'],
        src_inv['EssentialContainerId']['value']['ID']['value'],
        src_inv['WeaponLoadOutContainerId']['value']['ID']['value'],
        src_inv['PlayerEquipArmorContainerId']['value']['ID']['value'],
        src_inv['FoodEquipContainerId']['value']['ID']['value'],
    ]}

    for clist, ids in [('CharacterContainerSaveData', src_char_ids), ('ItemContainerSaveData', src_item_ids)]:
        existing = {c['key']['ID']['value'] for c in targ_lvl[clist]['value']}
        for c in src_wsd.get(clist, {}).get('value', []):
            cid = c['key']['ID']['value']
            if cid in ids and cid not in existing:
                targ_lvl[clist]['value'].append(fast_deepcopy(c))

    # transfer_inventory_only
    inv_lookup_src = {v: k for k, v in {
        'CommonContainerId': src_inv['CommonContainerId']['value']['ID']['value'],
        'EssentialContainerId': src_inv['EssentialContainerId']['value']['ID']['value'],
        'WeaponLoadOutContainerId': src_inv['WeaponLoadOutContainerId']['value']['ID']['value'],
        'PlayerEquipArmorContainerId': src_inv['PlayerEquipArmorContainerId']['value']['ID']['value'],
        'FoodEquipContainerId': src_inv['FoodEquipContainerId']['value']['ID']['value'],
    }.items()}
    tgt_inv = targ_sd['InventoryInfo']['value']
    inv_lookup_tgt = {v: k for k, v in {
        'CommonContainerId': tgt_inv['CommonContainerId']['value']['ID']['value'],
        'EssentialContainerId': tgt_inv['EssentialContainerId']['value']['ID']['value'],
        'WeaponLoadOutContainerId': tgt_inv['WeaponLoadOutContainerId']['value']['ID']['value'],
        'PlayerEquipArmorContainerId': tgt_inv['PlayerEquipArmorContainerId']['value']['ID']['value'],
        'FoodEquipContainerId': tgt_inv['FoodEquipContainerId']['value']['ID']['value'],
    }.items()}
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

# ===== NOW RUN DYNAMICS =====
print('\n=== RUNNING DYNAMICS ===')
from palworld_save_tools.archive import UUID as PalUUID

src_container_ids = _collect_container_ids(host_json)
tgt_container_ids = _collect_container_ids(targ_json)
for _, (pj, _, _) in modified_targets_data.items():
    ids = _collect_container_ids(pj)
    src_container_ids |= ids
    tgt_container_ids |= ids

needed = set()
for c in src_wsd.get('ItemContainerSaveData', {}).get('value', []):
    try:
        if c['key']['ID']['value'] not in src_container_ids:
            continue
    except:
        continue
    for slot in c.get('value', {}).get('Slots', {}).get('value', {}).get('values', []):
        try:
            item = slot.get('RawData', {}).get('value', {}).get('item', {})
            if not isinstance(item, dict):
                continue
            dyn_id = item.get('dynamic_id', {})
            if not isinstance(dyn_id, dict):
                continue
            lid = dyn_id.get('local_id_in_created_world', '')
            norm = _normalize_lid(lid)
            if norm:
                needed.add(norm)
        except:
            continue

print(f'Needed dynamic IDs: {len(needed)}')

src_containers = src_wsd['DynamicItemSaveData']['value']['values']
tgt_containers = targ_lvl['DynamicItemSaveData']['value']['values']
print(f'Source dynamics: {len(src_containers)}, Target dynamics: {len(tgt_containers)}')

existing = set()
tgt_dict = {}
for dc in tgt_containers:
    try:
        norm = _normalize_lid(dc['RawData']['value']['id']['local_id_in_created_world'])
        if norm:
            existing.add(norm)
    except:
        continue

print(f'Target existing dynamic IDs: {len(existing)}')

id_map = {}
dynamic_guids = set()
collision_count = 0
for dc in src_containers:
    try:
        lid = dc['RawData']['value']['id']['local_id_in_created_world']
        if isinstance(lid, bytes) and lid == b'\x00' * 16:
            continue
        norm = _normalize_lid(lid)
        if not norm or norm not in needed:
            continue
    except:
        continue
    bumped = _bump_guid_str(norm, existing)
    if bumped != norm:
        collision_count += 1
        print(f'  BUMPED {norm[:16]}.. -> {bumped[:16]}..')
    copy = fast_deepcopy(dc)
    copy['RawData']['value']['id']['local_id_in_created_world'] = PalUUID.from_str(bumped)
    dynamic_guids.add(lid)
    tgt_dict[bumped] = copy
    id_map[norm] = bumped

print(f'Source dynamics in needed: {len(tgt_dict)}, collisions: {collision_count}')

preserved_map = {}
for dc in tgt_containers:
    try:
        lid = dc['RawData']['value']['id']['local_id_in_created_world']
        norm = _normalize_lid(lid)
        if norm and norm not in needed:
            preserved_map[norm] = dc
    except:
        continue
print(f'Preserved target dynamics (not in needed): {len(preserved_map)}')

tgt_dict.update(preserved_map)

# Check items for unmapped dynamic IDs
all_container_ids = src_container_ids | tgt_container_ids
unmapped_items = []
for c in targ_lvl.get('ItemContainerSaveData', {}).get('value', []):
    try:
        if c['key']['ID']['value'] not in all_container_ids:
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
            if norm and norm in id_map:
                dyn_id['local_id_in_created_world'] = PalUUID.from_str(id_map[norm])
            elif norm and norm not in id_map:
                # Check if it's in tgt_dict directly
                if norm not in tgt_dict:
                    unmapped_items.append(norm[:20])
        except:
            continue

print(f'Unmapped items (dynamic ID not in tgt_dict): {len(unmapped_items)}')
for u in unmapped_items[:10]:
    print(f'  {u}..')

targ_lvl['DynamicItemSaveData']['value']['values'] = list(tgt_dict.values())
print(f'Final dynamics list: {len(targ_lvl["DynamicItemSaveData"]["value"]["values"])}')

# Write files
write_sav(tgt_gvas, outdir + '/Level.sav')
for uid, (_, gvas_obj, _) in modified_targets_data.items():
    write_sav(gvas_obj, os.path.join(outdir, 'Players', uid + '.sav'))

print('\n=== VERIFY OUTPUT ===')
check_lvl = load_sav(outdir + '/Level.sav')
c_wsd = check_lvl.properties['worldSaveData']['value']
print(f'Written Level.sav dynamics: {len(c_wsd.get("DynamicItemSaveData",{}).get("value",{}).get("values",[]))}')
print(f'Item containers: {len(c_wsd.get("ItemContainerSaveData",{}).get("value",[]))}')
print(f'Char containers: {len(c_wsd.get("CharacterContainerSaveData",{}).get("value",[]))}')
print('DONE')
