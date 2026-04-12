# AI 起名模块 — 技术文档

> 版本：v1.0 | 日期：2026-04-11

---

## 1. 功能概述

AI 起名模块是整个系统的最终输出层。它在规则过滤产生的**候选字池**基础上，调用 LLM 完成语义层面的评估与排序，一次性推荐 100 个有质量保证的名字，并附带五行分析、字义意境与诗词出处。

整体流程：

```
用户在「浏览」页设置过滤条件
        ↓
候选字池 filtC1（名一·仄声）× filtC2（名二·平声）
        ↓
构造 Prompt（含字池 + 八字信息）
        ↓
POST /api/ai-names  →  server.py 代理  →  LLM API（流式）
        ↓
浏览器接收 SSE 流 → 解析 JSON → 渲染结果表格
```

---

## 2. 候选字池（输入约束）

### 2.1 字池来源

LLM 只能从**当前过滤后的字池**中选字，不允许自由发挥。字池由 `data/all_chars.json` 经前端实时过滤产生：

| 字池 | 变量 | 默认过滤条件 |
|------|------|------------|
| 名一 | `filtC1` | 仄声（3/4声）、五行全开、笔画 1-25 |
| 名二 | `filtC2` | 平声（1/2声）、五行全开、笔画 1-25 |

### 2.2 主要过滤维度

用户可在「浏览」页自由调整以下筛选项，调整后直接影响发给 LLM 的字池：

- **平仄**：可选 1声/2声/3声/4声 任意组合
- **五行**：金/木/火/水/土，可多选
- **开口度**：大开口 / 小开口
- **笔画数**：最小/最大笔画范围滑块
- **多音字**：开关，默认开启
- **黑名单**：已拉黑的字自动排除
- **字符搜索**：按汉字或拼音筛选

### 2.3 字池容量限制

当字池超过 300 字时，前端随机采样 300 字发给 LLM，避免 prompt 过长。实际字池大小在 UI 上实时显示（"名一 N 字 / 名二 N 字"）。

---

## 3. Prompt 工程

### 3.1 Prompt 结构

```
【宝宝信息】
姓氏：{surname}
{baziText}                  ← 用户在「八字信息」文本框中输入/编辑

【候选字池】
名字第一个字必须从以下 N 个字中选取：
{chars1}                    ← filtC1 各字以空格分隔

名字第二个字必须从以下 N 个字中选取：
{chars2}                    ← filtC2 各字以空格分隔

【起名要求】
1. 每个名字由两字组成，第一字来自名一字池，第二字来自名二字池
2. 根据八字五行，优先选能补充偏弱五行的字
3. 名字与"{surname}"姓搭配响亮好听，字义美好积极
4. 尽量选有诗词典故出处的字，在 source 字段注明
5. 避免谐音不雅、寓意消极的搭配

【严格输出格式】
直接输出 JSON 数组，共100条：
[{"name":"两字名","score":整数0-100,"wx":"五行补益简述",
  "meaning":"字义与意境","source":"诗词出处，无则空字符串"},...]
```

### 3.2 八字信息默认内容

页面预填了宝宝的生辰八字（用户可编辑）：

```
公历：2026年4月10日 13:00-15:00
农历：丙午年 壬辰月 甲寅日 辛未时
四柱：年柱丙午（火火）| 月柱壬辰（水土）| 日柱甲寅（木木）| 时柱辛未（金土）
八字五行：木×2  火×2  土×2  金×1  水×1
五行建议：金水偏弱，名字宜补金或水
```

编辑内容通过 `localStorage` 持久化，刷新后不丢失。

### 3.3 LLM 输出的 JSON 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 两字名（不含姓） |
| `score` | int (0-100) | 综合评分（八字契合 + 音韵 + 字义） |
| `wx` | string | 五行补益分析（1-2句） |
| `meaning` | string | 字义与意境解读 |
| `source` | string | 诗词或典故出处，无则空字符串 |

---

## 4. 服务端代理（server.py）

### 4.1 接口定义

```
POST /api/ai-names
Content-Type: application/json

{
  "model":   "deepseek-v3",       // 模型名
  "prompt":  "...",               // 完整 prompt
  "api_key": ""                   // 可选，空时使用服务器内置 key
}
```

响应为 **Server-Sent Events (SSE)** 流：

```
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Connection: close

data: {"choices":[{"delta":{"content":"["}}]}

data: {"choices":[{"delta":{"content":"{\\"name\\""}}]}

...

data: [DONE]
```

### 4.2 LLM API 配置

```python
LLM_BASE_URL = "http://openai.infly.tech/v1"
LLM_API_KEY  = "sk-..."          # 内置于 server.py
```

> **注意**：infly 接口使用自定义请求头 `apikey: <key>`，而非标准的 `Authorization: Bearer <key>`。

### 4.3 流式代理逻辑

```python
with urllib.request.urlopen(req, timeout=300) as resp:
    for line in resp:          # 逐行转发 SSE
        self.wfile.write(line)
        self.wfile.flush()
```

- `timeout=300` 秒，支持生成 100 个名字的耗时（约 30-90 秒）
- 使用 `Connection: close` + `self.close_connection = True` 确保响应结束后连接立即释放
- LLM API 错误（401/429/500等）会被捕获，以 `data: {"error": "..."}` 格式返回给前端

### 4.4 错误处理

