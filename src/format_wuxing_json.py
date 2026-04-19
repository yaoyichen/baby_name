"""
format_wuxing_json.py — 将 full_wuxing_dict.json 重新格式化

目标格式：
{
  "金": {
    "2":  ["人", "入", "厶", "刀", "匕"],
    "3":  ["刃", "小", "寸", "三", ...],
    ...
  },
  "木": { ... },
  ...
}

规则：
  - 每行一个笔画组，字符数组内联（不换行）
  - 笔画数字段对齐，可读性好
  - 数字 key 按整数升序排列
  - 五行顺序固定：金 木 火 土 水

运行：python src/format_wuxing_json.py
"""

import json
from pathlib import Path

ROOT     = Path(__file__).parent.parent
SRC_FILE = ROOT / "data" / "full_wuxing_dict.json"

WX_ORDER = ["金", "木", "火", "土", "水"]


def format_wuxing_json(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))

    lines = ["{"]
    wx_keys = [k for k in WX_ORDER if k in data] + [k for k in data if k not in WX_ORDER]

    for wi, wx in enumerate(wx_keys):
        stroke_dict = data[wx]
        # 按笔画数整数升序排列
        sorted_strokes = sorted(stroke_dict.items(), key=lambda x: int(x[0]))

        # 计算最长笔画 key 长度，用于对齐
        max_key_len = max(len(k) for k, _ in sorted_strokes) if sorted_strokes else 1

        lines.append(f'  "{wx}": {{')
        for si, (stroke, chars) in enumerate(sorted_strokes):
            # 字符数组内联，用中文逗号+空格分隔
            chars_json = ", ".join(f'"{c}"' for c in chars)
            # 笔画 key 右对齐（最多2位）
            key_str = f'"{stroke}"'.ljust(max_key_len + 2)
            comma = "," if si < len(sorted_strokes) - 1 else ""
            lines.append(f'    {key_str}: [{chars_json}]{comma}')

        comma = "," if wi < len(wx_keys) - 1 else ""
        lines.append(f'  }}{comma}')

    lines.append("}")

    output = "\n".join(lines) + "\n"
    path.write_text(output, encoding="utf-8")

    total = sum(
        len(chars)
        for wx in data.values()
        for chars in wx.values()
    )
    print(f"格式化完成：{total:,} 个字，{len(lines):,} 行 → {path}")
    print(f"文件大小：{path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    format_wuxing_json(SRC_FILE)
