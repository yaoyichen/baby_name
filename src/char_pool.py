"""
char_pool.py — 汉字池构建模块

数据来源：
  - data/chinese_chars.csv      通用规范汉字表（8105字），提供拼音/部首/繁体/五笔等
  - data/full_wuxing_dict.py    更可靠的五行与笔画数据，按五行分类，每 key 为笔画数

数据合并策略：
  - 候选字取两份数据的交集
  - 五行、笔画数 来自 full_wuxing_dict.py（优先级高）
  - 其余字段（拼音/部首/繁体/五笔等）来自 chinese_chars.csv

CSV 字段说明：
  num            序号
  word           汉字
  pinyin         拼音（含声调符号；多音字用逗号分隔，如 'dīng,zhēng'）
  radical        部首
  stroke_count   笔画数
  wuxing         五行（土/木/火/金/水，或 NULL/'-' 表示未知）
  traditional    繁体字
  wubi           五笔编码
  pinyin_initial 声母（零声母为 NULL）
  pinyin_final   韵母（如 'ao', 'i', 'un'）
  tone           声调数字（1/2/3/4）

处理规则：
  - 多音字（pinyin 含逗号）→ 过滤，避免读音歧义
  - 异常韵母（含 '|'、'^' 或为 'NULL'）→ 过滤
  - 不在 full_wuxing_dict.py 中的字 → 过滤（无法确认五行）
"""

from __future__ import annotations

import csv
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

# 数据文件路径（相对于本文件所在的 src 目录的上一级）
_DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_CSV = _DATA_DIR / "chinese_chars.csv"
DEFAULT_WUXING_DICT = _DATA_DIR / "full_wuxing_dict.py"

# 合法五行值
VALID_WUXING = frozenset({"木", "火", "土", "金", "水"})


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class CharAttr:
    """单个汉字的完整属性（来自 CSV + 开口度推导）"""
    char: str           # 汉字
    pinyin: str         # 第一读音（带调符），如 'yāo'
    tone: int           # 声调 1/2/3/4
    final: str          # 韵母，如 'ao', 'i', 'un'
    openness: str       # 'large'（大开口/开口呼）或 'small'（小开口）
    stroke_count: int   # 笔画数
    wuxing: str | None  # 五行（木/火/土/金/水），数据缺失时为 None
    radical: str        # 部首


class CharPool(NamedTuple):
    """分类后的字符池"""
    all_attrs: dict[str, CharAttr]   # char → CharAttr
    ze_pool: list[CharAttr]          # 仄声池（声调 3/4），用于名字第二字
    ping_pool: list[CharAttr]        # 平声池（声调 1/2），用于名字第三字


# ──────────────────────────────────────────────
# 开口度分类
# ──────────────────────────────────────────────

_SMALL_OPENING_INITIALS = frozenset(("i", "u", "v", "ü"))


def classify_openness(final: str) -> str:
    """
    根据韵母的四呼归属判断开口度。

    - large（大开口/开口呼）：韵母不以 i/u/ü 开头
      示例：ao, an, ang, e, o, en, er 等
    - small（小开口）：齐齿呼(i-)、合口呼(u-)、撮口呼(ü/v-)
      示例：i, in, ing, ia, u, un, uo, ü, üe 等
    """
    if not final:
        return "large"
    return "small" if final[0] in _SMALL_OPENING_INITIALS else "large"


# ──────────────────────────────────────────────
# CSV 加载与验证
# ──────────────────────────────────────────────

def _is_valid_final(final: str) -> bool:
    """过滤异常韵母（数据质量问题）"""
    if not final or final == "NULL":
        return False
    # 含 '|' 或 '^' 的是数据异常，如 'i|jī', 'e^'
    if "|" in final or "^" in final:
        return False
    return True


def _parse_wuxing(raw: str) -> str | None:
    """解析五行字段，无效值返回 None"""
    if raw in VALID_WUXING:
        return raw
    return None


