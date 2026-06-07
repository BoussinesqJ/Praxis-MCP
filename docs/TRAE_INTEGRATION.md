# PRAXIS 接入 Trae 指南

> Trae 是字节跳动推出的 AI 编程助手，支持 MCP 协议

---

## 一、前置条件

1. 已安装 Trae
2. 已安装 PRAXIS：`pip install -e .`
3. 已设置环境变量 `PRAXIS_WORKSPACE`

---

## 二、配置步骤

### 方式一：通过 Trae 设置界面

1. 打开 Trae
2. 进入 **设置** → **MCP Servers**
3. 点击 **添加 MCP Server**
4. 填写配置：

| 字段 | 值 |
|------|-----|
| 名称 | praxis |
| 类型 | stdio |
| 命令 | praxis |
| 参数 | serve |
| 环境变量 | PRAXIS_WORKSPACE=你的实际路径 |

### 方式二：直接编辑配置文件

Trae 的 MCP 配置文件位置：

- **Windows**: `%APPDATA%\Trae\mcp_servers.json`
- **macOS**: `~/Library/Application Support/Trae/mcp_servers.json`
- **Linux**: `~/.config/Trae/mcp_servers.json`

编辑配置文件，添加：

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

## 三、设置环境变量

### Windows

```cmd
# 临时设置（当前终端）
set PRAXIS_WORKSPACE=C:\你的实际路径\Portfolio vault

# 永久设置
setx PRAXIS_WORKSPACE "C:\你的实际路径\Portfolio vault"
```

### macOS / Linux

```bash
# 临时设置
export PRAXIS_WORKSPACE="/你的实际路径/Portfolio vault"

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export PRAXIS_WORKSPACE="/你的实际路径/Portfolio vault"' >> ~/.bashrc
source ~/.bashrc
```

---

## 四、验证接入

### 1. 测试 MCP Server 启动

```bash
praxis serve
```

如果看到 `PRAXIS MCP Server started` 表示启动成功。

### 2. 在 Trae 中测试

在 Trae 对话框中输入：

```
帮我看看当前持仓状态
```

Trae 会自动调用 `get_state` 工具返回组合状态。

---

## 五、使用示例

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

## 六、常见问题

### Q1: Trae 无法找到 praxis 命令

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
cd "C:\你的实际路径\Portfolio vault"
python -m praxis.cli serve
```

---

## 七、接入检查清单

- [ ] PRAXIS 已安装
- [ ] 环境变量已设置
- [ ] Trae 已配置 MCP Server
- [ ] MCP Server 可启动
- [ ] Trae 能调用工具

---

**接入完成后，你就可以在 Trae 中直接管理投资组合了！**
