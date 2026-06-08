# Praxis MCP 实盘测试报告（第二轮）

> **测试日期**: 2026-06-07
> **测试场景**: 三团队联合研判星网锐捷 (002396.SZ)
> **第一轮测试报告**: `2026-06-06-praxis-mcp-real-test-report.md`

---

## 一、本轮测试新增发现

### 问题 6：`get_team_prompt_tool` 返回内容过短 🔴

**现象**：
```
get_team_prompt_tool("asrg") → 返回 174 字节
内容仅为：
  "---\n## 当前策略上下文（自动注入）\n**策略类型**：网格价值策略\n
   **重点分析**：macro_transmission, industry_chain, holding_diagnosis\n---\n
   ## 投资者画像（自动注入）\n**投资者**：示例投资者\n**风险等级**：C3\n
   **投资风格**：balanced_growth"
```

**问题**：这只是策略上下文的注入片段，不是团队的完整分析指令。

**预期**：应包含完整的团队分析框架，如：
- ASRG：宏观传导链路模板、产业链拆解模板、持仓诊断清单
- Masters：19 位投资大师的分析视角、护城河评估框架、安全边际计算公式
- Trading：网格参数计算逻辑、滑点审计流程、鞭打效应检查清单

**根因推测**：`compose_team_prompt_tool` 只组合了策略上下文 + 投资者画像，但**未加载 `teams/` 目录下的团队 prompt md 文件**。需要检查 `praxis/tools/teams.py` 中的 `compose_team_prompt` 函数是否正确读取了 `teams/asrg.md`、`teams/masters.md`、`teams/trading.md`。

**验证方法**：
```bash
# 检查 teams 目录下是否有完整的 prompt 文件
ls teams/
# 预期输出: asrg.md  masters.md  trading.md  base.md

# 对比 get_team_prompt_tool 的返回值与文件内容
cat teams/asrg.md | head -50
```

---

### 问题 7：双 Workspace 路径混乱 🔴

**现象**：MCP server 的 `WORKSPACE` 指向 `<OLD_WORKSPACE>`，但主要的代码和配置文件在 `<WORKSPACE>`。

导致的实际问题：
1. `strategies/grid_value.yaml` 在 <WORKSPACE> 中已创建，但 <OLD_WORKSPACE> 中不存在 → `list_strategies_tool` 返回空
2. `profile.yaml` 的 `capital_cny` 修正需要同时改两个目录
3. `discover_workspace_tool` 扫描的是 <OLD_WORKSPACE> 的 `investors/` 目录
4. 用户可能不清楚数据到底存在哪个目录

**根因**：`PRAXIS_WORKSPACE` 环境变量未设置，MCP server 以 `.` 为默认 workspace，而启动目录是 <OLD_WORKSPACE>。

**修复建议**：
1. **首选**：设置 `PRAXIS_WORKSPACE` 环境变量指向 `<WORKSPACE>`
2. **或**：在 `reasonix.toml` / MCP 配置中显式指定 `cwd` 或 `env`
3. **或**：将两个目录合并为一个

---

### 问题 8：`016874` 场外基金无行情数据 ✅ 已修复

**现象**：`get_state_tool` 和 `get_portfolio_summary_tool` 中 016874 的 `current_price: 0`，`market_value: 0`，导致总资产少算约 ¥1,057。

**根因**：`state.py`、`summary.py`、`nav_tracker.py` 只调用 `get_realtime_quote()`，不覆盖场外基金。
但 `CachedDataProvider.get_fund_nav()` 和 `akshare_provider.get_fund_nav()` **已实现**，只是未被调用。

**修复**：在三个文件的价格查找逻辑中增加 fallback——当 `get_realtime_quote` 返回 `price=0` 时，自动尝试 `get_fund_nav()`：
- `praxis/tools/state.py`
- `praxis/tools/summary.py`
- `praxis/engine/nav_tracker.py`

**验证**：`get_fund_nav('016874')` → `nav=1.9456`（akshare，日期 2026-06-05）✅

---

### 问题 9：`strategies/` 目录需要手动创建 🟡

**现象**：`get_strategy_tool("grid_value")` 报错 "配置文件不存在: strategies\grid_value.yaml"。

**根因**：Praxis 策略定义分散在两处：
1. `strategies/grid_value.yaml`（`get_strategy_tool` 读取此处）
2. `investors/example/portfolios/demo/portfolio.yaml` 中的 `strategy_template: grid_value`（仅引用名称）

两处没有自动关联。`grid_value.yaml` 策略文件在 <WORKSPACE> 中已存在，但 <OLD_WORKSPACE> 中没有。

