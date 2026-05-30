import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from palworld_save_tools.palsav import decompress_sav_to_gvas, compress_gvas_to_sav
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS
from palobject import SKP_PALWORLD_CUSTOM_PROPERTIES

path = sys.argv[1]
with open(path, 'rb') as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES)
sd = gvas.properties['SaveData']['value']
raw = bytearray(raw_gvas)
search_off = 0

if 'WorldMapUISaveDataMap' in sd:
    for entry in sd['WorldMapUISaveDataMap']['value']:
        mv = entry['value']['MaskTextureData']['value']['values']
        sig = bytes(mv[:64])
        pos = raw.find(sig, search_off)
        if pos >= 0:
            raw[pos:pos+len(mv)] = b'\x00' * len(mv)
            search_off = pos + len(mv)
    print('WorldMapUISaveDataMap fog cleared')
elif 'WorldMapMaskTextureV4' in sd:
    mv = sd['WorldMapMaskTextureV4']['value']
    sig = bytes(mv[:64])
    pos = raw.find(sig, search_off)
    if pos >= 0:
        raw[pos:pos+len(mv)] = b'\x00' * len(mv)
    print('WorldMapMaskTextureV4 fog cleared')

sav = compress_gvas_to_sav(bytes(raw), save_type)
with open(path, 'wb') as f:
    f.write(sav)

print(f'Saved ({len(sav)} bytes)')
