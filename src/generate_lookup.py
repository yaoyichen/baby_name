"""
generate_lookup.py — 生成查名专用的扩展字库

输出 data/lookup_chars.json，只包含 NOT 在 all_chars.json 中的字。
查名时优先使用 all_chars.json（候选池），再补充本文件。

数据来源优先级：
  五行 / 笔画：full_wuxing_dict.py  >  chinese_chars.csv wuxing/stroke_count
  拼音 / 声调 / 开口度：chinese_chars.csv

用法：python3 src/generate_lookup.py
"""

from __future__ import annotations

import ast
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_CSV  = _ROOT / "data" / "chinese_chars.csv"
_DICT = _ROOT / "data" / "full_wuxing_dict.py"
_ALL  = _ROOT / "data" / "all_chars.json"
_OUT  = _ROOT / "data" / "lookup_chars.json"

# ── 声调符号 → 数字 ─────────────────────────────────────
_TONE_MARKS: dict[str, int] = {}
for _base, _variants in [
    ('a', 'āáǎà'), ('e', 'ēéěè'), ('i', 'īíǐì'),
    ('o', 'ōóǒò'), ('u', 'ūúǔù'), ('v', 'ǖǘǚǜ'),
]:
    for _i, _ch in enumerate(_variants, 1):
        _TONE_MARKS[_ch] = _i


def _tone_of(py: str) -> int:
    for ch in py:
        t = _TONE_MARKS.get(ch)
        if t:
            return t
    return 0


def _final_of(py: str) -> str:
    s = ''.join(
        c for c in unicodedata.normalize('NFD', py)
        if unicodedata.category(c) != 'Mn'
    ).replace('ü', 'v')
    for init in ('zh', 'ch', 'sh'):
        if s.startswith(init):
            return s[2:]
    if s and s[0] in 'bpmfdtnlgkhqxrzcsyw':
        return s[1:]
    return s


def _classify_openness(final: str) -> str:
    """大开口 / 小开口"""
    f = final.lower().lstrip('r')
    if f.startswith(('i', 'u', 'v', 'ü')):
        return 'small'
    return 'large'


def _load_wuxing_map() -> dict[str, tuple[str, int]]:
    """解析 full_wuxing_dict.py → {char: (wx, strokes)}"""
    content = _DICT.read_text(encoding='utf-8')
    wx_map: dict[str, tuple[str, int]] = {}
    name_to_cn = {
        'jin_dict': '金', 'mu_dict': '木', 'shui_dict': '水',
        'huo_dict': '火', 'tu_dict':  '土',
    }
    for var, wx_cn in name_to_cn.items():
        pat = rf'{var}\s*=\s*(\{{[\s\S]*?\}})\s*(?=#|\Z|[a-z_]+ ?=)'
        m = re.search(pat, content)
        if not m:
            continue
        d: dict = ast.literal_eval(m.group(1))
        for strokes, chars in d.items():
            for c in chars:
                wx_map[c] = (wx_cn, int(strokes))
    return wx_map


def generate() -> None:
    # 已在候选池中的字
    pool_chars: set[str] = set()
    if _ALL.exists():
        for entry in json.loads(_ALL.read_text(encoding='utf-8')):
            pool_chars.add(entry['c'])

    wuxing_map = _load_wuxing_map()

    results: list[dict] = []
    seen: set[str] = set()

    with _CSV.open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            char = row['word']
            if char in pool_chars or char in seen:
                continue
            seen.add(char)

            # 拼音：取第一读音
            raw_py = row.get('pinyin', '').strip()
            primary_py = raw_py.split(',')[0].strip() if raw_py else ''
            if not primary_py:
                continue

            # 声调
            try:
                tone = int(row['tone'])
            except (ValueError, TypeError):
                tone = _tone_of(primary_py)
            if tone not in (1, 2, 3, 4):
                tone = _tone_of(primary_py)

            # 韵母 / 开口度
            final = row.get('pinyin_final', '') or _final_of(primary_py)
            openness = _classify_openness(final)

            # 五行 / 笔画：优先 full_wuxing_dict
            if char in wuxing_map:
                wx, st = wuxing_map[char]
            else:
                wx = row.get('wuxing', '？') or '？'
                try:
                    st = int(row['stroke_count'])
                except (ValueError, TypeError):
                    st = 0

            entry: dict = {
                'c':    char,
                'py':   primary_py,
                'tone': tone,
                'wx':   wx,
                'st':   st,
                'open': openness,
            }

            # 多音字备注
            if ',' in raw_py:
                all_pys = [p.strip() for p in raw_py.split(',') if p.strip()]
                entry['multi'] = True
                entry['pys'] = [{'py': p, 'tone': _tone_of(p)} for p in all_pys]

            results.append(entry)

    _OUT.write_text(
        json.dumps(results, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
    print(f"✅ 扩展查名字库：{len(results)} 字 → {_OUT}")


if __name__ == '__main__':
    generate()
