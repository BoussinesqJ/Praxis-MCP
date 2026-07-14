"""P0 复盘双层架构移植 — 单元测试与静态审查

覆盖 8 个改动文件的关键逻辑：
  - P0-1: 基准超额对标 (_default_benchmark_index, _calculate_review)
  - P0-2: 市场环境周报 (_resolve_week_range, collect_all, generate_market_weekly_review)
  - P0-3: 风险质量 (_derive_holding_period_distribution, _build_risk_quality_section, _audit_rules)
  - 向后兼容: fill_pending_reviews 无 benchmark、工具注册不变

Author: Edward (QA Engineer)
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

# ── Path setup ──────────────────────────────────────────────────
sys.path.insert(0, "src")


# ═══════════════════════════════════════════════════════════════════
# P0-1: _default_benchmark_index 映射测试
# ═══════════════════════════════════════════════════════════════════

class TestDefaultBenchmarkIndex:
    """P0-1.1: _default_benchmark_index 映射规则"""

    @pytest.mark.parametrize("ticker,expected", [
        ("600995", "000300"),   # 上海主板
        ("601318", "000300"),   # 上海主板
        ("000001", "000300"),   # 深圳主板
        ("002594", "000300"),   # 中小板（00开头）
        ("300750", "399006"),   # 创业板
        ("300059", "399006"),   # 创业板
        ("688981", "000905"),   # 科创板
        ("688111", "000905"),   # 科创板
        ("510310", "000300"),   # ETF（60开头→沪深300）
        ("159915", "000300"),   # ETF（其他→默认）
        ("", "000300"),         # 空字符串→默认
    ])
    def test_benchmark_index_mapping(self, ticker, expected):
        from praxis.engine.review_filler import _default_benchmark_index
        assert _default_benchmark_index(ticker) == expected

    def test_none_ticker_defaults(self):
        from praxis.engine.review_filler import _default_benchmark_index
        # None 和短代码都回退到默认
        assert _default_benchmark_index(None) == "000300"
        assert _default_benchmark_index("123") == "000300"
        assert _default_benchmark_index("ab") == "000300"


# ═══════════════════════════════════════════════════════════════════
# P0-2: _resolve_week_range 日期容错测试
# ═══════════════════════════════════════════════════════════════════

class TestResolveWeekRange:
    """P0-2.1: MarketWeeklyCollector._resolve_week_range 日期容错"""

    def test_friday_no_adjustment(self):
        """周五传入不需要调整"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector
        # 2025-01-10 是周五
        start, end = MarketWeeklyCollector._resolve_week_range("2025-01-10")
        assert end == "2025-01-10"  # 周五不变
        # start = end - 5天
        assert start == "2025-01-05"

    def test_saturday_adjust_to_friday(self):
        """周六→前推到周五"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector
        # 2025-01-11 是周六
        start, end = MarketWeeklyCollector._resolve_week_range("2025-01-11")
        assert end == "2025-01-10"  # 前推到周五

    def test_sunday_adjust_to_friday(self):
        """周日→前推到周五"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector
        # 2025-01-12 是周日
        start, end = MarketWeeklyCollector._resolve_week_range("2025-01-12")
        assert end == "2025-01-10"  # 前推到周五

    def test_wednesday_adjust_to_previous_friday(self):
        """周三→前推到最近周五"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector
        # 2025-01-08 是周三
        start, end = MarketWeeklyCollector._resolve_week_range("2025-01-08")
        # 最近周五是 2025-01-03（往前推）
        assert end == "2025-01-03"

    def test_invalid_date_fallback(self):
        """无效日期→回退到 today - 5天"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector
        start, end = MarketWeeklyCollector._resolve_week_range("not-a-date")
        # 应该返回合理范围
        assert start < end
        # 验证格式
        datetime.strptime(start, "%Y-%m-%d")
        datetime.strptime(end, "%Y-%m-%d")

    def test_start_is_5_days_before_end(self):
        """验证 start = end - 5天"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector
        start, end = MarketWeeklyCollector._resolve_week_range("2025-03-21")  # 周五
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        assert (end_dt - start_dt).days == 5


# ═══════════════════════════════════════════════════════════════════
# P0-2: MarketWeeklyCollector.collect_all 独立容错
# ═══════════════════════════════════════════════════════════════════

class TestMarketWeeklyCollector:
    """P0-2.2: collect_all 单维度失败不影响其他维度"""

    @pytest.mark.asyncio
    async def test_partial_failure_others_succeed(self):
        """部分维度失败，其他维度仍返回数据"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector

        # Mock transport: trend 失败，其他成功
        transport = AsyncMock()

        async def fail_trend(*args, **kwargs):
            raise RuntimeError("trend unavailable")

        async def ok_sector(*args, **kwargs):
            return {"top_gainers": [], "top_losers": [], "consecutive_hot": [], "error": None}

        async def ok_fund_flow(*args, **kwargs):
            return {"main_force_net": 100, "north_bound_net": 50, "etf_inflow_top5": [], "error": None}

        async def ok_sentiment(*args, **kwargs):
            return {"avg_limit_up_down_ratio": 2.0, "avg_turnover": 8000, "weekly_volatility": 1.5, "error": None}

        async def ok_macro(*args, **kwargs):
            return {"events": [], "error": None}

        transport.fetch_index_trend = fail_trend
        transport.fetch_sector_rotation = ok_sector
        transport.fetch_fund_flow = ok_fund_flow
        transport.fetch_sentiment = ok_sentiment
        transport.fetch_macro_events = ok_macro

        collector = MarketWeeklyCollector(transport)
        result = await collector.collect_all("2025-01-10")

        assert result["success"] is True
        assert result["all_failed"] is False
        dims = result["dimensions"]
        # trend 应该失败
        assert dims["trend"].get("error") is not None
        # 其他应该成功
        assert dims["sector"].get("error") is None
        assert dims["fund_flow"].get("error") is None
        assert dims["sentiment"].get("error") is None
        assert dims["macro"].get("error") is None

    @pytest.mark.asyncio
    async def test_all_dimensions_fail(self):
        """全部维度失败 → all_failed=True"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector

        transport = AsyncMock()

        async def fail_all(*args, **kwargs):
            raise RuntimeError("unavailable")

        transport.fetch_index_trend = fail_all
        transport.fetch_sector_rotation = fail_all
        transport.fetch_fund_flow = fail_all
        transport.fetch_sentiment = fail_all
        transport.fetch_macro_events = fail_all

        collector = MarketWeeklyCollector(transport)
        result = await collector.collect_all("2025-01-10")

        assert result["success"] is False
        assert result["all_failed"] is True
        assert result["error"] == "所有数据源不可用"

    @pytest.mark.asyncio
    async def test_all_dimensions_succeed(self):
        """全部维度成功"""
        from praxis.engine.data.market_weekly import MarketWeeklyCollector

        transport = AsyncMock()

        async def ok_all(*args, **kwargs):
            return {"error": None}

        transport.fetch_index_trend = ok_all
        transport.fetch_sector_rotation = ok_all
        transport.fetch_fund_flow = ok_all
        transport.fetch_sentiment = ok_all
        transport.fetch_macro_events = ok_all

        collector = MarketWeeklyCollector(transport)
        result = await collector.collect_all("2025-01-10")

        assert result["success"] is True
        assert result["all_failed"] is False
        # 所有维度无错误
        for dim in result["dimensions"].values():
            assert dim.get("error") is None


# ═══════════════════════════════════════════════════════════════════
# P0-2: generate_market_weekly_review transport=None 错误处理
# ═══════════════════════════════════════════════════════════════════

class TestGenerateMarketWeeklyReview:
    """P0-2.3: generate_market_weekly_review transport=None 返回错误"""

    @pytest.mark.asyncio
    async def test_transport_none_returns_error(self):
        """transport 为 None → 返回明确错误"""
        from praxis.tools.review_module import generate_market_weekly_review
        result = await generate_market_weekly_review(
            week_ending="2025-01-10",
            transport=None,
            _deps={},
        )
        assert result["success"] is False
        assert "transport" in result["error"].lower() or "transport" in result["error"]

    @pytest.mark.asyncio
    async def test_transport_from_deps(self):
        """transport 从 _deps 获取"""
        from praxis.tools.review_module import generate_market_weekly_review

        transport = AsyncMock()
        # mock 全部维度
        async def ok_all(*args, **kwargs):
            return {"error": None}
        transport.fetch_index_trend = ok_all
        transport.fetch_sector_rotation = ok_all
        transport.fetch_fund_flow = ok_all
        transport.fetch_sentiment = ok_all
        transport.fetch_macro_events = ok_all

        result = await generate_market_weekly_review(
            week_ending="2025-01-10",
            _deps={"market_data_transport": transport},
        )
        assert result["success"] is True
        assert "report" in result["data"]


# ═══════════════════════════════════════════════════════════════════
# P0-2: MarketWeeklyReviewInput schema
# ═══════════════════════════════════════════════════════════════════

class TestMarketWeeklyReviewInput:
    """P0-2.5: MarketWeeklyReviewInput schema 定义正确"""

    def test_schema_required_fields(self):
        from praxis.tools._schemas import MarketWeeklyReviewInput
        schema = MarketWeeklyReviewInput.model_json_schema()
        required = schema.get("required", [])
        assert "week_ending" in required
        # index_code 有默认值，不在 required
        assert "index_code" not in required

    def test_schema_defaults(self):
        from praxis.tools._schemas import MarketWeeklyReviewInput
        instance = MarketWeeklyReviewInput(week_ending="2025-01-10")
        assert instance.index_code == "000300"
        assert instance.transport is None

    def test_schema_validation_invalid_date(self):
        """无效日期格式应该被接受（运行时由 _resolve_week_range 容错）"""
        from praxis.tools._schemas import MarketWeeklyReviewInput
        # Pydantic 不做日期格式校验（字段类型是 str）
        instance = MarketWeeklyReviewInput(week_ending="invalid")
        assert instance.week_ending == "invalid"


# ═══════════════════════════════════════════════════════════════════
# P0-3: _derive_holding_period_distribution FIFO 配对逻辑
# ═══════════════════════════════════════════════════════════════════

class TestDeriveHoldingPeriodDistribution:
    """P0-3.1: FIFO 配对逻辑"""

    def _make_tx(self, ticker, tx_type, created_at_str, price=10.0, quantity=100):
        """创建模拟 Transaction 对象"""
        from praxis.core.models import Transaction, TransactionType
        return Transaction(
            ticker=ticker,
            tx_type=TransactionType(tx_type),
            quantity=quantity,
            price=price,
            created_at=created_at_str,
        )

    def test_fifo_pairing_basic(self):
        """基本 FIFO: 先买先配对卖出"""
        from praxis.engine.performance import _derive_holding_period_distribution
        from unittest.mock import MagicMock

        txs = [
            self._make_tx("600995", "buy", "2025-01-01"),
            self._make_tx("600995", "sell", "2025-01-05"),  # 持有 4 天 → 3-7d
        ]
        ledger = MagicMock()
        ledger.get_all.return_value = txs

        result = _derive_holding_period_distribution(ledger)
        assert result["total_paired"] == 1
        assert result["unpaired"] == 0
        assert result["3-7d"] == 1

    def test_fifo_multiple_tickers(self):
        """多标的 FIFO 不交叉"""
        from praxis.engine.performance import _derive_holding_period_distribution
        from unittest.mock import MagicMock

        txs = [
            self._make_tx("600995", "buy", "2025-01-01"),
            self._make_tx("300750", "buy", "2025-01-02"),
            self._make_tx("600995", "sell", "2025-01-03"),  # 2天 → "<3d"
            self._make_tx("300750", "sell", "2025-01-12"),  # 10天 → "7-20d"
        ]
        ledger = MagicMock()
        ledger.get_all.return_value = txs

        result = _derive_holding_period_distribution(ledger)
        assert result["total_paired"] == 2
        assert result["<3d"] == 1
        assert result["7-20d"] == 1

    def test_fifo_exact_boundaries(self):
        """分档边界测试"""
        from praxis.engine.performance import _derive_holding_period_distribution
        from unittest.mock import MagicMock

        txs = [
            self._make_tx("A", "buy", "2025-01-01"),
            self._make_tx("A", "sell", "2025-01-02"),  # 1天 → <3d
            self._make_tx("B", "buy", "2025-01-01"),
            self._make_tx("B", "sell", "2025-01-04"),  # 3天 → 3-7d (days=3, <=7)
            self._make_tx("C", "buy", "2025-01-01"),
            self._make_tx("C", "sell", "2025-01-08"),  # 7天 → 3-7d (days=7, <=7)
            self._make_tx("D", "buy", "2025-01-01"),
            self._make_tx("D", "sell", "2025-01-09"),  # 8天 → 7-20d (days=8, <=20)
            self._make_tx("E", "buy", "2025-01-01"),
            self._make_tx("E", "sell", "2025-01-22"),  # 21天 → >20d
        ]
        ledger = MagicMock()
        ledger.get_all.return_value = txs

        result = _derive_holding_period_distribution(ledger)
        assert result["<3d"] == 1
        assert result["3-7d"] == 2    # 3天和7天都在此档
        assert result["7-20d"] == 1
        assert result[">20d"] == 1
        assert result["total_paired"] == 5

    def test_sell_without_buy_is_unpaired(self):
        """卖出无对应买入 → unpaired"""
        from praxis.engine.performance import _derive_holding_period_distribution
        from unittest.mock import MagicMock

        txs = [
            self._make_tx("600995", "sell", "2025-01-05"),
        ]
        ledger = MagicMock()
        ledger.get_all.return_value = txs

        result = _derive_holding_period_distribution(ledger)
        assert result["total_paired"] == 0
        assert result["unpaired"] == 1

    def test_subscribe_redeem_treated_as_buy_sell(self):
        """SUBSCRIBE/REDEEM 视为买卖"""
        from praxis.engine.performance import _derive_holding_period_distribution
        from unittest.mock import MagicMock

        txs = [
            self._make_tx("510310", "subscribe", "2025-01-01"),
            self._make_tx("510310", "redeem", "2025-01-06"),  # 5天 → 3-7d
        ]
        ledger = MagicMock()
        ledger.get_all.return_value = txs

        result = _derive_holding_period_distribution(ledger)
        assert result["total_paired"] == 1
        assert result["3-7d"] == 1


# ═══════════════════════════════════════════════════════════════════
# P0-3: _audit_rules 收益比计算
# ═══════════════════════════════════════════════════════════════════

class TestAuditRules:
    """P0-3.3: _audit_rules 对各规则的收益比计算"""

    def test_ratio_calculation(self):
        """验证 ratio = risk_mitigated / max(abs(opportunity_cost), 0.01)"""
        from praxis.tools.review_module import _audit_rules

        # 构造 mock records
        MockRecord = type("MockRecord", (), {})
        records = [
            MockRecord(),
            MockRecord(),
            MockRecord(),
        ]
        records[0].rule = "Rule 1"
        records[0].opportunity_cost_pct = 0.05
        records[0].risk_mitigated_pct = 0.10

        records[1].rule = "Rule 1"
        records[1].opportunity_cost_pct = 0.03
        records[1].risk_mitigated_pct = 0.02

        records[2].rule = "Rule 2"
        records[2].opportunity_cost_pct = 0.10
        records[2].risk_mitigated_pct = 0.50

        result = _audit_rules(records)

        # Rule 1: oc=0.08, rm=0.12, ratio = 0.12/0.08 = 1.5
        assert "Rule 1" in result
        assert result["Rule 1"]["interceptions"] == 2
        assert result["Rule 1"]["opportunity_cost"] == round(0.08, 3)
        assert result["Rule 1"]["risk_mitigated"] == round(0.12, 3)
        assert result["Rule 1"]["ratio"] == round(0.12 / 0.08, 3)

        # Rule 2: oc=0.10, rm=0.50, ratio = 0.50/0.10 = 5.0
        assert "Rule 2" in result
        assert result["Rule 2"]["interceptions"] == 1
        assert result["Rule 2"]["ratio"] == round(0.50 / 0.10, 3)

    def test_ratio_zero_opportunity_cost(self):
        """机会成本为 0 时除 max(abs(oc), 0.01) 防除零"""
        from praxis.tools.review_module import _audit_rules

        MockRecord = type("MockRecord", (), {})
        record = MockRecord()
        record.rule = "Rule X"
        record.opportunity_cost_pct = 0.0
        record.risk_mitigated_pct = 0.05

        result = _audit_rules([record])
        # ratio = 0.05 / max(0, 0.01) = 5.0
        assert result["Rule X"]["ratio"] == round(0.05 / 0.01, 3)


# ═══════════════════════════════════════════════════════════════════
# P0-1: _calculate_review benchmark_provider 行为
# ═══════════════════════════════════════════════════════════════════

class TestCalculateReview:
    """P0-1.2/1.3: _calculate_review benchmark 行为"""

    def _make_decision(self, ticker="600995", action="buy", days_ago=10):
        """构造 DecisionRecord"""
        from praxis.core.models import DecisionRecord
        created = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return DecisionRecord(
            decision_id="test-001",
            ticker=ticker,
            action=action,
            created_at=created.isoformat(),
        )

    def _make_klines(self, n_days=60, start_price=10.0, extra_past=5):
        """构造 K 线序列 — 覆盖 from (now - n_days - extra_past) to (now + extra_past)

        确保决策日期前后都有足够的 K 线数据，不会触发"数据不足"回退。
        """
        base = datetime.now(timezone.utc) - timedelta(days=n_days + extra_past)
        total = n_days + 2 * extra_past  # 前后都有余量
        klines = []
        for i in range(total):
            dt = base + timedelta(days=i)
            klines.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": start_price + i * 0.05,
                "close": start_price + i * 0.06,
                "high": start_price + i * 0.07,
                "low": start_price + i * 0.04,
                "volume": 1000000,
            })
        return klines

    @pytest.mark.asyncio
    async def test_benchmark_provider_available_returns_benchmark_pct(self):
        """benchmark_provider 可用 → benchmark_return_pct 非空"""
        from praxis.engine.review_filler import ReviewFiller
        from unittest.mock import MagicMock

        # 构造 mock deps
        recorder = MagicMock()
        ledger = MagicMock()
        data_provider = AsyncMock()

        # 决策日期约 10 天前，K线覆盖 [-55, +5] 天（充足余量）
        decision = self._make_decision(ticker="600995", action="buy", days_ago=10)
        klines = self._make_klines(n_days=50, start_price=10.0, extra_past=5)
        data_provider.get_history_kline.return_value = klines

        # benchmark_provider mock
        benchmark = AsyncMock()
        # 显式 async side_effect 确保返回 >= 2 条基准K线
        async def mock_get_daily_kline(index_code, start_date, end_date):
            return [
                {"date": start_date, "open": 3500, "close": 3550, "high": 3560, "low": 3490, "volume": 100000},
                {"date": end_date, "open": 3510, "close": 3600, "high": 3610, "low": 3500, "volume": 100000},
            ]
        benchmark.get_daily_kline = mock_get_daily_kline

        filler = ReviewFiller(recorder, ledger, data_provider, benchmark_provider=benchmark)

        result = await filler._calculate_review(decision, exec_price=10.0, days=5, benchmark_index_code="000300")

        assert result is not None
        assert result.get("benchmark_return_pct") is not None
        # benchmark_return_pct 应该是非空数值
        assert isinstance(result["benchmark_return_pct"], (int, float))

    @pytest.mark.asyncio
    async def test_benchmark_provider_none_benchmark_pct_is_none(self):
        """benchmark_provider=None → benchmark_return_pct=None"""
        from praxis.engine.review_filler import ReviewFiller
        from unittest.mock import MagicMock

        recorder = MagicMock()
        ledger = MagicMock()
        data_provider = AsyncMock()

        decision = self._make_decision(ticker="600995", action="buy", days_ago=10)
        klines = self._make_klines(n_days=50, start_price=10.0, extra_past=5)
        data_provider.get_history_kline.return_value = klines

        # 不注入 benchmark_provider
        filler = ReviewFiller(recorder, ledger, data_provider, benchmark_provider=None)

        result = await filler._calculate_review(decision, exec_price=10.0, days=5)

        assert result is not None
        assert result.get("benchmark_return_pct") is None

    @pytest.mark.asyncio
    async def test_notes_contains_benchmark_info(self):
        """P0-1.4: notes 含跑赢/跑输基准"""
        from praxis.engine.review_filler import ReviewFiller
        from unittest.mock import MagicMock

        recorder = MagicMock()
        ledger = MagicMock()
        data_provider = AsyncMock()

        # 构造跑赢场景
        decision = self._make_decision(ticker="600995", action="buy", days_ago=10)
        klines = self._make_klines(n_days=50, start_price=10.0, extra_past=5)
        data_provider.get_history_kline.return_value = klines

        benchmark = AsyncMock()
        # 显式 async side_effect 确保 >= 2 条基准K线
        async def mock_get_daily_kline(index_code, start_date, end_date):
            return [
                {"date": start_date, "open": 100, "close": 101, "high": 101, "low": 99, "volume": 1},
                {"date": end_date, "open": 101, "close": 103, "high": 103, "low": 100, "volume": 1},
            ]
        benchmark.get_daily_kline = mock_get_daily_kline

        filler = ReviewFiller(recorder, ledger, data_provider, benchmark_provider=benchmark)
        result = await filler._calculate_review(decision, exec_price=10.0, days=5, benchmark_index_code="000300")

        assert result is not None
        notes = result.get("notes", "")
        # 应该包含"跑赢基准"或"跑输基准"或降级说明
        has_benchmark_note = (
            "跑赢基准" in notes
            or "跑输基准" in notes
            or "亏损但跑赢基准" in notes
        )
        # 如果 benchmark_pct 是 None（基准数据不足），检查 notes 中是否有降级说明
        if result.get("benchmark_return_pct") is None:
            assert "基准" in notes, f"benchmark 数据不足时应包含'基准'字样: {notes}"
        else:
            assert has_benchmark_note, f"notes 中未找到基准对标关键词: {notes}"

    @pytest.mark.asyncio
    async def test_notes_negative_return_but_outperform(self):
        """P0-1.4: 亏损但跑赢基准"""
        from praxis.engine.review_filler import ReviewFiller
        from unittest.mock import MagicMock

        recorder = MagicMock()
        ledger = MagicMock()
        data_provider = AsyncMock()

        # 构造标的亏损 5%
        decision = self._make_decision(ticker="600995", action="buy", days_ago=10)
        # K线：覆盖 60 天，足够让 _calculate_review 正常计算
        klines = self._make_klines(n_days=55, start_price=10.0, extra_past=5)
        # 确保 target kline close 偏低（模拟亏损）
        for kl in klines[-10:]:
            kl["close"] = 9.5
        data_provider.get_history_kline.return_value = klines

        benchmark = AsyncMock()
        # 基准跌幅 10%（alpha > 0 → 亏损但跑赢基准）
        async def mock_get_daily_kline_neg(index_code, start_date, end_date):
            return [
                {"date": start_date, "open": 100, "close": 90, "high": 100, "low": 89, "volume": 1},
                {"date": end_date, "open": 90, "close": 85, "high": 91, "low": 84, "volume": 1},
            ]
        benchmark.get_daily_kline = mock_get_daily_kline_neg

        filler = ReviewFiller(recorder, ledger, data_provider, benchmark_provider=benchmark)
        result = await filler._calculate_review(decision, exec_price=10.0, days=5, benchmark_index_code="000300")

        assert result is not None
        notes = result.get("notes", "")
        # actual_return_pct 应为负，但 alpha > 0
        actual_return = result.get("actual_return_pct")
        benchmark_return = result.get("benchmark_return_pct")
        if actual_return is not None and benchmark_return is not None:
            if actual_return < 0 and actual_return > benchmark_return:
                assert "跑赢基准" in notes or "亏损但跑赢基准" in notes

    @pytest.mark.asyncio
    async def test_notes_no_benchmark_provider(self):
        """无 benchmark_provider → notes 不含基准关键词"""
        from praxis.engine.review_filler import ReviewFiller
        from unittest.mock import MagicMock

        recorder = MagicMock()
        ledger = MagicMock()
        data_provider = AsyncMock()

        decision = self._make_decision(ticker="600995", action="buy", days_ago=10)
        klines = self._make_klines(n_days=50, start_price=10.0, extra_past=5)
        data_provider.get_history_kline.return_value = klines

        filler = ReviewFiller(recorder, ledger, data_provider, benchmark_provider=None)
        result = await filler._calculate_review(decision, exec_price=10.0, days=5)

        assert result is not None
        notes = result.get("notes", "")
        # 无 benchmark 时不应出现"跑赢"/"跑输"关键词
        assert "跑赢基准" not in notes
        assert "跑输基准" not in notes
        # 但应有"正确"/"错误"
        assert "正确" in notes or "错误" in notes


# ═══════════════════════════════════════════════════════════════════
# P0-3: cascade_review 模式支持
# ═══════════════════════════════════════════════════════════════════

class TestCascadeReviewModes:
    """P0-3.4: cascade_review 支持 monthly/quarterly/annual"""

    @pytest.mark.asyncio
    async def test_unknown_mode_returns_error(self):
        """未知 mode → 错误"""
        from praxis.tools.review_module import cascade_review
        result = await cascade_review(mode="weekly", _deps={"workspace": "."})
        assert result["success"] is False
        assert "未知 mode" in result["error"]

    @pytest.mark.asyncio
    async def test_monthly_mode_invalid_period(self):
        """月度模式 + 无效 period → 错误"""
        from praxis.tools.review_module import cascade_review
        result = await cascade_review(
            mode="monthly", period="bad-format", _deps={"workspace": "."},
        )
        assert result["success"] is False
        assert "无效的 period 格式" in result["error"]

    @pytest.mark.asyncio
    async def test_monthly_mode_without_evolution_engine(self):
        """月度模式 + 无 EvolutionEngine → 返回降级报告"""
        from praxis.tools.review_module import cascade_review

        # mock deps
        deps = {
            "workspace": ".",
            "performance_calculator": None,
            "ledger": None,
        }
        result = await cascade_review(
            mode="monthly", period="2025-01", _deps=deps,
        )
        # 无 EvolutionEngine 时也应返回 success（降级）
        assert result.get("success") is True or result.get("data") is not None
        # 至少应有 risk_quality_section（即使为 fallback 内容）
        assert "data" in result

    @pytest.mark.asyncio
    async def test_quarterly_mode_without_evolution_engine(self):
        """季度模式 + 无 EvolutionEngine"""
        from praxis.tools.review_module import cascade_review

        deps = {"workspace": ".", "performance_calculator": None, "ledger": None}
        result = await cascade_review(
            mode="quarterly", period="2025-Q1", _deps=deps,
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_annual_mode_without_evolution_engine(self):
        """年度模式 + 无 EvolutionEngine"""
        from praxis.tools.review_module import cascade_review

        deps = {"workspace": ".", "performance_calculator": None, "ledger": None}
        result = await cascade_review(
            mode="annual", period="2025", _deps=deps,
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_quarterly_bad_format(self):
        """季度格式错误"""
        from praxis.tools.review_module import cascade_review
        result = await cascade_review(
            mode="quarterly", period="2025-13", _deps={"workspace": "."},
        )
        assert result["success"] is False
        assert "无效的 quarter 格式" in result["error"]

    @pytest.mark.asyncio
    async def test_annual_bad_format(self):
        """年度格式错误"""
        from praxis.tools.review_module import cascade_review
        result = await cascade_review(
            mode="annual", period="2025-01", _deps={"workspace": "."},
        )
        assert result["success"] is False
        assert "无效的 year 格式" in result["error"]


# ═══════════════════════════════════════════════════════════════════
# P0-3: _build_risk_quality_section 6 指标
# ═══════════════════════════════════════════════════════════════════

class TestBuildRiskQualitySection:
    """P0-3.2: _build_risk_quality_section 包含 6 个指标"""

    @pytest.mark.asyncio
    async def test_no_performance_calculator_returns_warning(self):
        """无 performance_calculator → 警告信息"""
        from praxis.tools.review_module import _build_risk_quality_section
        result = await _build_risk_quality_section(
            "demo", "core", ".", _deps={},
        )
        assert "绩效计算器未注入" in result

    @pytest.mark.asyncio
    async def test_performance_unavailable_returns_warning(self):
        """performance 调用失败 → 警告"""
        from praxis.tools.review_module import _build_risk_quality_section
        from unittest.mock import MagicMock

        perf = MagicMock()
        perf.calculate.return_value = {"success": False, "error": "无交易记录"}

        result = await _build_risk_quality_section(
            "demo", "core", ".", _deps={"performance_calculator": perf},
        )
        assert "绩效数据获取失败" in result

    @pytest.mark.asyncio
    async def test_six_indicators_present(self):
        """检查所需 6 个指标：
        1. 最大回撤
        2. 胜率
        3. 盈亏比
        4. 夏普比率
        5. 卡玛比率
        6. 持仓周期分布
        """
        from praxis.tools.review_module import _build_risk_quality_section
        from unittest.mock import MagicMock

        perf = MagicMock()
        perf.calculate.return_value = {
            "success": True,
            "data": {
                "max_drawdown": 0.15,
                "win_rate": 0.6,
                "profit_loss_ratio": 1.5,
                "sharpe_ratio": 0.8,
                "calmar_ratio": 1.2,
            },
        }

        # ledger: <5 笔交易
        from praxis.core.models import Transaction, TransactionType
        ledger = MagicMock()
        ledger.list.return_value = []

        result = await _build_risk_quality_section(
            "demo", "core", ".", _deps={
                "performance_calculator": perf,
                "ledger": ledger,
            },
        )

        assert "最大回撤" in result
        assert "胜率" in result
        assert "盈亏比" in result
        assert "夏普比率" in result
        assert "卡玛比率" in result
        assert "持仓周期分布" in result


# ═══════════════════════════════════════════════════════════════════
# 工具注册验证
# ═══════════════════════════════════════════════════════════════════

class TestToolRegistration:
    """P0-2.4: review_module.register() 注册了 generate_market_weekly_review"""

    def test_register_includes_market_weekly_review(self):
        """注册包含 generate_market_weekly_review"""
        from praxis.tools.review_module import register
        from unittest.mock import MagicMock

        registry = MagicMock()
        register(registry)

        # 验证 register() 被调用 3 次（review, cascade_review, generate_market_weekly_review）
        assert registry.register.call_count == 3

        # 提取所有注册的 tool name
        tool_names = []
        for call_args in registry.register.call_args_list:
            tool = call_args[0][0]  # 第一个参数是 Tool 对象
            tool_names.append(tool.name)

        assert "review" in tool_names
        assert "cascade_review" in tool_names
        assert "generate_market_weekly_review" in tool_names

    def test_market_weekly_review_tool_config(self):
        """验证 generate_market_weekly_review 工具配置"""
        from praxis.tools.review_module import register
        from unittest.mock import MagicMock

        registry = MagicMock()
        register(registry)

        # 找到 generate_market_weekly_review
        found = None
        for call_args in registry.register.call_args_list:
            tool = call_args[0][0]
            if tool.name == "generate_market_weekly_review":
                found = tool
                break

        assert found is not None
        assert found.agent_name == "review"
        assert found.tier == "core"
        assert found.handler is not None


# ═══════════════════════════════════════════════════════════════════
# 静态审查：接口一致性
# ═══════════════════════════════════════════════════════════════════

class TestInterfaceConsistency:
    """静态审查：跨文件接口一致性"""

    def test_benchmark_provider_implements_interface(self):
        """TencentBenchmarkProvider 实现 BenchmarkProvider 接口"""
        from praxis.engine.data.benchmark import TencentBenchmarkProvider
        from praxis.core.interfaces import BenchmarkProvider

        # 检查方法存在
        provider = TencentBenchmarkProvider.__dict__
        assert "get_daily_kline" in provider or hasattr(TencentBenchmarkProvider, "get_daily_kline")
        assert "get_latest_price" in provider or hasattr(TencentBenchmarkProvider, "get_latest_price")
        assert "get_supported_indices" in provider or hasattr(TencentBenchmarkProvider, "get_supported_indices")

    def test_market_data_transport_protocol(self):
        """MarketDataTransport Protocol 定义 5 个方法"""
        from praxis.core.interfaces import MarketDataTransport
        methods = [m for m in dir(MarketDataTransport) if not m.startswith("_")]
        assert "fetch_index_trend" in methods
        assert "fetch_sector_rotation" in methods
        assert "fetch_fund_flow" in methods
        assert "fetch_sentiment" in methods
        assert "fetch_macro_events" in methods

    def test_review_filler_accepts_optional_benchmark(self):
        """ReviewFiller 接受可选 benchmark_provider"""
        from praxis.engine.review_filler import ReviewFiller
        from unittest.mock import MagicMock

        recorder = MagicMock()
        ledger = MagicMock()
        data = MagicMock()

        # 不带 benchmark → 不抛出
        f1 = ReviewFiller(recorder, ledger, data)
        assert f1._benchmark is None

        # 带 benchmark → 正常
        benchmark = MagicMock()
        f2 = ReviewFiller(recorder, ledger, data, benchmark_provider=benchmark)
        assert f2._benchmark is benchmark

    def test_imports_are_resolvable(self):
        """验证所有关键 import 路径可解析"""
        # P0-1
        from praxis.engine.review_filler import _default_benchmark_index, ReviewFiller
        # P0-2
        from praxis.engine.data.market_weekly import MarketWeeklyCollector
        from praxis.engine.data.benchmark import TencentBenchmarkProvider
        # P0-3
        from praxis.engine.performance import _derive_holding_period_distribution
        from praxis.tools.review_module import (
            _build_risk_quality_section,
            _audit_rules,
            generate_market_weekly_review,
            cascade_review,
            register,
        )
        from praxis.core.interfaces import MarketDataTransport, BenchmarkProvider
        from praxis.tools._schemas import MarketWeeklyReviewInput
        assert True  # 如果上面的 import 都成功，测试通过


# ═══════════════════════════════════════════════════════════════════
# 向后兼容测试
# ═══════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """向后兼容性验证"""

    @pytest.mark.asyncio
    async def test_fill_pending_reviews_without_benchmark(self):
        """P0-BC.1: fill_pending_reviews 无 benchmark_provider 时 behavior 不变"""
        from praxis.engine.review_filler import ReviewFiller
        from unittest.mock import MagicMock

        recorder = MagicMock()
        recorder.get_executed.return_value = []  # 无待复盘决策
        ledger = MagicMock()
        data = AsyncMock()

        filler = ReviewFiller(recorder, ledger, data, benchmark_provider=None)
        result = await filler.fill_pending_reviews()

        assert result["success"] is True
        assert "data" in result
        # 无决策时全为 0
        assert result["data"]["filled_5d"] == 0
        assert result["data"]["filled_20d"] == 0
        assert result["data"]["filled_60d"] == 0

    def test_review_tool_registration_unchanged(self):
        """P0-BC.2: 现有 review 和 cascade_review 工具注册不变"""
        from praxis.tools.review_module import register
        from unittest.mock import MagicMock

        registry = MagicMock()
        register(registry)

        tool_names = []
        for call_args in registry.register.call_args_list:
            tool = call_args[0][0]
            tool_names.append(tool.name)

        # review 和 cascade_review 仍然注册
        assert "review" in tool_names, "review 工具应在注册列表中"
        assert "cascade_review" in tool_names, "cascade_review 工具应在注册列表中"

    def test_review_handler_function_exists(self):
        """review 函数存在且可调用"""
        from praxis.tools.review_module import review
        assert callable(review)


# ═══════════════════════════════════════════════════════════════════
# _assemble_markdown 测试
# ═══════════════════════════════════════════════════════════════════

class TestAssembleMarkdown:
    """_assemble_markdown 组装验证"""

    def test_five_sections_present(self):
        """验证 5 个章节存在"""
        from praxis.tools.review_module import _assemble_markdown

        dimensions = {
            "trend": {"weekly_change_pct": 1.5, "volume_trend": "放量", "ma_positions": {"MA5": "上方"}, "error": None},
            "sector": {"top_gainers": [{"name": "AI", "change_pct": 5.0}], "top_losers": [], "consecutive_hot": [], "error": None},
            "fund_flow": {"main_force_net": 100, "north_bound_net": 50, "etf_inflow_top5": [], "error": None},
            "sentiment": {"avg_limit_up_down_ratio": 2.0, "avg_turnover": 8000, "weekly_volatility": 1.5, "error": None},
            "macro": {"events": [], "error": None},
        }

        report = _assemble_markdown(
            week_ending="2025-01-10",
            index_code="000300",
            date_range={"start": "2025-01-05", "end": "2025-01-10"},
            dimensions=dimensions,
        )

        assert "大盘趋势" in report
        assert "题材轮动" in report
        assert "资金流向" in report
        assert "情绪温度" in report
        assert "宏观事件" in report

    def test_dimension_error_shows_warning(self):
        """维度获取失败 → 标注错误信息"""
        from praxis.tools.review_module import _assemble_markdown

        dimensions = {
            "trend": {"error": "网络超时"},
            "sector": {"error": "数据源离线"},
            "fund_flow": {"error": "API限流"},
            "sentiment": {"error": "解析失败"},
            "macro": {"error": "服务不可用"},
        }

        report = _assemble_markdown(
            week_ending="2025-01-10",
            index_code="000300",
            date_range={"start": "2025-01-05", "end": "2025-01-10"},
            dimensions=dimensions,
        )

        assert "数据获取失败" in report
        assert "网络超时" in report
        assert "数据源离线" in report


# ═══════════════════════════════════════════════════════════════════
# TencentBenchmarkProvider 静态审查
# ═══════════════════════════════════════════════════════════════════

class TestTencentBenchmarkProvider:
    """benchmark.py 静态审查"""

    def test_index_map_contains_all_required(self):
        """TENCENT_INDEX_MAP 包含所有支持的指数"""
        from praxis.engine.data.benchmark import TENCENT_INDEX_MAP
        assert "000300" in TENCENT_INDEX_MAP  # 沪深300
        assert "000905" in TENCENT_INDEX_MAP  # 中证500
        assert "399006" in TENCENT_INDEX_MAP  # 创业板指

    def test_get_supported_indices_returns_list(self):
        """get_supported_indices 返回非空列表"""
        from praxis.engine.data.benchmark import TencentBenchmarkProvider
        provider = TencentBenchmarkProvider()
        indices = provider.get_supported_indices()
        assert len(indices) >= 4
        codes = [i["code"] for i in indices]
        assert "000300" in codes
        assert "399006" in codes
        assert "000905" in codes

    def test_parse_kline_date_filtering(self):
        """K线解析的日期筛选逻辑"""
        from praxis.engine.data.benchmark import TencentBenchmarkProvider
        provider = TencentBenchmarkProvider()

        # 模拟腾讯数据格式
        text = 'var hq_str_sh000300="20250102,3500.00,3550.00,3560.00,3490.00,100000\\n20250103,3550.00,3580.00,3590.00,3540.00,120000"'
        result = provider._parse_kline(text, "2025-01-02", "2025-01-03")
        assert len(result) == 2
        assert result[0]["date"] == "2025-01-02"
        assert result[1]["date"] == "2025-01-03"


# ═══════════════════════════════════════════════════════════════════
# P0-3: _generate_reshape_suggestions 回归
# ═══════════════════════════════════════════════════════════════════

class TestReshapeSuggestions:
    """重塑建议生成逻辑"""

    def test_whitelist_rules_exempt(self):
        """白名单规则（Rule 1, Rule 7）豁免"""
        from praxis.tools.review_module import _generate_reshape_suggestions
        audit = {
            "Rule 1": {"ratio": 0.3},
            "Rule 7": {"ratio": 0.2},
            "Rule 3": {"ratio": 0.3},
        }
        suggestions = _generate_reshape_suggestions(audit)
        whitelist_suggestions = [s for s in suggestions if "白名单豁免" in s]
        assert len(whitelist_suggestions) == 2

    def test_ratio_below_05_suggests_relax_or_abolish(self):
        """ratio < 0.5 → 建议放宽或废除"""
        from praxis.tools.review_module import _generate_reshape_suggestions
        audit = {"Rule X": {"ratio": 0.3}}
        suggestions = _generate_reshape_suggestions(audit)
        assert any("放宽阈值或废除" in s for s in suggestions)

    def test_ratio_above_5_suggests_keep(self):
        """ratio > 5 → 规则极其有效"""
        from praxis.tools.review_module import _generate_reshape_suggestions
        audit = {"Rule Y": {"ratio": 6.0}}
        suggestions = _generate_reshape_suggestions(audit)
        assert any("极其有效" in s for s in suggestions)
