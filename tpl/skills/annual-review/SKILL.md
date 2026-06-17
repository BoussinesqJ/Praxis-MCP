---
name: annual-review
version: 4.1.0
requires:
  praxis-mcp: ">=3.5"
  rules_version: "v11"
description: 年度终极考核与铁律重塑 — 门闸防护 + 全年纪律代价聚合 + 十大铁律有效性评级
---

# annual-review (v4.1.0)

## 触发条件
- 用户说 `/annual-review`、"做年度复盘"、"今年复盘"
- 每年末（12月/1月初）触发

## 🔴 严禁并发调用规则 (CRITICAL)
底层 MCP 数据通道不支持高并发。必须**严格串行**调用工具。
绝对禁止使用并行工具调用（Parallel Tool Calling），否则将导致管道死锁崩溃。

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

## 🔴 交易前账实核对死线 (CRITICAL)
在复盘结论中，若带有任何买卖调仓倾向，必须在输出内容的首部加粗声明：**系统已触发【强制对账】纪律，请主理人确认底层账本与券商实盘资金一致。**

## 🔴 神圣不可侵犯红线 (CRITICAL)
无论底层给出的年度跑分多难看，以下两条规则是系统最高豁免权。AI **绝对不准**提议废除、收紧或剔除，必须原封不动地保留：

- **Rule 1**: ETF 网格买入拥有绝对豁免权，无视一切防守期仓位限额
- **Rule 7**: 网格内价格到位即可买

---

## 流程

```
Phase 1: 数据采集（严格串行）
│
│  📖 READ: project.md → 持仓 + 策略版本 + 全年变更记录
│           finance_status_card.md → 年初净值基准
│
│  ┌── 🔴 持仓双向同步 Checkpoint（比对 project.md vs portfolio.yaml）
│  │    通过 → 进入 1.1
│  │    不通过 → 阻塞直到同步完成
│  │
├── 1.1 sentinel_tool(action="scan")
├── 1.2 valuation_tool(action="all")
├── 1.3 get_performance_tool(investor, portfolio)
├── 1.4 nav_tool(action="history", days=365)
├── 1.5 cascade_review_tool(mode="annual", period="YYYY")
│       └── period 格式强制 YYYY（如 2026）

    ┌── 🔴 Gate Check: 持仓全量校验
    │
    └── 📋 Phase 1 数据快照

Phase 2: 纪律代价聚合（全年维度）
├── 2.1 读取 outputs/logs/skill-execution.jsonl 中近365天的记录
├── 2.2 统计全年纪律拦截总次数、规避风险%、错失收益%、净收益比
├── 2.3 读取 cascade_review_tool 返回的 data.rule_audit
│       └── 逐条规则的 ratio（拦截收益比）评级
│           ratio < 0.5 → 建议放宽或废除（白名单除外）
│           ratio 1.0~3.0 → 有效，保持
│           ratio > 5.0 → 极其有效，记录为标杆
├── 2.4 读取 data.annual_summary、data.reshape_suggestions、data.monthly_breakdown
└── 2.5 Rule 1 / Rule 7 即使 ratio 极低也必须白名单保留

Phase 3: 十大铁律大考与重塑
├── 3.1 逐条铁律输出 ratio 评级 + 保留/放宽/废除/合并建议
├── 3.2 白名单保护标注
├── 3.3 月度趋势分析：monthly_breakdown 中 net_benefit 全年走势
└── 3.4 重塑建议生成

Phase 4: 输出年报
│  ✍️ WRITE: finance_status_card.md → 强制更新
│            long-term.md → 追加归因审计结论（5日滚动归档）
│            project.md → 更新策略版本号（需主理人确认）
│
├── 4.1 🔴 强制更新 finance_status_card.md
├── 4.2 生成 outputs/YYYY-annual-review.md
└── 4.3 对话中输出精简总结

Phase 5: 审计日志
└── 5.1 写入 outputs/logs/skill-execution.jsonl
```

## AI 处理逻辑

1. 调用工具获取 `data.annual_summary`、`data.rule_audit`、`data.reshape_suggestions`、`data.monthly_breakdown`。
2. **终极绩效审计**：读取年度总拦截次数、规避风险%、错失收益%、净收益比。
3. **十大铁律大考**：深度剖析 `rule_audit` 中每条规则的 `ratio`（拦截收益比）：
   - ratio < 0.5：该规则弊大于利，建议放宽阈值或废除（白名单除外）
   - ratio 1.0~3.0：规则有效，保持现状
   - ratio > 5.0：规则极其有效，建议保持并记录为标杆
4. **重塑建议生成**：基于 `reshape_suggestions` 输出铁律废立建议。
5. **白名单保护**：即使 Rule 1 或 Rule 7 的 ratio 极低，也必须标注"白名单豁免"并保留。
6. **月度趋势分析**：观察 `monthly_breakdown` 中 net_benefit 的全年走势。

## 输出模板

```markdown
<!-- Skill: annual-review v4.1.0 | 周期: YYYY -->
# 🏛️ 年度终极考核与铁律重塑 (YYYY)

## 🏆 终极绩效审计
*(年度总收益、最大回撤、夏普比率、总拦截次数、净收益比)*

## ⚖️ 十大铁律大考与废立
*(逐条规则的 ratio 评级：保留/放宽/废除/合并)*

## 🛡️ 终极防线豁免
*(Rule 1 和 Rule 7 白名单豁免声明)*

## 📅 月度趋势回顾
*(12 个月 net_benefit 走势)*

## 🔮 下年度策略展望
*(基于全年数据，给出下年度的策略调整方向)*
```

## MCP 工具调用

```python
# Phase 1: 数据采集
sentinel_tool(action="scan")
valuation_tool(action="all")
get_performance_tool(investor, portfolio)
nav_tool(action="history", days=365)
cascade_review_tool(mode="annual", period="YYYY")
```

## Error Handling
- Phase 1 任一工具失败 → 重试1次 → 仍失败标记 "⚠️数据缺失"，继续后续Phase
- **Gate Check 失败** → 必须回退 Phase 1 补采，不可跳过
- 写文件失败 → 降级为对话输出
- 原则：输出可不完整，绝不伪造
