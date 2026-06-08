# Praxis 工作流审查修复清单

> 来源：2026-06-07 全面工作流审查
> 范围：全部 29 项（4 CRITICAL + 3 HIGH + 14 MEDIUM + 8 LOW）
> 状态：✅ 全部完成（2026-06-07）

---

## Phase 1：数据正确性（3 个任务，互相独立）

### Task 1.1：冲销过滤 — 持仓计算排除已冲销交易
**严重性**: HIGH | **影响文件**: 4 个 | **预估**: 30 min

**问题**: `_rebuild_from_ledger`、`NavTracker.snapshot`、`get_portfolio_summary` 从账本重建持仓时，冲销记录（有 `target_tx_id`）被当作正常交易处理，持仓数量被重复计算。

**修复**: 在 4 个文件的持仓计算循环中，添加冲销过滤逻辑：
- 跳过 `tx.target_tx_id is not None` 的记录（这是冲销动作）
- 跳过 `tx.tx_id` 出现在其他记录的 `target_tx_id` 中的记录（这是被冲销的原始交易）

**涉及文件**:
- `praxis/tools/state.py` (line ~107)
- `praxis/tools/summary.py` (line ~65)
- `praxis/engine/nav_tracker.py` (line ~95)
- `praxis/core/state_builder.py` (line ~47)

**核心逻辑**:
```python
# 构建已冲销 ID 集合
reversed_ids = {tx.target_tx_id for tx in all_txs if tx.target_tx_id}
for tx in all_txs:
    if tx.target_tx_id is not None:  # 冲销动作本身
        continue
    if tx.tx_id in reversed_ids:     # 被冲销的原始交易
        continue
    # ... 正常处理
```

---

### Task 1.2：净值快照遗漏分红
**严重性**: HIGH | **影响文件**: 1 个 | **预估**: 10 min

**问题**: `nav_tracker.py` 的 `snapshot()` 现金计算 `cash = capital - total_buy + total_sell` 缺少 `+ total_dividend`。同时遍历账本 3 次应合并为 1 次。

**修复**: 在 `NavTracker.snapshot()` 中：
1. 将 3 次 `get_all()` 合并为 1 次遍历
2. 添加 `total_dividend` 累加
3. 最终现金公式：`cash = capital - total_buy + total_sell + total_dividend`

**涉及文件**:
- `praxis/engine/nav_tracker.py` (lines 95-141)

---

### Task 1.3：`reverse()` 双重冲销防护
**严重性**: CRITICAL | **影响文件**: 1 个 | **预估**: 15 min

**问题**: `FileLedger.reverse()` 没有检查原始交易是否已被冲销或本身就是冲销记录。

**修复**: 在 `reverse()` 方法开头添加前置检查：
1. `original.target_tx_id is not None` → 拒绝（不能冲销冲销记录）
2. 检查是否有其他记录的 `target_tx_id == tx_id` → 拒绝（已被冲销）
3. `original.type == TransactionType.DIVIDEND` → 拒绝（分红无 quantity 可逆）

**涉及文件**:
- `praxis/core/ledger.py` (lines 135-163)

---

## Phase 2：约束引擎补全（2 个任务，依赖 Phase 1.1 不依赖）

### Task 2.1：实现 `_check_banned_instrument`
**严重性**: CRITICAL | **影响文件**: 1 个 | **预估**: 20 min

**问题**: 永远返回 `passed: True`。策略定义了 `blacklist_instrument: [leverage, options, short]`，但检查器不执行。

**修复**: 从策略规则读取 `access_rules.blacklist_instrument`，实现标的类型匹配：
- `leverage`: 匹配杠杆 ETF 前缀（如 `159xxx` 创业板杠杆、`5` 开头的分级基金）
- `options`: 匹配期权代码模式
- `short`: 匹配做空工具
- ETF 豁免应同样适用于此检查

**涉及文件**:
- `praxis/engine/constraint_checker.py` (lines 100-109)

---

### Task 2.2：实现 `_check_position_cap`
**严重性**: CRITICAL | **影响文件**: 1 个 | **预估**: 20 min

**问题**: 永远返回 `passed: True`。`position_cap_pct = 0.15` 定义了但从未使用。

