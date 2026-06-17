# PRAXIS 投研纪律系统 — 工具使用指南
> 本 skill 是 PRAXIS 插件的配套说明，文档化所有 MCP 工具的使用方式、参数含义和常见工作流。
## 概述
PRAXIS 提供 31 个 MCP 工具（v3.5 整合后），覆盖以下功能域：
| 功能域 | 工具数 | 用途 |
|:---|:---:|:---|
| 发现与组合 | 3 | 探查 workspace、读写投资组合（整合 4 → 1） |
| 行情数据 | 2 | 实时行情 + 扩展行情（整合 4 → 1） |
| 状态与绩效 | 3 | 重建组合状态、计算绩效 |
| 交易管理 | 1 | 交易账本/审批/决策（整合 3 → 1） |
| 净值追踪 | 1 | 查询净值快照与历史 |
| 哨兵雷达 | 1 | 查询多头/空头哨兵 |
| 估值分析 | 1 | 指数 PE/PB 分位查询 |
| 情感分析 | 1 | 增强关键词 + 否定翻转（v4.0 升级） |
| 新闻情报 | 1 | NewsNow API 10+ 信源实时聚合（v4.0 升级） |
| 基准指数 | 1 | 获取基准指数数据 |
| AI 追踪 | 1 | 查看 AI 建议命中率 |
| 复盘 | 1 | 决策复盘分析 |
| 交易摩擦 | 1 | 交易摩擦分析 |
| 对账 | 1 | 组合对账 |
| 约束检查 | 1 | 检查交易约束 |
| 策略管理 | 1 | 列出/获取/对比策略（整合 3 → 1） |
| 进化引擎 | 1 | 评估进化、自进化、记忆管理（整合 4 → 1） |
| 灰度发布 | 1 | 准备和审批策略变更（整合 2 → 1） |
| 回测 | 1 | 运行策略回测 |
| 团队管理 | 1 | 团队配置/Prompt/模板（整合 3 → 1） |

## 首次使用
先调用 `discover_workspace_tool()` 获取可用的 investor/portfolio ID。

## 工具参考
### 发现与配置
- `discover_workspace_tool(无参数)` - 探查 workspace
- `portfolio_tool(action, investor, portfolio, ticker)` - 组合管理
  - `action`: summary / detail / state / config
- `update_portfolio_tool(investor, portfolio, field, value)` - 修改组合

### 行情
- `get_market_data_tool(tickers)` - 实时行情，例: `["510050","000001"]`
- `market_data_ext_tool(action, ticker, days, limit, rating)` - 扩展行情
  - `action`: fund_flow / northbound / dragon_tiger / research

### 新闻情报（v4.0 AlphaEar 升级）
- `news_tool(action, sources, count, limit)` - 财经新闻聚合
  - `action`: finance / trends / polymarket / list_sources
  - 数据源: NewsNow API（cls/华尔街见闻/雪球/微博/知乎/百度等 10+ 信源）
  - 超时保护: 10s，超时静默丢弃，不阻塞后续调用
  - 5 分钟内存缓存

### 情感分析（v4.0 增强关键词升级）
- `sentiment_tool(action, text, texts)` - 金融文本情感分析
  - `action`: analyze / batch
  - 策略: 关键词强信号优先 → 否定词翻转（10 字符窗口）→ 中等关键词评分
  - 支持否定词: "并未"、"没有"、"不是"、"不会"等
  - 实测命中率: 93%，响应 <0.1s

### 级联复盘（cascade_review_tool）
- `cascade_review_tool(mode, investor, portfolio, period)` - 级联复盘路由。⚠️ daily/weekly 模式已废弃，请用单工具串行
  - `mode`: monthly / quarterly / annual
  - `period`: YYYY-MM (月度) / YYYY-Qx (季度) / YYYY (年度)
  - monthly: 纪律代价报告 + 原始 JSON 统计 + 绩效 + 净值
  - quarterly: 3 个月聚合 + 进化评估 + 参数修改建议
  - annual: 12 个月 + 铁律审计 (Rule 1+7 白名单) + 重塑建议

### 对账与约束
- `reconcile_tool(investor, portfolio, nav)` - 对账计算
- `check_constraints_tool(investor, portfolio, action, ticker, amount)` - 约束检查

### 策略与进化
- `strategy_tool(action, strategy_name, strategy_a, strategy_b)` - 策略管理
  - `action`: get / list / compare
- `evolution_tool(action, investor, portfolio, strategy_name)` - 进化管理
  - `action`: evaluate / auto / memory / adaptive
- `grayscale_tool(action, strategy_name, change_description)` - 灰度验证
  - `action`: prepare / approve
- `run_backtest_tool(strategy_name, investor, portfolio, days)` - 回测

### AI 追踪
- `get_ai_tracking_tool(team)` - 建议命中率，按团队筛选

## AlphaEar Skills（已安装）
位于 `.agents/skills/`，供 Agent 理解数据源能力：
- `alphaear-news` — NewsNow + Polymarket 新闻聚合
- `alphaear-sentiment` — 增强关键词情感分析

## 红线提醒
- Protocol 3：持仓/规则变更需用户确认
- 三位一体隔离：long-term.md 不写具体数字
- Rule 7：网格内价格到位即可买
*** End of File
