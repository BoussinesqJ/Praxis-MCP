# CLI 命令手册

> 17 个命令组，供开发/调试使用

---

## 命令列表

### 组合管理
```bash
praxis portfolio get --investor example --portfolio demo
```

### 标的详情
```bash
praxis asset --investor example --portfolio demo --ticker STOCK_A
```

### 行情数据
```bash
praxis market quote --tickers STOCK_A,ETF_300
```

### 对账计算
```bash
praxis reconcile --investor example --portfolio demo
```

### 约束检查
```bash
praxis constraints --investor example --portfolio demo \
  --action buy --ticker STOCK_A --amount 3000
```

### 状态查询
```bash
praxis state --investor example --portfolio demo
```

### 交易账本
```bash
praxis ledger list
praxis ledger add --ticker STOCK_A --action buy --quantity 100 --price 13.50
praxis ledger reverse --tx-id tx-20260601-001 --reason "价格错误"
```

### 决策记录
```bash
praxis decision list
praxis decision get --decision-id dc-20260601-001
praxis decision create --ticker STOCK_A --action buy --confidence 0.75 --reasoning "网格触发"
```

### 绩效指标
```bash
praxis performance --investor example --portfolio demo
```

### 策略管理
```bash
praxis strategy list
praxis strategy get --name grid_value
```

### 进化引擎
```bash
praxis evolution evaluate --strategy grid_value --investor example --portfolio demo
praxis evolution evolve --strategy grid_value --investor example --portfolio demo
```

### 基准指数
```bash
praxis benchmark list
praxis benchmark get --code 000300 --days 60
```

### 净值追踪
```bash
praxis nav snapshot --investor example --portfolio demo
praxis nav history --investor example --portfolio demo --days 30
```

### AI 追踪
```bash
praxis ai-tracking --team asrg
```

### 回测
```bash
praxis backtest --strategy grid_value --investor example --portfolio demo --days 90
praxis backtest compare --strategy-a grid_value --strategy-b momentum --days 90
```

### 复盘
```bash
praxis review fill
praxis review list
praxis review calibration --team asrg
```

### 配置验证
```bash
praxis validate
```

---

## 相关链接

- [[MCP工具清单]] — MCP 对应工具
- [[API文档]] — 详细接口说明

---

#CLI #命令行 #开发调试
