import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from palworld_aio.utils import sav_to_gvasfile
def get_record_data(gvas):
    props = gvas.properties if hasattr(gvas, 'properties') else gvas.get('properties', {})
    save_data = props.get('SaveData', {}).get('value', {})
    if not save_data:
        return None
    return save_data.get('RecordData', {}).get('value', {})
def extract_map_keys(record_data, key):
    prop = record_data.get(key, {})
    if not prop:
        return set()
    return {e['key'] for e in prop.get('value', []) if e.get('value', False)}
def extract_world_map_flags(record_data):
    prop = record_data.get('UnlockedWorldMapFlags', {})
    if not prop:
        return {}
    return {e['key']: e.get('value', False) for e in prop.get('value', [])}
def scan_saves(players_dir):
    per_player_ft = []
    area_keys = set()
    world_flags = {}
    area_barrier = set()
    scanned = 0
    for fname in sorted(os.listdir(players_dir)):
        if not fname.endswith('.sav') or '_dps' in fname:
            continue
        path = os.path.join(players_dir, fname)
        try:
            gvas = sav_to_gvasfile(path)
            record = get_record_data(gvas)
            if record is None:
                continue
            scanned += 1
            per_player_ft.append(extract_map_keys(record, 'FastTravelPointUnlockFlag'))
            area_keys |= extract_map_keys(record, 'FindAreaFlagMap')
            wf = extract_world_map_flags(record)
            for k, v in wf.items():
                if v:
                    world_flags[k] = True
            area_barrier |= extract_map_keys(record, 'AreaBarrierUnlockFlags')
        except Exception as e:
            print(f'  Skipping {fname}: {e}')
    return (scanned, per_player_ft, area_keys, world_flags, area_barrier)
def main():
    saves_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'TestSaves', 'PylarUpdated', 'Players')
    output = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', 'resources', 'game_data', 'reference_unlock_data.json')
    if not os.path.isdir(saves_dir):
        print(f'Directory not found: {saves_dir}')
        sys.exit(1)
    print(f'Scanning: {saves_dir}')
    scanned, per_player_ft, area_keys, world_flags, area_barrier = scan_saves(saves_dir)
    print(f'Scanned {scanned} player save(s)')
    ft_guids = set.union(*per_player_ft) if per_player_ft else set()
    ref_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'game_data', 'reference_unlock_data.json')
    if os.path.exists(ref_path):
        try:
            old_ref = json.load(open(ref_path, 'r'))
            old_ft = set(old_ref.get('FastTravelPointUnlockFlag_guids', []))
            before = len(ft_guids)
            ft_guids |= old_ft
            if len(ft_guids) > before:
                print(f'  Added {len(ft_guids) - before} GUIDs from existing reference')
        except Exception:
            pass
    result = {'FastTravelPointUnlockFlag_guids': sorted(ft_guids), 'FindAreaFlagMap_keys': sorted(area_keys), 'UnlockedWorldMapFlags': world_flags or {'MainMap': True, 'Tree': True}, 'AreaBarrierUnlockFlags_guids': sorted(area_barrier)}
    with open(output, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'Written: {output}')
    print(f'  FT points: {len(ft_guids)}')
    print(f'  Area flags: {len(area_keys)}')
    print(f'  World map flags: {len(world_flags)}')
    print(f'  Area barriers: {len(area_barrier)}')
if __name__ == '__main__':
    main()