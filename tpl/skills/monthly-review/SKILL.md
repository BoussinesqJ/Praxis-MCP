---
name: monthly-review
version: 4.1.0
requires:
  praxis-mcp: ">=3.5"
  rules_version: "v11"
description: 月度纪律与盈亏归因复盘 — 门闸防护 + 30天纪律代价聚合 + CIO 宏观对撞
---

# monthly-review (v4.1.0)

## 触发条件
- 用户说 `/monthly-review`、"做月度复盘"、"本月复盘"
- 每月末触发

## 🔴 严禁并发调用规则 (CRITICAL)
底层 MCP 数据通道不支持高并发。必须**严格串行**调用工具。绝对禁止使用并行工具调用（Parallel Tool Calling），否则将导致管道死锁。

## 🔴 交易前账实核对死线 (CRITICAL)
在复盘结论中，若带有任何买卖调仓倾向，必须在输出内容的首部加粗声明：**系统已触发【强制对账】纪律，请主理人确认底层账本与券商实盘资金一致。**

## 🔴 写入纪律 (CRITICAL)
任何写回状态卡的操作，必须在对话中先展示 diff 内容（旧值 → 新值），经主理人确认后才能写入。

## 🔴 成本价唯一源 (CRITICAL)
复盘报告中所有标的的**成本价**必须从 `project.md` 持仓表的「成本」列读取。
`portfolio_tool` / `nav_tool` 返回的成本仅做交叉参考，不可直接写入报告。

## 🔴 持仓全量校验 Gate (CRITICAL)
Phase 1 完成后、Phase 2 开始前，强制执行 project.md 标的列表 vs portfolio_tool 返回标的列表的集合比对，
不一致则回退 Phase 1。

## 🔴 状态卡联锁更新 (CRITICAL)
报告落盘时强制检测 finance_status_card.md 时间戳，过期则展示 diff 经确认后同步写入。

## 🔴 净值强制入库 (CRITICAL)
Phase 4 末尾必须调用 nav_tool(action="record") 记录净值快照，失败标记 ⚠️ 未交卷。

## 🔴 持仓双向同步 (CRITICAL)
Phase 1 入口比对 project.md vs portfolio.yaml 的标的列表，不一致则阻塞修复。

---

## 流程

```
Phase 1: 数据采集（严格串行）
│
│  📖 READ: project.md → 持仓 + 网格参数 + 策略版本
│           finance_status_card.md → 上期净值
│
│  ┌── 🔴 持仓双向同步 Checkpoint（比对 project.md vs portfolio.yaml）
│  │    通过 → 进入 1.1
│  │    不通过 → 阻塞直到同步完成
│  │
├── 1.1 sentinel_tool(action="scan")
├── 1.2 valuation_tool(action="all")
├── 1.3 get_performance_tool(investor, portfolio)
├── 1.4 nav_tool(action="history", days=30)
├── 1.5 portfolio_tool(action="summary", investor, portfolio)
├── 1.6 cascade_review_tool(mode="monthly", period="YYYY-MM")
│       └── period 格式强制 YYYY-MM（如 2026-06）
├── 1.7 market_data_ext_tool(action="northbound", days=20)
├── 1.8 news_tool(action="finance")
└── 1.9 sentiment_tool(action="analyze", text=<新闻标题>)

    ┌── 🔴 Gate Check: 持仓全量校验
    │
    └── 📋 Phase 1 数据快照（结构化输出）

Phase 2: 纪律代价聚合（30天维度）
├── 2.1 读取 outputs/logs/skill-execution.jsonl 中近30天的记录
├── 2.2 统计本月纪律拦截总次数
├── 2.3 计算本月纪律净收益 = 规避风险总额 - 错失收益总额
├── 2.4 拦截收益比分析（<1.0 纠偏 / 1.0~3.0 肯定 / >3.0 标杆）
└── 2.5 读取 cascade_review_tool 返回的 data.evolution

Phase 3: 输出月报
│  ✍️ WRITE: finance_status_card.md → 强制更新
│            long-term.md → 追加归因审计结论（5日滚动归档）
│            project.md → 更新策略版本号（需主理人确认）
│
├── 3.1 🔴 强制更新 finance_status_card.md
├── 3.2 生成 outputs/YYYY-MM-monthly-review.md
└── 3.3 对话中输出精简总结

Phase 4: 审计日志
├── 4.1 写入 outputs/logs/skill-execution.jsonl
└── 4.2 🔴 nav_tool(action="record") → 记录当月净值
```

## AI 处理逻辑

1. 调用工具获取 `data.raw_stats` 和 `data.discipline_report`。
2. 重点关注 `raw_stats.interception_ratio`（拦截收益比）。
3. **拦截收益比 < 1.0**：防守纪律导致了亏损或踏空。AI 必须结合当月大盘行情进行 CIO 视角的"宽慰"或"纠偏"，强调防守纪律对于本金安全的兜底作用。
4. **拦截收益比 ≥ 3.0**：规则极其有效，正面肯定纪律系统的价值。
5. **无拦截记录**：说明系统处于观察期或数据积累中，不做过度解读。
6. 若 `data.evolution.should_evolve` 为 true，提示主理人关注元进化建议；若 false 且理由为"样本不足"，建议继续观察。

## 输出模板

```markdown
<!-- Skill: monthly-review v4.1.0 | 周期: YYYY-MM -->
# 🛡️ 月度纪律与盈亏归因 (YYYY-MM)

## 📊 数据核账声明
*(强制声明：请主理人核对实盘可用资金与持仓量与报告基数是否一致)*

## 🛑 本月纪律代价
*(展示总拦截次数、规避风险%、错失收益%、以及最终的净拦截收益比)*

## 📉 CIO 宏观对撞分析
*(基于本月大盘走势，锐评纪律系统的有效性：是帮了倒忙，还是挽救了本金？)*

## 🔮 元进化提示
*(若 should_evolve=true，列出建议的参数调整方向；否则注明"规则稳定，无需调整")*

## 📋 操作建议
*(若有调仓建议，首部必须加粗声明强制对账纪律)*
```

## MCP 工具调用

```python
# Phase 1: 数据采集（严格串行）
sentinel_tool(action="scan")
valuation_tool(action="all")
get_performance_tool(investor, portfolio)
nav_tool(action="history", days=30)
portfolio_tool(action="summary", investor, portfolio)
cascade_review_tool(mode="monthly", period="YYYY-MM")
market_data_ext_tool(action="northbound", days=20)
news_tool(action="finance")
sentiment_tool(action="analyze", text="<新闻标题>")
```

## Error Handling
- Phase 1 任一工具失败 → 重试1次 → 仍失败标记 "⚠️数据缺失"，继续后续Phase
- Phase 4.2 nav_tool 失败 → 标记 nav_recorded: false，报告标记 ⚠️ 未交卷
- **Gate Check 失败** → 必须回退 Phase 1 补采，不可跳过
- 写文件失败 → 降级为对话输出
- 原则：输出可不完整，绝不伪造
