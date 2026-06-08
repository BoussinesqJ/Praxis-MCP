# PRAXIS 开发内容整理

> 最后更新：2026-06-04
> 版本：V2.1 Phase 6 完成

---

## 一、项目概览

**PRAXIS** — Practice, Reflection, And eXponential Improvement System

一个可验证、可审计、可复盘、可进化的个人投研纪律系统。

### 核心定位

- **V1 定位**：个人 A 股 / ETF / 场外基金组合的投研纪律系统
- **投资者**：示例投资者，7 万，C3-C4
- **策略**：网格价值策略 v1.0
- **市场**：A 股 / ETF / 场外基金，CNY 计价

---

## 二、代码统计

| 类别 | 文件数 | 说明 |
|:----:|:------:|------|
| 源代码 | 42 | praxis/ 目录下所有 .py 文件 |
| 测试 | 13 | tests/ 目录下所有 .py 文件 |
| 配置 | 4 | YAML 配置文件 |
| 数据 | 2 | JSONL 数据文件 |
| 文档 | 10+ | Markdown 文档 |
| **总计** | **71+** | — |

---

## 三、源代码结构

### 3.1 核心模块 (praxis/core/)

```
praxis/core/
├── __init__.py
├── interfaces.py              # 8 个抽象基类接口
├── ledger.py                  # 交易账本（append-only）
├── state_builder.py           # 状态重建器
└── models/                    # 11 个 Pydantic 模型
    ├── __init__.py
    ├── asset.py               # 资产类型/分类枚举
    ├── audit.py               # 审计事件模型
    ├── decision.py            # 决策记录模型
    ├── error.py               # 6 个错误类型
    ├── investor.py            # 投资者画像模型
    ├── portfolio.py           # 投资组合模型
    ├── prompt_change.py       # Prompt 变更模型
    ├── rule.py                # 规则 Schema + 预定义规则
    ├── state.py               # 组合状态 + 绩效指标
    ├── strategy.py            # 策略模板模型
    └── transaction.py         # 交易记录模型
```

### 3.2 引擎层 (praxis/engine/)

```
praxis/engine/
├── __init__.py
├── config_loader.py           # YAML 配置加载器
├── reconciliation.py          # 对账引擎（dry-run/write）
├── constraint_checker.py      # 约束检查器（5 项约束）
├── decision_recorder.py       # 决策记录器（append-only）
├── performance.py             # 增强绩效计算器
├── evolution.py               # 进化引擎
├── prompt_composer.py         # Prompt 注入器（四层结构）
├── prompt_scanner.py          # Prompt 安全扫描器（15 种危险模式）
├── prompt_change_recorder.py  # Prompt 变更记录器
├── ai_tracker.py              # AI 建议命中率统计
├── nav_tracker.py             # 日频净值追踪器
├── version_compare.py         # 策略版本对比
├── review_filler.py           # 复盘自动回填器
├── data/                      # 数据层
│   ├── realtime.py            # 腾讯财经实时行情
│   ├── benchmark.py           # 基准指数数据源
│   └── provider.py            # 统一数据源调度（三级容错）
└── execution/                 # 交易摩擦
    ├── fee_model.py           # 费用模型（A股/ETF/场外基金）
    ├── slippage_model.py      # 滑点模型
    └── trading_calendar.py    # A 股交易日历
```

### 3.3 MCP 工具 (praxis/tools/)

```
praxis/tools/
├── __init__.py
├── portfolio.py               # get_portfolio, get_asset_detail
├── market.py                  # get_market_data
├── engine.py                  # reconcile, check_constraints
├── state.py                   # get_state
├── ledger.py                  # get_ledger, add_transaction, reverse_transaction
├── decision.py                # get_decision_record, list_decisions, create_decision
├── performance.py             # get_performance
├── strategy.py                # get_strategy, list_strategies, update_portfolio
├── evolution.py               # evaluate_evolution, evolve_strategy
├── benchmark.py               # get_benchmark_data, list_benchmarks
├── nav.py                     # record_nav, get_nav_snapshot, get_nav_history
└── ai_tracking.py             # get_ai_tracking
```

### 3.4 入口文件

```
praxis/
├── __init__.py
├── mcp_server.py              # MCP Server 入口（53 个工具）
└── cli.py                     # CLI 入口（17 个命令组）
```

---

## 四、MCP 工具清单（53 个）

