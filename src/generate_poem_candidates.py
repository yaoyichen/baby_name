"""
generate_poem_candidates.py — 从古诗文语料库提取名字候选对

约束：
  - 两字均须在 full_wuxing_dict × chinese_chars.csv 交集中
  - char1 为仄声（声调 3/4），char2 为平声（声调 1/2）（平仄平 命名格式的名字部分）
  - 散文体书籍（楚辞/辞赋）额外按逗号切分，且每片段最多保留 8 个有效字
  - 按 (char1, char2) 全局去重，保留首次出现的诗句来源

输出：data/poem_candidates.json
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
_OUT_FILE = _ROOT / "data" / "poem_candidates.json"

BOOKS: list[tuple[str, str]] = [
    ("shijing", "诗经"),
    ("chuci",   "楚辞"),
    ("yuefu",   "乐府诗集"),
    ("tangshi", "唐诗三百首"),
    ("gushi",   "古诗三百首"),
    ("songci",  "宋词精选"),
    ("cifu",    "著名辞赋"),
]

# 散文体书籍：额外用逗号分句
PROSE_BOOKS: frozenset[str] = frozenset({"chuci", "cifu"})

# 每片段最多允许的有效字数（超出则跳过，避免长散文爆炸式组合）
MAX_VALID = 8

BAD_CHARS: frozenset[str] = frozenset(
    "胸鬼懒禽鸟鸡我邪罪凶丑仇鼠蟋蟀淫秽妹狐鸡鸭蝇悔鱼肉苦犬吠窥血丧"
    "饥女搔父母昏狗蟊疾病痛死潦哀痒害蛇牲妇狸鹅穴畜烂兽靡爪氓劫鬣螽"
    "毛婚姻匪婆羞辱"
)
PUNC: frozenset[str] = frozenset("《》！*^$%~!@#…&￥—+=、。，？；''""：·`\"'")

_HTML  = re.compile(r"<[^>]+>")
_SPC   = re.compile(r"[\s\u3000\u00a0]+")
_PAR   = re.compile(r"[\(（][^)）]*[\)）]")
_VERSE = re.compile(r"[！。？；\n]+")
_PROSE = re.compile(r"[！。？；，、\n]+")


def _clean(s: str) -> str:
    s = _HTML.sub("", s)
    s = _PAR.sub("", s)
    return _SPC.sub("", s)


def _sentences(content: str, prose: bool) -> list[str]:
    seg = _PROSE if prose else _VERSE
    return [p for p in seg.split(_clean(content)) if len(p) >= 2]


def _valid_chars(seg: str, pool: dict) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ch in seg:
        if ch in PUNC or ch in BAD_CHARS or ch not in pool or ch in seen:
            continue
        seen.add(ch)
        out.append(ch)
    return out


def generate(verbose: bool = True) -> None:
    # ── 加载字符池 ───────────────────────────────────
    wuxing_map = load_wuxing_from_dict()
    char_attrs  = load_chars_from_csv(wuxing_map=wuxing_map)
    if verbose:
        print(f"字符池：{len(char_attrs):,} 字")

    # 仄声池 / 平声池（用于快速判断）
    ze_chars:   frozenset[str] = frozenset(
        c for c, a in char_attrs.items() if a.tone in (3, 4))
    ping_chars: frozenset[str] = frozenset(
        c for c, a in char_attrs.items() if a.tone in (1, 2))

    # ── 遍历诗文 ─────────────────────────────────────
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []

    for bookkey, bookname_default in BOOKS:
        path = _POEM_DIR / f"{bookkey}.json"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            poems = json.load(f)

        is_prose = bookkey in PROSE_BOOKS
        added = 0

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

            for sent in _sentences(content, is_prose):
                valid = _valid_chars(sent, char_attrs)
                if len(valid) < 2:
                    continue
                # 散文片段：跳过过长的（避免 C(n,2) 爆炸）
                if is_prose and len(valid) > MAX_VALID:
                    continue

                # 生成有序对：c1=仄声, c2=平声
                ze_in   = [c for c in valid if c in ze_chars]
                ping_in = [c for c in valid if c in ping_chars]

                clean_sent = "".join(c for c in sent if c not in PUNC)

                for c1 in ze_in:
                    for c2 in ping_in:
                        if c1 == c2:
                            continue
                        pair = (c1, c2)
                        if pair in seen:
                            continue
                        seen.add(pair)
                        a1, a2 = char_attrs[c1], char_attrs[c2]
                        result.append({
                            "c1": c1, "c2": c2,
                            "c1_py": a1.pinyin, "c1_tone": a1.tone,
                            "c1_wx": a1.wuxing,  "c1_st": a1.stroke_count,
                            "c2_py": a2.pinyin, "c2_tone": a2.tone,
                            "c2_wx": a2.wuxing,  "c2_st": a2.stroke_count,
                            "sent":    clean_sent,
                            **meta,
                        })
                        added += 1

        if verbose:
            print(f"  [{bookkey:8s}] {len(poems):4d} 首  →  +{added:,}")

    # ── 写出 ─────────────────────────────────────────
    _OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    kb = _OUT_FILE.stat().st_size / 1024
    if verbose:
        print(f"\n总候选对：{len(result):,}  →  {kb:.0f} KB  →  {_OUT_FILE}")


if __name__ == "__main__":
    generate()
