# PRAXIS Agent

> AI 驱动的投研纪律系统 — 把交易决策从"主观判断"变成"可回放、可审计、可约束"的工作流。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io/)
[![Pydantic](https://img.shields.io/badge/pydantic-v2-red.svg)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

PRAXIS Agent 是一个**纪律优先**的投研辅助框架。它通过多智能体协作 + 三态 Guardrail 状态机 + 完整审计日志，把"为什么买/为什么卖/为什么没买"全部落到可追溯的记录上。

---

## 目录

- [核心特性](#核心特性)
- [架构概览](#架构概览)
- [安装](#安装)
- [使用指南](#使用指南)
  - [数据采集：多源行情与自定义信源](#1-数据采集多源行情与自定义信源)
  - [哨兵雷达：8 ETF 市场情绪全景扫描](#2-哨兵雷达8-etf-市场情绪全景扫描)
  - [估值分位：PE-TTM 历史温度计](#3-估值分位pe-ttm-历史温度计)
  - [约束检查：交易前纪律校验](#4-约束检查交易前纪律校验)
  - [组合对账：交易账本 → 持仓状态](#5-组合对账交易账本--持仓状态)
  - [绩效分析：12 项风险收益指标](#6-绩效分析12-项风险收益指标)
  - [复盘体系：三级复盘闭环](#7-复盘体系三级复盘闭环)
  - [Guardrail：三态写保护](#8-guardrail三态写保护)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [开发](#开发)
- [安全说明](#安全说明)
- [致谢](#致谢)
- [许可证](#许可证)

---

## 核心特性

| 能力 | 说明 |
|------|------|
| **多智能体协作** | 5 个独立 Agent（Market / Risk / Decision / Review / Admin），按职责拆分 29 个工具 |
| **多源行情容错** | 5 源降级链 + 单点故障隔离 + TTL 缓存，零 API Key 起步 |
| **哨兵雷达** | 8 ETF 双层矩阵 + Rule 23 情绪起爆器 + Rule 26 攻防仓位阶梯 |
| **估值分位** | 沪深300/上证50/中证500/中证1000 PE-TTM 历史分位温度计 |
| **约束检查** | 策略驱动的 5 项交易前纪律校验（板块/工具/金额/现金/上限） |
| **组合对账** | FIFO 移动加权平均 + 实时行情注入 → 持仓/市值/浮盈 |
| **绩效分析** | 基于 NAV 序列的 12 项精确风险收益指标 + 持仓周期分布 |
| **三级复盘** | 基础复盘 → 级联复盘 → 市场周报自动生成 |
| **三态 Guardrail** | `LOCKED` / `ACTIVE` / `AUDITING` 状态机控制所有写操作，紧急解锁需 token |
| **Pydantic Schema 全覆盖** | 21 种 Input Schema，杜绝裸 dict 流转 |
| **双存储后端** | `jsonl`（默认，零依赖）+ `sqlite`（生产推荐） |
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

## 安装

### 1. 环境要求

| 要求 | 说明 |
|------|------|
| **Python** | 3.11+（使用 `asyncio` + `type \|` 语法） |
| **操作系统** | Linux / macOS / Windows 全平台 |
| **磁盘** | ≥ 200 MB（代码 + 依赖 + 数据缓存） |
| **网络** | 访问腾讯/新浪/东方财富公开 API（无需 API Key） |
| **可选依赖** | `mootdx`（通达信直连）、`akshare`（全量 PE 历史） |

### 2. 从零开始安装（每个步骤可复制粘贴）

> **提示**：以下命令在项目根目录执行。如果你是从 GitHub 克隆的，先 `cd praxis-mcp`。

```bash
# ============================================================
# Step 1: 创建虚拟环境
# ============================================================

# Linux / macOS
python3 -m venv .venv

# Windows PowerShell
python -m venv .venv

# ============================================================
# Step 2: 激活虚拟环境
# ============================================================

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# ============================================================
# Step 3: 安装 praxis-mcp
# ============================================================

# 基础安装（jsonl 后端 + 腾讯/新浪公开数据源，零额外依赖）
pip install praxis-mcp

# 或：完整安装（含 AKShare PE 历史、Baostock K 线、测试依赖）
pip install praxis-mcp[all]

# 或：从源码可编辑安装（推荐开发时使用）
pip install -e .[all,dev]

# ============================================================
# Step 4: 配置环境变量
# ============================================================

# 复制模板
cp .env.example .env

# 编辑 .env（用你习惯的编辑器），至少设置以下三项：
#   PRAXIS_WORKSPACE=/absolute/path/to/your/workspace
#   PRAXIS_EMERGENCY_TOKEN=<openssl rand -hex 32 的输出>
#   PRAXIS_LOG_LEVEL=INFO

# Linux / macOS 快速生成 token 并写入 .env：
echo "PRAXIS_EMERGENCY_TOKEN=$(openssl rand -hex 32)" >> .env

# Windows PowerShell：
# $token = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
# "PRAXIS_EMERGENCY_TOKEN=$token" | Out-File -Append .env

# ============================================================
# Step 5: 创建工作区目录结构
# ============================================================

mkdir -p "${PRAXIS_WORKSPACE:-./workspace}/data"
mkdir -p "${PRAXIS_WORKSPACE:-./workspace}/config"
mkdir -p "${PRAXIS_WORKSPACE:-./workspace}/logs"
```

### 3. 验证安装

```bash
# 运行核心模块快速冒烟测试（无需网络）
python scripts/verify_all.py

# 运行全量单元测试（跳过需要网络的慢测试）
pytest -m "not slow"

# 运行全量测试（含集成测试）
pytest

# 检查 MCP server 能否正常启动（stdio 模式，Ctrl+C 退出）
praxis-mcp --help
```

### 4. 在 MCP 客户端中配置

#### WorkBuddy 配置示例

在 WorkBuddy 的 `mcp.json` 中添加如下配置：

```json
{
  "mcpServers": {
    "praxis-agent": {
      "command": "python",
      "args": ["-m", "praxis.cli"],
      "cwd": "/absolute/path/to/praxis-mcp",
      "env": {
        "PRAXIS_WORKSPACE": "/absolute/path/to/your/workspace",
        "PRAXIS_EMERGENCY_TOKEN": "your-64-char-hex-token-here",
        "PRAXIS_STORAGE_BACKEND": "sqlite",
        "PRAXIS_LOG_LEVEL": "INFO",
        "PRAXIS_LOG_JSON": "true",
        "NO_PROXY": "*"
      }
    }
  }
}
```

> **配置要点**：
> - `cwd` 必须指向项目根目录（包含 `pyproject.toml` 的目录）
> - `PRAXIS_EMERGENCY_TOKEN` 不能为空，否则紧急解锁功能禁用
> - `NO_PROXY=*` 确保数据源请求直连，不被代理拦截
> - `PRAXIS_STORAGE_BACKEND` 生产环境推荐 `sqlite`

#### 其他 MCP 客户端（Claude Desktop / Cursor 等）

配置格式类似，核心是：
- **transport**：`stdio`
- **command**：`python -m praxis.cli`（或 `praxis-mcp`，取决于安装方式）
- **环境变量**：同上

#### SSE 模式（远程访问）

```bash
# 启动 SSE 服务
PRAXIS_TRANSPORT=sse PRAXIS_PORT=8080 praxis-mcp

# 客户端配置
{
  "mcpServers": {
    "praxis-agent": {
      "transport": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

---

## 使用指南

以下按分析场景组织，每个场景说明：**数据从哪来 → 经过什么逻辑 → 输出什么判断**。

---

### 1. 数据采集：多源行情与自定义信源

PRAXIS 的数据采集层是整个系统的感知基础。所有分析工具共享同一套数据管道。

#### 1.1 内置 5 源降级链

系统按优先级自动编排数据源，当前源失败或返回空数据时自动降级：

| 优先级 | 数据源 | 说明 | 依赖 |
|--------|--------|------|------|
| **5** | **Tencent（腾讯财经）** | 主力数据源，零 API Key，HTTP 公开接口，响应最快 | 无（httpx 内置） |
| **8** | **mootdx（通达信）** | TCP 直连通达信行情服务器，不封 IP，五档盘口 | `pip install mootdx` |
| **10** | **AKShare** | 开源财经数据库，覆盖 PE 历史、资金流向、龙虎榜 | `pip install akshare` |
| **30** | **Baostock** | 历史 K 线补全，适合离线/回测场景 | `pip install baostock` |
| **50** | **EastMoney（东方财富）** | 最终兜底，资金流向、研报、龙虎榜 | 无（httpx 内置） |

**降级逻辑**：同一批 ticker 请求，当前优先级数据源只补齐缺失的标的，下一个源只请求仍未获取到的标的。

#### 1.2 单点故障隔离

```
请求: [000001, 600519, 300750, 688981]
       │
       ▼ Tencent (P=5)
       ├── 000001 ✓ 获取成功
       ├── 600519 ✓ 获取成功
       ├── 300750 ✗ 返回空
       └── 688981 ✗ 返回空
              │
              ▼ mootdx (P=8) — 只请求缺失的
              ├── 300750 ✓ 获取成功
              └── 688981 ✗ 仍需降级
                     │
                     ▼ AKShare (P=10)
                     └── 688981 ✓ 获取成功

最终结果: 4/4 全部获取，不因单个标的影响整批
```

#### 1.3 TTL 缓存机制

- **内存缓存**：默认 300 秒（5 分钟），`dict` + timestamp 实现
- **文件持久化**：JSON 格式落盘到 `{workspace}/data/cache/`，进程重启后可恢复
- **缓存清洗**：过期条目自动清除，避免脏数据污染

```python
# 使用示例
from praxis.engine.data import CachedDataProvider

provider = CachedDataProvider(
    cache_dir="./data",
    cache_ttl_seconds=300,  # 5 分钟 TTL
    workspace=".",
)

# 首次调用：走网络请求
quotes = await provider.get_realtime_quote(["000001", "600519"])

# 300 秒内重复调用：命中内存缓存（毫秒级返回）
quotes = await provider.get_realtime_quote(["000001", "600519"])

await provider.close()
```

#### 1.4 自定义信源

在 `providers/` 目录下放置一个继承 `DataProvider` 的 `.py` 文件，系统启动时 `auto_discover` 自动扫描注册。

**Step 1：编写提供器**

```python
# providers/my_custom_provider.py
"""自定义数据源示例 — 对接自建行情服务"""

from praxis.core.interfaces import DataProvider
from praxis.core.exceptions import DataError

# 优先级：3（最高，优先于内置源）
PRIORITY = 3

class MyCustomProvider(DataProvider):
    """自建行情服务数据源"""

    def __init__(self, api_base: str = "http://localhost:9000"):
        self._api_base = api_base

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """从自建服务获取实时行情"""
        if not tickers:
            return {}
        # 实现你的数据获取逻辑
        # 返回格式: {ticker: {name, price, prev_close, open, volume,
        #                     high, low, change, change_pct, amount,
        #                     timestamp, source}, ...}
        ...

    async def get_history_kline(self, ticker: str, period: str = "day",
                                 count: int = 60) -> list[dict]:
        """获取历史 K 线"""
        # 返回格式: [{date, open, close, high, low, volume, source}, ...]
        ...

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值"""
        # 返回格式: {ticker, nav, acc_nav, nav_date, source}
        ...

    async def close(self) -> None:
        """清理资源"""
        pass
```

**Step 2：注册（自动发现）**

无需手动注册。`CachedDataProvider(auto_discover=True)` 启动时自动扫描 `providers/` 目录，加载所有 `PRIORITY` 字段的 `DataProvider` 子类。

**Step 3：配置覆盖（可选）**

在 `config/data_sources.yaml` 中显式控制启用/禁用：

```yaml
sources:
  my_custom_provider:
    enabled: true
    priority: 3
    config:
      api_base: "http://192.168.1.100:9000"
```

#### 1.5 熔断自愈

每个数据源有独立健康状态追踪：

```
健康状态机:
  Healthy ──(连续3次失败)──→ Unhealthy ──(60s 冷却)──→ Half-Open
  Half-Open ──(探测成功)──→ Healthy
  Half-Open ──(探测失败)──→ Unhealthy（重置冷却计时）
```

- 连续 3 次失败 → 标记 `unhealthy`，暂停使用
- 60 秒冷却后进入 `Half-Open`，尝试一次探测请求
- 探测成功 → 恢复 `healthy`；探测失败 → 继续 `unhealthy`

---

### 2. 哨兵雷达：8 ETF 市场情绪全景扫描

哨兵雷达（SentinelEngine）是 PRAXIS 的核心市场感知模块，通过 8 只 ETF 组成双层矩阵，每日扫描多空趋势，驱动仓位决策。

#### 2.1 双层矩阵结构

| 层级 | ETF 代码 | 名称 | 角色 |
|------|---------|------|------|
| **大局风格层** | 510300 | 沪深300ETF | 大盘价值基准 |
| | 159915 | 创业板ETF | 成长风险偏好 |
| | 512000 | 券商ETF | 市场情绪温度计 |
| | 159601 | 恒生科技ETF | 港股科技风向标 |
| **执行持仓层** | 512480 | 半导体ETF | 硬科技弹性基准 |
| | 515050 | 通信ETF | 通信行业哨兵 |
| | 515220 | 煤炭ETF | 防御与红利基准 |
| | 511220 | 国债ETF | 避险资产基准 |

#### 2.2 判定逻辑

每一步扫描经过 4 个步骤：

```
Step 1: 数据获取 → 从新浪/腾讯获取最近 70 日 K 线
Step 2: 均线计算 → MA10 / MA20 / MA30 / MA60
Step 3: 多空判定 → 价格 vs MA20
    ├── close > MA20 × 1.01 → bullish（多头）
    ├── close < MA20 × 0.99 → bearish（空头）
    └── 其他 → neutral（中性）
Step 4: 量能分类 → 当前成交量 vs 5日均量
    ├── vol_ratio > 1.5 → 异常放量
    ├── vol_ratio < 0.6 → 静默缩量
    └── 其他 → 量平
```

#### 2.3 Rule 26：攻防仓位阶梯

根据 `bullish_count`（看多 ETF 数量）自动推导仓位上限：

| bullish_count | 市场状态 | 最大仓位 | 操作策略 |
|---------------|---------|---------|---------|
| 0 – 2 | 绝对防守期 | **10%** | 减仓/观望，仅持有防御性标的 |
| 3 – 5 | 适度试探期 | **20%** | 小仓位试探，严格止损 |
| 6 – 8 | 积极配置期 | **30% → 50%** | 逐步加仓，宽止损 |

#### 2.4 Rule 23：情绪起爆器

连续 2 个交易日 `bullish_count ≥ 4` 触发"情绪起爆器"信号：

- **含义**：市场情绪由冷转暖，确认反弹趋势
- **操作提示**：可考虑加仓至对应阶梯上限
- **持久化**：扫描结果写入 `data/sentinel_history.jsonl`，支持回溯验证

#### 2.5 外部 K 线注入

哨兵引擎支持外部 K 线数据注入，避免重复网络请求。典型用法是 WorkBuddy 通过 `westock-mcp` 或 `tdx-connector` 采集 K 线后传入：

```python
# 从外部采集 K 线后注入哨兵
sentinel = SentinelEngine(workspace=".", config_loader=loader,
                          investor_id="default", portfolio_id="main")

# 外部采集的 K 线数据
external_klines = {
    "510300": [{"date": "2026-01-15", "open": 3.95, "close": 3.98, ...}, ...],
    "159915": [{"date": "2026-01-15", "open": 2.35, "close": 2.38, ...}, ...],
}

# scan() 方法会优先使用传入数据，仅缺失部分走网络获取
result = await sentinel.scan()

# 结果解读
print(f"看多 ETF: {result['bullish_count']}/8")
print(f"仓位上限: {result['position_limit_pct']}%")
print(f"市场状态: {result['state']}")
print(f"Rule23 触发: {result['rule23_triggered']}")
```

---

### 3. 估值分位：PE-TTM 历史温度计

基于 AKShare `stock_index_pe_lg` 全量 PE 历史数据，计算指数当前 PE 在全历史区间和近 10 年维度中的分位。

#### 3.1 覆盖指数

| 代码 | 名称 | 数据来源 |
|------|------|---------|
| 000300 | 沪深300 | AKShare stock_index_pe_lg（全量历史 PE） |
| 000016 | 上证50 | 同上 |
| 000905 | 中证500 | 同上 |
| 000852 | 中证1000 | 同上 |

#### 3.2 计算逻辑

```
Step 1: 从 AKShare 获取全量 PE-TTM 历史数据
Step 2: 使用"滚动市盈率"(PE-TTM)列，比静态 PE 更准确
Step 3: 排序计算分位数

    pe_30pct  = 排序后第 30% 位置的值
    pe_80pct  = 排序后第 80% 位置的值

Step 4: 判定当前 PE 位置
    ├── current_pe < pe_30pct  → undervalued（低估）
    ├── current_pe > pe_80pct  → overvalued（高估）
    └── 其他                  → fairly_valued（合理）
```

#### 3.3 输出示例

```python
{
    "index_code": "000300",
    "index_name": "沪深300",
    "current_pe": 12.45,
    "percentile_all": 28.5,      # 全历史 28.5%，处于低估区间
    "percentile_10y": 35.2,      # 近 10 年 35.2%，相对合理偏低
    "pe_30pct": 12.82,
    "pe_80pct": 18.34,
    "data_days": 4560,
    "below_30pct": true,         # 低于 30% 分位 → 低估信号
    "above_80pct": false
}
```

> **注意**：估值分位需要 `akshare` 依赖（`pip install praxis-mcp[all]` 或 `pip install akshare`）。

---

### 4. 约束检查：交易前纪律校验

每笔交易执行前，ConstraintChecker 执行 5 项硬约束校验。未通过任一项 → 交易被拦截。

#### 4.1 5 项硬约束

| # | 约束 | 检查逻辑 | 违规示例 |
|---|------|---------|---------|
| 1 | **禁入板块** | ticker 不能以 688/588（科创板）、300/159（创业板）开头 | 买入 688001 中芯国际 → 拦截 |
| 2 | **工具限制** | 禁止期权合约、可转债、分级基金、期货、融资融券 | 买入 10005558 50ETF 期权 → 拦截 |
| 3 | **最小交易金额** | 买入金额 > 5,000 元（策略可调） | 买入 2,000 元 → 拦截 |
| 4 | **现金底线** | 交易后现金 ≥ 总资产 × 5%（策略可调） | 买入后只剩 3% 现金 → 拦截 |
| 5 | **单标的上限** | 单一标的 ≤ 总资产 × 30%（策略可调） | 茅台已占 35% → 拦截 |

#### 4.2 策略驱动模式

约束阈值优先从策略 YAML 模板动态读取，未配置时回退到硬编码默认值：

```yaml
# config/strategies/default.yaml
strategy:
  rules:
    execution_rules:
      min_transaction:
        min_amount_cny: 5000       # → 约束 #3
    risk_rules:
      cash_floor:
        min_pct: 5.0                # → 约束 #4
      position_cap:
        max_single_pct: 30.0        # → 约束 #5
      stop_loss:
        default_pct: -10.0
      max_drawdown:
        pct: 20.0
```

#### 4.3 使用示例

```python
from praxis.engine.constraint_checker import SimpleConstraintChecker

checker = SimpleConstraintChecker(investor=profile, portfolio=portfolio,
                                   strategy=strategy)

# 买入前检查
violations = checker.check(
    state=current_state,
    action="buy",
    ticker="600519",
    amount=10000,
)

if violations:
    for v in violations:
        print(f"❌ {v['rule']}: {v['message']}")
else:
    print("✅ 所有约束通过，可以执行交易")
```

---

### 5. 组合对账：交易账本 → 持仓状态

ReconciliationEngine 从交易账本重建持仓状态，注入实时行情计算市值和浮盈。

#### 5.1 对账流程

```
Ledger (append-only 交易记录)
    │
    ▼ Step 1: 累加所有 executed 交易
    │   FIFO 移动加权平均法计算持仓成本
    │   买入 → 增加持仓份额，更新加权均价
    │   卖出 → 减少持仓份额（先入先出）
    │
    ▼ Step 2: 注入实时行情
    │   调用 DataProvider.get_realtime_quote(tickers)
    │   计算: 市值 = 持仓份额 × 当前价
    │         浮盈 = 市值 - 持仓成本
    │
    ▼ Step 3: 计算组合全景
    │   总市值 = Σ 各标的市值 + 现金余额
    │   现金余额 = 初始资金 - Σ 买入 + Σ 卖出 - Σ 手续费
    │
    ▼ Output: PortfolioState
        {positions, cash, total_market_value, total_cost, pnl}
```

#### 5.2 外部行情注入

支持外部采集的行情数据传入，避免对账模块自行发起网络请求：

```python
# 方式 1：通过 DataProvider 自动获取
state = await engine.reconcile("investor_01", "main")

# 方式 2：外部注入行情
external_quotes = {
    "600519": {"price": 1689.00, "name": "贵州茅台", ...},
    "000001": {"price": 12.45, "name": "平安银行", ...},
}
state = await engine.reconcile_with_quotes(
    "investor_01", "main", external_quotes
)
```

#### 5.3 输出结构

```python
PortfolioState:
    positions: [
        {ticker, name, shares, avg_cost, market_price,
         market_value, pnl, pnl_pct, weight_pct}
    ]
    cash: {balance, initial_capital, total_deposited, total_withdrawn}
    total_market_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
```

---

### 6. 绩效分析：12 项风险收益指标

EnhancedPerformanceCalculator 基于 NAV 序列精确计算 12 项指标，不再使用简单 `(sell-buy)/capital` 近似。

#### 6.1 计算方法

所有指标从两个数据源交叉计算：

| 数据源 | 内容 |
|--------|------|
| **NAV 序列** | `nav_tracker` 记录的每日净值历史 |
| **Ledger** | `FileLedger` 中的每笔交易记录 |

#### 6.2 12 项指标一览

| 类别 | 指标 | 计算方式 |
|------|------|---------|
| **收益** | `total_return` | `latest_nav - 1.0`，从 NAV 序列直接读取 |
| | `annualized_return` | `(1 + total_return)^(365/天數) - 1` |
| | `benchmark_return` | 同期基准（沪深300）涨跌幅 |
| | `excess_return` | `total_return - benchmark_return` |
| **风险** | `max_drawdown` | NAV 序列峰值到谷值的最大跌幅 |
| | `volatility` | 日收益率标准差 × √365 |
| | `sharpe_ratio` | `annualized_return / volatility` |
| | `calmar_ratio` | `annualized_return / max_drawdown` |
| **交易** | `win_rate` | 盈利交易笔数 / 总交易笔数 |
| | `profit_loss_ratio` | 平均盈利 / 平均亏损 |
| | `turnover_rate` | 期间交易总额 / 平均资产规模 |
| | `total_fee` | 所有交易手续费之和 |

#### 6.3 持仓周期分布

交易按持有天数自动分为 4 档：

| 档位 | 持有周期 | 典型场景 |
|------|---------|---------|
| **短线** | < 3 天 | 事件驱动 / 情绪交易 |
| **短中期** | 3 – 7 天 | 波段操作 |
| **中期** | 7 – 20 天 | 趋势跟踪 |
| **长线** | > 20 天 | 价值持仓 |

```python
from praxis.engine.performance import EnhancedPerformanceCalculator

calc = EnhancedPerformanceCalculator(
    ledger=ledger,
    initial_capital=70000,
    nav_tracker=nav_tracker,
)

metrics = calc.calculate(
    investor_id="default",
    portfolio_id="main",
)

print(f"累计收益: {metrics['total_return']:.2%}")
print(f"最大回撤: {metrics['max_drawdown']:.2%}")
print(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
print(f"胜率:     {metrics['win_rate']:.1%}")
```

---

### 7. 复盘体系：三级复盘闭环

#### 7.1 基础复盘：决策记录 + 信心校准

每笔交易决策执行后，填充决策记录：

```
决策记录 (DecisionRecord):
    ├── 决策时间 / 标的 / 方向 / 金额
    ├── 决策理由（引用 Rule 编号）
    ├── 当时市场状态（哨兵快照 + PE 分位）
    ├── 信心评级（1–5）
    └── 事后验证：实际结果 vs 预期
```

#### 7.2 级联复盘：月度/季度/年度聚合

从单笔决策记录聚合到时间维度的分析：

```
月度复盘:
    本月交易笔数 / 胜率 / 平均持仓周期
    本月最大回撤 / 收益贡献者排名
    纪律违规次数与类型

季度复盘:
    季度夏普比率 / Calmar 比率
    策略规则有效性评估（哪条 Rule 贡献了最多收益）
    仓位阶梯使用情况

年度复盘:
    年化收益 vs 基准
    最大回撤修复天数
    策略迭代建议
```

#### 7.3 市场周报：自动生成四件套

`generate_market_weekly_review` 工具自动生成：

| 报告 | 内容 | 数据源 |
|------|------|--------|
| **风险质量报告** | 当前 Guardrail 状态、哨兵仓位阶梯、估值分位风险提示 | Sentinel + Valuation + Guardrail |
| **纪律报告** | 本周约束违规统计、紧急解锁记录、异常交易标记 | ConstraintChecker + Audit Log |
| **级联评估** | 月度/季度绩效级联分析 | Performance + Review |
| **信号追踪** | Rule 23 触发历史、哨兵趋势变化、关键信号演变 | Sentinel History + Signal Tracker |

---

### 8. Guardrail：三态写保护

Guardrail 是 PRAXIS 的最终风控防线，控制所有写操作。

#### 8.1 三态状态机

```
         ┌──────────────────────────────┐
         │        UNINITIALIZED          │
         │      （首次启动初始态）        │
         └────────┬──────────┬──────────┘
                  │          │
        initialize│          │initialize
                  ▼          ▼
         ┌──────────┐  ┌──────────┐
         │  LOCKED  │  │  ACTIVE  │
         │ 禁止写操作│  │ 正常操作  │
         └────┬─────┘  └──┬───┬──┘
              │           │   │
      unlock  │   lock    │   │ trigger_review
              │           │   │
              ▼           ▼   ▼
         ┌──────────┐  ┌───────────┐
         │  ACTIVE  │  │ AUDITING  │
         │ （恢复）  │  │ 只读+复盘  │
         └──────────┘  └─────┬─────┘
                             │
                 complete    │
                 _review     │
                             ▼
                        ┌──────────┐
                        │  ACTIVE  │
                        └──────────┘
```

#### 8.2 状态行为

| 状态 | 读操作 | 写操作 | 复盘操作 | 进入条件 |
|------|--------|--------|---------|---------|
| `LOCKED` | ✅ | ❌ 全部拦截 | ❌ | 紧急锁定 / 初始化选择 |
| `ACTIVE` | ✅ | ✅ | ❌ | unlock / 复盘完成 |
| `AUDITING` | ✅ | ❌ | ✅ | 复盘触发 |

#### 8.3 Emergency Token 紧急解锁

- `LOCKED` → `ACTIVE` 需要 `PRAXIS_EMERGENCY_TOKEN`
- 每次紧急解锁记录完整审计日志（谁、什么时间、什么原因）
- Token 应为 64 位随机 hex（`openssl rand -hex 32`），不得使用弱密码

#### 8.4 SQLite 持久化

状态变更写入 SQLite `guardrail_state` 表，进程重启后状态不丢失。配合 structlog JSON Lines 实现完整审计链。

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
| `PRAXIS_HOST` | `127.0.0.1` | SSE 模式监听地址 |
| `PRAXIS_PORT` | `8080` | SSE 模式监听端口 |
| `PRAXIS_TOOL_TIMEOUT` | `30` | 工具调用超时秒数 |
| `PRAXIS_LOG_LEVEL` | `INFO` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `PRAXIS_LOG_JSON` | `true` | JSON 格式日志（生产推荐） |
| `PRAXIS_ORCHESTRATION_MODE` | `agent` | 编排模式：`agent` / `direct` |

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
│   ├── tools/                   # 29 个 MCP 工具实现 + Schema
│   │   ├── _schemas.py          # 21 种 Pydantic Input Schema
│   │   ├── registers.py         # 统一 register() 导出
│   │   ├── market.py            # 行情
│   │   ├── decision_module.py   # 决策
│   │   ├── review_module.py     # 复盘
│   │   └── ...                  # 其他 25 个工具
│   └── engine/                  # 数据提供器 + 业务引擎
│       ├── data/                # 外部数据源实现
│       │   ├── provider.py      # CachedDataProvider (TTL + 降级链)
│       │   ├── realtime.py      # 腾讯财经数据源 (P=5)
│       │   ├── mootdx_provider.py # 通达信数据源 (P=8)
│       │   └── registry.py      # 数据源注册表（自动发现 + 配置覆盖）
│       ├── sentinel.py          # 哨兵扫描引擎 (Rule23 + Rule26)
│       ├── valuation.py         # PE-TTM 估值分位引擎
│       ├── constraint_checker.py # 5 项交易前纪律校验
│       ├── nav_tracker.py       # 净值追踪
│       ├── reconciliation.py    # 对账引擎（FIFO 移动加权平均）
│       └── performance.py       # 12 项绩效指标计算
├── tests/                       # 单元测试，覆盖核心模块
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
- 新增数据源必须继承 `DataProvider` 并设置 `PRIORITY` 变量

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

- **📖 零基础教程**：[`docs/TUTORIAL.md`](docs/TUTORIAL.md) — 从安装到日常使用的完整指南
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
- [通达信 (mootdx)](https://github.com/rainx/mootdx) — TCP 直连行情
- [AKShare](https://akshare.akfamily.xyz/) — 开源财经数据库
- [Baostock](http://baostock.com/) — 历史 K 线
- [东方财富](https://data.eastmoney.com/) — 资金流向、龙虎榜、研报

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
