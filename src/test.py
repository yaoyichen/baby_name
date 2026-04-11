import json
import itertools
import asyncio
from typing import List, Dict, Set
from pypinyin import pinyin, Style

# ==========================================
# 模块 1：数据加载与特征空间缩减 (Data & Space Reduction)
# ==========================================

# 1. 模拟全量康熙字典属性库 (Universal DB)
# 实际生产中，替换为真实的 wuxing_kangxi.json
MOCK_UNIVERSAL_DB = """
{
    "姚": {"strokes": 9, "element": "土"},
    "溯": {"strokes": 13, "element": "水"},
    "渊": {"strokes": 11, "element": "水"},
    "泓": {"strokes": 8, "element": "水"},
    "衍": {"strokes": 9, "element": "水"},
    "洲": {"strokes": 9, "element": "水"},
    "泽": {"strokes": 8, "element": "水"},
    "润": {"strokes": 10, "element": "水"},
    "坦": {"strokes": 8, "element": "土"},
    "辰": {"strokes": 7, "element": "土"},
    "境": {"strokes": 14, "element": "土"},
    "基": {"strokes": 11, "element": "土"},
    "城": {"strokes": 9, "element": "土"},
    "策": {"strokes": 12, "element": "木"},
    "重": {"strokes": 9, "element": "火"} 
}
"""
UNIVERSAL_DB = json.loads(MOCK_UNIVERSAL_DB)

# 2. 人工圈定的正面语义白名单 (The Curated Whitelist)
WHITELIST_GROUPS = {
    "时空与维度": ["辰", "宇", "宙", "纬", "阔", "洲", "境", "穹", "渊", "瀚"],
    "推演与秩序": ["易", "溯", "衍", "秩", "序", "策", "弈", "鉴", "衡", "理"],
    "承载与厚重": ["坦", "基", "泰", "岳", "岸", "筑", "鼎", "城", "厚", "钧"],
    "流动与生机": ["泓", "润", "川", "跃", "济", "霖", "源", "湛", "清", "泽"],
    "多音字负例测试": ["重"],  # 故意放入多音字用于测试过滤器
}
CURATED_WHITELIST = set(itertools.chain.from_iterable(WHITELIST_GROUPS.values()))


def is_polyphone(char: str) -> bool:
    """判断汉字是否为多音字"""
    try:
        pinyin_list = pinyin(char, heteronym=True)[0]
        return len(pinyin_list) > 1
    except Exception:
        return True


def build_input_pool(surname: str) -> List[str]:
    """构建极高纯度的运算池"""
    valid_pool = CURATED_WHITELIST.intersection(set(UNIVERSAL_DB.keys()))
    if surname in valid_pool:
        valid_pool.remove(surname)

    final_pool = [char for char in valid_pool if not is_polyphone(char)]

    removed_count = len(valid_pool) - len(final_pool)
    if removed_count > 0:
        print(f"🧹 [拦截器] 清理了 {removed_count} 个易混淆的多音字。")

    return final_pool


# ==========================================
# 模块 2：规则硬过滤层 (Heuristic Filter)
# ==========================================


class NameGenerator:
    def __init__(self, surname: str):
        self.surname = surname
        self.allowed_elements = ["水", "土", "木"]  # Bazi约束：木火通明，用水土调候
        self.max_stroke_variance = 15.0  # 控制视觉灰度方差

    def get_tone(self, char: str) -> int:
        p = pinyin(char, style=Style.TONE3, heteronym=False)[0][0]
        try:
            return int(p[-1])
        except ValueError:
            return 0

    def check_tones(self, name: str) -> bool:
        """严格校验：平仄平 (2声 - 3/4声 - 1/2声)"""
        t2, t3 = self.get_tone(name[1]), self.get_tone(name[2])
        return (t2 in [3, 4]) and (t3 in [1, 2])

    def check_elements(self, name: str) -> bool:
        """五行安全校验"""
        for char in name[1:]:
            if UNIVERSAL_DB[char]["element"] not in self.allowed_elements:
                return False
        return True

    def check_visual_balance(self, name: str) -> bool:
        """视觉方差校验"""
        strokes = [UNIVERSAL_DB.get(c, {}).get("strokes", 10) for c in name]
        mean = sum(strokes) / len(strokes)
        variance = sum((x - mean) ** 2 for x in strokes) / len(strokes)
        return variance <= self.max_stroke_variance

    def generate(self, pool: List[str]) -> List[str]:
        valid_names = []
        for c2, c3 in itertools.product(pool, pool):
            if c2 == c3:
                continue

            name = f"{self.surname}{c2}{c3}"
            if not self.check_tones(name):
                continue
            if not self.check_elements(name):
                continue
            if not self.check_visual_balance(name):
                continue

            valid_names.append(name)
        return valid_names


# ==========================================
# 模块 3：LLM 语义重排层 (Semantic Reranking)
# ==========================================


async def async_llm_evaluator(name: str, semaphore: asyncio.Semaphore) -> Dict:
    """带并发控制的 LLM 评估器"""
    async with semaphore:
        # 模拟网络 IO
        await asyncio.sleep(0.2)

        # 模拟大模型打分逻辑
        mock_score = 8.0
        if "辰" in name or "渊" in name:
            mock_score += 1.5
        if "策" in name:
            mock_score += 0.8

        return {
            "name": name,
            "score": round(min(mock_score, 9.9), 1),
            "reasoning": f"字型结构稳健，意境深远，符合客观推演的底层逻辑。",
        }


async def run_llm_batch(names: List[str], max_concurrency: int = 10) -> List[Dict]:
    """并发调度所有的 LLM 评估任务"""
    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = [async_llm_evaluator(name, semaphore) for name in names]
    return await asyncio.gather(*tasks)


# ==========================================
# 主程序流水线 (Pipeline Execution)
# ==========================================


async def main():
    surname = "姚"
    print("=== Phase 0: 特征空间初始化 ===")
    active_pool = build_input_pool(surname)
    print(f"-> 最终进入计算引擎的运算池大小: N = {len(active_pool)}\n")

    print("=== Phase 1: 启发式硬过滤 ===")
    generator = NameGenerator(surname)
    hard_filtered_names = generator.generate(active_pool)
    print(f"-> 初筛完成！生成 {len(hard_filtered_names)} 个完全合规的名字。")
    print(f"-> 样本预览: {hard_filtered_names[:5]} ...\n")

    print("=== Phase 2: LLM 异步语义重排 ===")
    scored_results = await run_llm_batch(hard_filtered_names, max_concurrency=5)
    scored_results.sort(key=lambda x: x["score"], reverse=True)

    print("=== Top 3 推荐榜单 ===")
    for idx, res in enumerate(scored_results[:3]):
        name = res["name"]
        strokes = [UNIVERSAL_DB[c]["strokes"] for c in name]
        elements = [UNIVERSAL_DB.get(c, {}).get("element", "") for c in name]
        print(f"[{idx+1}] 【{name}】 | 得分: {res['score']}")
        print(f"    - 物理参数: 笔画 {strokes} | 五行 {elements}")
        print(f"    - 语义评价: {res['reasoning']}")


if __name__ == "__main__":
    asyncio.run(main())
