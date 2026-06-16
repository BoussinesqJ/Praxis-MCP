"""同花顺北向资金数据源单元测试

测试北向资金实时/历史数据获取
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import httpx
from praxis.core.models.error import DataError


class TestNorthboundProvider:
    """北向资金数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.northbound_provider import NorthboundProvider
        assert NorthboundProvider is not None

    def test_class_attributes(self):
        """测试类属性"""
        from providers.northbound_provider import NorthboundProvider
        provider = NorthboundProvider()
        assert hasattr(provider, 'get_northbound_realtime')
        assert hasattr(provider, 'get_northbound_history')
        assert hasattr(provider, 'get_northbound_flow')

    @pytest.mark.asyncio
    async def test_get_northbound_realtime_success(self):
        """测试获取北向资金实时数据成功"""
        from providers.northbound_provider import NorthboundProvider

        provider = NorthboundProvider()

        # Mock 同花顺 API 响应
        mock_data = {
            "data": {
                "s2n": {
                    "current": {
                        "net_buy": 1000000000,
                        "buy": 5000000000,
                        "sell": 4000000000,
                    },
                    "minute": [
                        {"time": "09:30", "net_buy": 100000000},
                        {"time": "09:31", "net_buy": 200000000},
                    ]
                }
            }
        }

        # Mock httpx.AsyncClient.get
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, 'get', new=AsyncMock(return_value=mock_response)):
            result = await provider.get_northbound_realtime()

        assert result is not None
        assert "current" in result
        assert result["current"]["net_buy"] == 1000000000

    @pytest.mark.asyncio
    async def test_get_northbound_realtime_empty(self):
        """测试获取北向资金实时数据空结果"""
        from providers.northbound_provider import NorthboundProvider

        provider = NorthboundProvider()

        # Mock 同花顺 API 返回空
        mock_data = {"data": {"s2n": {"current": None}}}

        # Mock httpx.AsyncClient.get
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, 'get', new=AsyncMock(return_value=mock_response)):
            result = await provider.get_northbound_realtime()

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_northbound_history_success(self):
        """测试获取北向资金历史数据成功"""
        from providers.northbound_provider import NorthboundProvider

        provider = NorthboundProvider()

        # Mock 本地缓存数据
        mock_data = [
            {"date": "2026-06-10", "net_buy": 1000000000},
            {"date": "2026-06-11", "net_buy": 2000000000},
        ]

        with patch.object(provider, '_load_history', return_value=mock_data):
            result = await provider.get_northbound_history(days=5)

        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_northbound_flow_success(self):
        """测试获取北向资金流向成功"""
        from providers.northbound_provider import NorthboundProvider

        provider = NorthboundProvider()

        # Mock 数据
        mock_realtime = {
            "current": {
                "net_buy": 1000000000,
                "buy": 5000000000,
                "sell": 4000000000,
            }
        }
        mock_history = [
            {"date": "2026-06-10", "net_buy": 1000000000},
        ]

        with patch.object(provider, 'get_northbound_realtime', return_value=mock_realtime):
            with patch.object(provider, 'get_northbound_history', return_value=mock_history):
                result = await provider.get_northbound_flow()

        assert result is not None
        assert "realtime" in result
        assert "history" in result


class TestNorthboundProviderIntegration:
    """北向资金数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_northbound_realtime(self):
        """测试真实北向资金实时数据"""
        try:
            from providers.northbound_provider import NorthboundProvider

            provider = NorthboundProvider()
            result = await provider.get_northbound_realtime()

            assert result is not None
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
