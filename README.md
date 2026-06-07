# PRAXIS - 投研纪律系统

> **Practice, Reflection, And eXponential Improvement System**
> 可验证、可审计、可复盘、可进化的个人投研纪律系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/tests-418-brightgreen.svg)](tests/)

---

## 🎯 系统定位

**R1.0 定位**：个人 A 股 / ETF / 场外基金组合的投研纪律系统（开源版本）

**核心价值**：
- 📊 投研闭环验证（策略是否跑赢基准）
- 🔒 纪律约束执行（风控规则不可绕过）
- 📝 决策全程记录（可复盘、可追溯）
- 🧬 策略持续进化（基于绩效数据，非事后叙事）

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/Praxis.git
cd Praxis

# 安装依赖
pip install -e .
```

### 配置 AI 工具

1. 设置环境变量：
   ```bash
   # Windows
   setx PRAXIS_WORKSPACE "你的实际路径\Portfolio vault"

   # Linux/Mac
   export PRAXIS_WORKSPACE="/你的实际路径/Portfolio vault"
   ```

2. 复制配置模板：
   ```bash
   cp config/trae_config.example.json config/trae_config.json
   cp config/claude_desktop_config.example.json config/claude_desktop_config.json
   ```

3. 编辑配置文件，将 `${PRAXIS_WORKSPACE}` 替换为你的实际路径

详细接入说明：[docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md)

### CLI 使用

```bash
praxis serve          # 启动 MCP Server
praxis --help         # 查看帮助
praxis portfolio get -i example -p demo   # 读取组合
praxis market --tickers 600995,510310                  # 获取行情
praxis performance -i example -p demo     # 绩效指标
praxis validate                                        # 验证配置
```

---

## 📊 系统能力

### MCP 工具（63 个）

| 类别 | 工具数 | 说明 |
|:----:|:------:|------|
| Workspace 发现 | 1 | 零参数自动发现投资者/组合/状态 |
| 查询工具 | 20 | 组合/行情/状态/绩效查询 |
| 写入工具 | 8 | 交易/决策/进化（需审批） |
| 投资者管理 | 3 | 创建投资者/组合/一键初始化 |
| 审批流程 | 3 | 审批/拒绝/待审批列表 |
| 数据清理 | 2 | 物理删除/按标签清空 |
| 聚合概览 | 1 | 一次调用返回完整组合视图 |
| 团队工具 | 5 | 三大团队 Prompt 管理 |
| 模板工具 | 4 | 输出模板管理（需审批） |
| 复盘工具 | 3 | 复盘自动回填/汇总/校准 |
| 交易摩擦 | 4 | 费用/滑点/交易时间/确认日 |
| 数据质量 | 3 | 行情质量检查/清洗/报告 |
| Prompt版本 | 6 | 安全检查/版本管理/回滚/差异 |

### MCP 资源（1 个）

| URI | 说明 |
|:---|:---|
| `praxis://workspace/discovery` | Workspace 元数据，连接握手时自动暴露 |

### CLI 命令（17 个命令组）

