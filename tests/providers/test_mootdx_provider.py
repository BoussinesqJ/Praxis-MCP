"""mootdx 数据源单元测试

测试通达信 TCP 直连数据获取
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from praxis.core.models.error import DataError


class TestMootdxProvider:
    """mootdx 数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.mootdx_provider import MootdxProvider, PRIORITY
        assert PRIORITY == 1
        assert MootdxProvider is not None

    def test_priority(self):
        """测试优先级"""
        from providers.mootdx_provider import MootdxProvider
        provider = MootdxProvider()
        assert provider.priority == 1

    def test_class_attributes(self):
        """测试类属性"""
        from providers.mootdx_provider import MootdxProvider
        provider = MootdxProvider()
        assert hasattr(provider, 'get_realtime_quote')
        assert hasattr(provider, 'get_history_kline')
        assert hasattr(provider, 'get_fund_nav')

    @pytest.mark.asyncio
    async def test_get_realtime_quote_success(self):
        """测试获取实时行情成功"""
        from providers.mootdx_provider import MootdxProvider

        provider = MootdxProvider()

        # Mock mootdx client
        mock_client = MagicMock()
        mock_client.quotes.return_value = [
            {
                'code': '510050',
                'name': '科创50ETF',
                'price': 1.599,
                'last_close': 1.591,
                'open': 1.575,
                'high': 1.609,
                'low': 1.569,
                'volume': 347797,
                'amount': 5522.0,
                'bid1': 1.598,
                'ask1': 1.600,
            }
        ]

        with patch.object(provider, '_client', mock_client):
            result = await provider.get_realtime_quote(["510050"])

        assert "510050" in result
        assert result["510050"]["price"] == 1.599
        assert result["510050"]["source"] == "mootdx"

    @pytest.mark.asyncio
    async def test_get_realtime_quote_empty(self):
        """测试获取实时行情空结果"""
        from providers.mootdx_provider import MootdxProvider

        provider = MootdxProvider()

        # Mock mootdx client returning empty
        mock_client = MagicMock()
        mock_client.quotes.return_value = []

        with patch.object(provider, '_client', mock_client):
            with pytest.raises(DataError) as exc_info:
                await provider.get_realtime_quote(["999999"])
            assert "mootdx" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_history_kline_success(self):
        """测试获取历史K线成功"""
        from providers.mootdx_provider import MootdxProvider

        provider = MootdxProvider()

        # Mock mootdx client
        mock_client = MagicMock()
        mock_client.bars.return_value = [
            {'datetime': '2026-06-10', 'open': 1.58, 'high': 1.61, 'low': 1.57, 'close': 1.60, 'volume': 300000},
            {'datetime': '2026-06-11', 'open': 1.575, 'high': 1.609, 'low': 1.569, 'close': 1.599, 'volume': 347797},
        ]

        with patch.object(provider, '_client', mock_client):
            result = await provider.get_history_kline("510050", period="day", count=2)

        assert len(result) == 2
        assert result[0]["close"] == 1.60
        assert result[0]["source"] == "mootdx"

    @pytest.mark.asyncio
    async def test_get_history_kline_empty(self):
        """测试获取历史K线空结果"""
        from providers.mootdx_provider import MootdxProvider

        provider = MootdxProvider()

        # Mock mootdx client returning empty
        mock_client = MagicMock()
        mock_client.bars.return_value = []

        with patch.object(provider, '_client', mock_client):
            result = await provider.get_history_kline("999999")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_fund_nav_raises(self):
        """测试基金净值抛出异常"""
        from providers.mootdx_provider import MootdxProvider

        provider = MootdxProvider()

        with pytest.raises(DataError) as exc_info:
            await provider.get_fund_nav("510050")
        assert "mootdx" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭"""
        from providers.mootdx_provider import MootdxProvider

        provider = MootdxProvider()
        mock_client = MagicMock()

        with patch.object(provider, '_client', mock_client):
            await provider.close()

        # 关闭不应抛出异常


class TestMootdxProviderIntegration:
    """mootdx 数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_realtime_quote(self):
        """测试真实实时行情获取"""
        try:
            from providers.mootdx_provider import MootdxProvider

            provider = MootdxProvider()
            result = await provider.get_realtime_quote(["000001"])

            assert "000001" in result
            assert result["000001"]["price"] > 0
            assert result["000001"]["source"] == "mootdx"
        except ImportError:
            pytest.skip("mootdx 未安装")
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_history_kline(self):
        """测试真实历史K线获取"""
        try:
            from providers.mootdx_provider import MootdxProvider

            provider = MootdxProvider()
            result = await provider.get_history_kline("000001", period="day", count=5)

            assert len(result) > 0
            assert result[0]["source"] == "mootdx"
        except ImportError:
            pytest.skip("mootdx 未安装")
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