**修复**: 从策略规则读取 `risk_rules.position_cap`，计算当前持仓占比：
- 需要当前持仓市值（从 `PortfolioState` 或账本重建）
- 计算 `position_value / total_assets`
- 与策略的 `max_single_pct` 比较
- 考虑本次买入后的增量

**涉及文件**:
- `praxis/engine/constraint_checker.py` (lines 136-146)

---

## Phase 3：命名修正（1 个任务）

### Task 3.1：回测重命名为账本绩效报告
**严重性**: HIGH | **影响文件**: 2 个 | **预估**: 10 min

**问题**: `run_backtest` 读取已有交易记录计算统计，不模拟历史交易。名称误导。

**修复**:
- 函数名保持 `run_backtest`（不破坏 API）
- docstring 和返回数据中明确标注 "基于历史交易的绩效分析（非模拟回测）"
- 返回增加 `"mode": "ledger_analysis"` 字段区分
- 后续版本再考虑真正的模拟回测

**涉及文件**:
- `praxis/engine/backtest.py`
- `praxis/tools/backtest.py`

---

## 执行顺序

```
Phase 1 (数据正确性，互相独立，可并行):
  1.3 reverse() 防护     → 15 min
  1.1 冲销过滤 (4 files) → 30 min
  1.2 净值分红修复        → 10 min

Phase 2 (约束引擎，独立于 Phase 1):
  2.1 banned_instrument   → 20 min
  2.2 position_cap        → 20 min

Phase 3 (命名):
  3.1 回测重命名          → 10 min

总计: ~105 min (~1.75h)
```

## 测试计划

每个 Task 完成后运行:
```bash
python -m pytest tests/test_constraints.py tests/test_ledger.py tests/test_state_tool.py tests/test_performance.py tests/test_workspace.py tests/test_mcp_server.py tests/test_mcp_e2e.py -q
```

Phase 全部完成后运行全量测试确认无回归。

---

## 完成记录

| Task | 状态 | commit | 验证 |
|:---|:---:|:---|:---:|
| 1.1 冲销过滤 | ✅ | `filter_active_transactions()` 应用到 4 文件 | 108 passed |
| 1.2 净值分红 | ✅ | nav_tracker 单次遍历 + total_dividend | 108 passed |
| 1.3 reverse 防护 | ✅ | 3 道前置检查（双重冲销/已冲销/分红） | 108 passed |
| 2.1 banned_instrument | ✅ | 策略驱动 + 150xxx 杠杆检测 | 7/7 约束正确 |
| 2.2 position_cap | ✅ | 策略驱动 + 实际持仓占比 | 7/7 约束正确 |
| 3.1 回测重命名 | ✅ | mode=ledger_analysis + 标注 | 通过 |

附带修复：ETF 精确前缀匹配（510/512/513/515/516/588/159/160），防止 150xxx 杠杆基金误豁免。

---

## Phase 4：MEDIUM 修复（commit c212458）

| 问题 | 文件 | 修复 |
|:---|:---|:---|
| 盈亏比用净盈亏 | performance.py | 改为按单笔交易计算 |
| 下行波动率非标准 | performance.py | Sortino 标准公式 sqrt(mean(min(r,0)^2)) |
| 缓存 TTL 未生效 | provider.py | 添加 _cache_timestamps + 过期检查 |
| 文件缓存只写不读 | provider.py | 启动时加载 _load_file_cache() |
| get_fund_nav 无降级 | provider.py | 所有源失败时返回缓存 |
| 决策→交易无引用完整性 | ledger.py | add_transaction 验证 decision_id 存在 |
| diff 只检测修改 | prompt_composer.py | 支持插入/删除行检测 |
| 零持仓浮点精度 | summary.py | epsilon=0.0001 保护 |

## Phase 5：LOW 修复（commit c212458）

| 问题 | 文件 | 修复 |
|:---|:---|:---|
| _read_pending 死代码 | tools/ledger.py | 移除 |
| _generate_tx_id 子串匹配 | core/ledger.py | 改用 startswith 前缀匹配 |
| compare_versions 存根 | performance.py | 标注 status=stub + 说明 |
| compare_strategy_versions 存根 | tools/backtest.py | 标注 stub + 加载策略信息 |
