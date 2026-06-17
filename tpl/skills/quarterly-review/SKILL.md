---
name: quarterly-review
version: 4.1.0
requires:
  praxis-mcp: ">=3.5"
  rules_version: "v11"
description: 季度跑分与元进化复盘 — 门闸防护 + 90天纪律代价聚合 + 三团队季度归因
---

# quarterly-review (v4.1.0)

## 触发条件
- 用户说 `/quarterly-review`、"做季度复盘"、"本季复盘"
- 每季度末（3/6/9/12月）触发

## 与 daily-review 的区别

| 维度 | daily-review | quarterly-review |
|:---|:---|:---|
| **视角** | 战术执行 | 战略归因 |
| **关注** | 今天有没有犯错 | 本季度纪律系统有效吗 |
| **数据范围** | 当日 | 近90天 |
| **输出** | 明日操作矩阵 | 季末元进化建议 + 规则有效性评级 |

## 🔴 严禁并发调用规则 (CRITICAL)
底层 MCP 数据通道不支持高并发。必须**严格串行**调用工具。
绝对禁止使用并行工具调用（Parallel Tool Calling），否则将导致管道死锁崩溃。

## 🔴 写入纪律 (CRITICAL)
任何写回状态卡的操作，必须在对话中先展示 diff 内容（旧值 → 新值），经主理人确认后才能写入。

## 🔴 成本价唯一源 (CRITICAL)
复盘报告中所有标的的**成本价**必须从 `project.md` 持仓表的「成本」列读取。
`portfolio_tool` / `nav_tool` 返回的成本仅做交叉参考（标注"工具参考值"），不可直接写入报告。
若两者偏差 >2%，应抛异常并提示手工核对。

## 🔴 持仓全量校验 Gate (CRITICAL)
Phase 1 完成后、Phase 2 开始前，强制执行 project.md 标的列表 vs portfolio_tool 返回标的列表的集合比对，
不一致则回退 Phase 1。

## 🔴 状态卡联锁更新 (CRITICAL)
报告落盘时强制检测 finance_status_card.md 时间戳，过期则展示 diff 经确认后同步写入。

## 🔴 交易前账实核对死线 (CRITICAL)
在复盘结论中，若带有任何买卖调仓倾向，必须在输出内容的首部加粗声明：**系统已触发【强制对账】纪律，请主理人确认底层账本与券商实盘资金一致。**

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
├── 1.4 nav_tool(action="history", days=90)
├── 1.5 cascade_review_tool(mode="quarterly", period="YYYY-Qx")
│       └── period 格式强制 YYYY-Qx（如 2026-Q2）
├── 1.6 market_data_ext_tool(action="research", ticker="000001", limit=20)

    ┌── 🔴 Gate Check: 持仓全量校验
    │
    └── 📋 Phase 1 数据快照（结构化输出）

Phase 2: 纪律代价聚合（90天维度）
├── 2.1 读取 outputs/logs/skill-execution.jsonl 中近90天的记录
│       └── 聚合字段：total_assets / sentinel / rules_violations / discipline_cost
├── 2.2 统计本季度纪律拦截总次数
├── 2.3 计算季度纪律净收益 = 规避风险总额 - 错失收益总额
├── 2.4 逐月 net_benefit 趋势：持续恶化、持续改善还是震荡
├── 2.5 读取 cascade_review_tool 返回的 data.evolution
│       └── 重点：参数修改建议（网格间距、止损红线）
└── 2.6 若 evolution.should_evolve 为 false 且理由为"样本不足"→ 建议继续观察

Phase 3: 三团队季度归因
├── 3.1 ASRG：本季度持仓标的基本面逻辑是否发生变化？
├── 3.2 Masters：铁律规则的有效性评估（哪些规则拦截有效/无效）
├── 3.3 Trading：网格执行效率 + 滑点/摩擦成本统计
└── 3.4 LCD 共识仲裁：三方是否一致？不一致则启动对撞

Phase 4: 输出季报
│  ✍️ WRITE: finance_status_card.md → 强制更新
│            long-term.md → 追加归因审计结论（5日滚动归档）
│            project.md → 更新策略版本号（需主理人确认）
│
├── 4.1 🔴 强制更新 finance_status_card.md
├── 4.2 生成 outputs/YYYY-Qx-quarterly-review.md
└── 4.3 对话中输出精简总结

Phase 5: 审计日志
└── 5.1 写入 outputs/logs/skill-execution.jsonl
```

## AI 处理逻辑

1. 调用工具获取 `data.monthly_reports`（3 个月明细）、`data.quarterly_summary`（季度汇总）、`data.evolution`（进化评估）。
2. **重点读取 `data.evolution` 中的参数修改建议**（如网格间距、止损红线的机器建议）。
3. **人工复核兜底 (CRITICAL)**：AI 不能盲从底层的机器跑分。如果机器建议"放大网格激进做多"，但当前处于大盘极度高估的"绝对防守期"（哨兵多头 ≤ 2/8），AI 必须行使否决权，打回机器的修改建议。
4. 观察 3 个月的 `net_benefit` 趋势：是持续恶化、持续改善、还是震荡。
5. 若 `evolution.should_evolve` 为 false 且理由为"样本不足"，建议继续观察而非强行调参。

## 输出模板

```markdown
<!-- Skill: quarterly-review v4.1.0 | 周期: YYYY-Qx -->
# 🎯 季度跑分与元进化 (YYYY-Qx)

## 📊 90天纪律代价聚合
*(纪律拦截总次数、规避风险总额、错失收益总额、净收益比、逐月趋势)*

## 🧠 机器进化建议
*(底层代码算出的参数调优建议：should_evolve / reason / suggested_changes)*

## ⚖️ CIO 战术校准与裁决
*(AI 结合当前行情，对上述机器建议进行批准或一票否决的裁决)*
*(若当前处于绝对防守期，即使机器建议激进做多，也必须否决)*

## 📋 下季度观测要点
*(基于趋势判断，建议下季度重点关注哪些指标)*
```

## MCP 工具调用

```python
# Phase 1: 数据采集
sentinel_tool(action="scan")
valuation_tool(action="all")
get_performance_tool(investor, portfolio)
nav_tool(action="history", days=90)
cascade_review_tool(mode="quarterly", period="YYYY-Qx")
market_data_ext_tool(action="research", ticker="000001", limit=20)
```

## Error Handling
- Phase 1 任一工具失败 → 重试1次 → 仍失败标记 "⚠️数据缺失"，继续后续Phase
- **Gate Check 失败** → 必须回退 Phase 1 补采，不可跳过
- 写文件失败 → 降级为对话输出
- 原则：输出可不完整，绝不伪造
