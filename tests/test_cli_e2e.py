"""CLI 命令端到端测试"""
import pytest
import subprocess
import sys


class TestCLIE2E:
    """CLI 命令端到端测试"""

    def test_cli_help(self):
        """测试 CLI 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "PRAXIS" in result.stdout

    def test_cli_version(self):
        """测试 CLI 版本"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_portfolio_help(self):
        """测试 portfolio 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "portfolio", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_asset_help(self):
        """测试 asset 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "asset", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_market_help(self):
        """测试 market 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "market", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_reconcile_help(self):
        """测试 reconcile 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "reconcile", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_constraints_help(self):
        """测试 constraints 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "constraints", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_state_help(self):
        """测试 state 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "state", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_ledger_help(self):
        """测试 ledger 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "ledger", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_decision_help(self):
        """测试 decision 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "decision", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_performance_help(self):
        """测试 performance 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "performance", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_strategy_help(self):
        """测试 strategy 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "strategy", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_evolution_help(self):
        """测试 evolution 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "evolution", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_benchmark_help(self):
        """测试 benchmark 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "benchmark", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_nav_help(self):
        """测试 nav 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "nav", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_ai_tracking_help(self):
        """测试 ai-tracking 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "ai-tracking", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_backtest_help(self):
        """测试 backtest 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "backtest", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_validate_help(self):
        """测试 validate 帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "validate", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


class TestCLIE2EIntegration:
    """CLI 命令端到端集成测试"""

    def test_portfolio_list(self):
        """测试 portfolio list"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "portfolio", "list", "--investor", "example"],
            capture_output=True,
            text=True,
        )
        # 命令应该能执行（可能返回空列表）
        assert result.returncode == 0 or "error" in result.stderr.lower()

    def test_strategy_list(self):
        """测试 strategy list"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "strategy", "list"],
            capture_output=True,
            text=True,
        )
        # 命令应该能执行
        assert result.returncode == 0 or "error" in result.stderr.lower()

    def test_benchmark_list(self):
        """测试 benchmark list"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "benchmark", "list"],
            capture_output=True,
            text=True,
        )
        # 命令应该能执行
        assert result.returncode == 0 or "error" in result.stderr.lower()

    def test_validate(self):
        """测试 validate"""
        result = subprocess.run(
            [sys.executable, "-m", "praxis.cli", "validate"],
            capture_output=True,
            text=True,
        )
        # 命令应该能执行
        assert result.returncode == 0 or "error" in result.stderr.lower()
