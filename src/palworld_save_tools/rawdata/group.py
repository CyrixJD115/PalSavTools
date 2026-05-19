from typing import Any, Sequence
import uuid as _stdlib_uuid
from palworld_save_tools.archive import *
def player_info_reader(reader: FArchiveReader) -> dict[str, Any]:
    return {'player_uid': reader.guid(), 'player_info': {'last_online_real_time': reader.i64(), 'player_name': reader.fstring()}}
def player_info_writer(writer: FArchiveWriter, p: dict[str, Any]) -> None:
    writer.guid(p['player_uid'])
    writer.i64(p['player_info']['last_online_real_time'])
    writer.fstring(p['player_info']['player_name'])
def fguid_to_uuid(a: int, b: int, c: int, d: int) -> _stdlib_uuid.UUID:
    time_low = a & 0xFFFFFFFF
    time_mid = (b >> 16) & 0xFFFF
    time_hi_version = b & 0xFFFF
    clock_seq_hi_variant = (c >> 24) & 0xFF
    clock_seq_low = (c >> 16) & 0xFF
    node = ((c & 0xFFFF) << 32) | (d & 0xFFFFFFFF)
    return _stdlib_uuid.UUID(fields=(time_low, time_mid, time_hi_version, clock_seq_hi_variant, clock_seq_low, node))
def uuid_to_fguid(uid: _stdlib_uuid.UUID) -> tuple[int, int, int, int]:
    a = uid.time_low & 0xFFFFFFFF
    b = ((uid.time_mid & 0xFFFF) << 16) | (uid.time_hi_version & 0xFFFF)
    c = ((uid.clock_seq_hi_variant & 0xFF) << 24) | ((uid.clock_seq_low & 0xFF) << 16) | ((uid.node >> 32) & 0xFFFF)
    d = uid.node & 0xFFFFFFFF
    return a, b, c, d
def decode(reader: FArchiveReader, type_name: str, size: int, path: str) -> dict[str, Any]:
    if type_name != 'MapProperty':
        raise Exception(f'Expected MapProperty, got {type_name}')
    value = reader.property(type_name, size, path, nested_caller_path=path)
    group_map = value['value']
    for group in group_map:
        group_type = group['value']['GroupType']['value']['value']
        group_bytes = group['value']['RawData']['value']['values']
        group['value']['RawData']['value'] = decode_bytes(reader, group_bytes, group_type)
    return value
def decode_bytes(parent_reader: FArchiveReader, group_bytes: Sequence[int], group_type: str) -> dict[str, Any]:
    reader = parent_reader.internal_copy(bytes(group_bytes), debug=False)
    group_data = {'group_type': group_type, 'group_id': reader.guid(), 'group_name': reader.fstring(), 'individual_character_handle_ids': reader.tarray(instance_id_reader)}
    if group_type in ['EPalGroupType::Guild', 'EPalGroupType::IndependentGuild', 'EPalGroupType::Organization']:
        group_data |= {'org_type': reader.byte()}
    if group_type == 'EPalGroupType::Organization':
        group_data |= {'trailing_bytes': reader.byte_list(12)}
    if group_type == 'EPalGroupType::Guild':
        guild: dict[str, Any] = {'leading_bytes': reader.byte_list(4), 'base_ids': reader.tarray(uuid_reader), 'unknown_1': reader.i32(), 'base_camp_level': reader.i32(), 'map_object_instance_ids_base_camp_points': reader.tarray(uuid_reader), 'guild_name': reader.fstring(), 'last_guild_name_modifier_player_uid': reader.guid(), 'unknown_2': reader.byte_list(4), 'admin_player_uid': reader.guid()}
        guild['unknown_3'] = reader.i32()
        guild['unknown_4'] = [int(b) for b in reader.byte_list(4)]
        players_header = reader.u16()
        guild['players_header'] = players_header
        players_count = reader.i32()
        players = []
        for _ in range(players_count):
            a = reader.u32()
            b = reader.u32()
            c = reader.u32()
            d = reader.u32()
            uid = fguid_to_uuid(a, b, c, d)
            pi = {'last_online_real_time': reader.i64(), 'player_name': reader.fstring()}
            tail = [int(b) for b in reader.byte_list(31)]
            players.append({'player_uid': uid, 'player_info': pi, 'unknown_tail': tail})
        guild['players'] = players
        if not reader.eof():
            guild['unknown_bytes'] = [int(b) for b in reader.read_to_end()]
        group_data |= guild
    if group_type == 'EPalGroupType::IndependentGuild':
        guild: dict[str, Any] = {'base_camp_level': reader.i32(), 'map_object_instance_ids_base_camp_points': reader.tarray(uuid_reader), 'guild_name': reader.fstring()}
        group_data |= guild
        indie = {'player_uid': reader.guid(), 'guild_name_2': reader.fstring(), 'player_info': {'last_online_real_time': reader.i64(), 'player_name': reader.fstring()}}
        group_data |= indie
    if not reader.eof():
        group_data['unknown_bytes'] = [int(b) for b in reader.read_to_end()]
    return group_data
