"""
generate_all_chars.py — 生成全量候选字数据

输出 data/all_chars.json，每条记录为一个候选字及其属性：
  {
    "c":    "明",
    "py":   "míng",
    "tone": 2,
    "wx":   "火",
    "st":   8,
    "open": "small",
    "sent": "花明月暗笼轻雾",   // 最佳诗文句（无则 null）
    "title":"无题", "author":"李商隐",
    "book": "唐诗三百首", "dynasty":"唐代", "bookkey":"tangshi"
  }

多音字额外字段：
    "multi": true,
    "pys":   [{"py":"guān","tone":1},{"py":"guàn","tone":4}]

候选字来源：full_wuxing_dict × chinese_chars.csv 交集
诗文来源：遍历所有诗集，为每个字找到一句最短的含该字诗句
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from char_pool import classify_openness, load_chars_from_csv, load_wuxing_from_dict

# ── 多音字辅助 ─────────────────────────────────────────
_TONE_MARKS: dict[str, int] = {}
for _base, _variants in [
    ('a', 'āáǎà'), ('e', 'ēéěè'), ('i', 'īíǐì'),
    ('o', 'ōóǒò'), ('u', 'ūúǔù'), ('v', 'ǖǘǚǜ'),
]:
    for _i, _ch in enumerate(_variants, 1):
        _TONE_MARKS[_ch] = _i

_INITIALS = frozenset(['zh','ch','sh','b','p','m','f','d','t','n','l',
                       'g','k','h','j','q','x','r','z','c','s','y','w'])


def _tone_of(py: str) -> int:
    """从带声调拼音字符串提取声调数字（1-4），轻声返回 0）"""
    for ch in py:
        t = _TONE_MARKS.get(ch)
        if t:
            return t
    return 0


def _final_of(py: str) -> str:
    """从带声调拼音提取韵母（用于判断开口度）"""
    # 去声调符号
    s = ''.join(
        c for c in unicodedata.normalize('NFD', py)
        if unicodedata.category(c) != 'Mn'
    ).replace('ü', 'v')
    # 去声母
    for init in ('zh', 'ch', 'sh'):
        if s.startswith(init):
            return s[2:]
    if s and s[0] in 'bpmfdtnlgkhqxrzcsyw':
        return s[1:]
    return s


def _load_multi_chars(
    csv_path: Path,
    wuxing_map: dict[str, tuple[str, int]],
    exclude: set[str],
) -> list[dict]:
    """加载多音字，返回带 multi/pys 标记的条目列表"""
    result = []
    with csv_path.open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            char = row['word']
            if char in exclude:
                continue
            if char not in wuxing_map:
                continue
            raw_py = row['pinyin']
            if ',' not in raw_py:
                continue

            all_pys = [p.strip() for p in raw_py.split(',') if p.strip()]
            if not all_pys:
                continue

            # 主读音使用 CSV tone / pinyin_final 字段
            try:
                primary_tone = int(row['tone'])
            except (ValueError, TypeError):
                primary_tone = _tone_of(all_pys[0])
            if primary_tone not in (1, 2, 3, 4):
                primary_tone = _tone_of(all_pys[0])
            if primary_tone not in (1, 2, 3, 4):
                continue

            primary_final = row.get('pinyin_final', '') or _final_of(all_pys[0])
            openness = classify_openness(primary_final)
            wuxing, stroke_count = wuxing_map[char]

            pys_info = []
            for py in all_pys:
                t = _tone_of(py)
                if t not in (1, 2, 3, 4):
                    t = 0  # 轻声
                pys_info.append({"py": py, "tone": t})

            result.append({
                "c":     char,
                "py":    all_pys[0],
                "tone":  primary_tone,
                "wx":    wuxing,
                "st":    stroke_count,
                "open":  openness,
                "multi": True,
                "pys":   pys_info,
            })
    return result

_ROOT      = Path(__file__).parent.parent
_POEM_DIR  = _ROOT / "data" / "poems"
_OUT_FILE  = _ROOT / "data" / "all_chars.json"
_TIER_FILE = _ROOT / "data" / "char_tier.json"


def _load_tier_map() -> dict[str, str]:
    """加载字级映射 {char: 'S'|'A'}，不在表中的字默认为 'B'"""
    if not _TIER_FILE.exists():
        return {}
    try:
        data = json.loads(_TIER_FILE.read_text(encoding="utf-8"))
        tier_map: dict[str, str] = {}
        for ch in data.get("S", []):
            tier_map[ch] = "S"
        for ch in data.get("A", []):
            if ch not in tier_map:   # S 优先
                tier_map[ch] = "A"
        return tier_map
    except Exception:
        return {}

BOOKS = [
    ("shijing", "诗经"),
    ("chuci",   "楚辞"),
    ("yuefu",   "乐府诗集"),
    ("tangshi", "唐诗三百首"),
    ("gushi",   "古诗三百首"),
    ("songci",  "宋词精选"),
    ("cifu",    "著名辞赋"),
]

PUNC = frozenset("《》！*^$%~!@#…&￥—+=、。，？；''""：·`\"'")
_HTML  = re.compile(r"<[^>]+>")
_SPC   = re.compile(r"[\s\u3000\u00a0]+")
_PAR   = re.compile(r"[\(（][^)）]*[\)）]")
_SPLIT = re.compile(r"[！。？；，、\n]+")


def _clean(s: str) -> str:
    s = _HTML.sub("", s)
    s = _PAR.sub("", s)
    return _SPC.sub("", s)


def _sentences(content: str) -> list[str]:
    return [p for p in _SPLIT.split(_clean(content)) if len(p) >= 2]


def _clean_sent(s: str) -> str:
    return "".join(c for c in s if c not in PUNC)


def build_char_poem_map() -> dict[str, dict]:
    """为每个汉字找到包含它的最短诗句（优先诗经/唐诗等正统诗集）"""
    # 优先级：诗经 > 唐诗 > 古诗 > 乐府 > 宋词 > 楚辞 > 辞赋
    priority = {k: i for i, (k, _) in enumerate(BOOKS)}

    # char -> {sent, title, author, book, dynasty, bookkey, priority, sent_len}
    char_best: dict[str, dict] = {}

    for bookkey, bookname_default in BOOKS:
        path = _POEM_DIR / f"{bookkey}.json"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            poems = json.load(f)

        prio = priority[bookkey]

        for poem in poems:
            content = poem.get("content", "")
            if not content:
                continue
            meta = {
                "title":   poem.get("title", ""),
                "author":  poem.get("author", ""),
                "book":    poem.get("book", bookname_default),
                "dynasty": poem.get("dynasty", ""),
                "bookkey": bookkey,
            }

            for sent in _sentences(content):
                clean = _clean_sent(sent)
                if len(clean) < 2:
                    continue

                for ch in set(clean):
                    if not ch or ch in PUNC:
                        continue
                    existing = char_best.get(ch)
                    # 优先选优先级高（数字小）的书，同书时选句子更短的
                    if (existing is None
                            or prio < existing["_prio"]
                            or (prio == existing["_prio"] and len(clean) < existing["_len"])):
                        char_best[ch] = {**meta, "sent": clean, "_prio": prio, "_len": len(clean)}

    return char_best


def generate(verbose: bool = True) -> None:
    if verbose:
        print("加载字符池…")
    tier_map    = _load_tier_map()
    wuxing_map  = load_wuxing_from_dict()
    char_attrs  = load_chars_from_csv(wuxing_map=wuxing_map)
    if verbose:
        print(f"  单音字：{len(char_attrs):,}")

    # 加载多音字（wuxing_map 有且不在单音字集合中的）
    csv_path = _ROOT / "data" / "chinese_chars.csv"
    multi_entries = _load_multi_chars(csv_path, wuxing_map, exclude=set(char_attrs.keys()))
    if verbose:
        print(f"  多音字：{len(multi_entries):,}")

    if verbose:
        print("扫描诗文，建立字→诗句映射…")
    char_poem = build_char_poem_map()
    has_poem = sum(1 for c in char_attrs if c in char_poem)
    if verbose:
        print(f"  含诗文来源：{has_poem:,} / {len(char_attrs):,} 字（单音字）")

    # 构建输出列表 — 单音字
    result = []
    for ch, a in char_attrs.items():
        entry: dict = {
            "c":    ch,
            "py":   a.pinyin,
            "tone": a.tone,
            "wx":   a.wuxing,
            "st":   a.stroke_count,
            "open": a.openness,
        }
        t = tier_map.get(ch)
        if t:
            entry["tier"] = t
        src = char_poem.get(ch)
        if src:
            entry["sent"]    = src["sent"]
            entry["title"]   = src["title"]
            entry["author"]  = src["author"]
            entry["book"]    = src["book"]
            entry["dynasty"] = src["dynasty"]
            entry["bookkey"] = src["bookkey"]
        result.append(entry)

    # 多音字：追加诗文来源和 tier
    for entry in multi_entries:
        ch = entry["c"]
        t = tier_map.get(ch)
        if t:
            entry["tier"] = t
        src = char_poem.get(ch)
        if src:
            entry["sent"]    = src["sent"]
            entry["title"]   = src["title"]
            entry["author"]  = src["author"]
            entry["book"]    = src["book"]
            entry["dynasty"] = src["dynasty"]
            entry["bookkey"] = src["bookkey"]
        result.append(entry)

    # 写出
    _OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    kb = _OUT_FILE.stat().st_size / 1024
    total = len(result)
    if verbose:
        print(f"\n输出：{total:,} 条（单音 {len(char_attrs):,} + 多音 {len(multi_entries):,}）"
              f"  →  {kb:.0f} KB  →  {_OUT_FILE}")


if __name__ == "__main__":
    generate()
