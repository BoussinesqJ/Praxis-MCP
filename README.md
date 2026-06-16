# PRAXIS - 投研纪律系统

> **Practice, Reflection, And eXponential Improvement System**
> 可验证、可审计、可复盘、可进化的个人投研纪律系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io/)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-28-blueviolet.svg)](#mcp-工具)
[![v4.0.0](https://img.shields.io/badge/version-v4.0.0-blue.svg)](#)

---

### 📚 终极文档导航图 (v4.0)
本系统拥有极其严密的 Agentic 文档与规则体系。无论您是人类开发者还是 AI 智能体，在查阅任何子文档（如 MCP 手册、复盘规范）前，请务必以 **[《Praxis 全量 SOP 与文档金字塔分级明细》](SOP_INDEX.md)** 为唯一准绳，防止被旧版本弃用指令误导。

---

## 系统定位

**v4.0.0 定位**：PortfolioParser 重构 + 风控黑名单修复 + BSE 支持

**核心理念**：**工具负责算，状态卡负责记，AI 负责串。**

**核心价值**：
- **单工具链式 SOP**：9 大场景串行调用链，杜绝并发卡死
- **级联复盘体系**：monthly/quarterly/annual 三级复盘，READ → TOOL → WRITE 状态卡联动
- **工业级数据源**：MX (API+Key) → 腾讯 → 东财 → akshare 四级降级链，单点故障隔离
- **增强关键词情感**：否定翻转 + 强信号保护，93% 命中率，<0.1s 响应
- **限流保护**：令牌桶 + 随机抖动，东财 API 间隔 ≥ 1s
- **熔断机制**：连续 3 次失败自动冷却 10 分钟

---

## 快速开始

### 安装

```bash
git clone https://github.com/BoussinesqJ/Praxis.git
cd Praxis
pip install -e .
```

### 配置

```bash
# 设置工作目录
# Windows
setx PRAXIS_WORKSPACE "你的实际路径\Portfolio vault"
# Linux/Mac
export PRAXIS_WORKSPACE="/你的实际路径/Portfolio vault"
```

### 启动 MCP Server

```bash
praxis serve
```

---

## 🎯 9 大实战场景（单工具串行调用）

### 第一梯队：主力作战

#### 场景 1：查询个股

> "XX 怎么样"

```
📖 READ:  project.md → 观察池标的列表 + 买入位 + 备注
🔧 TOOL:  get_market_data → fund_flow → news → sentiment → check_constraints
✍️ WRITE: 无（纯查询，不写回）
```

#### 场景 2：持仓网格

> 盘中盯盘 / 补仓研判

```
📖 READ:  project.md → 持仓成本/网格档位/止损位
          finance_status_card.md → 可用资金/资产配比
🔧 TOOL:  portfolio → trading_tool(list) + nav_tool(snapshot) → market_data → check_constraints
✍️ WRITE: project.md → 更新条件单/止损价/网格触发记录
```

#### 场景 3：选股

> 自上而下顺势选股

```
📖 READ:  project.md → 观察池现有标的
          long-term.md → 选股规则/市场限制(688/588/300禁入)/执行窗口
🔧 TOOL:  sentinel → valuation → dragon_tiger + northbound → news + sentiment → research
✍️ WRITE: project.md → 新标的入观察池（含买入位/积极买入位/备注）
```

#### 场景 4：复盘

> 日终 / 周末 / 月末周期性体检

```
📖 READ:  project.md → 当前持仓 + 策略版本记录
          finance_status_card.md → 账户概况 + 上次净值基准
🔧 TOOL:  reconcile → portfolio + nav → performance + benchmark
✍️ WRITE: finance_status_card.md → 更新净值/收益率/资产配比
```

#### 场景 5：归因进化

> 策略调整 / 系统大考

```
📖 READ:  long-term.md → 铁律规则库 + 历史归因审计
          project.md → 策略版本记录
🔧 TOOL:  review → evolution → 【人工复核】 → strategy
✍️ WRITE: long-term.md → 追加参数调整记录（执行 5 日滚动归档，防止文件熵增）
          project.md → 更新策略版本号 + 变更记录
```

### 第二梯队：特种后勤

| 场景 | 触发时机 | 调用链 |
|---|---|---|
| **⑥沙盒研发** | 验证新策略 | `run_backtest` → `trading_friction` → `grayscale` |
| **⑦AI 查岗** | 问责 AI 决策 | `get_ai_tracking` → `agent_tracking` → `team_tool` |
| **⑧极端干预** | 数据错乱 / 除权 | `data_quality` → 【逐项定位】→ `update_portfolio` |
| **⑨系统重置** | 初始化 / 风格大转弯 | `discover_workspace` → `investor` → `orchestrator` |

---

## 状态卡联动矩阵（核心纪律）

每个场景必须有完整的 **READ → TOOL → WRITE** 闭环：

```
📖 READ:  先读状态卡，获取上下文（成本/止损/规则/上次净值）
🔧 TOOL:  按 SOP 串行调用工具
🤔 JUDGE: AI 根据数据做判断
✍️ WRITE: 写回状态卡（必须先展示 diff，主理人确认后才写入）
```

### 三张状态卡

| 状态卡 | 职责 | 禁忌 |
|---|---|---|
| `project.md` | **唯一真相源** — 持仓/网格/止损/观察池 | 不存具体账单盈亏变化 |
| `finance_status_card.md` | 展示层 — 净值/收益率/资产配比 | 禁止越权发布操作指令 |
| `long-term.md` | 历史归因 — 铁律规则 + 参数变更记录 | **执行 5 日滚动归档 (超 5 日的旧记录从头部删除)** |

### 写入纪律

1. **先展示后写入** — 旧值 → 新值，主理人确认
2. **long-term.md 执行 5 日滚动归档 (超 5 日的旧记录从头部删除)** — 历史是审计线索
3. **project.md 是唯一真相源** — 持仓数据以它为准
4. **写入幂等** — 同一操作重复执行不产生副作用

---

## 📜 10 条铁律速查

| 编号 | 名称 | 核心逻辑 |
|:---:|:---|:---|
| Rule 1 | 🚀 价格到位即买 | **[最高优先级]** ETF 网格触发时绝对豁免一切防守期仓位限额 |
| Rule 2 | 情绪起爆器 | ≤2 哨兵 + RSI<20 → 放宽仓位至 20%/30% |
| Rule 3 | 阶梯仓位 | 哨兵数 → 20/30/40/60% 四档 |
| Rule 4 | 条件单退场 | 1 天暂停新建，2 天取消存量 |
| Rule 5 | 估值底线 | PE>80% 且 PB>70% 拦截 |
| Rule 6 | 科技暴露 | 016874+589850 ≤ 25% |
| Rule 7 | 周期陷阱 | 煤炭/半导体需景气度验证 |
| Rule 8 | 可控追高 | ≤总资产 × 3% |
| Rule 9 | 底仓锚定 | 首次建仓与网格触发的单笔基准提升至总资产 10% |
| Rule 10 | 刚性止损 | **全系统资产强制 -5% 刚性止损（铁壁）** |

---

## MCP 工具 (28 个活跃)

### 行情数据

| 工具 | 功能 |
|:---|:---|
| `get_market_data_tool` | 实时行情（四级降级 + 单点故障隔离） |
| `market_data_ext_tool` | 扩展行情（资金流向/北向/龙虎榜/研报） |
| `benchmark_tool` | 基准指数数据 |
| `valuation_tool` | 指数估值分位（PE-TTM） |
| `sentinel_tool` | 哨兵雷达（8 只哨兵 ETF 攻防状态） |

### 投资组合

| 工具 | 功能 |
|:---|:---|
| `portfolio_tool` | 组合管理（summary/detail/state/config） |
| `investor_tool` | 投资者与组合管理 |
| `nav_tool` | 净值管理（record/snapshot/history） |
| `reconcile_tool` | 对账计算（dry-run） |
| `update_portfolio_tool` | 修改组合配置（需审批） |

### 交易管理

| 工具 | 功能 |
|:---|:---|
| `trading_tool` | 交易管理（ledger/add/reverse/approve/reject） |
| `trading_friction_tool` | 交易摩擦成本（费用/滑点/交易时间） |
| `check_constraints_tool` | 交易约束检查 |

### 团队与分析

| 工具 | 功能 |
|:---|:---|
| `orchestrator_tool` | 团队分析编排（ASRG/Masters/Trading） |
| `team_tool` | 团队管理（config/prompt/template） |
| `agent_tracking_tool` | Agent 决策追踪 |
| `get_ai_tracking_tool` | AI 建议命中率 |

### 新闻与情感

| 工具 | 功能 |
|:---|:---|
| `news_tool` | 新闻获取（财联社/华尔街见闻/雪球等 10+ 信源） |
| `sentiment_tool` | 情感分析（增强关键词 + 否定翻转，93% 命中率） |

### 策略与进化

| 工具 | 功能 |
|:---|:---|
| `strategy_tool` | 策略管理（get/list/compare） |
| `review_tool` | 决策复盘（fill/summary/calibration） |
| `cascade_review_tool` | 级联复盘（monthly/quarterly/annual） |
| `evolution_tool` | 进化管理（evaluate/auto/memory/adaptive） |
| `run_backtest_tool` | 策略回测 |
| `grayscale_tool` | 灰度验证（prepare/approve） |
| `data_quality_tool` | 行情数据质量管理 |
| `discover_workspace_tool` | 发现 workspace 全景 |

---

## 数据源架构

### 四级降级链（单点故障隔离）

```
Tier 1: MX 妙想 API (API+Key)     ← 最高优先级，无封IP风险
  ↓ (单个标的失败时，只降级该标的)
Tier 2: 腾讯财经 (HTTP)            ← 不封IP，极速降级
  ↓
Tier 3: 东方财富 (HTTP)            ← 资金流/龙虎榜/研报专用
  ↓
Tier 4: akshare (HTTP)             ← 最终兜底，10s 超时斩杀
```

**单点故障隔离**：批量查询时，一个标的失败只降级该标的，不拖垮整批。

### 限流与熔断

```python
# 限流：令牌桶 + 随机抖动
- 东财 API 间隔 ≥ 1s
- 封禁阈值：>5次/秒, ≥10并发, ≥200次/分

# 熔断：连续失败自动冷却
- MX: 3 次失败 → 冷却 1 分钟
- 腾讯: 5 次失败 → 冷却 5 分钟
- 东财: 3 次失败 → 冷却 10 分钟
```

---

## 文档金字塔（优先级向下覆写）

```
🟥 Tier 0: 红线法典     project.md / AGENTS.md / REDLINE_RULES.md / soul.md
🟧 Tier 1: AI 行为宪法  SOP_INDEX.md (附录) / cascade_review / MEMORY.md
🟨 Tier 2: 架构蓝图     设计文档 / ROADMAP.md
🟩 Tier 3: 参考字典     API.md / README.md / DEVELOPMENT.md
```

**冲突时 Tier 0 永远大于 Tier 3。**

---

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行数据源测试
python -m pytest tests/core/ tests/providers/ -v

# 运行 MCP 工具测试
python -m pytest tests/test_mcp_tools.py -v
```

---

## 目录结构

```
Praxis/
├── praxis/
│   ├── core/                    # 核心模块（限流/熔断/缓存/接口）
│   ├── engine/
│   │   └── data/
│   │       ├── provider.py      # CachedDataProvider（多源容错 + 单点隔离）
│   │       ├── eastmoney.py     # 东方财富数据源
│   │       ├── realtime.py      # 腾讯财经数据源
│   │       ├── akshare_provider.py  # akshare 数据源（10s 超时）
│   │       └── registry.py      # 数据源注册表
│   ├── tools/                   # MCP 工具实现
│   ├── meta/                    # 元进化引擎
│   └── mcp_server.py            # MCP 服务器入口
├── obsidian/                  # 系统架构文档（Obsidian 推荐）
├── docs/
│   ├── SOP_INDEX.md  # 单工具链式 SOP（9 大场景）
│   └── ...
├── config/                      # 配置文件
└── tests/                       # 测试套件
```

---

## 更新日志

### v4.0.0 (2026-06-16) — PortfolioParser 重构 + 风控黑名单修复

#### 架构修复
- ✅ PortfolioParser 完整重构：从持仓表精准解析 3 只真实持仓（016874/600995/510310），不再将预算误统计为持仓市值
- ✅ 资金水位推导：total_assets 直接取自合计行，cash = total_assets - positions_value，仓位比精确至 10.9%
- ✅ 科创板风控黑名单修复：`_check_banned_market()` 新增 InvestorConstraints fallback，补齐 BSE 北交所前缀识别（83/87/92/43）
- ✅ 17/17 全量测试通过（此前 1 个故障已修复）

### v4.0.0 (2026-06-15) — 单工具链式 SOP + 级联复盘 + 状态卡联动

#### 架构变革
- ✅ Bundle 并发架构彻底清除（5 个函数物理删除）
- ✅ 单工具链式 SOP 确立（9 大场景，SOP_INDEX.md）
- ✅ 状态卡联动矩阵（READ → TOOL → WRITE）
- ✅ 数据源降级链单点故障隔离（一个标的失败不拖垮整批）
- ✅ akshare 10s 超时斩杀线（asyncio.wait_for + to_thread）

#### 新增功能
- ✅ `cascade_review_tool` — 级联复盘（monthly/quarterly/annual）
- ✅ AlphaEar 新闻集成（NewsNow API，10+ 信源，10s 超时保护）
- ✅ 增强关键词情感分析（否定翻转 + 强信号保护，93% 命中率）
- ✅ Skills 全面重写（13 个 Skill，v4.0.0 串行调用）

#### 文档整理
- ✅ SOP Index 文档金字塔（Tier 0-3 四级优先级）
- ✅ 毒教材焚书（7 个旧文档物理删除，12 个归档到 archive/）
- ✅ SOP Index 引流植入（project.md / AGENTS.md / README.md）

### v3.3.0 (2026-06-13) — 数据源架构重构

- ✅ 全局限流器（令牌桶 + 随机抖动）
- ✅ 熔断器（三态状态机 + 冷却机制）
- ✅ TTL 缓存层（12 小时内不重复请求）
- ✅ 资金流向 / 北向资金 / 龙虎榜 / 研报数据源
- ✅ 127/127 测试通过

---

## 许可证

MIT License

---

## 致谢

- [akshare](https://github.com/akfamily/akshare) - 金融数据接口
- [mootdx](https://github.com/mootdx/mootdx) - 通达信行情接口
- [go-stock](https://github.com/ArvinLovegood/go-stock) - 6.4k stars
- [a-stock-data](https://github.com/simonlin1212/a-stock-data) - 3.9k stars
- [adata](https://github.com/1nchaos/adata) - 4.7k stars
