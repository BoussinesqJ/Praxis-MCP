"""回测引擎测试"""
import pytest
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import json

from praxis.engine.backtest import SimpleBacktestEngine, BacktestConfig, BacktestResult
from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType


class TestSimpleBacktestEngine:
    """简单回测引擎测试"""

    def setup_method(self):
        """测试前准备"""
        # 创建临时目录
        self.tmp_dir = tempfile.mkdtemp()
        self.ledger = FileLedger(Path(self.tmp_dir) / "ledger")
        self.engine = SimpleBacktestEngine(self.ledger, initial_capital=70000)

    def test_run_backtest_basic(self):
        """测试基本回测"""
        # 添加测试交易（在回测期间内）
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=4.0,
            fee=5.0,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 运行回测
        config = BacktestConfig(
            strategy_name="grid_value",
            start_date="2026-01-01",
            end_date="2026-06-06",
        )
        result = self.engine.run_backtest(config)

        # 验证结果
        assert isinstance(result, BacktestResult)
        assert result.strategy_name == "grid_value"
        assert result.total_fee >= 0

    def test_run_backtest_with_nav(self):
        """测试带净值数据的回测"""
        # 添加测试交易
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=4.0,
            fee=5.0,
            created_at=datetime.now(timezone.utc),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 准备净值数据
        nav_series = [
            {"date": "2026-01-01", "nav": 1.0},
            {"date": "2026-03-01", "nav": 1.05},
            {"date": "2026-06-01", "nav": 1.1},
        ]

        # 运行回测
        config = BacktestConfig(
            strategy_name="grid_value",
            start_date="2026-01-01",
            end_date="2026-06-06",
        )
        result = self.engine.run_backtest(config, nav_series=nav_series)

        # 验证结果
        assert isinstance(result, BacktestResult)
        assert result.total_return is not None

    def test_run_backtest_with_benchmark(self):
        """测试带基准对比的回测"""
        # 添加测试交易
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=4.0,
            fee=5.0,
            created_at=datetime.now(timezone.utc),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 准备基准数据
        benchmark_series = [
            {"date": "2026-01-01", "close": 3000},
            {"date": "2026-03-01", "close": 3100},
            {"date": "2026-06-01", "close": 3200},
        ]

        # 运行回测
        config = BacktestConfig(
            strategy_name="grid_value",
            start_date="2026-01-01",
            end_date="2026-06-06",
            benchmark="000300",
        )
        result = self.engine.run_backtest(config, benchmark_series=benchmark_series)

        # 验证结果
        assert isinstance(result, BacktestResult)
        assert result.benchmark_return is not None
        assert result.excess_return is not None

    def test_calculate_metrics(self):
        """测试绩效指标计算"""
        # 添加测试交易
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=4.0,
            fee=5.0,
            created_at=datetime.now(timezone.utc),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 运行回测
        config = BacktestConfig(
            strategy_name="grid_value",
            start_date="2026-01-01",
            end_date="2026-06-06",
        )
        result = self.engine.run_backtest(config)

        # 验证绩效指标
        assert result.total_return is not None
        assert result.annualized_return is not None
        assert result.max_drawdown is not None
        assert result.sharpe_ratio is not None
        assert result.win_rate is not None

    def test_calculate_max_drawdown(self):
        """测试最大回撤计算"""
        # 净值序列：先涨后跌
        nav_series = [
            {"date": "2026-01-01", "nav": 1.0},
            {"date": "2026-02-01", "nav": 1.2},
            {"date": "2026-03-01", "nav": 0.9},  # 回撤 25%
            {"date": "2026-04-01", "nav": 1.1},
        ]

        # 添加测试交易
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=4.0,
            fee=5.0,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 运行回测
        config = BacktestConfig(
            strategy_name="grid_value",
            start_date="2026-01-01",
            end_date="2026-06-06",
        )
        result = self.engine.run_backtest(config, nav_series=nav_series)

        # 验证最大回撤（应为正数，表示回撤比例）
        assert result.max_drawdown is not None
        assert result.max_drawdown >= 0  # 回撤应为正数
        assert result.max_drawdown <= 1  # 回撤不超过 100%

    def test_calculate_sharpe_ratio(self):
        """测试夏普比率计算"""
        # 添加测试交易
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=4.0,
            fee=5.0,
            created_at=datetime.now(timezone.utc),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 运行回测
        config = BacktestConfig(
            strategy_name="grid_value",
            start_date="2026-01-01",
            end_date="2026-06-06",
        )
        result = self.engine.run_backtest(config)

        # 验证夏普比率
        assert result.sharpe_ratio is not None