def load_wuxing_from_dict(
    dict_path: Path = DEFAULT_WUXING_DICT,
) -> dict[str, tuple[str, int]]:
    """
    从 full_wuxing_dict.py 加载五行与笔画数据。

    该文件包含 jin_dict / mu_dict / huo_dict / shui_dict / tu_dict 五个字典，
    每个字典的结构为 {笔画数: [字, ...]}。

    Returns:
        char -> (wuxing, stroke_count) 映射
    """
    if not dict_path.exists():
        raise FileNotFoundError(
            f"找不到五行字典文件：{dict_path}\n"
            f"请确认 data/full_wuxing_dict.py 已放置在项目根目录的 data/ 文件夹中。"
        )

    spec = importlib.util.spec_from_file_location("full_wuxing_dict", dict_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    wuxing_source = [
        (mod.jin_dict, "金"),
        (mod.mu_dict, "木"),
        (mod.huo_dict, "火"),
        (mod.shui_dict, "水"),
        (mod.tu_dict, "土"),
    ]

    wuxing_map: dict[str, tuple[str, int]] = {}
    for d, wuxing_name in wuxing_source:
        for stroke_count, chars in d.items():
            for char in chars:
                wuxing_map[char] = (wuxing_name, stroke_count)

    return wuxing_map


def load_chars_from_csv(
    csv_path: Path = DEFAULT_CSV,
    wuxing_map: dict[str, tuple[str, int]] | None = None,
) -> dict[str, CharAttr]:
    """
    从 CSV 加载所有合格汉字，返回 char → CharAttr 映射。

    过滤规则：
      1. 多音字（pinyin 含逗号）→ 跳过
      2. 异常韵母（NULL、含特殊符号）→ 跳过
      3. 声调非 1-4 的特殊读音 → 跳过
      4. 若传入 wuxing_map，则只保留其中存在的字（取交集），
         并用 wuxing_map 中的五行和笔画数覆盖 CSV 原始值

    Args:
        csv_path:   CSV 文件路径
        wuxing_map: char -> (wuxing, stroke_count)，来自 full_wuxing_dict.py；
                    为 None 时回退到 CSV 中的五行/笔画字段
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"找不到汉字数据文件：{csv_path}\n"
            f"请确认 data/chinese_chars.csv 已放置在项目根目录的 data/ 文件夹中。"
        )

    attrs: dict[str, CharAttr] = {}

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            char = row["word"]

            # 若提供了五行字典，则只保留交集中的字
            if wuxing_map is not None and char not in wuxing_map:
                continue

            # 过滤多音字
            if "," in row["pinyin"]:
                continue

            # 过滤异常韵母
            final = row["pinyin_final"]
            if not _is_valid_final(final):
                continue

            # 过滤异常声调
            try:
                tone = int(row["tone"])
            except (ValueError, TypeError):
                continue
            if tone not in (1, 2, 3, 4):
                continue

            # 五行与笔画：优先使用 full_wuxing_dict.py 中的数据
            if wuxing_map is not None:
                wuxing, stroke_count = wuxing_map[char]
            else:
                wuxing = _parse_wuxing(row["wuxing"])
                try:
                    stroke_count = int(row["stroke_count"])
                except (ValueError, TypeError):
                    continue

            attrs[char] = CharAttr(
                char=char,
                pinyin=row["pinyin"],
                tone=tone,
                final=final,
                openness=classify_openness(final),
                stroke_count=stroke_count,
                wuxing=wuxing,
                radical=row["radical"],
            )

    return attrs


# ──────────────────────────────────────────────
# 公共入口
# ──────────────────────────────────────────────

def build_char_pool(
    surname: str,
    csv_path: Path = DEFAULT_CSV,
    wuxing_dict_path: Path = DEFAULT_WUXING_DICT,
    verbose: bool = True,
) -> CharPool:
    """
    构建完整的字符池。

    流程：
      1. 从 full_wuxing_dict.py 加载五行与笔画数据
      2. 从 CSV 加载全部 8105 字，取两份数据的交集
         （五行/笔画来自 full_wuxing_dict.py，其余来自 CSV）
      3. 过滤多音字、异常韵母、异常声调
      4. 排除姓氏本字
      5. 按声调分池：仄声池（3/4声）、平声池（1/2声）

    Args:
        surname:          姓氏，如 '姚'
        csv_path:         CSV 文件路径，默认 data/chinese_chars.csv
        wuxing_dict_path: 五行字典路径，默认 data/full_wuxing_dict.py
        verbose:          是否打印统计信息

    Returns:
        CharPool(all_attrs, ze_pool, ping_pool)
    """
    wuxing_map = load_wuxing_from_dict(wuxing_dict_path)
    raw_attrs = load_chars_from_csv(csv_path, wuxing_map=wuxing_map)
    total_raw = 8105  # 通用规范汉字表总字数（含多音字等待过滤的）

    # 排除姓氏本字
    raw_attrs.pop(surname, None)

    all_attrs = raw_attrs

    if verbose:
        filtered = total_raw - len(all_attrs)
        print(f"  通用规范汉字表总字数：{total_raw:,}")
        print(f"  过滤多音字/异常/不在五行字典中/姓氏：-{filtered:,} 字")
        print(f"  有效候选字（两表交集）：{len(all_attrs):,} 字")
        print(f"  含五行数据：           {len(all_attrs):,} 字（100%，均来自 full_wuxing_dict）")

    ze_pool = [a for a in all_attrs.values() if a.tone in (3, 4)]
    ping_pool = [a for a in all_attrs.values() if a.tone in (1, 2)]

    if verbose:
        print(f"  仄声池（3/4声）：      {len(ze_pool):,} 字")
        print(f"  平声池（1/2声）：      {len(ping_pool):,} 字")

    return CharPool(
        all_attrs=all_attrs,
        ze_pool=ze_pool,
        ping_pool=ping_pool,
    )


def get_char_attr(
    char: str,
    csv_path: Path = DEFAULT_CSV,
    wuxing_dict_path: Path = DEFAULT_WUXING_DICT,
) -> CharAttr | None:
    """
    查询单个汉字的属性（用于验证姓氏属性或外部调用）。
    五行/笔画来自 full_wuxing_dict.py，其余字段来自 CSV。
    注意：多音字或不在五行字典中的字返回 None。
    """
    wuxing_map = load_wuxing_from_dict(wuxing_dict_path)
    attrs = load_chars_from_csv(csv_path, wuxing_map=wuxing_map)
    return attrs.get(char)
