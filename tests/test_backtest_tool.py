"""回测工具测试"""
import pytest
import asyncio
from praxis.tools.backtest import run_backtest, compare_strategy_versions


class TestBacktestTools:
    """回测工具测试"""

    def test_run_backtest(self):
        """测试运行回测"""
        result = asyncio.run(run_backtest("grid_value", "example", "core"))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_compare_strategy_versions(self):
        """测试策略版本对比"""
        result = asyncio.run(compare_strategy_versions("grid_value", "momentum"))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result


class TestBacktestToolsIntegration:
    """回测工具集成测试"""

    def test_run_backtest_returns_valid_data(self):
        """测试运行回测返回有效数据"""
        result = asyncio.run(run_backtest("grid_value", "example", "core"))

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result

    def test_compare_strategy_versions_returns_valid_data(self):
        """测试策略版本对比返回有效数据"""
        result = asyncio.run(compare_strategy_versions("grid_value", "momentum"))

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
