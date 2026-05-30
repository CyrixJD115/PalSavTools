import json
import os
import sys
import concurrent.futures
from pathlib import Path
try:
    from deep_translator import GoogleTranslator
except ImportError:
    print('Installing deep-translator...')
    import subprocess
    subprocess.check_call(['uv', 'pip', 'install', 'deep-translator'])
    from deep_translator import GoogleTranslator
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = {'zh_CN': {'name': 'Simplified Chinese', 'code': 'zh-CN'}, 'de_DE': {'name': 'German', 'code': 'de'}, 'es_ES': {'name': 'Spanish', 'code': 'es'}, 'fr_FR': {'name': 'French', 'code': 'fr'}, 'ru_RU': {'name': 'Russian', 'code': 'ru'}, 'ja_JP': {'name': 'Japanese', 'code': 'ja'}, 'ko_KR': {'name': 'Korean', 'code': 'ko'}}
NEW_TRANSLATIONS = {'edit_pals.ctx.learnt_skills': 'Learnt Skills', 'edit_pals.ctx.bulk_sync_pal': 'Bulk Sync Pal', 'edit_pals.bulk_sync_pal_title': 'Bulk Sync Pal', 'edit_pals.bulk_sync_found': 'Found {count} {name}', 'edit_pals.bulk_sync_success': 'Updated {count} {name}!', 'edit_pals.bulk_sync_apply': 'Apply Bulk Sync', 'edit_pals.bulk_sync_no_changes': 'No changes detected.', 'edit_pals.learnt_skills_title': 'Learnt Skills', 'edit_pals.learnt_skills_count': '{count} skills learnt', 'edit_pals.confirm_remove_skill': 'Remove {name} from learnt moves?', 'edit_pals.learnt_skills_removed': '{name} removed from learnt moves.', 'calibrate.tree_button': 'Calibrate Tree', 'calibrate.tree_no_players': 'No players found on tree map', 'calibrate.tree_label': 'Player {n}/{total}: tree({ox},{oy}) - click where it should be  (right-click=undo)', '1.Clear fog from each existing LocalData.sav': '1.Clear fog from each existing LocalData.sav', '2.Create backups of each LocalData.sav before modifying': '2.Create backups of each LocalData.sav before modifying', '3.Preserve all existing map data (icons, markers, etc.)': '3.Preserve all existing map data (icons, markers, etc.)', 'Clearing fog in: {path}': 'Clearing fog in: {path}', 'Fog cleared successfully!': 'Fog cleared successfully!'}
OLD_KEYS = ['Copied LocalData.sav to: {path}', 'Restore completed successfully!', 'LocalData.sav Size: {file_size} bytes', "1.Use LocalData.sav from the 'resources' folder", '2.Create backups of each existing LocalData.sav', '3.Copy LocalData.sav to all other worlds/servers', 'restore_map.source', 'LocalData.sav not found: {file}']
def remove_old_keys_from_all():
    for lang_code in list(LANGUAGES.keys()) + ['en_US']:
        lang_file = PROJECT_ROOT / 'resources' / 'i18n' / f'{lang_code}.json'
        if not lang_file.exists():
            continue
        with open(lang_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        removed = [key for key in OLD_KEYS if data.pop(key, None) is not None]
        with open(lang_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if removed:
            print(f'  {lang_code}: removed {len(removed)} keys')
def add_english_keys():
    lang_file = PROJECT_ROOT / 'resources' / 'i18n' / 'en_US.json'
    with open(lang_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for key, english_text in NEW_TRANSLATIONS.items():
        data[key] = english_text
    with open(lang_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def translate_text(text: str, target_lang: str) -> str:
    translator = GoogleTranslator(source='en', target=target_lang)
    return translator.translate(text)
def add_keys_to_language(lang_code: str, lang_info: dict) -> bool:
    try:
        lang_file = PROJECT_ROOT / 'resources' / 'i18n' / f'{lang_code}.json'
        with open(lang_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for key, english_text in NEW_TRANSLATIONS.items():
            translated = translate_text(english_text, lang_info['code'])
            data[key] = translated
        with open(lang_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f'  [ERROR] Failed: {e}')
        return False
def main():
    print('\n' + '=' * 60)
    print('  UPDATING TRANSLATION KEYS')
    print('=' * 60)
    print('\nRemoving old keys...')
    remove_old_keys_from_all()
    print('\nEnglish (en_US)...')
    add_english_keys()
    print('  [OK] Success')
    print('\nTranslating to other languages (parallel processing)...')
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(LANGUAGES)) as executor:
        future_to_lang = {executor.submit(add_keys_to_language, lang_code, lang_info): lang_code for lang_code, lang_info in LANGUAGES.items()}
        for future in concurrent.futures.as_completed(future_to_lang):
            lang_code = future_to_lang[future]
            lang_info = LANGUAGES[lang_code]
            try:
                success = future.result()
                print(f"  {lang_info['name']} ({lang_code}): {('[OK] Success' if success else '[ERROR] Failed')}")
            except Exception as e:
                print(f"  {lang_info['name']} ({lang_code}): [ERROR] {e}")
    print('\n' + '=' * 60)
    print('  DONE')
    print('=' * 60)
if __name__ == '__main__':
    main()
    for p in [Path.cwd() / 'uv.lock', PROJECT_ROOT / 'uv.lock']:
        if p.exists():
            p.unlink()