---
name: stock-query
version: 4.0.0
requires:
  praxis-mcp: ">=3.5"
  praxis_sdk: ">=1.0"
  rules_version: "v11"
description: 非持仓标的交互路由 — Speed Insight / Full Audit 双路径 + v3.5 工具整合
---

# stock-query

## 触发条件

当用户咨询**非持仓标的**或**题材**时触发：

- "太极实业怎么样？"
- "半导体板块还能买吗？"
- "帮我看看 000001"
- "新能源有机会吗？"

## 强制逻辑

**严禁直接输出定性结论。必须调用 AskUserQuestion 提供双路径选择。**

## 交互流程

### Step 1: 识别标的

从用户输入中提取标的代码或名称：
- 直接代码：000001、600000
- 股票名称：太极实业、华明装备
- 板块题材：半导体、新能源

### Step 2: 提供双路径选择

```
请选择诊断模式：

**Path A [Speed Insight]** ⚡
- 仅获取实时价/均线/资金流
- 200 字以内真实数据驱动的简评
- 不落盘，低 Token 消耗（~2K tokens）

**Path B [Full Audit]** 📊
- 完整的三团队全链路研判
- 生成物理 .md 报告
- 高 Token 消耗（~68K tokens）
```

### Step 3: 执行对应路径

#### Path A: Speed Insight

```bash
cd /path/to/praxis
python praxis_sdk/scripts/stock_query.py --ticker <代码> --mode speed
```

输出格式：
```
**[标的代码] [标的名称]** ⚡ Speed Insight

- 最新价：¥XX.XX（涨跌幅：+X.X%）
- 引力场：[支撑/阻力] — [具体描述]
- 均线位置：MA10/MA20/MA30
- 资金流向：[流入/流出/中性]

**一句话结论**：[200字以内简评]
```

#### Path B: Full Audit

```bash
cd /path/to/praxis
run_skill({ name: "three-team", arguments: "<代码>" })
```

输出格式：
```
**[标的代码] [标的名称]** 📊 Full Audit

报告已生成：deliverables/a-share/YYYY-MM-DD-<代码>-联合研判.md

**核心结论**：
- ASRG：[一句话结论]
- Masters：[一句话结论]
- Trading：[一句话结论]

**操作建议**：[BUY/SELL/HOLD/WATCH]
```

## 数据底线

**严禁出现基于"通用知识"的模拟**。所有 Path 必须包含以下至少一项的调用结果：

1. `realtime_quote.py` — 实时行情
2. `mx-data` — 妙想数据
3. `akshare` — 本地数据源
4. `data_source.py` — 数据源管理器

**水印机制**：
- 如果数据源全部失败 → 输出必须包含 `⚠️ UNVERIFIED SIMULATION` 水印
- 如果部分数据缺失 → 输出必须标注 `⚠️ 部分数据缺失`

## 审计模式

使用 `audit_mode.py` 管理输出水印：

```python
from praxis_sdk.core.audit_mode import get_audit_mode

mode = get_audit_mode()

# Speed Insight 模式（默认实盘）
mode.set_live()

# 如果数据源失败，切换到模拟模式
if data_source_failed:
    mode.set_simulation("数据源不可用", authorized=False)
```

## Error Handling

```
- 数据源全部失败 → 显示错误信息 + UNVERIFIED SIMULATION 水印
- 部分数据缺失 → 标注缺失项，继续输出
- 用户未选择路径 → 默认 Path A（Speed Insight）
```

## Cost Control

```
- Path A: Token 上限 2K
- Path B: Token 上限 68K
- 每日 Path B 最多触发 1 次
```

## 与现有 Skill 的关系

| 场景 | 使用 Skill |
|:---|:---|
| 用户问持仓标的 | `/quick` 或 `/daily-review` |
| 用户问非持仓标的 | `/stock-query`（本 Skill） |
| 用户要求完整分析 | `/stock-query` → Path B → `/three-team` |