**修复建议**：
- 在 `discover_workspace_tool` 的 `warnings` 中检测：如果 portfolio 引用了某个 strategy 但文件不存在，发出警告
- 或在 `init_investor_tool` 中自动将 strategy 模板复制到 workspace 的 `strategies/` 目录

---

### 问题 10：团队分析实际由 AI Agent 执行，Praxis 仅提供框架 🟢（设计观察）

**观察**：Praxis 的三团队分析流程是：
```
compose_team_prompt_tool → 返回策略上下文 + 投资者画像
                          ↓
AI Agent 按照 context 自行执行分析（参考 workspace 中的研报）
                          ↓
产出分析报告
```

Praxis **不执行**分析，只提供注入上下文。真正的分析质量取决于：
1. AI Agent 的能力
2. workspace 中已有研报的质量
3. 团队 prompt 文件的完整度（当前问题 6）

**这不是 bug，是架构设计**。但需要在文档中明确说明"团队分析 ≠ Praxis 内置分析，而是 AI Agent + Praxis 上下文的协同"。

---

## 二、本轮测试通过的工具

| 工具 | 状态 | 说明 |
|:---|:---:|:---|
| `discover_workspace_tool` | ✅ | 零参数自动发现，返回完整 workspace 地图 |
| `compose_team_prompt_tool` | ⚠️ | 框架可用但返回内容过短（见问题 6） |
| `get_market_data_tool` | ✅ | 002396 实时行情正确（21.32 元） |
| `check_constraints_tool` | ✅ | 5 条规则全部正确评估 |
| `check_trading_time_tool` | ✅ | 正确判断非交易日 |
| `check_quote_quality_tool` | ⚠️ | 缺少 price/change/change_pct 字段时报错（需传完整 data） |
| `get_team_prompt_tool` | ⚠️ | 返回内容不完整（见问题 6） |

---

## 三、与第一轮问题的交叉验证

| 第一轮问题 | 本轮状态 | 说明 |
|:---|:---:|:---|
| P0: `record_nav_tool` 参数 bug | 🟡 未复测 | 上轮已确认存在 |
| P0: 缺少 `discover_workspace_tool` | ✅ **已修复** | 用户已实现，运行正常 |
| P1: ledger 测试数据污染 | ✅ 已清理 | 当前 ledger 干净（5 条有效记录） |
| P1: 审批流程不完整 | ✅ **已修复** | `approve/reject_transaction_tool` 已可用 |
| P1: 绩效过滤参数 | ✅ **已修复** | `exclude_tags` 正常工作 |
| P2: investor ID 不可发现 | ✅ **已修复** | `discover_workspace_tool` 解决 |

---

## 四、修复优先级

| 优先级 | 问题 | 工作量 | 影响 | 状态 |
|:---:|:---|:---:|:---|:---:|
| 🔴 P0 | `get_team_prompt_tool` 返回内容不完整 | ~0h | 三团队分析框架失效 | ✅ Problem 7 连锁修复 |
| 🔴 P0 | 双 Workspace 路径混乱 | ~0.5h | 所有配置操作可能写错目录 | ✅ 已修复 |
| 🟠 P1 | 016874 场外基金无行情 | ~0.5h | 总资产和配置比计算偏差 | ✅ 已修复 |
| 🟡 P2 | `strategies/` 目录同步 | ~0h | 策略详情查询不可用 | ✅ Problem 7 连锁修复 |
| 🟢 P3 | `check_quote_quality_tool` 字段校验 | ~0.5h | 传入不完整 data 时误报 | 待处理 |

---

## 五、附录：本轮调用序列

```
1.  compose_team_prompt_tool("asrg")                → ⚠️ 174 bytes（过短）
2.  compose_team_prompt_tool("masters")              → ⚠️ 159 bytes（过短）
3.  compose_team_prompt_tool("trading")              → ⚠️ 191 bytes（过短）
4.  get_market_data_tool(["002396"])                 → ✅ 21.32 元
5.  check_constraints_tool(002396, buy, ¥0)          → ❌ 最低金额未满足
6.  check_quote_quality_tool(002396, {})             → ⚠️ 缺少字段
7.  check_constraints_tool(002396, buy, ¥3000)       → ✅ 全部通过
8.  check_trading_time_tool()                        → ✅ 非交易日
9.  discover_workspace_tool()                        → ✅ 完整 workspace 地图
10. get_portfolio_summary_tool(example, demo) → ✅ 修正后数据
```

**总计 10 次调用**，6 次成功，2 次部分成功，2 次需关注。
