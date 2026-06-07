# PRAXIS 测试覆盖率提升设计

> **设计日期**: 2026-06-06  
> **设计目标**: 将测试覆盖率从 46% 提升到 70%+  
> **策略**: 核心模块优先，分 3 批实施

---

## 一、背景

当前 PRAXIS V1.1 测试覆盖率为 **46%**，有 **88 个模块**覆盖率低于 50%。其中 **10 个核心模块**覆盖率为 0%，需要优先补充测试。

### 覆盖率 0% 的核心模块

| 模块 | 重要性 | 说明 |
|------|:------:|------|
| `execution/fee_model.py` | P0 | 费用模型，交易成本计算 |
| `execution/slippage_model.py` | P0 | 滑点模型，交易成本计算 |
| `execution/trading_calendar.py` | P0 | 交易日历，T+1 规则 |
| `backtest.py` | P0 | 回测引擎，策略验证 |
| `review_filler.py` | P0 | 复盘回填，决策复盘 |
| `grayscale.py` | P1 | 灰度发布，策略进化 |
| `version_compare.py` | P1 | 版本对比，策略对比 |
| `prompt_scanner.py` | P1 | Prompt 安全扫描 |
| `prompt_composer.py` | P1 | Prompt 组合器 |
| `prompt_change_recorder.py` | P1 | Prompt 变更记录 |

---

## 二、设计方案

### 方案选择：按模块分批补充（方案 A）

**理由**：
1. 风险可控：每批完成后都有明确收益
2. 优先级清晰：先补充 P0 核心模块，再补充 P1 重要模块
3. 便于验证：每批完成后可以运行测试验证
4. 时间灵活：可以根据实际情况调整节奏

---

## 三、第 1 批：P0 核心模块测试

### 3.1 test_fee_model.py - 费用模型测试

**测试类结构**：

```python
class TestAShareFeeCalculator:
    """A 股费用计算器测试"""
    
    def test_buy_commission(self):
        """测试买入佣金计算"""
        
    def test_sell_commission(self):
        """测试卖出佣金计算"""
        
    def test_minimum_commission(self):
        """测试最低佣金（5元）"""
        
    def test_stamp_tax_buy(self):
        """测试买入无印花税"""
        
    def test_stamp_tax_sell(self):
        """测试卖出有印花税"""
        
    def test_transfer_fee(self):
        """测试过户费计算"""
        
    def test_etf_fee(self):
        """测试 ETF 费用（无印花税）"""
        
    def test_offshore_fund_fee(self):
        """测试场外基金费用（申购/赎回）"""


class TestOffshoreFundFeeCalculator:
    """场外基金费用计算器测试"""
    
    def test_subscribe_fee(self):
        """测试申购费"""
        
    def test_redeem_fee_short(self):
        """测试短期赎回费（< 7天）"""
        
    def test_redeem_fee_long(self):
        """测试长期赎回费（> 30天）"""
```

**预期测试数**：12 个

---

### 3.2 test_slippage_model.py - 滑点模型测试

**测试类结构**：

```python
class TestSlippageCalculator:
    """滑点计算器测试"""
    
    def test_buy_slippage(self):
        """测试买入滑点（价格上升）"""
        
    def test_sell_slippage(self):
        """测试卖出滑点（价格下降）"""
        
    def test_large_order_slippage(self):
        """测试大单滑点增加"""
        
    def test_slippage_amount(self):
        """测试滑点金额计算"""
        
    def test_slippage_pct(self):
        """测试滑点比例计算"""
```

**预期测试数**：5 个

---

### 3.3 test_trading_calendar.py - 交易日历测试

**测试类结构**：

```python
class TestTradingCalendar:
    """交易日历测试"""
    
    def test_is_trading_day_weekday(self):
        """测试工作日是交易日"""
        
    def test_is_trading_day_weekend(self):
        """测试周末不是交易日"""
        
    def test_is_trading_day_holiday(self):
        """测试节假日不是交易日"""
        
    def test_next_trading_day(self):
        """测试获取下一个交易日"""
        
    def test_next_trading_day_skip_weekend(self):
        """测试跳过周末"""
        
    def test_next_trading_day_skip_holiday(self):
        """测试跳过节假日"""
        
    def test_settlement_date_t1(self):
        """测试 T+1 交割日"""
```

**预期测试数**：7 个

---

### 3.4 test_backtest.py - 回测引擎测试

**测试类结构**：

```python
class TestSimpleBacktestEngine:
    """简单回测引擎测试"""
    
    def test_run_backtest_basic(self):
        """测试基本回测"""
        
    def test_run_backtest_with_nav(self):
        """测试带净值数据的回测"""
        
    def test_run_backtest_with_benchmark(self):
        """测试带基准对比的回测"""
        
    def test_calculate_metrics(self):
        """测试绩效指标计算"""
        
    def test_calculate_max_drawdown(self):
        """测试最大回撤计算"""
        
    def test_calculate_sharpe_ratio(self):
        """测试夏普比率计算"""
```

**预期测试数**：6 个

---

### 3.5 test_review_filler.py - 复盘回填器测试

**测试类结构**：