```bash
praxis serve          # 启动 MCP Server
praxis portfolio      # 组合管理
praxis asset          # 标的详情
praxis market         # 行情数据
praxis reconcile      # 对账计算
praxis constraints    # 约束检查
praxis state          # 状态查询
praxis ledger         # 交易账本
praxis decision       # 决策记录
praxis performance    # 绩效指标
praxis strategy       # 策略管理
praxis evolution      # 进化引擎
praxis benchmark      # 基准指数
praxis nav            # 净值追踪
praxis ai-tracking    # AI 建议命中率
praxis backtest       # 策略回测
praxis validate       # 配置验证
```

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    接入层 (Access Layer)                   │
│  MCP Server (Reasonix/Trae/Claude) + CLI (开发调试)     │
│  + MCP Resource (praxis://workspace/discovery)           │
├─────────────────────────────────────────────────────────┤
│                    决策层 (Decision Layer)                 │
│  Decision Record → 人工审批 → 执行 → 复盘                │
├─────────────────────────────────────────────────────────┤
│                    研究层 (Research Layer)                 │
│  AI 团队（ASRG / 大师圆桌 / 交易团队）                    │
├─────────────────────────────────────────────────────────┤
│                    规则层 (Rule Layer)                     │
│  风控约束 · 交易纪律 · 策略参数（6 级分级）               │
├─────────────────────────────────────────────────────────┤
│                    数据层 (Data Layer)                     │
│  多源行情（AKShare/Baostock/东方财富/腾讯）              │
│  场外基金净值（AKShare/东方财富）                         │
├─────────────────────────────────────────────────────────┤
│                    事实层 (Fact Layer)                     │
│  配置：YAML │ 账本：JSONL │ 状态：缓存 │ 审计：日志       │
└─────────────────────────────────────────────────────────┘
```

---

## 🤖 三大 AI 团队

| 团队 | 主理人 | 成员数 | 专业领域 |
|:----:|:------:|:------:|---------|
| **ASRG** | Gavin | 8 | 宏观策略→产业链→个股研究 |
| **大师圆桌** | Arthur | 21 | 13 位投资大师 + 6 位分析师 |
| **交易团队** | 协调器 | 12 | 多空辩论→网格优化→风险评估 |

---

## 📁 项目结构

```
Portfolio vault/
├── praxis/                          # 源代码
│   ├── mcp_server.py                # MCP Server 入口（63 工具 + 1 资源）
│   ├── cli.py                       # CLI 入口（17 个命令组）
│   ├── core/                        # 核心模块（模型/接口/账本/日志）
│   ├── engine/                      # 引擎层（对账/绩效/进化/回测/数据源）
│   │   └── data/                    # 多源数据源（AKShare/Baostock/东方财富/腾讯）
│   └── tools/                       # MCP 工具实现（含 workspace 发现）
├── data/                            # 数据目录
│   ├── ledger/                      # 交易账本（append-only）
│   ├── decisions/                   # 决策记录
│   ├── audit/                       # 审计日志
│   └── nav/                         # 净值记录
├── investors/                       # 投资者配置
├── strategies/                      # 策略模板
├── teams/                           # AI 团队配置
│   ├── base/                        # 基础 Prompt（安全/角色/工具策略）
│   ├── base_prompts/                # 三大团队 Prompt
│   ├── investor/                    # 投资者画像 Prompt
│   ├── strategy/                    # 策略上下文
│   ├── adaptive/                    # 自适应规则
│   └── output_templates/            # 输出模板
├── tests/                           # 测试套件（418 个测试）
├── docs/                            # 文档
├── config/                          # 接入配置模板
├── providers/                       # 数据源插件目录
└── README.md                        # 本文件
```

---

## 🧪 测试

```bash
python -m pytest tests/ -v    # 运行所有测试
python -m pytest tests/test_workspace.py -v  # 运行特定测试
```

**测试结果**：418 passed

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [docs/API.md](docs/API.md) | API 文档 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 部署文档 |
| [docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) | 接入指南 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 开发路线图 |

---

## 🔧 接入指南

PRAXIS 支持 MCP 协议，可接入以下工具：

| 工具 | 配置文件 |
|------|---------|
| Reasonix | `config/reasonix_config.example.toml` |
| Trae | `config/trae_config.example.json` |
| Claude Desktop | `config/claude_desktop_config.example.json` |
| Cherry Studio | 同 Claude Desktop 配置 |
| OpenCode | `config/opencode_config.example.json` |
| Tare | `config/tare_config.example.json` |

详细接入说明：[docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md)

---

## 🛡️ 安全机制

- ✅ 交易账本 append-only（不可覆盖）
- ✅ 幂等键防重复写入
- ✅ 原子写入保护
- ✅ Prompt 安全扫描（15 种危险模式）
- ✅ 规则系统 6 级分级
- ✅ 审计日志完整记录
- ✅ 推送前安全审查（强制）
- ✅ 路径遍历防护（validate_id + safe_path）
- ✅ 物理删除需 confirm 确认

---

## 📈 项目状态

| 指标 | 数值 |
|:----:|:----:|
| MCP 工具 | 63 |
| MCP 资源 | 1 |
| CLI 命令组 | 17 |
| 测试用例 | 418 |
| 数据源 | 4（AKShare/Baostock/东方财富/腾讯）+ 用户插件 |
| AI 团队 | 3 |
| 输出模板 | 5 |
| 版本 | r1.0.0 |

> 📋 开发路线图见 [docs/ROADMAP.md](docs/ROADMAP.md)

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🔗 相关链接

- [GitHub 仓库](https://github.com/your-username/Praxis.git)
