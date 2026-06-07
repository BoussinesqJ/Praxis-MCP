# MCP 工具清单

> 53 个 MCP 工具，支持多种 AI 工具接入

---

## 支持的 AI 工具

| 工具 | 接入方式 | 配置文件 |
|------|:--------:|---------|
| Claude Desktop | MCP Server | `config/claude_desktop_config.example.json` |
| Cherry Studio | MCP Server | 同 Claude Desktop |
| Trae | MCP Server | `config/trae_config.example.json` |
| OpenCode | MCP Server | `config/opencode_config.example.json` |
| Tare | MCP Server | `config/tare_config.example.json` |
| WorkBuddy | MCP Server | `config/workbuddy_config.example.json` |
| 牛马AI | MCP Server | `config/niuma_ai_config.example.json` |

---

## 工具分类总览

| 类别 | 工具数 | 说明 |
|:----:|:------:|------|
| 查询工具 | 20 | 组合/行情/状态/绩效查询 |
| 写入工具 | 8 | 交易/决策/进化（需审批） |
| 团队工具 | 5 | 三大团队 Prompt 管理 |
| 模板工具 | 4 | 输出模板管理（需审批） |
| 复盘工具 | 3 | 复盘自动回填/汇总/校准 |
| 交易摩擦 | 4 | 费用/滑点/交易时间/确认日 |
| 数据质量 | 3 | 行情质量检查/清洗/报告 |
| Prompt版本 | 6 | 安全检查/版本管理/回滚/差异 |

---

## 查询工具（20 个）

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
| list_prompt_versions | 列出Prompt版本 | 自动 |
| get_prompt_version | 获取Prompt版本 | 自动 |

---

## 写入工具（8 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| add_transaction | 添加交易记录 | 需审批 |
| reverse_transaction | 反向冲销交易 | 需审批 |
| approve_transaction | 审批交易 | 需审批 |
| create_decision | 创建决策记录 | 需审批 |
| update_portfolio | 修改组合配置 | 需审批 |
| record_nav | 记录当日净值 | 需审批 |
| evolve_strategy | 进化策略 | 需审批 |
| create_prompt_version | 创建Prompt版本 | 需审批 |

---

## 团队工具（5 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| list_teams | 列出AI团队 | 自动 |
| get_team_prompt | 获取团队Prompt | 自动 |
| compose_team_prompt | 组合团队Prompt | 自动 |
| list_output_templates | 列出输出模板 | 自动 |
| get_output_template | 获取输出模板 | 自动 |

---

## 模板工具（4 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| update_output_template | 更新输出模板 | 需审批 |
| approve_output_template_update | 审批模板更新 | 需审批 |
| create_output_template | 创建输出模板 | 需审批 |
| rollback_prompt | 回滚Prompt | 需审批 |

---

## 复盘工具（3 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| fill_reviews | 自动回填复盘 | 自动 |
| get_review_summary | 获取复盘汇总 | 自动 |
| get_confidence_calibration | 信心度校准 | 自动 |

---

## 交易摩擦工具（4 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| calculate_fee | 计算交易费用 | 自动 |
| calculate_slippage | 计算滑点 | 自动 |
| check_trading_time | 检查交易时间 | 自动 |
| get_confirm_date | 获取确认日期 | 自动 |

---

## 数据质量工具（3 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| check_quote_quality | 检查行情数据质量 | 自动 |
| clean_quote_data | 清洗行情数据 | 自动 |
| get_quality_report | 获取质量报告 | 自动 |

---

## Prompt版本工具（6 个）

| 工具 | 描述 | 权限 |
|------|------|:----:|
| check_prompt_safety | 检查Prompt安全性 | 自动 |
| get_version_diff | 获取版本差异 | 自动 |
| create_prompt_version | 创建Prompt版本 | 需审批 |
| rollback_prompt | 回滚Prompt | 需审批 |
| list_prompt_versions | 列出Prompt版本 | 自动 |
| get_prompt_version | 获取Prompt版本 | 自动 |

---

## 使用示例

```
用户: 帮我看看当前持仓状态

Agent: [调用 get_state(investor="example", portfolio="demo")]
       当前持仓：总资产 72,315 元，现金 92.7%...

用户: 南网储能跌到13.38了，帮我买入200股

Agent: [调用 add_transaction(...)] → 返回 pending_approval
       交易已记录为待审批状态。是否批准？

用户: 批准

Agent: [调用 approve_transaction(tx_id="tx-...")]
       交易已批准并写入账本。

用户: 计算一下买入200股南网储能的交易费用

Agent: [调用 calculate_fee(ticker="600995", asset_type="stock", action="buy", quantity=200, price=13.38)]
       交易费用：佣金 1.34 元，印花税 0 元，过户费 0.01 元，总计 1.35 元
```

---

## 相关链接

- [[CLI命令手册]] — CLI 对应命令
- [[API文档]] — 详细接口说明
- [[写操作安全]] — 写操作保护机制

---

#MCP工具 #接口 #Claude Desktop #Trae #OpenCode #Tare #WorkBuddy #牛马AI
