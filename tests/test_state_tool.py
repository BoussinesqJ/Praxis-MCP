"""状态工具测试"""
import pytest
import asyncio
from praxis.tools.state import get_state


class TestStateTools:
    """状态工具测试"""

    def test_get_state(self):
        """测试获取组合状态"""
        result = asyncio.run(get_state("example", "core"))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_state_returns_valid_data(self):
        """测试获取组合状态返回有效数据"""
        result = asyncio.run(get_state("example", "core"))

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result


class TestStateToolsIntegration:
    """状态工具集成测试"""

    def test_get_state_with_different_portfolios(self):
        """测试获取不同组合的状态"""
        # 测试不同的组合
        for investor, portfolio in [("example", "core"), ("example", "grid_value")]:
            result = asyncio.run(get_state(investor, portfolio))
            assert isinstance(result, dict)
            assert "success" in result
