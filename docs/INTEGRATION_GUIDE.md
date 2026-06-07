# PRAXIS 接入指南

> 本文档说明如何将 PRAXIS 接入各种 AI 工具

---

## 一、接入方式概览

| 工具 | 接入方式 | 状态 | 配置文件 |
|------|:--------:|:----:|---------|
| Claude Desktop | MCP Server | ✅ | `config/claude_desktop_config.example.json` |
| Cherry Studio | MCP Server | ✅ | 同 Claude Desktop 配置 |
| Trae | MCP Server | ✅ | `config/trae_config.example.json` |
| OpenCode | MCP Server | ✅ | `config/opencode_config.example.json` |
| Tare | MCP Server | ✅ | `config/tare_config.example.json` |
| WorkBuddy | MCP Server | ✅ | `config/workbuddy_config.example.json` |
| 牛马AI | MCP Server | ✅ | `config/niuma_ai_config.example.json` |
| 任意 AI Agent | CLI | ✅ | 通过命令行调用 |

---

## 二、通用配置步骤

### 2.1 安装 PRAXIS

```bash
cd "你的路径/Portfolio vault"
pip install -e .
```

### 2.2 设置环境变量

**Windows**：
```cmd
# 临时设置（当前终端）
set PRAXIS_WORKSPACE=C:\你的实际路径\Portfolio vault

# 永久设置
setx PRAXIS_WORKSPACE "C:\你的实际路径\Portfolio vault"
```

**macOS / Linux**：
```bash
# 临时设置
export PRAXIS_WORKSPACE="/你的实际路径/Portfolio vault"

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export PRAXIS_WORKSPACE="/你的实际路径/Portfolio vault"' >> ~/.bashrc
source ~/.bashrc
```

### 2.3 复制配置模板

```bash
# 选择你使用的工具对应的配置文件
cp config/claude_desktop_config.example.json config/claude_desktop_config.json
cp config/trae_config.example.json config/trae_config.json
cp config/opencode_config.example.json config/opencode_config.json
cp config/tare_config.example.json config/tare_config.json
cp config/workbuddy_config.example.json config/workbuddy_config.json
cp config/niuma_ai_config.example.json config/niuma_ai_config.json
```

### 2.4 编辑配置文件

将 `${PRAXIS_WORKSPACE}` 替换为你的实际路径。

---

## 三、各工具详细配置

### 3.1 Claude Desktop

**配置文件位置**：
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**配置内容**：
```json
{
  "mcpServers": {
    "praxis": {
      "command": "praxis",
      "args": ["serve"],
      "env": {
        "PRAXIS_WORKSPACE": "你的实际路径"
      }
    }
  }
}
```

---

### 3.2 Cherry Studio

**配置方式**：
1. 打开 Cherry Studio
2. 进入设置 → MCP Server
3. 添加新的 MCP Server：
   - 名称：praxis
   - 命令：`praxis serve`
   - 环境变量：`PRAXIS_WORKSPACE=你的实际路径`

---

### 3.3 Trae

**配置文件位置**：
- **Windows**: `%APPDATA%\Trae\mcp_servers.json`
- **macOS**: `~/Library/Application Support/Trae/mcp_servers.json`
- **Linux**: `~/.config/Trae/mcp_servers.json`

**配置内容**：
```json
{
  "mcpServers": {
    "praxis": {
      "command": "praxis",
      "args": ["serve"],
      "env": {
        "PRAXIS_WORKSPACE": "你的实际路径"
      }
    }
  }
}
```

**详细指南**：[TRAE_INTEGRATION.md](TRAE_INTEGRATION.md)

---

### 3.4 OpenCode

**配置内容**：
```json
{
  "mcpServers": {
    "praxis": {
      "command": "praxis",
      "args": ["serve"],
      "env": {
        "PRAXIS_WORKSPACE": "你的实际路径"
      }
    }
  }
}
```

---

### 3.5 Tare

