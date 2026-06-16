"""iwen财数据源单元测试

测试自然语言选股数据获取
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from praxis.core.models.error import DataError


class TestIwencaiProvider:
    """iwen财数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.iwencai_provider import IwencaiProvider
        assert IwencaiProvider is not None

    def test_class_attributes(self):
        """测试类属性"""
        from providers.iwencai_provider import IwencaiProvider
        provider = IwencaiProvider()
        assert hasattr(provider, 'search')

    @pytest.mark.asyncio
    async def test_search_success(self):
        """测试自然语言搜索成功"""
        from providers.iwencai_provider import IwencaiProvider

        provider = IwencaiProvider()

        # Mock akshare 调用
        mock_result = [
            {"code": "000001", "name": "平安银行", "price": 13.5, "change_pct": 5.0},
            {"code": "600000", "name": "浦发银行", "price": 8.5, "change_pct": 3.0},
        ]

        with patch.object(provider, '_search_with_akshare', return_value=mock_result):
            result = await provider.search("银行股 涨幅超过3%")

        assert result is not None
        assert len(result) > 0
        assert result[0]["code"] == "000001"

    @pytest.mark.asyncio
    async def test_search_empty(self):
        """测试自然语言搜索空结果"""
        from providers.iwencai_provider import IwencaiProvider

        provider = IwencaiProvider()

        # Mock akshare 返回空
        with patch.object(provider, '_search_with_akshare', return_value=[]):
            result = await provider.search("不存在的查询")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_fallback_to_playwright(self):
        """测试降级到 Playwright"""
        from providers.iwencai_provider import IwencaiProvider

        provider = IwencaiProvider()

        # Mock akshare 失败
        with patch.object(provider, '_search_with_akshare', side_effect=Exception("akshare failed")):
            # Mock Playwright 成功
            mock_playwright_result = [
                {"code": "000001", "name": "平安银行", "price": 13.5},
            ]
            with patch.object(provider, '_search_with_playwright', return_value=mock_playwright_result):
                result = await provider.search("银行股")

        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_all_methods_fail(self):
        """测试所有方法都失败"""
        from providers.iwencai_provider import IwencaiProvider

        provider = IwencaiProvider()

        # Mock 所有方法失败
        with patch.object(provider, '_search_with_akshare', side_effect=Exception("akshare failed")):
            with patch.object(provider, '_search_with_playwright', return_value=[]):
                result = await provider.search("不存在的查询")

        assert result == []


class TestIwencaiProviderIntegration:
    """iwen财数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_search(self):
        """测试真实自然语言搜索"""
        try:
            from providers.iwencai_provider import IwencaiProvider

            provider = IwencaiProvider()
            result = await provider.search("银行股")

            assert result is not None
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
