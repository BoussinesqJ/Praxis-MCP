# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.0.0] - 2026-06-16

### 分发版重构

#### Added
- **模板系统**：`tpl/` 目录含 project.md / finance_status_card.md / soul.md / long-term.md 四个示例模板，新用户 `cp tpl/*.example .` 即可开始
- **投资者示例**：`investors/example/` 含完整演示配置文件
- **完整架构文档**：`obsidian/` 13 篇设计文档 + 系统全景画布，支持 Obsidian 开箱阅读
- **环境变量路径注入**：`PRAXIS_WORKSPACE` + `PRAXIS_PROJECT_PATH` / `PRAXIS_CARD_PATH` / `PRAXIS_LONGTERM_PATH`，支持自定义文件位置

#### Changed
- **路径全解耦**：`rule_engine.py` / `portfolio_manager.py` / `check_invariants.py` 去掉所有硬编码个人路径，改为 env var 注入
- **工具脚本迁移**：`portfolio_manager.py` / `check_invariants.py` 从 `outputs/` 移至 `scripts/`
- **默认投资者 ID**：源码中 `investor="sanchisheng"` → `"demo"`
- **文档示例脱敏**：obsidian 文档中个股代码 `600995` → `000001`，投资者 ID `sanchisheng` → `demo`

#### Fixed
- **`rule_engine.py:PortfolioParser` budget 误统计为 positions_value**：预算行独立计入 budget，不影响持仓市值
- **`constraint_checker.py` 缺失北交所拦截**：新增 `is_bse` 判断，覆盖 83/87/92/43 开头代码
- **`rule_engine.py` 持仓解析全面重写**：从「持仓（防守姿态）」表解析真实持仓

#### Removed
- 所有 `sanchisheng` 个人投资者 ID 引用
- `MEMORY.md` 中个人工作区路径
- `__pycache__` 缓存文件

## [3.5.0] - 2026-06-14

### 工具整合优化

#### Added
- **8 个整合工具** (`praxis/mcp_server.py`)
  - `portfolio_tool`: 整合 4 个组合管理工具（summary/detail/state/config）
  - `trading_tool`: 整合 3 个交易工具（ledger/approve/reject/decision）
  - `market_data_ext_tool`: 整合 4 个数据源工具（fund_flow/northbound/dragon_tiger/research）
  - `review_bundle_tool`: 整合 2 个复盘工具（daily/weekly）
  - `strategy_tool`: 整合 3 个策略工具（get/list/compare）
  - `evolution_tool`: 整合 4 个进化工具（evaluate/auto/memory/adaptive）
  - `grayscale_tool`: 整合 2 个灰度工具（prepare/approve）
  - `team_tool`: 整合 3 个团队工具（config/prompt/template）

- **错误码标准化**
  - `INVALID_ACTION`: LLM 调用错误
  - `MISSING_PARAM`: 参数缺失
  - `DATA_SOURCE_ERROR`: 数据源异常
  - `TIMEOUT`: 工具调用超时

- **向后兼容**
  - 旧工具保留 1 个月，打 `[Deprecated]` 标签
  - `_TOOLS_TIER` 改为 dict 结构，支持 deprecated 标记

#### Changed
- **工具数量**: 56 → 31（减少 45%）
- **LLM Schema Token**: ~15K → ~8K（减少 47%）
- **所有 Skill 版本**: 升级到 v3.5.0

#### Fixed
- **参数分组策略**: 按 action 类型分组参数，使用 Optional 类型
- **性能监控**: Bundle 工具中添加 parallel_efficiency

---

## [3.4.0] - 2026-06-14

### Macro-Tool Bundle 效率优化

#### Added
- **健康检查器** (`praxis/health_checker.py`)
  - 启动时检测 mootdx/tencent/akshare 可用性
  - 永久跳过不可用数据源

- **5 个 Bundle 工具** (`praxis/mcp_server.py`)
  - `market_state_bundle_tool`: 市场状态（哨兵+估值+北向）
  - `daily_review_bundle_tool`: 日终复盘（7项数据并发）
  - `weekly_review_bundle_tool`: 周度复盘（7项数据并发）
  - `trading_session_bundle_tool`: 盘前策略（4项数据并发）
  - `stock_analysis_bundle_tool`: 个股分析（5项数据并发）

- **Bundle 特性**
  - 服务端内部并发拉取（asyncio.gather）
  - 客户端串行接收（防 stdio 污染）
  - 错误处理（return_exceptions=True）
  - 进度报告（progress 字段）

#### Changed
- **weekly-review 执行时间**: 60-120秒 → 5-15秒（10-20x）
- **daily-review 执行时间**: 30-60秒 → 3-8秒（10x）

