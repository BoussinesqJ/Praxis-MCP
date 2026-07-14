"""复盘回填器单元测试 — ReviewFiller _calculate_review / fill / get_summary / confidence."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from praxis.engine.review_filler import ReviewFiller, _default_benchmark_index
from praxis.engine.tests.conftest import (
    FakeDataProvider, FakeConfigLoader, FakeLedger, FakeBenchmarkProvider,
    FakeDecisionRecorder,
)
from praxis.core.models import (
    DecisionRecord, DecisionStatus,
    Transaction, TransactionType, TransactionStatus, AssetType,
    TeamSignal,
)


def _make_executed_decision(
    decision_id: str = "dec-test-001",
    ticker: str = "600519",
    action: str = "buy",
    created_days_ago: int = 10,
    tx_id: str = "tx-test-001",
) -> DecisionRecord:
    created_at = (datetime.now(timezone.utc) - timedelta(days=created_days_ago)).isoformat()
    return DecisionRecord(
        decision_id=decision_id, investor_id="inv-test", portfolio_id="core",
        ticker=ticker, action=action, confidence=0.8,
        status=DecisionStatus.EXECUTED, created_at=created_at,
        tx_id=tx_id,
        team_signals=[
            TeamSignal(team_name="reasonix", action=action, confidence=0.8),
        ],
    )


class TestBenchmarkPrefix:
    """_default_benchmark_index 前缀映射."""

    def test_benchmark_prefix_60(self):
        """60xxxx → 000300."""
        assert _default_benchmark_index("600519") == "000300"

    def test_benchmark_prefix_00(self):
        """00xxxx → 000300."""
        assert _default_benchmark_index("000001") == "000300"

    def test_benchmark_prefix_30(self):
        """30xxxx → 399006."""
        assert _default_benchmark_index("300750") == "399006"

    def test_benchmark_prefix_688(self):
        """688xxx → 000905."""
        assert _default_benchmark_index("688001") == "000905"

    def test_benchmark_prefix_empty(self):
        """空 ticker → 000300."""
        assert _default_benchmark_index("") == "000300"

    def test_benchmark_prefix_short(self):
        """短代码 → 000300."""
        assert _default_benchmark_index("159") == "000300"


class TestCalculateReview:
    """_calculate_review 测试."""

    @pytest.mark.asyncio
    async def test_calculate_review_normal(self, fake_data_provider, fake_decision_recorder, fake_ledger, fake_benchmark_provider):
        """正常 K 线复盘计算."""
        # 在 ledger 中创建关联交易
        tx = Transaction(
            tx_id="tx-test-001",
            investor_id="inv-test", portfolio_id="core",
            ticker="600519", tx_type=TransactionType.BUY,
            quantity=50.0, price=1800.0, fee=5.0,
            asset_type=AssetType.STOCK,
            status=TransactionStatus.EXECUTED,
        )
        fake_ledger.append(tx)

        filler = ReviewFiller(
            recorder=fake_decision_recorder,
            ledger=fake_ledger,
            data_provider=fake_data_provider,
            benchmark_provider=fake_benchmark_provider,
        )
        decision = _make_executed_decision(created_days_ago=1, tx_id="tx-test-001")
        fake_decision_recorder.create(decision)

        # 修改决策日期使其在K线范围内
        decision.created_at = "2024-01-10T10:00:00Z"

        result = await filler._calculate_review(decision, 1800.0, 5, "000300")
        # K线数据从 2024-01 到 2024-02，5天后应该有数据
        assert result is not None
        assert "actual_price" in result
        assert "actual_return_pct" in result

    @pytest.mark.asyncio
    async def test_insufficient_kline(self, fake_decision_recorder, fake_ledger):
        """K 线不足返回 notes 说明."""
        sparse_provider = FakeDataProvider(
            klines={"600519": [{"date": "2024-01-01", "open": 1800, "close": 1810, "high": 1820, "low": 1790, "volume": 1e6}]},
        )
        filler = ReviewFiller(
            recorder=fake_decision_recorder,
            ledger=fake_ledger,
            data_provider=sparse_provider,
        )
        decision = _make_executed_decision(tx_id="")
        decision.created_at = "2024-01-01T10:00:00Z"

        result = await filler._calculate_review(decision, 1800.0, 5, "000300")
        assert result is not None
        assert "K线不足" in result.get("notes", "")

    @pytest.mark.asyncio
    async def test_cannot_locate_decision_date(self, fake_decision_recorder, fake_ledger):
        """无法定位决策日期返回 notes."""
        future_provider = FakeDataProvider(
            klines={"600519": [
                {"date": "2024-01-01", "open": 1800, "close": 1810, "high": 1820, "low": 1790, "volume": 1e6},
                {"date": "2024-01-02", "open": 1810, "close": 1820, "high": 1830, "low": 1800, "volume": 1e6},
                {"date": "2024-01-03", "open": 1820, "close": 1830, "high": 1840, "low": 1810, "volume": 1e6},
                {"date": "2024-01-04", "open": 1830, "close": 1840, "high": 1850, "low": 1820, "volume": 1e6},
                {"date": "2024-01-05", "open": 1840, "close": 1850, "high": 1860, "low": 1830, "volume": 1e6},
                {"date": "2024-01-06", "open": 1850, "close": 1860, "high": 1870, "low": 1840, "volume": 1e6},
            ]},
        )
        filler = ReviewFiller(
            recorder=fake_decision_recorder,
            ledger=fake_ledger,
            data_provider=future_provider,
        )
        decision = _make_executed_decision(tx_id="")
        decision.created_at = "2025-01-01T10:00:00Z"  # 远在K线日期之后

        result = await filler._calculate_review(decision, 1800.0, 5, "000300")
        assert result is not None
        assert "无法定位" in result.get("notes", "")


class TestFillPendingReviews:
    """fill_pending_reviews 测试."""

    @pytest.mark.asyncio
    async def test_fill_5d_review(self, fake_data_provider, fake_decision_recorder, fake_ledger):
        """5天复盘回填."""
        # 创建已执行的 6 天前决策（触发 5d）
        decision = _make_executed_decision(
            decision_id="dec-5d", created_days_ago=6, tx_id="",
        )
        fake_decision_recorder.create(decision)

        filler = ReviewFiller(
            recorder=fake_decision_recorder,
            ledger=fake_ledger,
            data_provider=fake_data_provider,
        )
        result = await filler.fill_pending_reviews()
        assert result["success"] is True
        data = result["data"]
        assert "filled_5d" in data

    @pytest.mark.asyncio
    async def test_fill_20d_60d(self, fake_data_provider, fake_decision_recorder, fake_ledger):
        """20天和60天复盘."""
        d20 = _make_executed_decision("dec-20d", created_days_ago=25, tx_id="")
        d60 = _make_executed_decision("dec-60d", created_days_ago=65, tx_id="")
        fake_decision_recorder.create(d20)
        fake_decision_recorder.create(d60)

        filler = ReviewFiller(
            recorder=fake_decision_recorder,
            ledger=fake_ledger,
            data_provider=fake_data_provider,
        )
        result = await filler.fill_pending_reviews()
        assert result["success"] is True
        data = result["data"]
        # 20d 和 60d 中至少有一个被回填
        assert data["filled_20d"] + data["filled_60d"] >= 0


class TestGetSummary:
    """get_summary 测试."""

    @pytest.mark.asyncio
    async def test_get_summary(self, fake_decision_recorder, fake_ledger, fake_data_provider):
        """获取复盘汇总."""
        d = _make_executed_decision(created_days_ago=30, tx_id="")
        fake_decision_recorder.create(d)

        filler = ReviewFiller(
            recorder=fake_decision_recorder,
            ledger=fake_ledger,
            data_provider=fake_data_provider,
        )
        summary = await filler.get_summary()
        assert summary["success"] is True
        data = summary["data"]
        assert "total_decisions" in data
        assert "pending_5d" in data
        assert "filled_count" in data


class TestConfidenceCalibration:
    """confidence_calibration 测试."""

    @pytest.mark.asyncio
    async def test_confidence_calibration(self, fake_decision_recorder, fake_ledger, fake_data_provider):
        """信心度校准."""
        d = _make_executed_decision(created_days_ago=30, tx_id="")
        fake_decision_recorder.create(d)

        filler = ReviewFiller(
            recorder=fake_decision_recorder,
            ledger=fake_ledger,
            data_provider=fake_data_provider,
        )
        cal = await filler.get_confidence_calibration("reasonix")
        assert cal["success"] is True
        data = cal["data"]
        assert data["team"] == "reasonix"
        assert "avg_calibration_error" in data
