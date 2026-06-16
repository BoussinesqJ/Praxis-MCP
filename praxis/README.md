# Praxis — AI 投研纪律系统

> 基于 MCP (Model Context Protocol) 的智能投研工具集，为 AI Agent 提供结构化的投资决策支持。

## 概述

Praxis 是一套面向 A 股 ETF 投资的 AI 投研纪律系统，通过 MCP 协议为 AI Agent（Reasonix、Antigravity、Claude Code 等）提供 **30+ 个结构化工具**，覆盖从行情获取、情感分析到交易约束检查的完整投研链路。

核心设计理念：**AI 做决策，Praxis 管纪律**。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                   MCP Server (stdio)                 │
│                  praxis/mcp_server.py                │
├─────────┬──────────────┬──────────────┬──────────────┤
│  tools/ │   engine/    │    core/     │   prompts/   │
│ 30+ MCP │  业务逻辑引擎  │  基础设施     │  团队 Prompt  │
│  工具实现 │              │              │              │
├─────────┴──────────────┴──────────────┴──────────────┤
│                    数据层 / 存储层                      │
│          JSON Ledger · SQLite · JSONL Logs            │
└─────────────────────────────────────────────────────┘
```

### 目录结构

```
praxis/
├── mcp_server.py          # MCP Server 入口（FastMCP，stdio 传输）
├── cli.py                 # CLI 命令行工具
├── health_checker.py      # 系统健康检查
│
├── core/                  # 基础设施层
│   ├── cache.py           #   通用缓存
│   ├── circuit_breaker.py #   熔断器
│   ├── ledger.py          #   交易账本
│   ├── logger.py          #   结构化日志
│   ├── rate_limiter.py    #   限流器
│   ├── state_builder.py   #   状态重建
│   ├── validation.py      #   数据校验
│   └── models/            #   数据模型（asset, decision, rule, ...）
│
├── engine/                # 业务逻辑层
│   ├── sentinel.py        #   哨兵雷达（8 ETF 多空监控）
│   ├── valuation.py       #   估值分位（PE/PB 历史百分位）
│   ├── performance.py     #   绩效计算（收益率/夏普/回撤）
│   ├── constraint_checker.py # 交易约束检查
│   ├── reconciliation.py  #   对账引擎
│   ├── evolution.py       #   策略进化
│   ├── backtest.py        #   回测引擎
│   ├── orchestrator.py    #   三团队分析编排器
│   ├── ai_tracker.py      #   AI 建议命中追踪
│   ├── data/              #   数据源适配层
│   │   ├── eastmoney.py   #     东方财富 API
│   │   ├── akshare_provider.py # akshare 适配
│   │   ├── baostock_provider.py # baostock 适配
│   │   └── realtime.py   #     实时行情
│   └── execution/         #   交易执行模型
│       ├── fee_model.py   #     手续费模型
│       ├── slippage_model.py #  滑点模型
│       └── trading_calendar.py # 交易日历
│
├── tools/                 # MCP 工具实现层（30+ 工具）
│   ├── news.py            #   新闻聚合（AlphaEar NewsNow API）
│   ├── news_alphaear.py   #   AlphaEar NewsNow 对接层
│   ├── news_mx.py         #   妙想 API 新闻
│   ├── sentiment.py       #   情感分析（增强关键词 + 否定翻转）
│   ├── sentiment_alphaear.py # AlphaEar 情感引擎
│   ├── sentiment_keyword.py  # 基础关键词匹配
│   ├── sentinel.py        #   哨兵工具
│   ├── portfolio.py       #   组合管理
│   ├── trading_tool.py    #   交易管理
│   ├── performance.py     #   绩效工具
│   └── ...                #   更多工具
│
├── prompts/               # 三团队 Prompt 模板
│   ├── asrg/              #   ASRG 战术研究团队（4 人）
│   ├── masters/           #   Masters 哲学团队（4 人）
│   └── trading/           #   Trading 执行团队（5 人）
│
└── models/                # 模型/配置版本管理
    └── version.txt
