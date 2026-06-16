"""版本对比测试"""
import pytest
from praxis.engine.version_compare import VersionComparer, VersionComparison
from praxis.core.models.state import PerformanceMetrics


class TestVersionComparer:
    """版本对比测试"""

    def setup_method(self):
        """测试前准备"""
        self.comparer = VersionComparer()

    def test_compare_versions(self):
        """测试版本对比"""
        # 准备测试数据
        metrics_a = PerformanceMetrics(
            total_return=0.1,
            annualized_return=0.05,
            max_drawdown=-0.1,
            sharpe_ratio=0.8,
            calmar_ratio=0.5,
            win_rate=0.6,
            profit_loss_ratio=1.2,
            volatility=0.15,
            excess_return=0.02,
            benchmark_return=0.03,
            turnover_rate=0.3,
            total_fee=100.0,
            buy_count=10,
            sell_count=5,
            realized_pnl=500.0,
            total_dividend=50.0,
        )
        metrics_b = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.08,
            max_drawdown=-0.08,
            sharpe_ratio=1.0,
            calmar_ratio=0.7,
            win_rate=0.65,
            profit_loss_ratio=1.4,
            volatility=0.12,
            excess_return=0.05,
            benchmark_return=0.03,
            turnover_rate=0.25,
            total_fee=80.0,
            buy_count=8,
            sell_count=4,
            realized_pnl=600.0,
            total_dividend=60.0,
        )

        # 对比版本
        result = self.comparer.compare("v1.0", "v1.1", metrics_a, metrics_b)

        # 验证结果
        assert isinstance(result, VersionComparison)
        assert result.version_a == "v1.0"
        assert result.version_b == "v1.1"
        assert result.winner in ["v1.0", "v1.1", "tie"]

    def test_version_comparison_model(self):
        """测试版本对比模型"""
        metrics = PerformanceMetrics(
            total_return=0.1,
            annualized_return=0.05,
            max_drawdown=-0.1,
            sharpe_ratio=0.8,
            calmar_ratio=0.5,
            win_rate=0.6,
            profit_loss_ratio=1.2,
            volatility=0.15,
            excess_return=0.02,
            benchmark_return=0.03,
            turnover_rate=0.3,
            total_fee=100.0,
            buy_count=10,
            sell_count=5,
            realized_pnl=500.0,
            total_dividend=50.0,
        )

        comparison = VersionComparison(
            version_a="v1.0",
            version_b="v1.1",
            metrics_a=metrics,
            metrics_b=metrics,
            winner="tie",
            improvement={},
        )

        # 验证模型
        assert comparison.version_a == "v1.0"
        assert comparison.version_b == "v1.1"
        assert comparison.winner == "tie"