### 4.1 只读工具（20 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| get_portfolio | 读取组合配置 | 自动 |
| get_asset_detail | 读取标的详情 | 自动 |
| get_market_data | 获取行情数据 | 自动 |
| check_constraints | 检查约束 | 自动 |
| reconcile | 对账（dry-run） | 自动 |
| get_state | 从 ledger 重建状态 | 自动 |
| get_ledger | 查询交易记录 | 自动 |
| get_decision_record | 获取决策记录 | 自动 |
| list_decisions | 列出决策记录 | 自动 |
| get_performance | 计算绩效指标 | 自动 |
| get_strategy | 获取策略详情 | 自动 |
| list_strategies | 列出策略模板 | 自动 |
| evaluate_evolution | 评估进化维度 | 自动 |
| get_benchmark_data | 获取基准指数 | 自动 |
| list_benchmarks | 列出基准指数 | 自动 |
| get_nav_snapshot | 获取净值快照 | 自动 |
| get_nav_history | 获取净值历史 | 自动 |
| get_ai_tracking | AI 建议命中率 | 自动 |

### 4.2 写入工具（8 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| add_transaction | 添加交易记录 | 需审批 |
| reverse_transaction | 反向冲销交易 | 需审批 |
| create_decision | 创建决策记录 | 需审批 |
| update_portfolio | 修改组合配置 | 需审批 |
| record_nav | 记录当日净值 | 需审批 |
| evolve_strategy | 进化策略 | 需审批 |

---

## 五、CLI 命令清单（17 个命令组）

| 命令 | 描述 |
|------|------|
| praxis portfolio get | 读取组合配置 |
| praxis asset | 读取标的详情 |
| praxis market quote | 获取行情数据 |
| praxis reconcile | 对账计算 |
| praxis constraints | 检查约束 |
| praxis state | 从 ledger 重建状态 |
| praxis ledger list/add/reverse | 交易账本管理 |
| praxis decision get/list/create | 决策记录管理 |
| praxis performance | 计算绩效指标 |
| praxis strategy get/list | 策略管理 |
| praxis evolution evaluate/evolve | 进化引擎 |
| praxis benchmark list/get | 基准指数 |
| praxis nav snapshot/history | 净值追踪 |
| praxis ai-tracking | AI 建议命中率 |

---

## 六、Pydantic 模型清单（11 个）

| 模型 | 文件 | 说明 |
|------|------|------|
| InvestorProfile | investor.py | 投资者画像 |
| Portfolio | portfolio.py | 投资组合 |
| AssetType/Category | asset.py | 资产枚举 |
| StrategyTemplate | strategy.py | 策略模板 |
| Transaction | transaction.py | 交易记录 |
| DecisionRecord | decision.py | 决策记录 |
| PortfolioState | state.py | 组合状态 |
| PerformanceMetrics | state.py | 绩效指标 |
| AuditEvent | audit.py | 审计事件 |
| PromptChange | prompt_change.py | Prompt 变更 |
| RuleDefinition | rule.py | 规则定义 |

---

## 七、抽象基类接口（8 个）

| 接口 | 文件 | 方法数 |
|------|------|:------:|
| DataProvider | interfaces.py | 3 |
| ConfigLoader | interfaces.py | 4 |
| Ledger | interfaces.py | 4 |
| StateBuilder | interfaces.py | 2 |
| ConstraintChecker | interfaces.py | 1 |
| DecisionRecorder | interfaces.py | 5 |
| PerformanceCalculator | interfaces.py | 2 |
| AuditLogger | interfaces.py | 2 |

---

## 八、数据存储

### 8.1 数据边界

| 数据类型 | 存储格式 | 特性 | 文件位置 |
|---------|---------|------|---------|
| 配置 | YAML | 可读写 | investors/, strategies/ |
| 账本 | JSONL | append-only | data/ledger/ |
| 状态 | YAML | 可重建缓存 | data/state/ |
| 审计 | JSONL | append-only | data/audit/ |
| 决策 | JSONL | append-only | data/decisions/ |

### 8.2 数据文件

| 文件 | 格式 | 说明 |
|------|:----:|------|
| data/ledger/transactions.jsonl | JSONL | 交易账本（5 条样例） |
| data/decisions/decision_records.jsonl | JSONL | 决策记录（5 条样例） |
| data/config/benchmarks.yaml | YAML | 基准指数配置 |

---

## 九、测试覆盖

### 9.1 测试文件