```

## MCP 工具清单

### 核心工具（Core）

| 工具 | 说明 |
|:---|:---|
| `discover_workspace_tool` | 探查 workspace 全景 |
| `get_market_data_tool` | 实时行情 |
| `sentinel_tool` | 哨兵雷达（8 ETF 多空状态） |
| `valuation_tool` | 指数估值分位 |
| `news_tool` | 新闻聚合（10+ 信源） |
| `sentiment_tool` | 情感分析（关键词 + 否定翻转） |
| `portfolio_tool` | 组合管理 |
| `trading_tool` | 交易管理（账本/审批/决策） |
| `get_performance_tool` | 绩效计算 |
| `reconcile_tool` | 对账 |
| `check_constraints_tool` | 交易约束检查 |
| `nav_tool` | 净值追踪 |
| `benchmark_tool` | 基准指数 |
| `review_tool` | 决策复盘 |
| `agent_tracking_tool` | AI 建议命中率 |
| `trading_friction_tool` | 交易摩擦成本 |
| `market_data_ext_tool` | 扩展行情（资金流向/北向/龙虎榜/研报） |

### Bundle 工具（一次调用，并发执行）

| 工具 | 说明 |
|:---|:---|
| `market_state_bundle_tool` | ~~哨兵 + 估值 + 北向~~ [DEPRECATED] |
| `daily_review_bundle_tool` | ~~7 路并发日终复盘~~ [DEPRECATED] |
| `weekly_review_bundle_tool` | ~~周度复盘~~ [DEPRECATED] |
| `trading_session_bundle_tool` | ~~盘前策略~~ [DEPRECATED] |
| `stock_analysis_bundle_tool` | ~~个股深度分析~~ [DEPRECATED] |

### 进阶工具（Advanced）

| 工具 | 说明 |
|:---|:---|
| `strategy_tool` | 策略管理 |
| `evolution_tool` | 策略进化（元进化 + 自适应规则） |
| `grayscale_tool` | 灰度验证 |
| `run_backtest_tool` | 回测 |
| `orchestrator_tool` | 三团队分析编排 |
| `update_portfolio_tool` | 修改组合配置 |

### 管理工具（Admin）

| 工具 | 说明 |
|:---|:---|
| `investor_tool` | 投资者初始化 |
| `team_tool` | 团队/Prompt/模板管理 |
| `data_quality_tool` | 数据质量管理 |
| `get_ai_tracking_tool` | AI 追踪管理 |

## 快速开始

### 前置条件

- Python 3.10+
- 支持 MCP 协议的 AI Agent（Reasonix / Antigravity / Claude Code / OpenCode 等）

### 安装

```bash
git clone https://github.com/your-username/Praxis.git
cd Praxis
pip install -r requirements.txt
```

### MCP 配置

在项目根目录创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "praxis": {
      "command": "python",
      "args": ["praxis/mcp_server.py"],
      "env": {
        "PRAXIS_WORKSPACE": "/path/to/your/workspace",
        "PRAXIS_TOOLS_TIER": "core",
        "PYTHONPATH": "/path/to/Praxis"
      }
    }
  }
}
```

### 首次使用

在 AI Agent 中调用：
```
discover_workspace_tool()
```
获取可用的 investor/portfolio ID，然后即可使用全部工具。

## 新闻数据源

Praxis v3.5 集成 AlphaEar NewsNow API，支持 10+ 信源实时新闻聚合：

| 类别 | 信源 |
|:---|:---|
| 金融 | 财联社、华尔街见闻、雪球 |
| 综合 | 微博热搜、知乎热榜、百度热搜、今日头条、抖音、澎湃 |
| 科技 | 36氪、IT之家、V2EX、掘金、Hacker News |

- **超时保护**: 10 秒硬超时，超时静默丢弃
- **缓存**: 5 分钟内存缓存，带 stale cache 降级
- **优先级链**: NewsNow → 妙想 API → akshare 占位

## 情感分析

Praxis v3.5 采用增强关键词 + 否定翻转策略：

| 特性 | 说明 |
|:---|:---|
| 强关键词（权重×2） | 涨停/暴跌/腰斩/立案 等 30+ 词 |
| 中等关键词（权重×1） | 上涨/下跌/降息/加息 等 30+ 词 |
| 否定翻转 | "并未"/"没有"/"不是" 等 11 个否定词，10 字符窗口 |
| 强信号保护 | 关键词强信号优先于模型判定 |
| 命中率 | 93%（14 case 金融文本测试集） |
| 响应速度 | <0.1s/条 |

## 三团队协作框架

Praxis 内置三团队投研分析框架，通过 `orchestrator_tool` 编排：

| 团队 | 定位 | 成员 |
|:---|:---|:---|
| **ASRG** | 战术研究 | Ethan(宏观) · James(行业) · Kevin(量化) · Frank(消息面) |
| **Masters** | 哲学研判 | 巴菲特 · 格雷厄姆 · 芒格 · 风控经理 |
| **Trading** | 执行裁决 | 牛研究员 · 熊研究员 · 研究主管 · 风控 · 交易员 |

## 投研纪律体系

- **Rule 7**: 网格内价格到位即可买（最高优先级）
- **Rule 23**: 情绪起爆器验证（连续 3 日 ≥5/8 哨兵多头）
- **哨兵雷达**: 8 个 ETF 哨兵实时监控多空状态
- **交易约束**: 单标的仓位上限、单日买入上限、总仓位控制
- **三位一体隔离**: long-term.md 不写具体数字

## 版本历史

| 版本 | 日期 | 说明 |
|:---|:---|:---|
| v3.6 | 2026-06-15 | Bundle 并发架构清除 + 单工具链式 SOP + 级联复盘 + 状态卡联动 |
| v3.5 | 2026-06-11 ~ 06-15 | AlphaEar 集成 + 级联复盘体系 + 三团队编排器 |
| v3.0 | 2026-06 | 元进化 + 三团队 + reconcile + CLI |
| v2.0 | 2026-05 | 引力热力图 + daily-review + trading-session |
| v1.0 | 2026-05 | 目录结构 + 规则引擎 + LCD + 回归测试 |

## License

Private — 仅限授权访问