---

## [3.3.0] - 2026-06-14

### MCP 稳定性优化 + Stdio 管道防污染隔离

#### Added
- **Stdio 管道防污染隔离** (`praxis/mcp_server.py`)
  - 引入 `_safe_sync_runner` + `run_in_safe_thread` 安全包装器
  - 所有第三方库调用通过 `redirect_stdout` 隔离到 stderr
  - 全局抑制 httpx/httpcore/urllib3/akshare 日志噪音

- **串行调用约束**
  - 所有 Skill 文件添加串行调用声明
  - 禁止并行工具调用

#### Fixed
- **Asyncio 事件循环阻塞**
  - 所有同步调用用 `asyncio.to_thread()` 包裹
  - 18 处调用替换为 `run_in_safe_thread`

---

## [3.2.0] - 2026-06-13

### MCP 稳定性优化

#### Added
- **Asyncio 事件循环阻塞修复**
  - 所有同步调用用 `asyncio.to_thread()` 包裹

- **串行调用约束**
  - Skill 文件中明确禁止并行工具调用

- **SSE 传输层支持**
  - 支持 SSE 模式，更稳定

---

## [3.1.0] - 2026-06-13

### 数据源架构重构 + 业务层集成

#### Added
- **全局限流器** (`praxis/core/rate_limiter.py`)
  - 令牌桶 + 随机抖动
  - 并发控制
  - 滑动窗口频率跟踪
  
- **熔断器** (`praxis/core/circuit_breaker.py`)
  - 三态状态机 (CLOSED/OPEN/HALF_OPEN)
  - 连续失败自动冷却
  - 全局注册表

- **TTL 缓存层** (`praxis/core/cache.py`)
  - LRU 淘汰策略
  - 持久化到 JSON 文件
  - 命名空间隔离

- **东财基类** (`praxis/core/em_client.py`)
  - User-Agent 伪装
  - Session 复用
  - 自动重试机制
  - 集成限流器 + TTL 缓存

- **数据源**
  - MX (API+Key) - Tier 1 绝对主力
  - mootdx (TCP) - Tier 2 极速降级
  - tencent (HTTP) - Tier 2 备用
  - 资金流向 (`providers/fund_flow_provider.py`)
  - 北向资金 (`providers/northbound_provider.py`)
  - 龙虎榜 (`providers/dragon_tiger_provider.py`)
  - 研报 (`providers/research_report_provider.py`)
  - 巨潮公告 (`providers/cninfo_provider.py`)
  - iwen财 (`providers/iwencai_provider.py`)

- **MCP 工具**
  - `fund_flow_tool` - 资金流向
  - `northbound_tool` - 北向资金
  - `dragon_tiger_tool` - 龙虎榜
  - `research_report_tool` - 研报数据

- **Skill 更新**
  - `daily-review` - 新增资金流向/北向资金/龙虎榜
  - `trading-session` - 新增龙虎榜/资金流向
  - `three-team` - 新增研报数据

#### Changed
- 数据源优先级调整为 MX → mootdx → tencent → akshare
- 配置文件升级到 v3.1

#### Fixed
- 东财 API 封禁风险 (限流器保护)
- 数据源故障自动降级 (熔断器)
- 重复请求浪费令牌 (TTL 缓存)

---

## [3.0.0] - 2026-06-10

### Skill + MCP 双引擎

#### Added
- 断点续传机制
- 模型分级 (deep/quick)
- 结构化输出 (Pydantic schema)
- Alpha 追踪
- 延迟反思
- 逻辑硬化 (规则校验下沉)
- LCD 冲突检测

---

## [2.2.1] - 2026-06-08

### 交易时钟 + 数据源硬熔断

#### Added
- 交易时钟
- 数据源硬熔断
- 缓存审计
- 东财 API 裸连

---

## [2.2.0] - 2026-06-07

### 积极型进化

#### Added
- Alpha 逻辑豁免权
- 仓位红线非线性扩张
- 积极型安全垫保护

---

## [2.1.0] - 2026-06-06

### 引力热力图 + Daily Review

#### Added
- 引力热力图
- daily-review Skill
- trading-session Skill
- Claude Code 命令

---

## [2.0.0] - 2026-06-05

### 元进化 + Three Team

#### Added
- 元进化机制
- three-team Skill
- reconcile Skill
- Git push v2.1.0

---

## [1.0.0] - 2026-06-01

### 初始版本

#### Added
- 核心规则引擎
- LCD 冲突检测
- 哨兵雷达
- MCP 服务器
- 基础 Skill 体系
