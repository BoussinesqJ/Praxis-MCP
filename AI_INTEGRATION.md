# AI Agent 集成指南 — 将 Praxis MCP 接入你的 AI 客户端

> Praxis 通过 MCP（Model Context Protocol）与 AI 客户端通信。  
> 配置完成后，你的 AI 就能直接调用 Praxis 的 28 个投研工具。

---

## 快速开始

所有 AI 客户端共用同一个 MCP 服务器配置，核心参数：

```json
{
  "command": "python",
  "args": ["praxis/mcp_server.py"],
  "env": {
    "PRAXIS_WORKSPACE": ".",
    "PRAXIS_TOOLS_TIER": "core",
    "MX_APIKEY": "${MX_APIKEY}"
  }
}
```

---

## 各客户端配置

### 1. Claude Desktop

**配置文件**：项目根目录 `.mcp.json`（已提供，按需修改）

参考模板：`config/claude_desktop_config.example.json`

### 2. Claude Code (CLI)

自动读取项目根目录的 `.mcp.json`，无需额外配置。

验证连接：

```bash
claude
# 然后输入：/tools
# 应能看到 praxis 开头的 28 个工具列表
```

### 3. Trae

**配置文件**：`config/trae_config.example.json`

### 4. Workbuddy

**配置文件**：`config/workbuddy_config.example.json`

### 5. OpenCode

**配置文件**：`config/opencode_config.example.json`

### 6. Codex (formerly Cursor)

Codex 支持 MCP 协议，在设置中添加：

- **名称**：Praxis
- **命令**：`python praxis/mcp_server.py`
- **工作目录**：你的 Praxis 项目路径
- **环境变量**：`PRAXIS_WORKSPACE=.`, `PRAXIS_TOOLS_TIER=core`

### 7. Niuma AI / TARE

参考 `config/niuma_ai_config.example.json` / `config/tare_config.example.json`

---

## 环境变量说明

| 变量 | 必填 | 说明 |
|---|---|---|
| `PRAXIS_WORKSPACE` | 是 | 工作区路径，通常设为 `.` |
| `PRAXIS_TOOLS_TIER` | 是 | 工具层级，`core` 加载全部活跃工具 |
| `PYTHONPATH` | 推荐 | 设为 `.`，确保模块可导入 |
| `MX_APIKEY` | 否 | 妙想 API Key，不设置则自动降级到腾讯/东财 |

---

## 验证连接

配置完成后，向 AI 发送以下指令测试：

```
请列出你可以使用的所有工具。
```

```
请获取 000001（平安银行）的实时行情数据。
```

---

## 常见问题

**Q: MCP 服务器启动失败，提示 ModuleNotFoundError？**
A: 请确认已在项目目录下执行 `pip install -e .`。

**Q: MX_APIKEY 怎么获取？**
A: 可选配置。不配置时自动使用腾讯/东方财富直连，核心功能不受影响。

**Q: 不同 AI 客户端可以同时使用吗？**
A: 可以。每个客户端独立启动 MCP 进程，互不干扰。
