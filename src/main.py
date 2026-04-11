"""
main.py — CLI 入口

用法：
    python src/main.py
    python src/main.py --surname 姚
    python src/main.py --surname 姚 --output results.csv
    python src/main.py --surname 姚 --strict-openness --preview 20
    python src/main.py --surname 姚 --no-filters  # 仅生成，不应用过滤器

选项：
    --surname         姓氏（默认：姚）
    --output          CSV 输出文件路径（默认：results_<姓氏>_<日期>.csv）
    --no-csv          不输出 CSV 文件
    --strict-openness 启用严格开口度模式（名字后两字至少一个大开口）
    --no-filters      跳过所有过滤器，仅生成原始组合（用于调试）
    --preview         控制台预览数量（默认：10）
    --quiet           不打印详细统计信息
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# 将 src 目录加入路径，确保模块可以直接导入
sys.path.insert(0, str(Path(__file__).parent))

from char_pool import build_char_pool
from filters import OpennessFilter, ToneFilter
from generator import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="宝宝起名系统 v0.1 — 基于语言学规则的姓名候选生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python src/main.py
  python src/main.py --surname 李 --output 李姓候选.csv
  python src/main.py --strict-openness --preview 20
        """,
    )
    parser.add_argument(
        '--surname', default='姚',
        help='姓氏（默认：姚）',
    )
    parser.add_argument(
        '--output', default=None,
        help='CSV 输出路径（默认：results_<姓氏>_<日期>.csv）',
    )
    parser.add_argument(
        '--no-csv', action='store_true',
        help='不输出 CSV 文件',
    )
    parser.add_argument(
        '--strict-openness', action='store_true',
        help='严格开口度模式：名字后两字至少一个大开口',
    )
    parser.add_argument(
        '--no-filters', action='store_true',
        help='跳过所有过滤器，仅生成原始组合（调试用）',
    )
    parser.add_argument(
        '--preview', type=int, default=10,
        help='控制台预览候选名字数量（默认：10）',
    )
    parser.add_argument(
        '--quiet', action='store_true',
        help='不打印详细统计信息',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    verbose = not args.quiet

    print("=" * 55)
    print("  宝宝起名系统 v0.1")
    print(f"  姓氏：{args.surname}")
    print("=" * 55)

    # ── 阶段0：构建字符池 ──
    if verbose:
        print("\n[阶段0] 汉字池构建（data/chinese_chars.csv）")
    pool = build_char_pool(args.surname, verbose=verbose)

    # ── 配置过滤器 ──
    filters = []
    if not args.no_filters:
        filters = [
            ToneFilter(pattern=['ping', 'ze', 'ping']),
            OpennessFilter(strict=args.strict_openness),
        ]
        if verbose:
            print(f"\n[配置] 已启用过滤器：")
            for f in filters:
                print(f"  - {f.description}")

    # ── 确定 CSV 输出路径 ──
    output_csv: Path | None = None
    if not args.no_csv:
        if args.output:
            output_csv = Path(args.output)
        else:
            today = date.today().strftime('%Y%m%d')
            output_csv = Path(f"results_{args.surname}_{today}.csv")

    # ── 执行流水线 ──
    candidates = run_pipeline(
        surname=args.surname,
        pool=pool,
        filters=filters,
        output_csv=output_csv,
        preview_count=args.preview,
        verbose=verbose,
    )

    # ── 最终摘要 ──
    print("\n" + "=" * 55)
    print(f"  完成！共生成候选名字：{len(candidates):,} 个")
    if output_csv and output_csv.exists():
        print(f"  候选名单已保存至：{output_csv}")
    print("=" * 55)


if __name__ == '__main__':
    main()
