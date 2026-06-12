import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_SPEC_DIR = os.getcwd()
for _candidate in ['build_specs/pst.spec', 'pst.spec']:
    if os.path.exists(_candidate):
        _SPEC_DIR = os.path.dirname(os.path.abspath(_candidate))
        break
ROOT_DIR = os.path.abspath(os.path.join(_SPEC_DIR, '..'))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
RES_DIR = os.path.join(ROOT_DIR, 'resources')

datas = [
    (os.path.join(RES_DIR, 'icon.ico'), 'resources'),
    (os.path.join(RES_DIR, 'icon.png'), 'resources'),
    (os.path.join(RES_DIR, 'PST.png'), 'resources'),
    (os.path.join(RES_DIR, 'background.png'), 'resources'),
    (os.path.join(RES_DIR, 'logo.png'), 'resources'),
    (os.path.join(RES_DIR, 'pal.ico'), 'resources'),
    (os.path.join(RES_DIR, 'HackNerdFont-Regular.ttf'), 'resources'),
    (os.path.join(SRC_DIR, 'data'), 'src/data'),
    (os.path.join(SRC_DIR, 'games.json'), '.'),
]

for res_sub in ['i18n', 'tab_guide', 'UI', 'game_data', 'cert', 'readme']:
    path = os.path.join(RES_DIR, res_sub)
    if os.path.isdir(path):
        datas.append((path, os.path.join('resources', res_sub)))

datas += collect_data_files('nerdfont')
datas += collect_data_files('PySide6', subdir='translations')

hiddenimports = [
    'palsav', 'palsav.palsav', 'palsav.archive', 'palsav.paltypes',
    'palsav.gvas', 'palsav.json_tools', 'palsav._cityhash',
    'palsav.compressor', 'palsav.compressor.enums',
    'palsav.compressor.oozlib', 'palsav.compressor.zlib',
    'palsav.commands', 'palsav.commands.convert',
    'palsav.commands.backup', 'palsav.commands.diag',
    'palsav.commands.resave_test', 'palsav.commands.auto_update',
    'palsav.commands.roundtrip_validation',
    'palsav.rawdata',
] + collect_submodules('palsav.palsav.rawdata') + [
    'palooz', 'palworld_coord', 'palworld_toolsets',
    'palworld_xgp_import', 'nerdfont', 'orjson', 'brotli',
    'cbor2', 'zstandard', 'py7zr', 'packaging',
]

excludes = [
    'tkinter', 'test', 'unittest', 'pdb', 'lib2to3', 'distutils',
    'setuptools', 'pip', 'wheel', 'venv', 'ensurepip', 'numpy',
    'pandas', 'email', 'matplotlib', 'scipy', 'IPython',
    'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtDesigner',
    'PySide6.QtHelp', 'PySide6.QtTest', 'PySide6.QtDBus',
    'PySide6.QtPrintSupport', 'PySide6.QtSql', 'PySide6.QtUiTools',
    'PySide6.QtSvgWidgets', 'PySide6.QtXml', 'PySide6.QtQuickWidgets',
    'PySide6.QtBluetooth', 'PySide6.QtNetwork', 'PySide6.QtOpenGL',
    'PySide6.QtPositioning', 'PySide6.QtSensors', 'PySide6.QtSerialPort',
    'PySide6.QtWebSockets', 'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
]

a = Analysis(
    [os.path.join(SRC_DIR, 'palworld_aio', 'main.py')],
    pathex=[SRC_DIR, RES_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

_target_name = (
    'PalworldSaveTools.exe'
    if sys.platform == 'win32'
    else 'PalworldSaveTools'
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=_target_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    icon=os.path.join(RES_DIR, 'icon.ico'),
)
