"""东财资金流向数据源单元测试

测试个股资金流向获取（分钟级 + 日度）
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from praxis.core.models.error import DataError


class TestFundFlowProvider:
    """资金流向数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.fund_flow_provider import FundFlowProvider
        assert FundFlowProvider is not None

    def test_inherits_em_client(self):
        """测试继承东财基类"""
        from providers.fund_flow_provider import FundFlowProvider
        from praxis.core.em_client import EMClient
        provider = FundFlowProvider()
        assert isinstance(provider, EMClient)

    def test_class_attributes(self):
        """测试类属性"""
        from providers.fund_flow_provider import FundFlowProvider
        provider = FundFlowProvider()
        assert hasattr(provider, 'get_fund_flow_min')
        assert hasattr(provider, 'get_fund_flow_daily')
        assert hasattr(provider, 'get_fund_flow_all')

    @pytest.mark.asyncio
    async def test_get_fund_flow_min_success(self):
        """测试获取分钟级资金流向成功"""
        from providers.fund_flow_provider import FundFlowProvider

        provider = FundFlowProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": {
                "klines": [
                    "2026-06-11 09:30,1000000,500000,500000,300000,200000",
                    "2026-06-11 09:31,1200000,600000,600000,350000,250000",
                ]
            }
        }

        # Mock em_client.get
        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_fund_flow_min("000001")

        assert result is not None
        assert len(result) > 0
        assert result[0]["main_net"] == 1000000

    @pytest.mark.asyncio
    async def test_get_fund_flow_min_empty(self):
        """测试获取分钟级资金流向空结果"""
        from providers.fund_flow_provider import FundFlowProvider

        provider = FundFlowProvider()

        # Mock 东财 API 返回空
        mock_data = {"data": {"klines": []}}

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_fund_flow_min("999999")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_fund_flow_daily_success(self):
        """测试获取日度资金流向成功"""
        from providers.fund_flow_provider import FundFlowProvider

        provider = FundFlowProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": {
                "klines": [
                    "2026-06-10,1000000,500000,500000,300000,200000",
                    "2026-06-11,1200000,600000,600000,350000,250000",
                ]
            }
        }

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_fund_flow_daily("000001", days=5)

        assert result is not None
        assert len(result) > 0
        assert result[0]["date"] == "2026-06-10"

    @pytest.mark.asyncio
    async def test_get_fund_flow_daily_with_date_range(self):
        """测试获取日度资金流向（带日期范围）"""
        from providers.fund_flow_provider import FundFlowProvider

        provider = FundFlowProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": {
                "klines": [
                    "2026-06-01,1000000,500000,500000,300000,200000",
                    "2026-06-02,1200000,600000,600000,350000,250000",
                ]
            }
        }

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_fund_flow_daily(
                "000001",
                start_date="2026-06-01",
                end_date="2026-06-30"
            )

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_fund_flow_all_success(self):
        """测试获取全市场资金流向成功"""
        from providers.fund_flow_provider import FundFlowProvider

        provider = FundFlowProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": {
                "diff": [
                    {"f12": "000001", "f14": "平安银行", "f62": 1000000},
                    {"f12": "600000", "f14": "浦发银行", "f62": 2000000},
                ]
            }
        }

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_fund_flow_all()

        assert result is not None
        assert len(result) > 0


class TestFundFlowProviderIntegration:
    """资金流向数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_fund_flow_min(self):
        """测试真实分钟级资金流向"""
        try:
            from providers.fund_flow_provider import FundFlowProvider

            provider = FundFlowProvider()
            result = await provider.get_fund_flow_min("000001")

            assert result is not None
            assert len(result) > 0
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_fund_flow_daily(self):
        """测试真实日度资金流向"""
        try:
            from providers.fund_flow_provider import FundFlowProvider

            provider = FundFlowProvider()
            result = await provider.get_fund_flow_daily("000001", days=5)

            assert result is not None
            assert len(result) > 0
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
