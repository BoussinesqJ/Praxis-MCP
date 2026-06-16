# Skill 工作流链路参考

> Praxis 提供 28 个 MCP 原子工具，以下链路展示如何将它们串联为完整工作流。  
> 你可以根据自己 AI 客户端的 Skill 格式（`.claude/skills/`、Trae 规则、Workbuddy workflow 等），将以下步骤改编为 Skill 文件。

---

## 1. 日终复盘 (Daily Review)

**目标**：物理对账 + 绩效归因 + 纪律审计 + 状态卡更新

```
Step 1   get_market_data_tool(tickers=[持仓列表])
          → 拉取持仓标的最新行情

Step 2   portfolio_tool(action="summary", investor="xxx", portfolio="core")
          → 组合概览：持仓市值、现金、盈亏

Step 3   reconcile_tool(investor="xxx", portfolio="core")
          → 物理对账：账本 vs 券商

Step 4   nav_tool(action="snapshot", investor="xxx", portfolio="core")
          → 净值快照

Step 5   performance_tool(investor="xxx", portfolio="core")
          → 绩效指标：收益率、夏普、最大回撤

Step 6   sentinel_tool(action="scan")
          → 哨兵雷达：当前市场攻防状态

Step 7   market_data_ext_tool(action="fund_flow", ticker="重点标的")
          → 资金流向（辅助判断）

Step 8   review_tool(mode="monthly", investor="xxx", period="YYYY-MM")
          → 纪律代价归因（月度复盘入口）

Step 9   evolution_tool(action="evaluate", investor="xxx", strategy="grid_value")
          → 策略进化评估

Step 10  decision_tool(action="record", ...)
          → 记录当日决策
```

---

## 2. 盘前策略 (Trading Session)

**目标**：哨兵判定 → 估值水位 → 交易约束 → 挂单计划

```
Step 1   sentinel_tool(action="scan")
          → 8 哨兵多空状态，判定当前市场阶段（防守/中性/积极）

Step 2   sentinel_tool(action="status")
          → 各哨兵 MACD/均线/RSI 细节

Step 3   valuation_tool(action="percentile")
          → 主要指数估值分位 PE-TTM

Step 4   benchmark_tool(action="list")
          → 基准指数行情

Step 5   constraint_tool(action="check", investor="xxx", action="buy", ticker="标的", amount=金额)
          → 检查买入约束是否通过

Step 6   portfolio_tool(action="summary", investor="xxx")
          → 当前持仓与可用现金
```

---

## 3. 快速巡检 (Quick Check)

**目标**：10 秒了解市场状态和持仓健康度

```
Step 1   sentinel_tool(action="scan")
          → 哨兵雷达总览

Step 2   get_market_data_tool(tickers=["510300", "159915", "512000"])
          → 核心 ETF 实时行情

Step 3   portfolio_tool(action="summary", investor="xxx")
          → 持仓概览
```

---

## 4. 个股研究 (Stock Research)

**目标**：快速了解一只非持仓标的

```
Step 1   get_market_data_tool(tickers=["000001"])
          → 实时行情

Step 2   market_data_ext_tool(action="research", ticker="000001", limit=10)
          → 最新研报

Step 3   market_data_ext_tool(action="fund_flow", ticker="000001")
          → 资金流向
```

---

## 5. 三团队联合研判 (Three-Team Research)

**目标**：ASRG 战术 + Masters 哲学 + Trading 执行

```
Step 1   get_market_data_tool(tickers=["标的"])
          → 基础行情

Step 2   orchestrator_tool(action="run_team", team="asrg", ticker="标的")
          → ASRG 战术分析

Step 3   orchestrator_tool(action="run_team", team="masters", ticker="标的")
          → Masters 哲学研判

Step 4   orchestrator_tool(action="run_team", team="trading", ticker="标的")
          → Trading 执行方案

Step 5   orchestrator_tool(action="compile", team="asrg")
          → Gavin 汇编产出最终报告
```

---

## 6. 数据源维护 (Data Source Maintenance)

**目标**：检查数据源健康状态

```
Step 1   get_market_data_tool(tickers=["000001"])
          → 测试主数据源

Step 2   sentinel_tool(action="history")
          → 哨兵历史数据

Step 3   benchmark_tool(action="list")
          → 基准指数数据
```

---

## 附录：工具速查

| 工具 | 用途 | 文档 |
|---|---|---|
| `get_market_data_tool` | 实时行情 | `obsidian/11-MCP工具清单.md` |
| `sentinel_tool` | 哨兵雷达 | 同上 |
| `portfolio_tool` | 组合管理 | 同上 |
| `reconcile_tool` | 物理对账 | 同上 |
| `review_tool` | 级联复盘 | 同上 |
| `evolution_tool` | 策略进化 | 同上 |
| 完整清单 | 28 个工具详情 | `obsidian/11-MCP工具清单.md` |