def encode(writer: FArchiveWriter, property_type: str, properties: dict[str, Any]) -> int:
    if property_type != 'MapProperty':
        raise Exception(f'Expected MapProperty, got {property_type}')
    del properties['custom_type']
    group_map = properties['value']
    for group in group_map:
        if 'values' in group['value']['RawData']['value']:
            continue
        p = group['value']['RawData']['value']
        encoded_bytes = encode_bytes(p)
        group['value']['RawData']['value'] = {'values': [b for b in encoded_bytes]}
    return writer.property_inner(property_type, properties)
def encode_bytes(p: dict[str, Any]) -> bytes:
    writer = FArchiveWriter()
    writer.guid(p['group_id'])
    writer.fstring(p['group_name'])
    writer.tarray(instance_id_writer, p['individual_character_handle_ids'])
    if p['group_type'] in ['EPalGroupType::Guild', 'EPalGroupType::IndependentGuild', 'EPalGroupType::Organization']:
        writer.byte(p['org_type'])
    if p['group_type'] == 'EPalGroupType::Organization':
        writer.write(bytes(p['trailing_bytes']))
    if p['group_type'] == 'EPalGroupType::IndependentGuild':
        writer.guid(p['player_uid'])
        writer.fstring(p['guild_name_2'])
        writer.i64(p['player_info']['last_online_real_time'])
        writer.fstring(p['player_info']['player_name'])
    if p['group_type'] == 'EPalGroupType::Guild':
        writer.write(bytes(p['leading_bytes']))
        writer.tarray(uuid_writer, p['base_ids'])
        writer.i32(p['unknown_1'])
        writer.i32(p['base_camp_level'])
        writer.tarray(uuid_writer, p['map_object_instance_ids_base_camp_points'])
        writer.fstring(p['guild_name'])
        writer.guid(p['last_guild_name_modifier_player_uid'])
        writer.write(bytes(p['unknown_2']))
        writer.guid(p['admin_player_uid'])
        writer.i32(p.get('unknown_3', 0))
        writer.write(bytes(p.get('unknown_4', [0, 0, 1, 0])))
        writer.u16(p.get('players_header', 0))
        writer.i32(len(p['players']))
        for player in p['players']:
            if 'unknown_tail' in player:
                puid = player['player_uid']
                if isinstance(puid, str):
                    puid = _stdlib_uuid.UUID(puid)
                a, b, c, d = uuid_to_fguid(puid)
                writer.u32(a)
                writer.u32(b)
                writer.u32(c)
                writer.u32(d)
                writer.i64(player['player_info']['last_online_real_time'])
                writer.fstring(player['player_info']['player_name'])
                writer.write(bytes(player['unknown_tail']))
            else:
                player_info_writer(writer, player)
    if 'unknown_bytes' in p:
        writer.write(bytes(p['unknown_bytes']))
    if 'trailing_bytes' in p:
        writer.write(bytes(p['trailing_bytes']))
    encoded_bytes = writer.bytes()
    return encoded_bytes