**配置内容**：
```json
{
  "mcpServers": {
    "praxis": {
      "command": "praxis",
      "args": ["serve"],
      "env": {
        "PRAXIS_WORKSPACE": "你的实际路径"
      }
    }
  }
}
```

---

### 3.6 WorkBuddy

**配置内容**：
```json
{
  "mcpServers": {
    "praxis": {
      "command": "praxis",
      "args": ["serve"],
      "env": {
        "PRAXIS_WORKSPACE": "你的实际路径"
      }
    }
  }
}
```

---

### 3.7 牛马AI

**配置内容**：
```json
{
  "mcpServers": {
    "praxis": {
      "command": "praxis",
      "args": ["serve"],
      "env": {
        "PRAXIS_WORKSPACE": "你的实际路径"
      }
    }
  }
}
```

---

## 四、CLI 接入（任意 AI Agent）

如果 AI Agent 不支持 MCP 协议，可以通过 CLI 调用：

### 命令格式

```bash
# 设置环境变量
export PRAXIS_WORKSPACE="你的实际路径"

# 调用工具
praxis portfolio get --investor example --portfolio demo
praxis market quote --tickers 600995,510310
praxis reconcile --investor example --portfolio demo
praxis ledger list
praxis performance --investor example --portfolio demo
praxis benchmark list
praxis ai-tracking
```

### 在 Python 中调用

```python
import subprocess

def call_praxis(command: str) -> str:
    """调用 PRAXIS CLI"""
    result = subprocess.run(
        ["praxis"] + command.split(),
        capture_output=True,
        text=True
    )
    return result.stdout

# 使用示例
output = call_praxis("portfolio get --investor example --portfolio demo")
```

---

## 五、验证接入

### 5.1 测试 MCP Server

```bash
# 启动 MCP Server
praxis serve

# 在另一个终端测试
praxis portfolio get --investor example --portfolio demo
```

### 5.2 测试 CLI

```bash
# 运行所有测试
python -m pytest tests/ -v

# 测试特定功能
praxis benchmark list
praxis ai-tracking
```

### 5.3 在 AI 工具中测试

在 AI Agent 中输入：

```
帮我看看当前持仓状态
```

如果配置正确，AI Agent 会调用 `get_state` 工具返回组合状态。

---

## 六、使用示例

### 查询类

```
帮我看看当前持仓状态
查询一下南网储能的实时行情
列出所有交易记录
计算一下我的投资绩效
```

### 操作类

```
南网储能跌到13.38了，帮我买入200股
帮我记录今天的净值：总资产72315，持仓5277，现金67037
评估一下网格价值策略的进化维度
```

### 分析类

```
对比一下沪深300基准，我的策略跑赢了吗？
统计一下AI团队的建议命中率
```

---

## 七、常见问题

### Q1: 无法找到 praxis 命令

**解决方案**：
```bash
# 检查 praxis 是否已安装
pip show praxis

# 如果未安装，执行
pip install -e .
```

### Q2: 环境变量未生效

**解决方案**：
```bash
# 检查环境变量
echo %PRAXIS_WORKSPACE%  # Windows
echo $PRAXIS_WORKSPACE   # macOS/Linux

# 如果为空，重新设置
set PRAXIS_WORKSPACE=你的路径  # Windows
export PRAXIS_WORKSPACE="你的路径"  # macOS/Linux
```

### Q3: MCP Server 启动失败

**解决方案**：
```bash
# 手动测试启动
cd "你的路径/Portfolio vault"
python -m praxis.cli serve
```

---

## 八、接入检查清单

- [ ] PRAXIS 已安装：`pip install -e .`
- [ ] 环境变量已设置：`PRAXIS_WORKSPACE`
- [ ] 配置文件已复制并编辑
- [ ] MCP Server 可启动：`praxis serve`
- [ ] CLI 可调用：`praxis --help`
- [ ] 测试通过：`python -m pytest tests/`
- [ ] AI Agent 已配置 MCP Server
- [ ] 工具调用正常

---

**PRAXIS 已准备好接入任何支持 MCP 协议的 AI 工具！**
