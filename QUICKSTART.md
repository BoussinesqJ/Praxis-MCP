# Praxis 快速上手 — 5 分钟从零到第一个工具

> 适用版本：v4.0.0+  
> 预期时间：5 分钟  
> 前置条件：Python 3.11+、pip

---

## 1. 安装

```bash
# 进入项目目录
cd praxis

# 安装核心依赖
pip install -e .

# （可选）安装扩展数据源
pip install -e ".[all]"    # akshare + baostock
# 或单独安装
pip install -e ".[akshare]"
pip install -e ".[baostock]"
```

验证安装：

```bash
praxis --version
# 输出: Praxis v4.0.0

praxis --help
# 输出: 所有可用子命令列表
```

---

## 2. 创建配置文件

从模板创建你的个人配置文件：

```bash
# 持仓/网格配置（SSOT）
cp tpl/project.md.example project.md

# 资产状态卡
cp tpl/finance_status_card.md.example finance_status_card.md

# 投资信条
cp tpl/soul.md.example soul.md

# 历史归因（需 memory/ 目录）
mkdir -p memory
cp tpl/long-term.md.example memory/long-term.md

# 投资者画像
cp -r tpl/investors/demo/* investors/example/
```

然后用编辑器打开上述文件，将 `{{PLACEHOLDER}}` 替换为你的真实数据。

---

## 3. 配置 MCP 客户端

Praxis 通过 MCP 协议与 AI 客户端通信。参考示例配置：

| 客户端 | 配置文件 |
|---|---|
| Claude Desktop | `config/claude_desktop_config.example.json` |
| OpenCode | `config/opencode_config.example.json` |
| Trae | `config/trae_config.example.json` |
| Workbuddy | `config/workbuddy_config.example.json` |

配置要点：

```json
{
  "mcpServers": {
    "praxis": {
      "command": "python",
      "args": ["praxis/mcp_server.py"],
      "env": {
        "PRAXIS_WORKSPACE": ".",
        "PRAXIS_TOOLS_TIER": "core",
        "MX_APIKEY": "${MX_APIKEY}"   // 可选：妙想数据源 API Key
      }
    }
  }
}
```

> 无需 MCP 客户端？也可直接使用 CLI 工具。

---

## 4. 第一个工具调用

### CLI 模式

```bash
# 获取实时行情
praxis market quote --tickers 000001,600000

# 查看组合状态
praxis portfolio get --investor example --portfolio core

# 运行约束检查
praxis constraints --investor example --portfolio core --action buy --ticker 000001 --amount 3000

# 资产对账
praxis reconcile --investor example --portfolio core
```

### MCP 模式（通过 AI 客户端）

启动 MCP 服务器后，向 AI 发送以下指令：

```
请获取 000001（平安银行）的实时行情数据。
```

AI 会自动调用 `get_market_data_tool` 返回结果。

### 完整场景示例

```bash
# 日终复盘全流程
praxis market quote --tickers 000001,510050    # 1. 拉行情
praxis portfolio get --investor example         # 2. 看持仓
praxis reconcile --investor example             # 3. 物理对账
```

---

## 5. 状态卡联动机制

Praxis 的核心工作流围绕三张状态卡：

```
project.md  ←── SSOT（唯一真相源：持仓/网格/止损/规则）
    ↑                    ↓
    |     finance_status_card.md（展示层：净值/资产配比）
    |                    ↓
    +── long-term.md（历史归因：版本变更记录）
```

**读写原则**：
1. **先展示后写入** — AI 展示 diff，主理人确认后才写入
2. **SSOT 唯一** — 持仓数据以 `project.md` 为准
3. **5 日滚动** — `long-term.md` 超 5 日记录自动清除

---

## 6. 下一步

| 你想做什么 | 看什么 |
|---|---|
| 了解系统全景 | `obsidian/00-系统全景.md`（推荐 Obsidian 打开） |
| 查所有 MCP 工具 | `obsidian/11-MCP工具清单.md` |
| 查看 SOP 分级 | `SOP_INDEX.md` |
| 查看架构/命令/约定 | `AGENTS.md` |
| 查看变更历史 | `CHANGELOG.md` |
| 了解 AI 团队协作 | `obsidian/02-AI投研团队.md` |

---

## 附录：目录结构

```
praxis/
├── praxis/              # 核心引擎 + MCP 服务器 + 30+ 工具
├── praxis_sdk/          # 开发层 SDK
├── providers/           # 数据源插件
├── config/              # 客户端配置示例
├── scripts/             # 工具脚本
├── strategies/          # 策略模板
├── obsidian/            # 系统架构文档（支持 Obsidian）
├── tpl/                 # 首次运行模板
├── tests/               # 测试套件
├── pyproject.toml       # Python 项目配置
└── .mcp.json            # MCP 服务器配置
```