| 异常类型 | 处理方式 |
|---------|---------|
| `HTTPError` (401/429/500) | 返回 `data: {"error": "LLM API 错误 N: ..."}` |
| `URLError` (网络不通) | 返回 `data: {"error": "网络连接失败: ..."}` |
| 其他异常 | 返回 `data: {"error": "..."}` |
| 所有错误后 | 追加 `data: [DONE]` 确保前端流结束 |

---

## 5. 前端（analysis/index.html）

### 5.1 模型选择

支持 70+ 个模型，按厂商分 optgroup：

| 分组 | 代表模型 |
|------|---------|
| ⭐ 推荐 | deepseek-v3、gpt-4.1-mini、qwen-plus-latest、claude-sonnet-4-6 |
| GPT 4.x | gpt-4o、gpt-4o-mini、gpt-4.1、gpt-4.1-nano |
| GPT 5 | gpt-5、gpt-5-mini、gpt-5-nano |
| Claude 4 | claude-sonnet-4-6、claude-opus-4-6 |
| O 系列 | o4-mini、o3、o1 |
| DeepSeek | deepseek-v3、deepseek-r1 |
| Qwen (通义) | qwen-max、qwen-plus、qwen-turbo |
| Kimi | kimi-k2-0711-preview |
| Yi / GLM / Hunyuan / Mistral / Llama / Gemma | 各系列主流版本 |

默认模型：`deepseek-v3`（中文能力强，性价比高）。选择与 API key 均通过 `localStorage` 持久化。

### 5.2 流式接收与解析

```javascript
const reader = response.body.getReader();
const decoder = new TextDecoder();
let sseBuffer = '', fullContent = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  sseBuffer += decoder.decode(value, { stream: true });
  const lines = sseBuffer.split('\n');
  sseBuffer = lines.pop();               // 保留不完整行

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    const data = line.slice(6).trim();
    if (data === '[DONE]') break;
    const obj = JSON.parse(data);
    if (obj.error) throw new Error(obj.error);
    fullContent += obj.choices?.[0]?.delta?.content || '';
  }
}
```

**进度显示**：通过统计 `fullContent` 中 `"name":` 出现次数实时显示「已生成 N 个」。

### 5.3 JSON 解析容错

LLM 输出偶尔不完全符合 JSON 规范，`parseAIResults()` 有多层兜底：

1. 直接 `JSON.parse(text)` — 最理想情况
2. 提取 `[...]` 子串再 parse — 应对前后有多余文字
3. 截掉末尾不完整对象后 parse — 应对流被中断
4. 逐个提取完整 `{...}` 对象 — 最后兜底

### 5.4 结果表格

结果按 `score` 降序排列，每行包含：

| 列 | 内容 |
|----|------|
| # | 排名 |
| 名字 | 姓＋名（大字），下方展示两字的五行徽章 |
| 评分 | 彩色圆角徽章（绿/金/红，≥85/≥70/<70） |
| 五行分析 | `wx` 字段 |
| 字义意境 | `meaning` 字段 |
| 诗词出处 | `source` 字段，无则显示"—" |
| 收藏 | ♡/♥ 按钮，与「收藏夹」tab 共享数据 |

> 收藏逻辑复用全局 `toggleFav(a, b, surname)` 函数，收藏的名字可在「收藏夹」tab 中查看完整属性与五格三才分析。

---

## 6. 状态与持久化

| 数据 | 存储位置 | 说明 |
|------|---------|------|
| 选用模型 | `localStorage('ai_model')` | 刷新后记忆 |
| API Key | `localStorage('ai_api_key')` | 覆盖服务器内置 key |
| 姓氏 | `localStorage('ai_surname')` | 同步更新主姓氏 |
| 八字文本 | `localStorage('ai_bazi_text')` | 用户自定义内容 |
| 收藏夹 | `localStorage('name_favs')` | 跨 tab 共享 |

---

## 7. 使用流程

```
1. 启动服务：python3 server.py
   → http://localhost:8080/analysis/

2. 「浏览」tab：根据八字五行需求调整筛选条件
   - 推荐：名一选仄声+金水五行，名二选平声+金水五行
   - 字池大小参考左下角"名一 N 字 / 名二 N 字"

3. 切换到「AI起名」tab
   - 确认/编辑「八字信息」文本框
   - 选择模型（推荐 deepseek-v3 或 qwen-plus-latest）
   - 点击「✦ 生成 100 个名字」

4. 等待生成（约 30-90 秒，进度实时显示）

5. 结果表格按评分排序展示，点击 ♡ 收藏心仪的名字

6. 切换到「收藏夹」tab 查看完整属性与五格三才评分
```

---

## 8. 注意事项

- **字池为空**时「生成」按钮禁用，需先在「浏览」页设置筛选条件
- **模型能力差异**：中文起名建议优先选用 DeepSeek / Qwen / Claude 系列，对中国文化理解更深
- **生成可中断**：点击「⏹ 停止生成」可随时终止，已接收的内容会尝试解析并展示
- **API Key**：默认使用服务器内置 key（`server.py` 中 `LLM_API_KEY` 常量），如需更换在 UI 的 API Key 框输入新 key 即可（优先级高于内置）
- **Token 消耗**：100 个名字约消耗 8000-16000 output tokens，建议使用性价比高的模型（如 gpt-4.1-mini、deepseek-v3）

---

*本文档对应代码版本：`analysis/index.html`（AI起名模块）+ `server.py`（/api/ai-names 端点）*
