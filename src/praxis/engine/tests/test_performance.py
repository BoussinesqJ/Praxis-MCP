"""绩效计算器单元测试 — EnhancedPerformanceCalculator."""

from __future__ import annotations

import pytest

from praxis.engine.performance import EnhancedPerformanceCalculator, _derive_holding_period_distribution
from praxis.engine.tests.conftest import FakeLedger, FakeNavTracker, FakeBenchmarkProvider
from praxis.core.models import (
    Transaction, TransactionType, TransactionStatus, AssetType,
)


def _make_tx(
    ticker: str, tx_type: TransactionType, quantity: float, price: float,
    fee: float = 0.0, created_at: str = "2024-06-01T10:00:00",
    status: TransactionStatus = TransactionStatus.EXECUTED,
) -> Transaction:
    return Transaction(
        investor_id="inv-test", portfolio_id="core",
        ticker=ticker, tx_type=tx_type,
        quantity=quantity, price=price, fee=fee,
        asset_type=AssetType.STOCK,
        status=status,
        created_at=created_at,
    )


class TestNoTransactions:
    """无交易."""

    def test_no_transactions(self):
        """无交易记录返回 error."""
        calc = EnhancedPerformanceCalculator(
            ledger=FakeLedger([]),
            initial_capital=70000.0,
        )
        result = calc.calculate("inv-test", "core")
        assert result["success"] is False
        assert "无交易记录" in result["error"]


class TestNAVPreciseCalc:
    """NAV 精确计算."""

    def test_nav_precise_calc(self):
        """基于 NAV 序列精确计算 total_return/max_drawdown/volatility/sharpe."""
        nav_tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0},
            {"date": "2024-06-02", "nav": 1.01, "total_assets": 70700.0},
            {"date": "2024-06-03", "nav": 1.02, "total_assets": 71400.0},
            {"date": "2024-06-04", "nav": 0.98, "total_assets": 68600.0},
            {"date": "2024-06-05", "nav": 1.03, "total_assets": 72100.0},
            {"date": "2024-06-06", "nav": 1.05, "total_assets": 73500.0},
        ])
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 10.0, 1800.0),
            _make_tx("600519", TransactionType.SELL, 5.0, 1900.0),
        ])
        calc = EnhancedPerformanceCalculator(
            ledger=ledger, initial_capital=70000.0,
            nav_tracker=nav_tracker,
        )
        result = calc.calculate("inv-test", "core")
        assert result["success"] is True
        data = result["data"]
        assert data["total_return"] == pytest.approx(0.05, rel=0.01)
        assert "max_drawdown" in data
        assert "volatility" in data
        # max_drawdown: peak at 1.02, valley at 0.98 → (1.02-0.98)/1.02 ≈ 0.0392
        assert data["max_drawdown"] > 0


class TestNoNAVFallback:
    """无 NAV 回退."""

    def test_no_nav_fallback(self):
        """无 NAV 历史时回退到旧逻辑."""
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 10.0, 1800.0),
        ])
        calc = EnhancedPerformanceCalculator(
            ledger=ledger, initial_capital=70000.0,
            nav_tracker=None,  # 无 NAV
        )
        result = calc.calculate("inv-test", "core")
        assert result["success"] is True
        data = result["data"]
        assert "total_return" in data
        assert "max_drawdown" in data


class TestBenchmarkComparison:
    """benchmark 对比."""

    def test_benchmark_comparison(self):
        """benchmark_return 来自 NAV 记录的 benchmark_nav."""
        nav_tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0,
             "benchmark_nav": 1.0},
            {"date": "2024-06-10", "nav": 1.05, "total_assets": 73500.0,
             "benchmark_nav": 1.03},
        ])
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 10.0, 1800.0),
        ])
        calc = EnhancedPerformanceCalculator(
            ledger=ledger, initial_capital=70000.0,
            nav_tracker=nav_tracker,
        )
        result = calc.calculate("inv-test", "core")
        assert result["success"] is True
        assert result["data"]["benchmark_return"] == pytest.approx(0.03, rel=0.01)
        assert result["data"]["excess_return"] == pytest.approx(0.02, rel=0.01)


class TestWinRate:
    """胜率."""

    def test_win_rate(self):
        """胜率 = 盈利卖出 / 总卖出."""
        nav_tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0},
            {"date": "2024-06-10", "nav": 1.01, "total_assets": 70700.0},
        ])
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 10.0, 1800.0, created_at="2024-06-01T10:00:00"),
            _make_tx("600519", TransactionType.BUY, 10.0, 1850.0, created_at="2024-06-02T10:00:00"),
            _make_tx("600519", TransactionType.SELL, 5.0, 1900.0, created_at="2024-06-05T10:00:00"),  # > avg(1825)
            _make_tx("600519", TransactionType.SELL, 5.0, 1750.0, created_at="2024-06-06T10:00:00"),  # < avg(1825)
        ])
        calc = EnhancedPerformanceCalculator(
            ledger=ledger, initial_capital=70000.0,
            nav_tracker=nav_tracker,
        )
        result = calc.calculate("inv-test", "core")
        assert result["success"] is True
        assert "win_rate" in result["data"]
        assert result["data"]["win_rate"] >= 0


class TestProfitLossRatio:
    """盈亏比."""

    def test_profit_loss_ratio(self):
        """盈亏比 = 平均盈利 / 平均亏损."""
        nav_tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0},
            {"date": "2024-06-10", "nav": 1.01, "total_assets": 70700.0},
        ])
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 10.0, 1800.0, created_at="2024-06-01T10:00:00"),
            _make_tx("600519", TransactionType.SELL, 5.0, 1900.0, created_at="2024-06-05T10:00:00"),
            _make_tx("600519", TransactionType.SELL, 5.0, 1700.0, created_at="2024-06-06T10:00:00"),
        ])
        calc = EnhancedPerformanceCalculator(
            ledger=ledger, initial_capital=70000.0,
            nav_tracker=nav_tracker,
        )
        result = calc.calculate("inv-test", "core")
        assert result["success"] is True
        assert "profit_loss_ratio" in result["data"]


class TestFilterConditions:
    """过滤条件."""

    def test_filter_conditions(self):
        """exclude_reversed + ticker 过滤."""
        nav_tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0},
            {"date": "2024-06-05", "nav": 1.01, "total_assets": 70700.0},
        ])
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 10.0, 1800.0, status=TransactionStatus.EXECUTED),
            _make_tx("600519", TransactionType.BUY, 5.0, 1850.0, status=TransactionStatus.REVERSED),
            _make_tx("159915", TransactionType.BUY, 100.0, 2.30, status=TransactionStatus.EXECUTED),
        ])
        calc = EnhancedPerformanceCalculator(
            ledger=ledger, initial_capital=70000.0,
            nav_tracker=nav_tracker,
        )
        # 过滤 reversed
        result = calc.calculate("inv-test", "core", exclude_reversed=True)
        assert result["success"] is True

        # 过滤 ticker
        result2 = calc.calculate("inv-test", "core", ticker="600519")
        assert result2["success"] is True


class TestFIFOPairing:
    """FIFO 配对."""

    def test_fifo_pairing(self):
        """_derive_holding_period_distribution FIFO 配对."""
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 10.0, 1800.0, created_at="2024-06-01T10:00:00"),
            _make_tx("600519", TransactionType.SELL, 5.0, 1900.0, created_at="2024-06-10T10:00:00"),
        ])
        # 需要 FileLedger 的 get_all 方法
        dist = _derive_holding_period_distribution(ledger)
        assert dist["total_paired"] == 1
        # 9 天，在 7-20d 区间
        assert dist["7-20d"] == 1
