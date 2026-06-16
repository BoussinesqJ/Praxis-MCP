# MCP 工具清单

> v4.0.0 完整版：28 个活跃工具（+ 23 个 deprecated 已隐藏）
> 单工具串行调用，并发逻辑交由 AI 前端思维链完成

---

## 设计原则

**v4.0 架构变革**：
- ~~Bundle 并发工具~~ → 已物理删除，后端只保留最纯粹的原子工具
- AI 前端按 SOP 串行调用，每个工具独立超时保护
- 单点故障隔离：一个标的失败不拖垮整批

---

## 行情数据（5 个）

| 工具 | 功能 | 数据源 |
|:---|:---|:---|
| `get_market_data_tool` | 实时行情（四级降级 + 单点隔离） | MX → 腾讯 → 东财 → akshare |
| `market_data_ext_tool` | 扩展行情（fund_flow/northbound/dragon_tiger/research） | 东财 push2/datacenter/reportapi |
| `benchmark_tool` | 基准指数数据（data/list） | 腾讯财经 |
| `valuation_tool` | 指数估值分位 PE-TTM（percentile/all） | 东财 |
| `sentinel_tool` | 哨兵雷达 — 8 只哨兵 ETF 攻防状态（scan/rule23_status/history） | 腾讯财经 |

---

## 投资组合（5 个）

| 工具 | 功能 | action |
|:---|:---|:---|
| `portfolio_tool` | 组合管理 | summary / detail / state / config |
| `investor_tool` | 投资者与组合管理 | create / create_portfolio / init |
| `nav_tool` | 净值管理 | record / snapshot / history |
| `reconcile_tool` | 对账计算（dry-run） | — |
| `update_portfolio_tool` | 修改组合配置（需审批） | — |

---

## 交易管理（3 个）

| 工具 | 功能 | action |
|:---|:---|:---|
| `trading_tool` | 交易管理 | ledger / add / reverse / approve / reject / decision |
| `trading_friction_tool` | 交易摩擦成本 | fee / slippage / trading_time / confirm_date |
| `check_constraints_tool` | 交易约束检查 | — |

---

## 团队与分析（4 个）

| 工具 | 功能 | action |
|:---|:---|:---|
| `orchestrator_tool` | 团队分析编排（ASRG/Masters/Trading） | plan / member_prompt / compile_prompt |
| `team_tool` | 团队管理 | config / prompt / template |
| `agent_tracking_tool` | Agent 决策追踪 | record / consensus / rank |
| `get_ai_tracking_tool` | AI 建议命中率 | — |

---

## 新闻与情感（2 个）

| 工具 | 功能 | action |
|:---|:---|:---|
| `news_tool` | 新闻获取（财联社/华尔街见闻/雪球等 10+ 信源） | finance / trends / polymarket / list_sources |
| `sentiment_tool` | 情感分析（增强关键词 + 否定翻转，93% 命中率） | analyze / batch |

> ⚠️ 新闻 → 情感必须串行：先 `news_tool` 取标题，再 `sentiment_tool` 打分

---

## 策略与进化（9 个）

| 工具 | 功能 | action |
|:---|:---|:---|
| `strategy_tool` | 策略管理 | get / list / compare |
| `review_tool` | 决策复盘 | fill / summary / calibration |
| `cascade_review_tool` | **级联复盘（v4.0 新增）** | monthly / quarterly / annual |
| `evolution_tool` | 进化管理 | evaluate / auto / memory / adaptive |
| `run_backtest_tool` | 策略回测（实验性） | — |
| `grayscale_tool` | 灰度验证 | prepare / approve |
| `data_quality_tool` | 行情数据质量 | check / clean / report |
| `discover_workspace_tool` | 发现 workspace 全景 | — |
| `output_template_tool` | 输出模板管理 | list / get / create / update / approve |

---

## 级联复盘详解（v4.0 新增）

`cascade_review_tool` 替代了旧的 `review_bundle_tool`，支持三级复盘：

| 模式 | 周期 | 内容 |
|:---|:---|:---|
| `monthly` | 月度 | 纪律代价月报 |
| `quarterly` | 季度 | 3 个月聚合 + 进化评估 |
| `annual` | 年度 | 12 个月 + 铁律审计 |

```python
# 月度复盘
cascade_review_tool(mode="monthly", period="2026-06")

# 季度复盘
cascade_review_tool(mode="quarterly", period="2026-Q2")

# 年度复盘
cascade_review_tool(mode="annual", period="2026")
```

---

## 数据源降级链

### 四级降级（单点故障隔离）

```
Tier 1: MX 妙想 API (API+Key)     ← 最高优先级，无封IP风险
  ↓ (单个标的失败时，只降级该标的)
Tier 2: 腾讯财经 (HTTP)            ← 不封IP，极速降级
  ↓
Tier 3: 东方财富 (HTTP)            ← 资金流/龙虎榜/研报专用
  ↓
Tier 4: akshare (HTTP)             ← 最终兜底，10s 超时斩杀
```

### 限流与熔断

```python
# 限流：令牌桶 + 随机抖动
- 东财 API 间隔 ≥ 1s
- 封禁阈值：>5次/秒, ≥10并发, ≥200次/分

# 熔断：连续失败自动冷却
- MX: 3 次失败 → 冷却 1 分钟
- 腾讯: 5 次失败 → 冷却 5 分钟
- 东财: 3 次失败 → 冷却 10 分钟

# akshare 超时斩杀
- _AKSHARE_TIMEOUT = 10.0
- 超时抛 DataError，不阻塞主线程
```

---

## 9 大场景调用链速查

| 场景 | 调用链 |
|---|---|
| ①查询个股 | market_data → fund_flow → news → sentiment → check_constraints |
| ②持仓网格 | portfolio → trading+nav → market_data → check_constraints |
| ③选股 | sentinel → valuation → dragon_tiger+northbound → news+sentiment → research |
| ④复盘 | reconcile → portfolio+nav → performance+benchmark |
| ⑤归因进化 | review → evolution → 【人工复核】 → strategy |
| ⑥沙盒研发 | run_backtest → trading_friction → grayscale |
| ⑦AI查岗 | get_ai_tracking → agent_tracking → team_tool |
| ⑧极端干预 | data_quality → 【逐项定位】→ update_portfolio |
| ⑨系统重置 | discover_workspace → investor → orchestrator |

> 详见 [[docs/SOP_INDEX.md (附录)_v4.0]]

---

## 合并工具使用示例

```python
# 查询交易记录
trading_tool(action="ledger", ticker="000001")

# 添加交易记录
trading_tool(action="add", ticker="000001", trade_action="buy", quantity=200, price=13.38)

# 执行哨兵扫描
sentinel_tool(action="scan")

# 获取净值历史
nav_tool(action="history", investor="demo", portfolio="core", days=30)

# 级联复盘（月度）
cascade_review_tool(mode="monthly", period="2026-06")

# 编排器 — 生成成员 Prompt
orchestrator_tool(action="member_prompt", team="asrg", member_id="ethan", ticker="000001", model_hint="quick")

# 记录 Agent 决策
agent_tracking_tool(action="record", agent_id="reasonix", ticker="000001", decision_action="buy", confidence=0.8, reasoning="缩量企稳")

# 自动回填复盘
review_tool(action="fill")
```

---

## 相关链接

- [[00-系统全景]] — 系统架构总览
- [[02-AI投研团队]] — 编排器与模型路由详情
- [[03-自动化闭环]] — 断点续传与延迟反思
- [[12-CLI命令手册]] — CLI 对应命令

---

#MCP工具 #接口 #v4.0 #单工具串行
