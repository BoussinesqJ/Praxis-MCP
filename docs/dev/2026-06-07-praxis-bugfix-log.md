# Praxis MCP Bug 修复记录

> **修复日期**: 2026-06-07
> **修复人**: AI Agent (Reasonix) + 用户实时协同
> **关联测试报告**: `2026-06-06-praxis-mcp-real-test-report.md`、`2026-06-07-praxis-mcp-test-round2.md`

---

## 修复清单

### Bug 1：腾讯行情 API 302 重定向（HTTPS 升级）🔴

**现象**：
```
get_benchmark_data_tool("000300") → "获取指数K线失败: Redirect response '302 Moved Temporarily'"
```

**根因**：腾讯财经 API 强制升级 HTTPS，Praxis 中 5 处 URL 仍使用 `http://`。

**修复**：

| 文件 | 行号 | 修改前 | 修改后 |
|:---|:---:|:---|:---|
| `praxis/engine/data/benchmark.py` | 36 | `http://qt.gtimg.cn` | `https://qt.gtimg.cn` |
| `praxis/engine/data/benchmark.py` | 37 | `http://web.ifzq.gtimg.cn` | `https://web.ifzq.gtimg.cn` |
| `praxis/engine/data/realtime.py` | 34 | `http://qt.gtimg.cn` | `https://qt.gtimg.cn` |
| `praxis/engine/data/realtime.py` | 35 | `http://web.ifzq.gtimg.cn` | `https://web.ifzq.gtimg.cn` |
| `praxis/engine/data/realtime.py` | 36 | `http://qt.gtimg.cn` | `https://qt.gtimg.cn` |

**验证方式**：重启 MCP → 调用 `get_benchmark_data_tool("000300")` → 应返回 K 线数据

**影响范围**：所有依赖腾讯行情的工具（get_benchmark_data、get_market_data、get_nav_snapshot）

---

### Bug 2：6/1 南网储能减仓交易未录入 Praxis 🔴

**现象**：
```
get_performance_tool(exclude_tags=["opening","migration"])
→ sell_count: 0, realized_pnl: 0  (应为 1 笔卖出，利润 203.20 元)
```

**根因**：初始化时只录入了 opening positions（买入），未录入后续的实盘交易（6/1 减仓 100 股 @16.35）。

**修复**：补录两笔交易（买+卖配对，tag: `real`）：

| tx_id | 类型 | 标的 | 数量 | 价格 | 标签 | 说明 |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| tx-20260607-002 | buy | 600995 | 100 | 14.318 | `["real"]` | 原始建仓第1批，与卖出配对 |
| tx-20260607-001 | sell | 600995 | 100 | 16.35 | `["real"]` | 6/1 手动止盈减仓 |

**验证**：
```
get_performance_tool(exclude_tags=["opening","migration"])
→ realized_pnl: ¥203.20 ✅
→ win_rate: 100% ✅
→ buy_count: 1, sell_count: 1 ✅
```

---

### Bug 3：绩效 tag 隔离导致买卖配对断裂 🟡

**现象**：排除 `opening`/`migration` 标签后，卖出记录（tag: `real`）没有对应的买入记录（tag: `opening`），导致 Praxis 将全部卖出收入（¥1,635）当作已实现利润。

**修复**：为配对的买入交易补录相同的 `real` 标签，确保买卖在同一 tag 分组中。

**教训**：标签体系设计时需明确：
- `opening`：初始化导入的开仓记录，非真实交易
- `migration`：同上，数据迁移用途
- `real`：真实实盘交易（有对应的买卖配对）
- `test`：测试数据，绩效计算时排除

---

### Bug 4：双 Workspace 路径混乱（第一轮发现）🔴

**现象**：MCP 的 `WORKSPACE` 指向 `<OLD_WORKSPACE>`，但实际代码和配置在 `<WORKSPACE>`。

**修复**：用户在 MCP 配置中修正了 `PRAXIS_WORKSPACE` 环境变量指向 `Portfolio vault`。

**验证**：
```
discover_workspace_tool()
→ workspace: "<WORKSPACE>" ✅
```

---

### Bug 5：`get_team_prompt_tool` 返回内容过短（第二轮发现）🔴

**现象**：`compose_team_prompt_tool("asrg")` 仅返回 174 字节的策略上下文片段，缺少完整的 7 人团队框架。

**根因**：`teams/` 目录下的 prompt md 文件未被正确加载。

**修复**：用户修复了 prompt 加载逻辑。修复后返回 10,375 字节，包含：
- 安全守则 + 角色定义 + 工具权限
- ASRG 7 位成员完整档案
- 6 套 Workflow 定义
- 策略框架 + 投资者画像

**验证**：
```
compose_team_prompt_tool("asrg") → length: 10375 ✅
```

---

## 修复后 Praxis 完整功能矩阵

| 功能模块 | 状态 | 说明 |
|:---|:---:|:---|
| Workspace 自动发现 | ✅ | `discover_workspace_tool` 零参数工作 |
| 投资者/组合管理 | ✅ | profile.yaml + portfolio.yaml 正确读取 |
| 交易账本 | ✅ | 6 笔记录（4 opening + 2 real），tag 隔离正确 |
| 绩效计算 | ✅ | 已实现盈亏 ¥203.20，胜率 100% |
| 策略合规检查 | ✅ | 5 条规则全功能 |
| 团队 Prompt | ✅ | ASRG/Masters/Trading 完整加载 |
| 场内行情 | ✅ | 通过 Baostock 获取 |
| 场外基金净值 | ✅ | 016874 现价 1.9456 |
| 基准指数 | ⏳ | 已修复代码，需重启 MCP 验证 |
| NAV 净值记录 | ⏳ | `record_nav_tool` Optional 参数 bug 未复测 |
| 策略模板 | ✅ | `grid_value.yaml` 已创建 |

---

## Tag 使用规范（建议）

```
add_transaction_tool(..., tags=["real"])      → 真实实盘交易（参与绩效计算）
add_transaction_tool(..., tags=["opening"])   → 初始化导入的开仓记录（绩效排除）
add_transaction_tool(..., tags=["migration"]) → 数据迁移记录（绩效排除）
add_transaction_tool(..., tags=["test"])      → 测试数据（绩效排除）

get_performance_tool(exclude_tags=["opening","migration","test"])
→ 只计算 "real" 标签的交易绩效
```
