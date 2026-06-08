"""E1.8 — 绩效计算器测试"""
import pytest
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.engine.performance import EnhancedPerformanceCalculator


@pytest.fixture
def workspace():
    return "C:/Users/77271/Desktop/Portfolio vault"


@pytest.fixture
def ledger(workspace):
    ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
    return FileLedger(ledger_path)


@pytest.fixture
def calculator(ledger):
    return EnhancedPerformanceCalculator(ledger, initial_capital=70000)


class TestPerformanceCalculation:
    """绩效计算测试"""

    def test_calculate_basic(self, calculator):
        """基本计算测试"""
        metrics = calculator.calculate("example", "demo")
        assert hasattr(metrics, 'total_return')
        assert hasattr(metrics, 'annualized_return')
        assert hasattr(metrics, 'win_rate')
        assert hasattr(metrics, 'total_fee')

    def test_calculate_returns(self, calculator):
        """收益率计算"""
        metrics = calculator.calculate("example", "demo")
        assert isinstance(metrics.total_return, float)

    def test_calculate_trade_stats(self, calculator):
        """交易统计（空数据）"""
        metrics = calculator.calculate("example", "demo")
        assert metrics.buy_count >= 0
        assert metrics.sell_count >= 0
        assert metrics.total_fee >= 0

    def test_calculate_win_rate(self, calculator):
        """胜率计算"""
        metrics = calculator.calculate("example", "demo")
        assert 0 <= metrics.win_rate <= 1

    def test_calculate_turnover(self, calculator):
        """换手率计算"""
        metrics = calculator.calculate("example", "demo")
        assert metrics.turnover_rate >= 0
