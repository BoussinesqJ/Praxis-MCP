# AGENTS.md — Praxis 投研纪律系统

> Practice, Reflection, And eXponential Improvement System
> AETF网格投研纪律系统，通过 MCP 协议为 AI Agent 提供 28 个结构化投研工具。

> 🚨 **AI 行为最高准则**：所有 AI 成员在学习新技能或查阅系统规范前，必须先掌握 [SOP_INDEX.md](SOP_INDEX.md) 的向下覆写逻辑（Tier 0 永远大于 Tier 3）。

## Project

- **Stack**: Python 3.11+ / Pydantic 2 / MCP (stdio) / httpx / pytest (asyncio_mode=auto)
- **Entry point**: `praxis/mcp_server.py` (MCP Server, stdio transport, 28 个活跃工具)
- **CLI**: `python -m praxis.cli` (15 个子命令：market / portfolio / ledger / strategy / ...)
- **Config**: `reasonix.toml` (agent), `.mcp.json` (MCP server), `project.md` (持仓真相源)
- **Version**: v4.0.0

## Commands

```bash
# 测试
pytest                          # 全量测试 (617+ 用例，tests/)
pytest -m unit                  # 单元测试
pytest -m integration           # 集成测试
pytest tests/test_rules.py      # 规则引擎测试 (17 用例)

# MCP 启动
python praxis/mcp_server.py

# CLI
python -m praxis.cli --help
```

## Architecture

```
praxis/
├── mcp_server.py      # MCP 入口：28 工具注册 + 级联复盘路由
├── tools/             # MCP 工具实现层（42 个文件，每个一个功能域）
│   ├── market.py      #   实时行情
│   ├── sentinel.py    #   哨兵雷达（MCP 工具层）
│   ├── ledger.py      #   交易账本（sync）
│   ├── review.py      #   级联复盘（monthly/quarterly/annual）
│   ├── engine.py      #   约束检查入口
│   └── ...            #   fund_flow/northbound/dragon_tiger/portfolio/strategy/evolution...
├── engine/            # 业务逻辑层（22 个模块）
│   ├── sentinel.py    #   哨兵雷达引擎（8 ETF 多空，MA20 趋势判定）
│   ├── constraint_checker.py  # 约束检查器（现金底线动态化）
│   ├── grayscale.py   #   策略灰度验证
│   ├── data/          #   数据源适配（eastmoney/akshare/baostock/mx）
│   ├── execution/     #   交易执行模型（fee/slippage/calendar）
│   └── ...            #   evolution/review_filler/backtest/config_loader/...
├── core/              # 基础设施（cache/circuit_breaker/ledger/logger/rate_limiter）
└── models/            # Pydantic 数据模型（investor/portfolio/asset/state/strategy）

praxis_sdk/            # 开发层 SDK（独立于 MCP 分发层）
├── core/rule_engine.py  # 规则引擎 + PortfolioParser
└── core/lcd_detector.py # 冲突检测

.agents/skills/        # 13 个 AI Skill 模板
├── daily-review/      #   日终复盘（10 步串行）
├── trading-session/   #   盘前策略（9 步串行）
├── weekly-review/     #   周度复盘
├── monthly-review/    #   月度复盘（cascade_review_tool）
├── quick-check/       #   秒级巡检
└── reconcile/         #   文档一致性校验

.githooks/             # Git 钩子
└── pre-commit         #   审计日志：soul.md/SOP_INDEX.md 变更时自动写 data/audit/changes.jsonl
```

## Conventions

- **串行调用铁律**：所有 MCP 工具必须严格串行调用，禁止并行工具调用（Parallel Tool Calling），否则管道死锁。
- **async/sync 混合**：`tools/fund_flow.py`, `northbound.py`, `dragon_tiger.py`, `research_report.py` 是 `async def`，调用时必须 `await`。`tools/ledger.py`, `decision.py` 是 sync，不加 `await`。
- **新闻降级链**: NewsNow API (10s) → 妙想 MX (10s) → akshare 占位。绝不返回假新闻。
- **情感策略**: 增强关键词 + 否定翻转（10 字符窗口），无 PyTorch（MCP stdio 安全铁律）。
- **安全白名单**: Rule 1（ETF 网格绝对豁免）+ Rule 7（价格到位即可买）永不废除。
- **cash_floor 动态化**: 由哨兵快照的 `position_limit_pct` 自动计算，`strategies/grid_value.yaml` 中的 `min_pct` 仅做兜底。
- **SSOT**: `project.md` 是持仓唯一真相源，`data/ledger/transactions.jsonl` 是交易账本。
- **代理穿透**: MCP 启动时 `os.environ.setdefault("NO_PROXY", "*")`。
- **审计留痕**: 修改 `soul.md` / `SOP_INDEX.md` 前必须通过 git commit 触发 `.githooks/pre-commit` 自动写 `data/audit/changes.jsonl`。

## Notes

- `praxis_sdk/` 和 `praxis/` 是两个独立代码库，中间通过 `tools/engine.py` 桥接
- MX API Key 通过环境变量 `MX_APIKEY` 注入（`.mcp.json` 中配置）
- Polymarket API 国内不可达（10s 静默丢弃）
- 哨兵重构后 8 只 ETF：510300/159915/512000/159928/512100/512480/516970/515220
