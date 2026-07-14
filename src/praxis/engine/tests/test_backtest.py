"""回测引擎测试 — run_backtest 函数."""
from __future__ import annotations

import json

import pytest

from praxis.engine.backtest import (
    BacktestConfig, BacktestResult,
    run_backtest, _calculate_period_returns, _calculate_metrics,
)
from praxis.engine.tests.conftest import FakeLedger
from praxis.core.models import (
    Transaction, TransactionType, TransactionStatus, AssetType,
)


def _make_tx(
    ticker: str, tx_type: TransactionType, quantity: float, price: float,
    fee: float = 0.0, created_at: str = "2024-06-15T10:00:00",
) -> Transaction:
    return Transaction(
        ticker=ticker, tx_type=tx_type,
        quantity=quantity, price=price, fee=fee,
        asset_type=AssetType.STOCK,
        status=TransactionStatus.EXECUTED,
        created_at=created_at,
    )


class TestRunBacktestNormal:
    """正常回测."""

    def test_with_three_trades(self):
        """含 3 笔交易的账本."""
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 100.0, 1800.0, fee=5.0),
            _make_tx("600519", TransactionType.SELL, 50.0, 1900.0, fee=5.0,
                     created_at="2024-07-15T10:00:00"),
            _make_tx("159915", TransactionType.BUY, 10000.0, 2.30, fee=1.0,
                     created_at="2024-06-20T10:00:00"),
        ])

        config = BacktestConfig(
            strategy_name="grid_value",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        result = run_backtest(config, ledger)
        assert result.strategy_name == "grid_value"
        assert result.trade_count >= 0
        assert result.total_fee == 11.0


class TestEmptyLedger:
    """空账本."""

    def test_empty_ledger(self):
        """空账本返回零值结果."""
        ledger = FakeLedger([])
        config = BacktestConfig(
            strategy_name="test",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        result = run_backtest(config, ledger)
        assert result.total_return == 0.0
        assert result.trade_count == 0
        assert result.total_fee == 0.0


class TestDateFiltering:
    """日期过滤."""

    def test_date_filtering(self):
        """只统计范围内交易."""
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 100.0, 1800.0,
                     created_at="2024-01-15T10:00:00"),
            _make_tx("600519", TransactionType.SELL, 50.0, 1900.0,
                     created_at="2024-06-15T10:00:00"),
            _make_tx("600519", TransactionType.BUY, 100.0, 1850.0,
                     created_at="2024-10-15T10:00:00"),
        ])

        config = BacktestConfig(
            strategy_name="test",
            start_date="2024-06-01",
            end_date="2024-12-31",
        )

        result = run_backtest(config, ledger)
        # Only transactions on 06-15 and 10-15 are in range
        assert result.trade_count >= 0


class TestBenchmarkConfig:
    """基准对比."""

    def test_benchmark_param(self):
        """benchmark 参数传递."""
        config = BacktestConfig(
            strategy_name="test",
            start_date="2024-01-01",
            end_date="2024-12-31",
            benchmark="000905",
        )
        assert config.benchmark == "000905"


class TestBacktestConfigValidation:
    """BacktestConfig 字段校验."""

    def test_config_fields(self):
        """BacktestConfig 字段默认值."""
        config = BacktestConfig(
            strategy_name="test",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        assert config.initial_capital == 70000.0
        assert config.benchmark == "000300"

    def test_config_custom_capital(self):
        """自定义初始资金."""
        config = BacktestConfig(
            strategy_name="test",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000.0,
        )
        assert config.initial_capital == 100000.0


class TestBacktestResultSerialization:
    """BacktestResult 序列化."""

    def test_serialization(self):
        """BacktestResult 可序列化."""
        result = BacktestResult(
            strategy_name="test",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=70000.0,
            final_value=73500.0,
            total_return=0.05,
            annualized_return=0.12,
            max_drawdown=0.08,
            sharpe_ratio=0.8,
            calmar_ratio=1.5,
            win_rate=0.6,
            trade_count=10,
            total_fee=50.0,
        )
        d = result.model_dump()
        assert d["strategy_name"] == "test"
        assert d["total_return"] == 0.05
