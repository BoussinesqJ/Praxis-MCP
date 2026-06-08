# PRAXIS API 文档

## MCP 工具详细说明

### 1. get_portfolio

**描述**：读取投资组合配置

**参数**：
- `investor` (string, 必需): 投资者ID（如 example）
- `portfolio` (string, 必需): 组合ID（如 demo）

**返回**：
```json
{
  "success": true,
  "data": {
    "strategy_type": "grid_value",
    "version": "v9.0",
    "assets": [...],
    "sentinels": {...}
  }
}
```

### 2. get_asset_detail

**描述**：读取单个标的详情（含网格/止损/止盈）

**参数**：
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID
- `ticker` (string, 必需): 标的代码（如 600995）

**返回**：
```json
{
  "success": true,
  "data": {
    "ticker": "600995",
    "name": "南网储能",
    "grid": [...],
    "stop_loss": {...},
    "take_profit": [...]
  }
}
```

### 3. get_market_data

**描述**：获取实时行情数据

**参数**：
- `tickers` (list[string], 必需): 标的代码列表

**返回**：
```json
{
  "success": true,
  "data": {
    "600995": {
      "price": 13.50,
      "change": 0.15,
      "change_pct": 1.12,
      "volume": 1234567
    }
  }
}
```

### 4. reconcile

**描述**：对账计算（dry-run 模式）

**参数**：
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID
- `nav` (float, 可选): 场外基金净值

**返回**：
```json
{
  "success": true,
  "data": {
    "state": {...},
    "formatted": "=== 组合状态快照 ===\n..."
  }
}
```

### 5. check_constraints

**描述**：检查交易约束

**参数**：
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID
- `action` (string, 必需): 操作类型（buy/sell/subscribe/redeem）
- `ticker` (string, 必需): 标的代码
- `amount` (float, 可选): 交易金额

**返回**：
```json
{
  "success": true,
  "data": {
    "checks": [
      {
        "rule": "access_rules.blacklist_market",
        "level": "advisory",
        "message": "标的 600995 不在禁入板块",
        "passed": true
      }
    ],
    "all_passed": true,
    "blocked": []
  }
}
```

### 6. get_state

**描述**：从 ledger 重建组合状态

**参数**：
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID

**返回**：
```json
{
  "success": true,
  "data": {
    "state": {...},
    "formatted": "=== 组合状态（从 Ledger 重建）===\n...",
    "validation_issues": []
  }
}
```

### 7. get_ledger

**描述**：查询交易记录

**参数**：
- `ticker` (string, 可选): 标的代码（过滤）
- `limit` (int, 可选): 返回数量上限，默认 100

**返回**：
```json
{
  "success": true,
  "data": {
    "total": 5,
    "transactions": [...]
  }
}
```

### 8. add_transaction

**描述**：添加交易记录（需审批）

**参数**：
- `ticker` (string, 必需): 标的代码
- `action` (string, 必需): 操作类型
- `quantity` (float, 必需): 数量
- `price` (float, 必需): 价格
- `fee` (float, 可选): 手续费
- `decision_id` (string, 可选): 关联的决策ID
- `idempotency_key` (string, 可选): 幂等键
- `auto_approve` (bool, 可选): 是否自动审批

**返回**：
```json
{
  "success": true,
  "data": {
    "status": "confirmed",
    "tx_id": "tx-20260601-001",
    "message": "交易已确认: buy 600995 100@13.5"
  }
}
```

### 9. reverse_transaction

**描述**：反向冲销交易

**参数**：
- `tx_id` (string, 必需): 要冲销的交易ID
- `reason` (string, 必需): 冲销原因

**返回**：
```json
{
  "success": true,
  "data": {
    "original_tx_id": "tx-20260601-001",
    "correction_tx_id": "tx-20260601-002",
    "message": "已冲销 tx-20260601-001，冲销记录: tx-20260601-002"
  }
}
```

### 10. get_decision_record

**描述**：获取决策记录

**参数**：
- `decision_id` (string, 必需): 决策ID

**返回**：
```json
{
  "success": true,
  "data": {
    "decision_id": "dc-20260601-001",
    "ticker": "600995",
    "action": "buy",
    "confidence": 0.75,
    "reasoning": "网格触发",
    "status": "executed"
  }
}
```

### 11. list_decisions

**描述**：列出决策记录

**参数**：
- `status` (string, 可选): 状态过滤
- `limit` (int, 可选): 返回数量

**返回**：
```json
{
  "success": true,
  "data": {
    "total": 5,
    "decisions": [...]
  }
}
```

### 12. create_decision

**描述**：创建决策记录

**参数**：
- `ticker` (string, 必需): 标的代码
- `action` (string, 必需): 操作类型
- `confidence` (float, 必需): 信心度（0-1）
- `reasoning` (string, 必需): 决策理由

**返回**：
```json
{
  "success": true,
  "data": {
    "decision_id": "dc-20260601-001",
    "status": "pending_approval",
    "message": "决策已创建: buy 600995，信心=0.75"
  }
}
```

### 13. get_performance

**描述**：计算绩效指标

**参数**：
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID

**返回**：
```json
{
  "success": true,
  "data": {
    "metrics": {
      "total_return": -0.0423,
      "annualized_return": -0.8609,
      "win_rate": 1.0,
      "total_fee": 15.0
    },
    "formatted": "=== 绩效指标 ===\n..."
  }
}
```

### 14. get_strategy

**描述**：获取策略详情

**参数**：
- `strategy_name` (string, 必需): 策略名称

**返回**：
```json
{
  "success": true,
  "data": {
    "name": "网格价值策略",
    "description": "...",
    "rules": [...],
    "ai_teams": {...},
    "evolution_dimensions": [...]
  }
}
```

### 15. list_strategies

**描述**：列出所有策略模板

**返回**：
```json
{
  "success": true,
  "data": {
    "strategies": ["grid_value"]
  }
}
```

### 16. update_portfolio

**描述**：修改组合配置（需审批）

**参数**：
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID
- `field` (string, 必需): 字段名
- `value` (string, 必需): 新值

**返回**：
```json
{
  "success": true,
  "data": {
    "status": "pending_approval",
    "field": "version",
    "old_value": "v9.0",
    "new_value": "v10.0",
    "message": "修改预览: version = v10.0，需人工审批后写入"
  }
}
```

### 17. evaluate_evolution

**描述**：评估进化维度

**参数**：
- `strategy_name` (string, 必需): 策略名称
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID

**返回**：
```json
{
  "success": true,
  "data": {
    "dimensions": [...],
    "overall_health": "critical",
    "evolution_suggestions": [...],
    "formatted": "=== 进化维度评估 ===\n..."
  }
}
```

### 18. evolve_strategy

**描述**：进化策略（需审批）

**参数**：
- `strategy_name` (string, 必需): 策略名称
- `investor` (string, 必需): 投资者ID
- `portfolio` (string, 必需): 组合ID

**返回**：
```json
{
  "success": true,
  "data": {
    "status": "pending_approval",
    "backup_path": "strategies/grid_value.20260601_120000.bak",
    "message": "进化评估完成，策略文件已备份。需人工审批后执行修改。",
    "evaluation": {...}
  }
}
```

## 错误响应

所有工具在失败时返回：

```json
{
  "success": false,
  "error": "错误描述"
}
```

## 错误类型

- `PraxisError`: 基础异常
- `ConfigError`: 配置错误
- `DataError`: 数据错误（行情/API）
- `ReconcileError`: 对账错误
- `LedgerError`: 账本错误
- `ConstraintViolation`: 约束违反
