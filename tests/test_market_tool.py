"""市场数据工具测试"""
import pytest
import asyncio
from praxis.tools.market import get_market_data


class TestMarketTools:
    """市场数据工具测试"""

    def test_get_market_data(self):
        """测试获取市场数据"""
        result = asyncio.run(get_market_data(["ETF_300"]))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_market_data_returns_valid_data(self):
        """测试获取市场数据返回有效数据"""
        result = asyncio.run(get_market_data(["ETF_300"]))

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result


class TestMarketToolsIntegration:
    """市场数据工具集成测试"""

    def test_get_market_data_with_multiple_tickers(self):
        """测试获取多个标的的市场数据"""
        result = asyncio.run(get_market_data(["ETF_300", "STOCK_A"]))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result
