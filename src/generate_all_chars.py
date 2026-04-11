"""
generate_all_chars.py — 生成全量候选字数据

输出 data/all_chars.json，每条记录为一个候选字及其属性：
  {
    "c":    "明",
    "py":   "míng",
    "tone": 2,
    "wx":   "火",
    "st":   8,
    "sent": "花明月暗笼轻雾",   // 最佳诗文句（无则 null）
    "title":"无题", "author":"李商隐",
    "book": "唐诗三百首", "dynasty":"唐代", "bookkey":"tangshi"
  }

候选字来源：full_wuxing_dict × chinese_chars.csv 交集（5597 字）
诗文来源：遍历所有诗集，为每个字找到一句最短的含该字诗句
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from char_pool import load_chars_from_csv, load_wuxing_from_dict

_ROOT     = Path(__file__).parent.parent
_POEM_DIR = _ROOT / "data" / "poems"
_OUT_FILE = _ROOT / "data" / "all_chars.json"

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
    wuxing_map = load_wuxing_from_dict()
    char_attrs  = load_chars_from_csv(wuxing_map=wuxing_map)
    if verbose:
        print(f"  有效字符：{len(char_attrs):,}")

    if verbose:
        print("扫描诗文，建立字→诗句映射…")
    char_poem = build_char_poem_map()
    has_poem = sum(1 for c in char_attrs if c in char_poem)
    if verbose:
        print(f"  含诗文来源：{has_poem:,} / {len(char_attrs):,} 字")

    # 构建输出列表
    result = []
    for ch, a in char_attrs.items():
        entry: dict = {
            "c":    ch,
            "py":   a.pinyin,
            "tone": a.tone,
            "wx":   a.wuxing,
            "st":   a.stroke_count,
            "open": a.openness,   # "large"=大开口  "small"=小开口
        }
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
    if verbose:
        print(f"\n输出：{len(result):,} 条  →  {kb:.0f} KB  →  {_OUT_FILE}")


if __name__ == "__main__":
    generate()
