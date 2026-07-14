# PRAXIS Agent

> AI 驱动的投研纪律系统 — 把交易决策从"主观判断"变成"可回放、可审计、可约束"的工作流。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io/)
[![Pydantic](https://img.shields.io/badge/pydantic-v2-red.svg)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

PRAXIS Agent 是一个**纪律优先**的投研辅助框架。它通过多智能体协作 + 三态 Guardrail 状态机 + 完整审计日志，把"为什么买/为什么卖/为什么没买"全部落到可追溯的记录上。

---

## 核心特性

| 能力 | 说明 |
|------|------|
| **多智能体协作** | 5 个独立 Agent（Market / Risk / Decision / Review / Admin），按职责拆分 28 个工具 |
| **三态 Guardrail** | `LOCKED` / `ACTIVE` / `AUDITING` 状态机控制所有写操作，紧急解锁需 token |
| **Pydantic Schema 全覆盖** | 21 种 Input Schema，杜绝裸 dict 流转 |
| **双存储后端** | `jsonl`（默认，零依赖）+ `sqlite`（生产推荐） |
| **多源行情容错** | 腾讯 → 东方财富 → AKShare → Baostock 降级链，零 API Key 起步 |
| **结构化复盘** | 自动生成"风险质量 / 纪律报告 / 级联评估 / 信号追踪"四件套 |
| **5 大功能开关** | 通过环境变量灰度发布新功能，默认安全（关闭态） |
| **完整审计日志** | structlog + JSON Lines，结构化可检索 |

---

## 架构概览

```
┌────────────────────────────────────────────────────────┐
│                    MCP Server (≤250 行)                │
│        接收工具调用 → 路由到 Agent → 返回结果           │
└────────────────────────────────────────────────────────┘
         │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼
     ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
     │Market│  │ Risk │  │Decision│ │Review│  │Admin │
     │ 5 工具│  │ 4 工具│  │ 3 工具 │ │ 3 工具│  │ 5 工具│
     └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘
        │         │         │         │         │
        └─────────┴─────────┼─────────┴─────────┘
                            ▼
              ┌──────────────────────────┐
              │   Engine Layer           │
              │   - CachedDataProvider   │
              │   - SentinelEngine       │
              │   - NavTracker           │
              │   - ReconciliationEngine │
              │   - PerformanceCalc      │
              └──────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      ┌──────────────┐            ┌──────────────┐
      │ JSONL / SQLite│            │ 外部数据源    │
      │   本地存储     │            │ 腾讯/东财/AKShare│
      └──────────────┘            └──────────────┘
```

更详细的架构说明、时序图、类图请参考 [`docs/system_design.md`](docs/system_design.md)。

---

## 快速开始

### 1. 环境要求

- **Python 3.11+**（使用了 `asyncio` + `type |` 语法）
- **操作系统**：Linux / macOS / Windows 全平台
- **数据源**：默认走公开 API（零 API Key），仅在启用 AKShare/Baostock 时需要 `pip install praxis-mcp[all]`

### 2. 安装

```bash
# 基础安装（仅 jsonl 后端 + 公开数据源）
pip install praxis-mcp

# 完整安装（包含 AKShare / Baostock / 测试依赖）
pip install praxis-mcp[all]

# 从源码安装（开发模式）
git clone <repository-url>
cd praxis-mcp
pip install -e .[all,dev]
```

### 3. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，至少设置以下两项：
#   PRAXIS_WORKSPACE=/path/to/your/data/workspace
#   PRAXIS_EMERGENCY_TOKEN=$(openssl rand -hex 32)  # 重要：必须用随机强密码
```

> ⚠️ **安全提示**：`PRAXIS_EMERGENCY_TOKEN` 是 Guardrail 紧急解锁的凭证，等同于"绕过所有写风控的万能钥匙"。**绝对不要**用简单密码、**绝对不要**提交到 git（`.gitignore` 已经默认排除 `.env`）。

### 4. 启动 MCP Server

```bash
# 方式 1：作为 stdio MCP 进程（推荐，IDE/MCP 客户端调用）
praxis-mcp

# 方式 2：作为 SSE HTTP 服务（远程访问）
PRAXIS_TRANSPORT=sse PRAXIS_PORT=8080 praxis-mcp
```

### 5. 验证安装

```bash
# 运行全量测试
pytest

# 运行核心模块的快速冒烟测试
python scripts/verify_all.py
```

---

## 配置说明

所有可调参数通过环境变量控制，完整列表见 [`.env.example`](.env.example)。下表是最常用的几项：

| 变量 | 默认 | 说明 |
|------|------|------|
| `PRAXIS_WORKSPACE` | `.` | 数据工作区根目录（包含 `data/`、`config/`、`logs/`） |
| `PRAXIS_EMERGENCY_TOKEN` | `""` | Guardrail 紧急解锁令牌，**留空即禁用该功能** |
| `PRAXIS_AGENT_MODE` | `true` | 启用多智能体调度 |
| `PRAXIS_GUARDRAIL_ENABLED` | `true` | 启用三态状态机风控 |
| `PRAXIS_STORAGE_BACKEND` | `jsonl` | `jsonl` 或 `sqlite` |
| `PRAXIS_MEMORY_ENABLED` | `false` | 启用记忆库（消耗更多内存） |
| `PRAXIS_TRANSPORT` | `stdio` | MCP 传输协议：`stdio` 或 `sse` |
| `PRAXIS_LOG_LEVEL` | `INFO` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `PRAXIS_LOG_JSON` | `true` | JSON 格式日志（生产推荐） |

---

## 项目结构

```
praxis-mcp/
├── src/praxis/
│   ├── __init__.py              # 版本号 + Feature Flags
│   ├── mcp_server.py            # MCP 编排入口（≤250 行）
│   ├── agents/                  # Agent 框架 + 5 个 Agent 实现
│   │   ├── base.py              # BaseAgent ABC + AgentDependencies DI
│   │   ├── tool_registry.py     # 插件式 ToolRegistry
│   │   ├── market.py            # 行情/扩展/基准/新闻/情感
│   │   ├── risk.py              # 哨兵/估值/约束/摩擦
│   │   ├── decision.py          # 交易/决策/组合写
│   │   ├── review.py            # 复盘/级联/追踪
│   │   └── admin.py             # 组合读/净值/对账/发现/绩效
│   ├── core/                    # 核心接口 + 数据模型 + 基础设施
│   │   ├── models.py            # 21 个 Pydantic 模型
│   │   ├── interfaces.py        # 10 个抽象基类
│   │   ├── guardrail.py         # 三态状态机 + SQLite 持久化
│   │   ├── logging_config.py    # structlog 统一日志
│   │   └── feature_flags.py     # 五大开关灰度系统
│   ├── db/
│   │   └── schema.sql           # SQLite v1.0 DDL（8 张核心表）
│   ├── tools/                   # 28 个 MCP 工具实现 + Schema
│   │   ├── _schemas.py          # 21 种 Pydantic Input Schema
│   │   ├── registers.py         # 统一 register() 导出
│   │   ├── market.py            # 行情
│   │   ├── decision_module.py   # 决策
│   │   ├── review_module.py     # 复盘
│   │   └── ...                  # 其他 25 个工具
│   └── engine/                  # 数据提供器 + 业务引擎
│       ├── data_provider.py     # CachedDataProvider (TTL + 降级链)
│       ├── data/                # 外部数据源实现
│       ├── sentinel.py          # 哨兵扫描引擎
│       ├── nav_tracker.py       # 净值追踪
│       ├── reconciliation.py    # 对账
│       └── performance.py       # 绩效计算
├── tests/                       # 57 个单元测试，覆盖核心模块
├── scripts/                     # 终端验证 + 数据迁移脚本
├── docs/                        # 架构设计文档
│   ├── system_design.md         # 系统设计 + 时序图 + 类图
│   ├── class-diagram.mermaid    # 类图（Mermaid 格式）
│   └── sequence-diagram.mermaid # 时序图
├── .env.example                 # 环境变量模板
├── .gitignore                   # Git 忽略规则
├── pyproject.toml               # 项目配置 + 依赖声明
└── OVERVIEW.md                  # 重构完成报告（内部）
```

---

## 开发

### 运行测试

```bash
# 全量测试
pytest

# 覆盖率报告
pytest --cov=src/praxis --cov-report=html

# 仅单元测试
pytest -m unit

# 跳过慢测试（无网络）
pytest -m "not slow"

# 跑指定的测试文件
pytest tests/core/test_guardrail.py -v
```

### 代码规范

- 遵循 **PEP 8** + **Google-style docstring**
- 公共 API 必须有类型注解（`mypy --strict` 通过）
- 新增工具必须在 `src/praxis/tools/_schemas.py` 注册 Pydantic Schema
- 新增 Agent 必须继承 `BaseAgent` 并通过 `ToolRegistry` 注册工具

### 本地开发模式

```bash
# 安装 pre-commit（可选）
pip install pre-commit
pre-commit install

# 增量开发
pip install -e .[all,dev]
# 修改 src/ 下的代码 → 直接生效，无需重新安装
```

---

## 文档

- **架构设计**：[`docs/system_design.md`](docs/system_design.md)
- **类图**：[`docs/class-diagram.mermaid`](docs/class-diagram.mermaid)
- **时序图**：[`docs/sequence-diagram.mermaid`](docs/sequence-diagram.mermaid)
- **重构报告**：[`OVERVIEW.md`](OVERVIEW.md)

---

## 安全说明

PRAXIS Agent 涉及**真实资金决策**，请认真对待以下事项：

1. **`PRAXIS_EMERGENCY_TOKEN` 是最敏感的配置**
   - 泄露 = 任何拿到 token 的人都能绕过所有写风控
   - 建议用 `openssl rand -hex 32` 或 `uuidgen | tr -d '-'` 生成
   - 定期轮换（建议每 90 天）

2. **默认配置是"安全优先"**
   - Guardrail 默认开启，紧急解锁默认禁用
   - 5 大 Feature Flag 默认关闭新功能
   - 公开数据源零 API Key，避免凭证泄露

3. **审计日志**
   - 所有写操作（交易/决策/参数调整）会写结构化日志
   - 日志格式为 JSON Lines，可用 `jq` / `LogQL` 检索
   - 建议把 `logs/` 目录纳入独立备份

4. **披露安全漏洞**
   - 如发现安全漏洞，请**不要**在公开 issue 中提交
   - 私下联系维护者，给出可复现的 PoC
   - 我们会在 24 小时内响应

---

## 致谢

PRAXIS Agent 的数据源来自以下公开服务（按降级链顺序）：

- [腾讯财经](https://qt.gtimg.cn/) — 公开行情 API
- [东方财富](https://data.eastmoney.com/) — 资金流向、龙虎榜、研报
- [AKShare](https://akshare.akfamily.xyz/) — 开源财经数据库
- [Baostock](http://baostock.com/) — 历史 K 线

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源。

```
Copyright (c) 2026 BoussinesqJ
```

---

## 贡献

欢迎贡献！提交 PR 前请确保：

1. 通过 `pytest`（覆盖率不下降）
2. 公共 API 有完整 docstring + 类型注解
3. 涉及安全/数据模型的改动附上迁移说明
4. PR 描述中说明 `动机 / 方案 / 风险 / 回滚方案` 四要素

> 本项目遵守 [Contributor Covenant](https://www.contributor-covenant.org/) 行为准则。
