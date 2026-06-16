"""E2.4 — CLI 端到端测试"""
import pytest
from click.testing import CliRunner
from praxis.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIPortfolio:
    """CLI 组合管理测试"""

    def test_portfolio_get(self, runner):
        """测试 portfolio get 命令"""
        result = runner.invoke(main, [
            "portfolio", "get",
            "--investor", "example",
            "--portfolio", "demo",
        ])
        assert result.exit_code == 0
        assert "grid_value" in result.output

    def test_portfolio_get_nonexistent(self, runner):
        """测试不存在的组合"""
        result = runner.invoke(main, [
            "portfolio", "get",
            "--investor", "example",
            "--portfolio", "nonexistent",
        ])
        assert result.exit_code == 1


class TestCLIAsset:
    """CLI 标的详情测试"""

    def test_asset_get(self, runner):
        """测试 asset 命令"""
        result = runner.invoke(main, [
            "asset",
            "--investor", "example",
            "--portfolio", "demo",
            "--ticker", "STOCK_A",
        ])
        assert result.exit_code == 0


class TestCLIConstraints:
    """CLI 约束检查测试"""

    def test_constraints_pass(self, runner):
        """测试约束检查通过"""
        result = runner.invoke(main, [
            "constraints",
            "--investor", "example",
            "--portfolio", "demo",
            "--action", "buy",
            "--ticker", "ETF_300",
            "--amount", "3000",
        ])
        assert result.exit_code == 0
        assert "通过" in result.output

    def test_constraints_fail(self, runner):
        """测试约束检查失败"""
        result = runner.invoke(main, [
            "constraints",
            "--investor", "example",
            "--portfolio", "demo",
            "--action", "buy",
            "--ticker", "688001",
            "--amount", "3000",
        ])
        assert result.exit_code == 0
        assert "未通过" in result.output


class TestCLILedger:
    """CLI 交易账本测试"""

    def test_ledger_list(self, runner):
        """测试 ledger list 命令"""
        result = runner.invoke(main, ["ledger", "list"])
        assert result.exit_code == 0
        assert "交易总数" in result.output


class TestCLIDecision:
    """CLI 决策记录测试"""

    def test_decision_list(self, runner):
        """测试 decision list 命令"""
        result = runner.invoke(main, ["decision", "list"])
        assert result.exit_code == 0
        assert "决策总数" in result.output


class TestCLIPerformance:
    """CLI 绩效指标测试"""

    def test_performance(self, runner):
        """测试 performance 命令"""
        result = runner.invoke(main, [
            "performance",
            "--investor", "example",
            "--portfolio", "demo",
        ])
        assert result.exit_code == 0
        assert "绩效指标" in result.output


class TestCLIStrategy:
    """CLI 策略管理测试"""

    def test_strategy_list(self, runner):
        """测试 strategy list 命令"""
        result = runner.invoke(main, ["strategy", "list"])
        assert result.exit_code == 0
        assert "grid_value" in result.output

    def test_strategy_get(self, runner):
        """测试 strategy get 命令"""
        result = runner.invoke(main, [
            "strategy", "get",
            "--name", "grid_value",
        ])
        assert result.exit_code == 0
        assert "网格价值策略" in result.output


class TestCLIEvolution:
    """CLI 进化引擎测试"""

    def test_evolution_evaluate(self, runner):
        """测试 evolution evaluate 命令"""
        result = runner.invoke(main, [
            "evolution", "evaluate",
            "--strategy", "grid_value",
            "--investor", "example",
            "--portfolio", "demo",
        ])
        assert result.exit_code == 0
        assert "进化维度评估" in result.output
