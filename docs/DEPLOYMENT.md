# PRAXIS 部署文档

## 系统要求

- Python 3.11+
- 操作系统：Windows/macOS/Linux

## 安装步骤

### 1. 克隆仓库

```bash
git clone <repository-url>
cd "Portfolio vault"
```

### 2. 安装依赖

```bash
pip install -e .
```

依赖列表：
- pydantic >= 2.0
- pyyaml >= 6.0
- httpx >= 0.27
- mcp >= 1.0
- click >= 8.0

### 3. 配置环境变量

```bash
# Windows
set PRAXIS_WORKSPACE=C:\Users\77271\Desktop\Portfolio vault

# macOS/Linux
export PRAXIS_WORKSPACE="/你的实际路径/Portfolio vault"
```

## Claude Desktop 配置

### 1. 找到配置文件

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### 2. 添加 MCP Server

在配置文件中添加：

```json
{
  "mcpServers": {
    "praxis": {
      "command": "praxis",
      "args": ["serve"],
      "env": {
        "PRAXIS_WORKSPACE": "/你的实际路径/Portfolio vault"
      }
    }
  }
}
```

### 3. 重启 Claude Desktop

保存配置后，重启 Claude Desktop 以加载新的 MCP Server。

### 4. 验证连接

在 Claude Desktop 中输入：

```
帮我看看当前持仓状态
```

如果配置正确，Claude 会调用 PRAXIS 的 MCP 工具返回组合状态。

## CLI 使用

### 启动 MCP Server

```bash
praxis serve
```

### 常用命令

```bash
# 查看帮助
praxis --help

# 读取组合配置
praxis portfolio get --investor example --portfolio demo

# 获取行情数据
praxis market quote --tickers 600995,510310

# 对账计算
praxis reconcile --investor example --portfolio demo

# 检查约束
praxis constraints --investor example --portfolio demo \
  --action buy --ticker 600995 --amount 3000

# 查看交易记录
praxis ledger list

# 查看决策记录
praxis decision list

# 计算绩效指标
praxis performance --investor example --portfolio demo

# 查看策略详情
praxis strategy get --name grid_value

# 评估进化维度
praxis evolution evaluate --strategy grid_value \
  --investor example --portfolio demo
```

## 数据目录结构

```
data/
├── ledger/                      # 交易账本（append-only）
│   └── transactions.jsonl
├── decisions/                   # 决策记录（append-only）
│   └── decision_records.jsonl
├── audit/                       # 审计日志（append-only）
│   └── README.md
├── state/                       # 状态缓存（可重建）
└── market_cache/                # 行情缓存
```

## 配置文件结构

```
investors/
└── example/
    ├── profile.yaml             # 投资者画像
    └── portfolios/
        └── demo/
            └── portfolio.yaml   # 组合配置

strategies/
└── grid_value.yaml              # 策略模板

teams/
├── base_prompts/                # 基础 prompt
└── strategy_contexts/           # 策略上下文
    └── grid_value.yaml
```

## 故障排除

### 1. MCP Server 无法启动

**症状**：Claude Desktop 无法连接到 PRAXIS

**解决方案**：
1. 检查 Python 是否正确安装
2. 检查依赖是否安装：`pip list | grep praxis`
3. 检查环境变量是否设置：`echo %PRAXIS_WORKSPACE%`
4. 手动测试：`praxis serve`

### 2. 行情数据获取失败

**症状**：`get_market_data` 返回错误

**解决方案**：
1. 检查网络连接
2. 检查腾讯财经 API 是否可访问
3. 检查标的代码是否正确

### 3. 交易记录丢失

**症状**：`get_ledger` 返回空列表

**解决方案**：
1. 检查 `data/ledger/transactions.jsonl` 文件是否存在
2. 检查文件权限
3. 从备份恢复

### 4. 约束检查失败

**症状**：`check_constraints` 返回 blocked

**解决方案**：
1. 检查标的是否在禁入板块（科创板/创业板）
2. 检查交易金额是否低于最小限额
3. 检查现金比例是否低于底线

## 备份与恢复

### 备份

```bash
# 备份交易账本
cp data/ledger/transactions.jsonl data/ledger/transactions.jsonl.backup

# 备份决策记录
cp data/decisions/decision_records.jsonl data/decisions/decision_records.jsonl.backup

# 备份配置
cp -r investors/ investors.backup/
cp -r strategies/ strategies.backup/
```

### 恢复

```bash
# 恢复交易账本
cp data/ledger/transactions.jsonl.backup data/ledger/transactions.jsonl

# 恢复决策记录
cp data/decisions/decision_records.jsonl.backup data/decisions/decision_records.jsonl

# 恢复配置
cp -r investors.backup/ investors/
cp -r strategies.backup/ strategies/
```

## 安全建议

1. **定期备份**：每天备份交易账本和决策记录
2. **权限控制**：限制对数据目录的访问权限
3. **审计日志**：定期检查审计日志，发现异常行为
4. **幂等键**：使用幂等键防止重复写入
5. **反向冲销**：错误交易使用反向冲销，不要直接修改账本
