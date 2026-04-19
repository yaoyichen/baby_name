"""
convert_wuxing_to_json.py — 一次性将 full_wuxing_dict.py 转换为 full_wuxing_dict.json

JSON 格式：
{
  "金": {"2": ["人","入",...], "3": [...], ...},
  "木": {...},
  "火": {...},
  "土": {...},
  "水": {...}
}

运行：python src/convert_wuxing_to_json.py
"""

import importlib.util
import json
from pathlib import Path

ROOT     = Path(__file__).parent.parent
SRC_FILE = ROOT / "data" / "full_wuxing_dict.py"
DST_FILE = ROOT / "data" / "full_wuxing_dict.json"

spec = importlib.util.spec_from_file_location("full_wuxing_dict", SRC_FILE)
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

result = {}
for attr, label in [
    ("jin_dict",  "金"),
    ("mu_dict",   "木"),
    ("huo_dict",  "火"),
    ("tu_dict",   "土"),
    ("shui_dict", "水"),
]:
    d = getattr(mod, attr, {})
    result[label] = {str(k): v for k, v in d.items()}

DST_FILE.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

# 转换完成后立即格式化为可读格式（每行一个笔画组）
import sys
sys.path.insert(0, str(Path(__file__).parent))
from format_wuxing_json import format_wuxing_json
format_wuxing_json(DST_FILE)