| 文件 | 测试数 | 覆盖模块 |
|------|:------:|---------|
| test_models.py | 15 | Pydantic Schema |
| test_ledger.py | 13 | 交易账本 |
| test_constraints.py | 10 | 约束检查器 |
| test_config.py | 14 | 配置加载器 |
| test_state_builder.py | 7 | 状态重建器 |
| test_performance.py | 5 | 绩效计算器 |
| test_decision.py | 10 | 决策记录器 |
| test_evolution.py | 6 | 进化引擎 |
| test_cli.py | 11 | CLI 端到端 |
| test_errors.py | 8 | 错误路径 |
| test_rules.py | 15 | 规则系统 |
| test_friction.py | 9 | 交易摩擦 |
| test_data_quality.py | 6 | 数据质量 |
| test_prompt_versioning.py | 8 | Prompt版本 |
| **总计** | **329** | — |

### 9.2 测试结果

```
329 passed in 65.04s
```

---

## 十、安全机制

### 10.1 写操作保护

- ✅ 幂等键防重复
- ✅ 原子写入
- ✅ 审计日志
- ✅ 反向冲销（不用覆盖）

### 10.2 Prompt 安全

- ✅ 四层结构（base/strategy/investor/adaptive）
- ✅ 15 种危险模式检测
- ✅ 变更审批流程
- ✅ 审计记录

### 10.3 规则系统

- ✅ 6 级规则分级
- ✅ 规则 Schema 定义
- ✅ 规则测试用例

---

## 十一、建议落实情况

| 优先级 | 建议 | 落实状态 |
|:------:|---------|:--------:|
| P0 | V1 收窄定位 | ✅ |
| P0 | SSOT 边界 | ✅ |
| P0 | MCP + CLI 双入口 | ✅ |
| P0 | AI 写权限分级 | ✅ |
| P0 | Decision Record | ✅ |
| P0 | 回测路径 | ✅ |
| P0 | 文档矛盾 | ✅ |
| P1 | Data Provider Adapter | ✅ |
| P1 | Prompt Sandbox 安全 | ✅ |
| P1 | 规则分级 + 测试 | ✅ |
| P1 | 交易摩擦建模 | ✅ |
| P1 | 多 Agent 评价 | ✅ |

---

## 十二、文档清单

| 文档 | 位置 | 说明 |
|------|------|------|
| README.md | 根目录 | 项目介绍 |
| docs/API.md | docs/ | API 文档 |
| docs/DEPLOYMENT.md | docs/ | 部署文档 |
| docs/SECURITY_AUDIT.md | docs/ | 安全审计 |
| docs/PHASE6_PROGRESS.md | docs/ | Phase 6 进度 |
| obsidian/00-系统全景.md | obsidian/ | MOC 总导航 |
| obsidian/04-12*.md | obsidian/ | 知识图谱笔记 |
| obsidian/系统架构-完整版.canvas | obsidian/ | 可视化架构图 |

---

## 十三、配置文件清单

| 文件 | 位置 | 说明 |
|------|------|------|
| investors/example/profile.yaml | investors/ | 投资者画像 |
| investors/example/portfolios/demo/portfolio.yaml | investors/ | 组合配置 |
| strategies/grid_value.yaml | strategies/ | 策略模板 |
| data/config/benchmarks.yaml | data/config/ | 基准指数配置 |
| teams/base/system_role.md | teams/ | 系统角色 |
| teams/base/safety_guards.md | teams/ | 安全守则 |
| teams/base/tool_policy.md | teams/ | 工具权限 |
| teams/strategy/grid_value.md | teams/ | 策略 Prompt |
| teams/investor/example.md | teams/ | 投资者 Prompt |
| teams/adaptive/learned_rules.md | teams/ | 自适应规则 |

---

## 十四、下一步建议

### 短期（1-2 周）

1. **接入真实数据**
   - 迁移 project.md 中的历史交易
   - 对账验证新旧系统 diff=0
   - 验证行情数据准确性

2. **Claude Desktop 集成**
   - 配置 MCP Server
   - 测试所有工具调用
   - 端到端场景测试

### 中期（1-2 月）

3. **完善复盘机制**
   - 实现 5d/20d/60d 自动回填
   - 接入历史行情数据
   - 计算实际收益率

4. **绩效验证**
   - 计算完整绩效指标
   - 基准指数对比
   - AI 建议命中率统计

### 长期（3-6 月）

5. **策略进化**
   - 基于绩效数据优化策略
   - 网格间距调整
   - 止损线优化

---

**PRAXIS V2.1 开发完成，共 71+ 文件，329 个测试，53 个 MCP 工具，17 个 CLI 命令组。**
