---
name: weekly-review
version: 4.1.0
requires:
  praxis-mcp: ">=3.5"
  rules_version: "v11"
description: 周度复盘 — 绩效归因 + 纪律代价周度汇总 + 系统元进化 + 状态卡联动
---

# weekly-review (v4.1.0)

## 触发条件
- 用户说 `/weekly-review`、"做周复盘"、"本周复盘"
- 每周五收盘后或周末手动触发

## 与 daily-review 的区别

| 维度 | daily-review | weekly-review |
|:---|:---|:---|
| **视角** | 战术执行 | 战略纠偏 |
| **关注** | 今天有没有犯错 | 这周赚的钱是因为大盘好还是选股好 |
| **输出** | 明日操作矩阵 | 绩效归因 + 元进化建议 |
| **频率** | 每日 | 每周 |

## 🔴 严禁并发调用规则 (CRITICAL)
底层 MCP 数据通道不支持高并发。必须**严格串行**调用工具。
绝对禁止使用并行工具调用（Parallel Tool Calling），否则将导致管道死锁崩溃。

## 🔴 写入纪律 (CRITICAL)
任何写回状态卡的操作，必须在对话中先展示 diff 内容（旧值 → 新值），经主理人确认后才能写入。long-term.md 的写入尤其敏感——执行 5 日滚动归档，防止文件熵增。

## 🔴 成本价唯一源 (CRITICAL)
复盘报告中所有标的的**成本价**必须从 `project.md` 持仓表的「成本」列读取。
`portfolio_tool` / `nav_tool` 返回的成本仅做交叉参考（标注"工具参考值"），不可直接写入报告。
若两者偏差 >2%，应抛异常并提示手工核对。

## 🔴 持仓全量校验 Gate (CRITICAL)
Phase 1 完成后、Phase 2 开始前，强制执行：
```
Step 1: 从 project.md 读取持仓标的列表 → expected_set
Step 2: 从 portfolio_tool 返回的持仓数据提取标的列表 → actual_set
Step 3: 比对 expected_set == actual_set？
        否 → 列出 missing = expected_set - actual_set
             列出 extra  = actual_set - expected_set
             打印"⚠️ 持仓数量不匹配，回退 Phase 1 补采数据"
             回退 Phase 1 重新采集
        是 → ✅ 通过，进入 Phase 2
```

## 🔴 状态卡联锁更新 (CRITICAL)
Phase 4 中「更新 finance_status_card.md」为**强制非可选**步骤：
```
复盘报告落盘 outputs/ → 检测 finance_status_card.md 时间戳 →
若时间戳 < 今日 → 强制展示 diff（旧值→新值清单）→ 主理人确认 → 同步写入
```

---

## 流程

```
Phase 1: 周度数据聚合（严格串行，每个工具单独调用）
│
│  📖 READ: project.md → 当前持仓 + 策略版本记录
│           finance_status_card.md → 账户概况 + 上次净值基准
│
│  ┌── 🔴 持仓双向同步 Checkpoint（比对 project.md vs portfolio.yaml）
│  │    通过 → 进入 1.1
│  │    不通过 → 自动补齐 portfolio.yaml / 标记人工确认 → 阻塞直到同步完成
│  │
├── 1.1 sentinel_tool(action="scan") → 哨兵扫描 [等待返回]
├── 1.2 valuation_tool(action="all") → 估值分位 [等待返回]
├── 1.3 market_data_ext_tool(action="northbound", days=5) → 北向资金 [等待返回]
├── 1.4 market_data_ext_tool(action="fund_flow", ticker="000001") → 资金流向 [等待返回]
├── 1.5 get_performance_tool(investor, portfolio) → 绩效指标 [等待返回]
├── 1.6 nav_tool(action="history", days=5) → 本周净值走势 [等待返回]
└── 1.7 market_data_ext_tool(action="research", ticker="000001", limit=10) → 本周研报 [等待返回]

    ┌── 🔴 Gate Check: 持仓全量校验（比对 project.md vs portfolio_tool 标的集合）
    │    通过 → 进入 Phase 2  不通过 → 打印缺失列表，回退 Phase 1
    │
    └── 📋 Phase 1 数据快照（结构化输出，供Phase2-4使用）:
        {
          "哨兵": "X/8 多/空",
          "持仓标的": ["ticker1","ticker2",...],
          "今日新增": ["ticker"],
          "各标现价": {"ticker": price},
          "总市值": number,
          "现金": number,
          "总资产": number,
          "总浮盈": number,
          "project.md标的数": expected_count,
          "实际标的数": actual_count,
          "对账结果": "✅ 吻合 / ⚠️ 偏差见missing列表"
        }

Phase 2: 绩效与纪律归因
├── 2.1 计算 Alpha 收益：跑赢或跑输大盘多少？
├── 2.2 统计纪律代价：本周因止损/防追高拦截规避了多少回撤，或错失了多少反弹
├── 2.3 Agent 胜率排名：调用 agent_tracking_tool(action="rank")
├── 2.4 资金流向归因：主力资金是否与持仓方向一致
└── 2.5 北向资金归因：北向资金是否支持持仓逻辑

Phase 3: 元进化评估
│  📖 READ: long-term.md → 铁律规则库 + 历史归因审计
│
├── 3.1 如果本周跑输基准，或纪律错失成本过高
├── 3.2 调用 evolution_tool(action="evaluate", strategy_name="core")
└── 3.3 对参数（网格间距、止损红线）提出自动进化建议

Phase 4: 输出周报
│  ✍️ WRITE: finance_status_card.md → 更新净值/收益率/资产配比
│            long-term.md → 追加归因审计结论（执行 5 日滚动归档）
│            project.md → 更新策略版本号（需主理人确认）
│
├── 4.1 🔴 强制更新 finance_status_card.md
│       └── 检测状态卡时间戳 < 今日 → 打印 diff → 主理人确认 → 写入
├── 4.2 生成 outputs/YYYY-WW-weekly-review.md
└── 4.3 对话中输出精简摘要

Phase 5: 审计日志
└── 5.1 写入 outputs/logs/skill-execution.jsonl
```

## MCP 工具调用

```python
# Phase 1: 周度数据聚合（严格串行，每个工具单独调用）
sentinel_tool(action="scan")                                       # 哨兵扫描
valuation_tool(action="all")                                       # 估值分位
market_data_ext_tool(action="northbound", days=5)                  # 北向资金
market_data_ext_tool(action="fund_flow", ticker="000001")          # 资金流向
get_performance_tool(investor="demo", portfolio="core")     # 绩效指标
nav_tool(action="history", days=5)                                 # 本周净值走势
market_data_ext_tool(action="research", ticker="000001", limit=10) # 本周研报

# Phase 2: 归因分析
agent_tracking_tool(action="rank")                                 # Agent 胜率排名

# Phase 3: 元进化
evolution_tool(action="evaluate", investor="demo", portfolio="core", strategy_name="core")
```

## Error Handling
- Phase 1 任一工具失败 → 重试1次 → 仍失败标记 "⚠️数据缺失"，继续后续Phase
- 写文件失败 → 降级为对话输出
- 原则：输出可不完整，绝不伪造
- **Gate Check 失败** → 必须回退 Phase 1 补采，不可跳过