```python
class TestReviewFiller:
    """复盘回填器测试"""
    
    def test_fill_pending_reviews(self):
        """测试回填待复盘决策"""
        
    def test_fill_5d_review(self):
        """测试 5 日复盘回填"""
        
    def test_fill_20d_review(self):
        """测试 20 日复盘回填"""
        
    def test_fill_60d_review(self):
        """测试 60 日复盘回填"""
        
    def test_get_review_summary(self):
        """测试获取复盘汇总"""
        
    def test_calculate_return(self):
        """测试收益率计算"""
```

**预期测试数**：6 个

---

### 第 1 批总结

| 测试文件 | 测试数 | 覆盖模块 |
|---------|:------:|---------|
| test_fee_model.py | 12 | 费用模型 |
| test_slippage_model.py | 5 | 滑点模型 |
| test_trading_calendar.py | 7 | 交易日历 |
| test_backtest.py | 6 | 回测引擎 |
| test_review_filler.py | 6 | 复盘回填器 |
| **总计** | **36** | — |

**预期覆盖率提升**：从 46% 提升到约 55%

---

## 四、第 2 批：P1 重要模块测试

### 4.1 test_grayscale.py - 灰度发布测试

**测试类结构**：

```python
class TestStrategyGrayscale:
    """策略灰度发布测试"""
    
    def test_prepare_grayscale(self):
        """测试准备灰度发布"""
        
    def test_approve_grayscale(self):
        """测试审批灰度发布"""
        
    def test_grayscale_config(self):
        """测试灰度配置"""
```

**预期测试数**：5 个

---

### 4.2 test_version_compare.py - 版本对比测试

**测试类结构**：

```python
class TestVersionComparer:
    """版本对比测试"""
    
    def test_compare_versions(self):
        """测试版本对比"""
        
    def test_calculate_diff(self):
        """测试差异计算"""
```

**预期测试数**：4 个

---

### 4.3 test_prompt_scanner.py - Prompt 安全扫描测试

**测试类结构**：

```python
class TestPromptScanner:
    """Prompt 安全扫描测试"""
    
    def test_scan_safe_prompt(self):
        """测试安全 Prompt"""
        
    def test_scan_unsafe_prompt(self):
        """测试不安全 Prompt"""
        
    def test_detect_injection(self):
        """测试注入攻击检测"""
        
    def test_detect_dangerous_patterns(self):
        """测试危险模式检测"""
```

**预期测试数**：6 个

---

### 4.4 test_prompt_composer.py - Prompt 组合器测试

**测试类结构**：

```python
class TestPromptComposer:
    """Prompt 组合器测试"""
    
    def test_compose_base_prompt(self):
        """测试基础 Prompt 组合"""
        
    def test_compose_strategy_prompt(self):
        """测试策略 Prompt 组合"""
        
    def test_compose_investor_prompt(self):
        """测试投资者 Prompt 组合"""
```

**预期测试数**：5 个

---

### 第 2 批总结

| 测试文件 | 测试数 | 覆盖模块 |
|---------|:------:|---------|
| test_grayscale.py | 5 | 灰度发布 |
| test_version_compare.py | 4 | 版本对比 |
| test_prompt_scanner.py | 6 | Prompt 安全扫描 |
| test_prompt_composer.py | 5 | Prompt 组合器 |
| **总计** | **20** | — |

**预期覆盖率提升**：从 55% 提升到约 60%

---

## 五、第 3 批：覆盖率提升

### 5.1 补充已有测试的边界场景

- 补充 `test_ledger.py` 的异常路径测试
- 补充 `test_decision.py` 的边界场景测试
- 补充 `test_evolution.py` 的异常路径测试

### 5.2 补充 MCP 工具测试

- 补充 `test_teams.py` - 团队管理工具测试
- 补充 `test_review.py` - 复盘工具测试
- 补充 `test_grayscale.py` - 灰度发布工具测试

### 第 3 批总结

**预期测试数**：20 个  
**预期覆盖率提升**：从 60% 提升到约 70%

---

## 六、总体计划

| 批次 | 测试数 | 覆盖率目标 | 优先级 |
|:----:|:------:|:----------:|:------:|
| 第 1 批 | 36 | 55% | P0 |
| 第 2 批 | 20 | 60% | P1 |
| 第 3 批 | 20 | 70% | P2 |
| **总计** | **76** | **70%** | — |

---

## 七、验收标准

### 7.1 测试质量标准

- 每个测试函数有清晰的 docstring
- 测试覆盖正常路径、边界场景、异常路径
- 测试数据使用 mock 或 fixture，不依赖真实数据
- 测试可独立运行，不依赖执行顺序

### 7.2 覆盖率标准

- 核心模块（execution/、backtest、review_filler）覆盖率 > 80%
- 重要模块（grayscale、version_compare、prompt_*）覆盖率 > 70%
- 整体覆盖率 > 70%

### 7.3 验收流程

1. 每批完成后运行 `pytest tests/ -v`
2. 检查覆盖率报告 `pytest --cov=praxis`
3. 确认所有测试通过
4. 更新文档

---

## 八、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 测试数据依赖 | 测试不稳定 | 使用 mock 和 fixture |
| 模块耦合 | 测试困难 | 使用依赖注入 |
| 时间不足 | 进度延迟 | 优先完成 P0 模块 |

---

**设计完成，准备实现！**
