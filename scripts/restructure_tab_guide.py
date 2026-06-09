"""Restructure all tab_guide HTMLs for better readability.

For every HTML file under resources/tab_guide/<lang>/:
    - Convert inline <b>Label:</b> headings → <h4>Label</h4>
    - Break longer paragraphs into <ul><li> lists
    - Style the Power-User Tip as a highlighted block
    - Add a <style> block for consistent formatting
"""

import os
import re

BASE = os.path.join(os.path.dirname(__file__), '..', 'resources', 'tab_guide')

HEADER_COLOR = '#4a90e2'
TIP_COLOR = '#7DD3FC'
TEXT_COLOR = '#e0e0e0'
CARD_BG = '#0d1117'

STYLE_BLOCK = f'''<style>
h4 {{ color: {HEADER_COLOR}; font-size: 13px; font-weight: bold; margin: 6px 0 1px 0; }}
p  {{ color: {TEXT_COLOR}; font-size: 12px; margin: 1px 0 3px 0; line-height: 1.5; }}
ul {{ color: {TEXT_COLOR}; font-size: 12px; margin: 1px 0 3px 0; padding-left: 18px; line-height: 1.5; }}
li {{ margin: 0; }}
.tip {{ background: {CARD_BG}; border-left: 3px solid {TIP_COLOR}; padding: 4px 8px; margin: 6px 0 0 0; border-radius: 4px; }}
.tip-title {{ color: {TIP_COLOR}; font-weight: bold; font-size: 12px; }}
</style>
'''

P_PATTERN = re.compile(
    r'<p>'
    r'(<b(?:\s+style="[^"]*")?>)'
    r'([^<]+?)'
    r'</b>\s*'
    r'(.*?)'
    r'</p>',
    re.DOTALL
)


def _split_sentences(text):
    """Split text at '. ' boundaries, avoiding abbreviations."""
    parts = re.split(r'(?<=\.)(?:\s+)(?=[A-Z\"\(\-])', text)
    return [p.strip() for p in parts if p.strip()]


def _make_bullets(text):
    """Convert multi-sentence paragraph into a bullet list."""
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return f'<p>{text}</p>\n'
    items = '\n'.join(f'  <li>{s}</li>' for s in sentences)
    return f'<ul>\n{items}\n</ul>\n'


def convert_body(html):
    """Parse original 5-<p> HTML, convert to structured layout."""
    sections = []
    tip_label = tip_content = None

    for m in P_PATTERN.finditer(html):
        raw_label = m.group(2).strip().rstrip(':').strip()
        content = m.group(3).strip()
        is_tip = '7DD3FC' in m.group(1)
        if is_tip:
            tip_label = raw_label
            tip_content = content
        else:
            sections.append((raw_label, content))

    out = STYLE_BLOCK
    out += '<div>\n'

    for label, content in sections:
        out += f'<h4>{label}</h4>\n'
        if label.startswith('Functional'):
            out += f'<p>{content}</p>\n'
        else:
            out += _make_bullets(content)

    if tip_label:
        out += '<div class="tip">\n'
        out += f'<p class="tip-title">{tip_label}</p>\n'
        out += f'<p>{tip_content}</p>\n'
        out += '</div>\n'

    out += '</div>'
    return out


def main():
    for lang in sorted(os.listdir(BASE)):
        lang_dir = os.path.join(BASE, lang)
        if not os.path.isdir(lang_dir) or lang.startswith('__'):
            continue
        for fname in sorted(os.listdir(lang_dir)):
            if not fname.endswith('.html'):
                continue
            fpath = os.path.join(lang_dir, fname)
            with open(fpath, 'r', encoding='utf-8') as f:
                original = f.read()
            converted = convert_body(original)
            if converted != original:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(converted)
                print(f'Converted: {lang}/{fname}')
            else:
                print(f'Skipped (no change): {lang}/{fname}')


if __name__ == '__main__':
    main()
