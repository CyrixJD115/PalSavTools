"""
import_libs — headless CLI/library variant.

All Qt/PySide6 imports and GUI classes have been removed.
The public names that other modules imported from here are retained:
  - backup_whole_directory(source_folder, backup_folder)
"""

import os, ssl
import sys, argparse, collections, copy, ctypes, datetime, gc, json, shutil, glob
import logging, multiprocessing, platform, re, subprocess, threading, pickle, zipfile, string, palworld_coord
import time, traceback, uuid, io, pathlib, urllib.request, tempfile, random
from multiprocessing import shared_memory

from i18n import init_language, t, set_language, get_language, load_resources
from palsav.archive import *
from palsav.paltypes import *
import palsav.rawdata.group as palworld_save_group
from palobject import *
from palsav.gvas import *
from palsav.json_tools import *
from palworld_coord import sav_to_map
from collections import defaultdict
from common import *

logger = logging.getLogger("pst.import_libs")


def backup_whole_directory(source_folder, backup_folder):
    import os, sys, shutil, datetime as dt

    def get_timestamp():
        return dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    source_folder = os.path.abspath(source_folder)
    if not os.path.isabs(backup_folder):
        base_path = "."
        backup_folder = os.path.abspath(os.path.join(base_path, backup_folder))
    else:
        backup_folder = os.path.abspath(backup_folder)

    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    print("Now backing up Level.sav,LevelMeta.sav and Players folder...")
    timestamp = get_timestamp()
    backup_path = os.path.join(backup_folder, f"PalworldSave_backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)

    level_src = os.path.join(source_folder, "Level.sav")
    levelmeta_src = os.path.join(source_folder, "LevelMeta.sav")
    players_src = os.path.join(source_folder, "Players")

    if os.path.exists(level_src):
        shutil.copy2(level_src, os.path.join(backup_path, "Level.sav"))
    if os.path.exists(levelmeta_src):
        shutil.copy2(levelmeta_src, os.path.join(backup_path, "LevelMeta.sav"))
    if os.path.exists(players_src):
        shutil.copytree(players_src, os.path.join(backup_path, "Players"))

    print(f"Backup created at: {backup_path}")
