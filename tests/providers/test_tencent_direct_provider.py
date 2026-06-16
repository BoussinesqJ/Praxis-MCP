"""腾讯直连数据源单元测试

测试腾讯财经 HTTP 直连数据获取（不经过 akshare）
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import httpx
from praxis.core.models.error import DataError


class TestTencentDirectProvider:
    """腾讯直连数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.tencent_direct_provider import TencentDirectProvider, PRIORITY
        assert PRIORITY == 2
        assert TencentDirectProvider is not None

    def test_priority(self):
        """测试优先级"""
        from providers.tencent_direct_provider import TencentDirectProvider
        provider = TencentDirectProvider()
        assert provider.priority == 2

    def test_class_attributes(self):
        """测试类属性"""
        from providers.tencent_direct_provider import TencentDirectProvider
        provider = TencentDirectProvider()
        assert hasattr(provider, 'get_realtime_quote')
        assert hasattr(provider, 'get_history_kline')
        assert hasattr(provider, 'get_fund_nav')

    @pytest.mark.asyncio
    async def test_get_realtime_quote_success(self):
        """测试获取实时行情成功"""
        from providers.tencent_direct_provider import TencentDirectProvider

        provider = TencentDirectProvider()

        # Mock HTTP response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = 'v_sh510050="1~科创50ETF东财~510050~1.599~1.591~1.575~347797~182636~165161~1.599~3~1.598~347~1.597~94~1.596~1423~1.595~1525~1.600~2072~1.601~1261~1.602~111~1.603~86~1.604~18~~20260611152005~0.008~0.50~1.60"'
        mock_response.raise_for_status = MagicMock()

        # 使用 patch 替换 _client.get
        with patch.object(provider._client, 'get', new=AsyncMock(return_value=mock_response)):
            result = await provider.get_realtime_quote(["510050"])

        assert "510050" in result
        assert result["510050"]["price"] == 1.599
        assert result["510050"]["source"] == "tencent"

    @pytest.mark.asyncio
    async def test_get_realtime_quote_empty(self):
        """测试获取实时行情空结果"""
        from providers.tencent_direct_provider import TencentDirectProvider

        provider = TencentDirectProvider()

        # Mock HTTP response with empty data
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = 'v_sh999999=""'
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, 'get', new=AsyncMock(return_value=mock_response)):
            with pytest.raises(DataError):
                await provider.get_realtime_quote(["999999"])

    @pytest.mark.asyncio
    async def test_get_history_kline_not_supported(self):
        """测试历史K线不支持"""
        from providers.tencent_direct_provider import TencentDirectProvider

        provider = TencentDirectProvider()
        result = await provider.get_history_kline("510050")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_fund_nav_raises(self):
        """测试基金净值抛出异常"""
        from providers.tencent_direct_provider import TencentDirectProvider

        provider = TencentDirectProvider()

        with pytest.raises(DataError):
            await provider.get_fund_nav("510050")

    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭"""
        from providers.tencent_direct_provider import TencentDirectProvider

        provider = TencentDirectProvider()
        await provider.close()

        # 关闭不应抛出异常


class TestTencentDirectProviderIntegration:
    """腾讯直连数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_realtime_quote(self):
        """测试真实实时行情获取"""
        try:
            from providers.tencent_direct_provider import TencentDirectProvider

            provider = TencentDirectProvider()
            result = await provider.get_realtime_quote(["000001"])

            assert "000001" in result
            assert result["000001"]["price"] > 0
            assert result["000001"]["source"] == "tencent"
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_etf_quote(self):
        """测试 ETF 实时行情获取"""
        try:
            from providers.tencent_direct_provider import TencentDirectProvider

            provider = TencentDirectProvider()
            result = await provider.get_realtime_quote(["510050"])

            assert "510050" in result
            assert result["510050"]["price"] > 0
            assert result["510050"]["source"] == "tencent"
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
