"""回测工具测试"""
import pytest

pytestmark = pytest.mark.skip(
    reason="compare_strategy_versions 尚未实现。保留测试文件作为设计规格文档。"
)


class TestBacktestTools:
    """回测工具测试"""

    def test_run_backtest(self):
        """测试运行回测"""
        from praxis.tools.backtest import run_backtest
        import asyncio
        result = asyncio.run(run_backtest("grid_value", "example", "core"))
        assert isinstance(result, dict)
        assert "success" in result

    def test_compare_strategy_versions(self):
        """测试策略版本对比"""
        from praxis.engine.version_compare import compare_strategy_versions
        import asyncio
        result = asyncio.run(compare_strategy_versions("grid_value", "momentum"))
        assert isinstance(result, dict)
        assert "success" in result


class TestBacktestToolsIntegration:
    """回测工具集成测试"""

    def test_run_backtest_returns_valid_data(self):
        """测试运行回测返回有效数据"""
        from praxis.tools.backtest import run_backtest
        import asyncio
        result = asyncio.run(run_backtest("grid_value", "example", "core"))
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result

    def test_compare_strategy_versions_returns_valid_data(self):
        """测试策略版本对比返回有效数据"""
        from praxis.engine.version_compare import compare_strategy_versions
        import asyncio
        result = asyncio.run(compare_strategy_versions("grid_value", "momentum"))
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
