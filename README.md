# PRAXIS - 投研纪律系统

> **Practice, Reflection, And eXponential Improvement System**
> 可验证、可审计、可复盘、可进化的个人投研纪律系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io/)

---

## 🎯 系统定位

**r1.1 定位**：个人 A 股 / ETF / 场外基金组合的投研纪律系统（自进化架构 + 金融技能集成）

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
git clone https://github.com/BoussinesqJ/Praxis-MCP.git
cd Praxis-MCP

# 安装依赖
pip install -e .

# 安装可选数据源
pip install -e ".[all]"    # AKShare + Baostock
```

### 配置 AI 工具

1. 设置环境变量：
   ```bash
   # Windows
   setx PRAXIS_WORKSPACE "你的实际路径\Praxis-MCP"

   # Linux/Mac
   export PRAXIS_WORKSPACE="/你的实际路径/Praxis-MCP"
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
praxis market --tickers 600995,510310     # 获取行情
praxis performance -i example -p demo     # 绩效指标
praxis validate                            # 验证配置
```

---

## 📊 系统能力

### MCP 工具（83 个）

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
| **自适应规则** | **4** | **规则学习/审批/激活** |
| **进化记忆** | **3** | **记忆归档/时间线/回溯查询** |
| **多 Agent 协作** | **3** | **Agent 决策/共识检查/排名** |
| **财经新闻** | **4** | **实时新闻/热点报告/预测市场** |
| **情感分析** | **2** | **FinBERT 情感评分/批量分析** |
| **估值/哨兵** | **6** | **估值分位/哨兵雷达/Rule 23/26** |

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

## 🧬 自进化架构（r1.0）+ 金融技能集成（r1.1）

Praxis 通过事件驱动实现自进化闭环：

```
交易执行 → auto_evolve → 评估 4 维度
                        → 备份策略
                        → 落盘报告
                        → 归档进化记忆
                        → 学习自适应规则
                        → 人工审批
                        → 执行 + 沉淀
```

- **自适应规则引擎**：从交易/NAV 历史中学习模式，自动生成规则草案
- **长期记忆**：进化记忆归档、时间线生成、类似情况回溯查询
- **多 Agent 协作**：Agent 决策标准化、共识检查、准确率排名
- **事件驱动触发**：交易完成后自动触发进化评估 + 规则学习

---

## 📰 金融技能集成（r1.1）

集成 [AlphaEar](https://github.com/RKiding/AlphaEar) 金融分析技能：

| 能力 | 工具 | 数据源 |
|:---|:---|:---|
| 实时新闻 | `get_finance_news_tool` | 财联社/华尔街见闻/雪球等 10+ 信源 |
| 热点报告 | `get_unified_trends_tool` | 微博/知乎/华尔街见闻聚合 |
| 预测市场 | `get_polymarket_tool` | Polymarket |
| 情感分析 | `analyze_sentiment_tool` | FinBERT / LLM |
| 股票基本面 | `alphaear_stock_provider` | AKShare + Yahoo Finance |

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
Praxis-MCP/
├── praxis/                          # 源代码
│   ├── mcp_server.py                # MCP Server 入口（83 工具 + 1 资源）
│   ├── cli.py                       # CLI 入口（17 个命令组）
│   ├── core/                        # 核心模块（模型/接口/账本/日志）
│   ├── engine/                      # 引擎层（对账/绩效/进化/回测/数据源）
│   │   ├── data/                    # 多源数据源（AKShare/Baostock/东方财富/腾讯）
│   │   ├── adaptive_rules.py        # 自适应规则引擎
│   │   ├── consensus.py             # 多 Agent 共识引擎
│   │   ├── sentinel.py              # 哨兵雷达引擎
│   │   └── evolution_memory.py      # 进化记忆存储
│   └── tools/                       # MCP 工具实现
│       ├── sentinel.py              # 哨兵雷达工具
│       ├── valuation.py             # 估值分位工具
│       ├── sentiment.py             # 情感分析工具
│       └── news.py                  # 新闻聚合工具
├── data/                            # 数据目录（运行时生成）
│   ├── ledger/                      # 交易账本（append-only）
│   ├── decisions/                   # 决策记录
│   ├── audit/                       # 审计日志
│   └── nav/                         # 净值记录
├── investors/                       # 投资者配置
│   └── example/                     # 示例投资者
├── strategies/                      # 策略模板
├── teams/                           # AI 团队配置
│   ├── base/                        # 基础 Prompt（安全/角色/工具策略）
│   ├── base_prompts/                # 三大团队 Prompt
│   ├── investor/                    # 投资者画像 Prompt
│   ├── strategy/                    # 策略上下文
│   ├── adaptive/                    # 自适应规则
│   └── output_templates/            # 输出模板
├── providers/                       # 数据源插件
│   ├── _example_provider.py         # 插件开发示例
│   └── alphaear_stock_provider.py   # AlphaEar 股票数据源
├── tests/                           # 测试套件
├── docs/                            # 文档
│   └── dev/                         # 设计文档
├── config/                          # 接入配置模板
├── obsidian/                        # Obsidian 知识库
├── scripts/                         # 工具脚本
├── CHANGELOG.md                     # 更新日志
├── CONTRIBUTING.md                  # 贡献指南
├── LICENSE                          # MIT 许可证
└── pyproject.toml                   # 项目配置
```

---

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_workspace.py -v

# 运行快速冒烟测试
python -m pytest tests/test_isolation_p0.py tests/test_constraints_p0.py tests/test_performance_p0.py -v
```

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [docs/API.md](docs/API.md) | API 文档 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 部署文档 |
| [docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) | 接入指南 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 开发路线图 |
| [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) | 安全审计 |
| [docs/dev/](docs/dev/) | 设计文档 |

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
| MCP 工具 | 83 |
| MCP 资源 | 1 |
| CLI 命令组 | 17 |
| 数据源 | 5（AKShare/Baostock/东方财富/腾讯/AlphaEar）+ 用户插件 |
| AI 团队 | 3 |
| 输出模板 | 5 |
| 版本 | r1.1.0 |

> 📋 开发路线图见 [docs/ROADMAP.md](docs/ROADMAP.md)

---

## 🤝 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🔗 相关链接

- [GitHub 仓库](https://github.com/BoussinesqJ/Praxis-MCP.git)
- [MCP 协议](https://modelcontextprotocol.io/)
- [AlphaEar 金融技能](https://github.com/RKiding/AlphaEar)
