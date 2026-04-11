# 宝宝起名系统

基于通用规范汉字表（8105字）的多规则名字筛选工具。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（默认姚姓，输出 CSV）
python src/main.py

# 指定姓氏
python src/main.py --surname 李

# 严格开口度模式（名字后两字至少一个大开口）
python src/main.py --strict-openness

# 查看所有选项
python src/main.py --help
```

## 项目结构

```
baby_name/
├── data/
│   └── chinese_chars.csv      # 通用规范汉字数据（8105字，含拼音/笔画/五行）
├── docs/
│   └── PRD.md                 # 产品需求文档
├── src/
│   ├── char_pool.py           # 字符池构建（CSV加载、多音字过滤、属性预计算）
│   ├── generator.py           # 名字生成器（笛卡尔积 + 过滤流水线）
│   ├── main.py                # CLI 入口
│   └── filters/
│       ├── base.py            # 过滤器抽象基类
│       ├── tone_filter.py     # 平仄规则（默认：平仄平）
│       └── openness_filter.py # 开口度规则
├── requirements.txt
└── README.md
```

## 当前过滤规则（v0.1）

| 规则 | 说明 |
|------|------|
| 多音字过滤 | 排除读音歧义的字 |
| 平仄平 | 姓平—名1仄—名2平，读音有节奏感 |
| 开口度 | 避免三字全为小开口（局促音） |

## 数据说明

`data/chinese_chars.csv` 字段：

| 字段 | 说明 |
|------|------|
| word | 汉字 |
| pinyin | 拼音（含调符；多音字用逗号分隔） |
| tone | 声调（1-4） |
| pinyin_final | 韵母 |
| stroke_count | 笔画数 |
| wuxing | 五行（木/火/土/金/水） |
| radical | 部首 |

## 后续规划

- **v0.2**：八字五行过滤（用神/忌神匹配）
- **v0.3**：LLM 语义评分（批量打分 + Top-N 推荐）
- **v1.0**：Web 界面

详细规划见 [docs/PRD.md](docs/PRD.md)。
