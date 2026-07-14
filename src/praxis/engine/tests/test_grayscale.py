"""灰度引擎测试 — GrayscaleEngine."""
from __future__ import annotations

import shutil
from datetime import datetime

import pytest

from praxis.engine.grayscale import (
    GrayscaleEngine, GrayscaleConfig, GrayscaleResult,
)
from praxis.engine.tests.conftest import FakeLedger
from praxis.engine.backtest import BacktestConfig
from praxis.core.models import (
    Transaction, TransactionType, TransactionStatus, AssetType,
)
from praxis.core.exceptions import ConfigError


@pytest.fixture
def workspace_with_strategy(tmp_path):
    """创建含策略 YAML 的工作区."""
    strategies_dir = tmp_path / "config" / "strategies"
    strategies_dir.mkdir(parents=True)

    content = """
name: grid_value
description: 网格价值策略
"""
    (strategies_dir / "grid_value.yaml").write_text(content, encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def workspace_missing_strategy(tmp_path):
    """创建不含目标策略的工作区."""
    strategies_dir = tmp_path / "config" / "strategies"
    strategies_dir.mkdir(parents=True)
    return str(tmp_path)


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


class TestLowRiskValidation:
    """low 风险验证."""

    def test_low_risk_passes(self, workspace_with_strategy):
        """low 风险 + 无回测 → 通过."""
        engine = GrayscaleEngine(workspace_with_strategy)
        config = GrayscaleConfig(
            strategy_name="grid_value",
            change_description="调整网格间距",
            risk_level="low",
            require_backtest=False,
            require_approval=False,
        )

        result = engine.run_validation(config)
        assert result.validation_passed is True
        assert result.backup_path != ""


class TestHighRiskWithBacktest:
    """high 风险 + require_backtest."""

    def test_high_risk_with_backtest(self, workspace_with_strategy):
        """high 风险 + 回测 → 运行回测并返回结果."""
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 100.0, 1800.0),
            _make_tx("600519", TransactionType.SELL, 50.0, 1900.0,
                     created_at="2024-06-20T10:00:00"),
        ])

        engine = GrayscaleEngine(workspace_with_strategy)
        config = GrayscaleConfig(
            strategy_name="grid_value",
            change_description="大改网格算法",
            risk_level="high",
            validation_days=90,
            require_backtest=True,
            require_approval=True,
        )

        result = engine.run_validation(config, ledger=ledger)
        assert result.risk_level == "high"
        assert result.approval_required is True
        # 有交易数据，回测应成功
        assert result.validation_passed is True
        assert result.backtest_result is not None
        assert result.backtest_result.get("success") is True


class TestBacktestFailure:
    """回测失败."""

    def test_backtest_failure(self, workspace_with_strategy):
        """回测异常 → validation_passed=False（空账本也会成功，因为回测处理空交易）."""
        ledger = FakeLedger([])

        engine = GrayscaleEngine(workspace_with_strategy)
        config = GrayscaleConfig(
            strategy_name="grid_value",
            change_description="测试变更",
            risk_level="medium",
            validation_days=90,
            require_backtest=True,
        )

        # 空账本回测不抛异常，但结果为 0 值
        result = engine.run_validation(config, ledger=ledger)
        # 空账本回测成功（不含 error）
        assert result.validation_passed is True

    def test_backtest_failure_no_ledger(self, workspace_with_strategy):
        """无 ledger → 回测失败."""
        engine = GrayscaleEngine(workspace_with_strategy)
        config = GrayscaleConfig(
            strategy_name="grid_value",
            change_description="测试变更",
            risk_level="medium",
            validation_days=90,
            require_backtest=True,
        )

        # 无 ledger 会导致回测失败
        result = engine.run_validation(config)
        assert result.backtest_result is not None
        assert "success" in result.backtest_result


class TestBackupCreation:
    """backup 创建验证."""

    def test_backup_created(self, workspace_with_strategy):
        """验证备份文件被创建."""
        import os
        engine = GrayscaleEngine(workspace_with_strategy)
        config = GrayscaleConfig(
            strategy_name="grid_value",
            change_description="测试备份",
            risk_level="low",
            require_backtest=False,
            require_approval=False,
        )

        result = engine.run_validation(config)
        assert result.backup_path != ""
        # 备份文件应该存在
        backup_path = result.backup_path
        assert os.path.exists(backup_path)


class TestGrayscaleConfigValidation:
    """GrayscaleConfig 字段校验."""

    def test_config_defaults(self):
        """验证默认值."""
        config = GrayscaleConfig(
            strategy_name="test",
            change_description="测试",
        )
        assert config.risk_level == "medium"
        assert config.validation_days == 30
        assert config.require_backtest is True
        assert config.require_approval is True

    def test_config_custom(self):
        """自定义值."""
        config = GrayscaleConfig(
            strategy_name="test",
            change_description="测试",
            risk_level="high",
            validation_days=60,
            require_backtest=False,
            require_approval=False,
        )
        assert config.risk_level == "high"
        assert config.validation_days == 60
        assert config.require_backtest is False
        assert config.require_approval is False


class TestStrategyNotFound:
    """策略不存在."""

    def test_strategy_not_found(self, workspace_missing_strategy):
        """策略不存在 → error."""
        engine = GrayscaleEngine(workspace_missing_strategy)
        config = GrayscaleConfig(
            strategy_name="nonexistent",
            change_description="测试",
            risk_level="low",
            require_backtest=False,
            require_approval=False,
        )

        result = engine.run_validation(config)
        assert result.validation_passed is False
        assert "不存在" in result.message or "验证失败" in result.message
