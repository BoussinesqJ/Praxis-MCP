# PRAXIS 工具权限策略

> 此文件定义各工具的权限级别和使用规则
> **安全级别：不可自动修改**

## 权限级别

| 级别 | 说明 | 示例 |
|------|------|------|
| AUTO | 自动执行，无需审批 | get_portfolio, get_market_data |
| APPROVE | 需要人工审批 | add_transaction, update_portfolio |
| ADMIN | 管理员操作 | evolve_strategy |

## 工具权限表

### 只读工具（AUTO）
- get_portfolio
- get_asset_detail
- get_market_data
- check_constraints
- reconcile (dry-run)
- get_state
- get_ledger
- get_decision_record
- list_decisions
- get_performance
- get_strategy
- list_strategies
- evaluate_evolution
- get_benchmark_data
- list_benchmarks
- get_nav_snapshot
- get_nav_history
- get_ai_tracking

### 写入工具（APPROVE）
- add_transaction
- reverse_transaction
- create_decision
- update_portfolio
- record_nav

### 管理工具（ADMIN）
- evolve_strategy

## 使用规则

1. 只读工具可以直接调用
2. 写入工具必须返回 pending_approval 状态
3. 管理工具需要额外确认
4. 所有工具调用都记录审计日志
