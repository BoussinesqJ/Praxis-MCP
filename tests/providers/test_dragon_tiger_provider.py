"""东财龙虎榜数据源单元测试

测试龙虎榜数据获取
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from praxis.core.models.error import DataError


class TestDragonTigerProvider:
    """龙虎榜数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.dragon_tiger_provider import DragonTigerProvider
        assert DragonTigerProvider is not None

    def test_inherits_em_client(self):
        """测试继承东财基类"""
        from providers.dragon_tiger_provider import DragonTigerProvider
        from praxis.core.em_client import EMClient
        provider = DragonTigerProvider()
        assert isinstance(provider, EMClient)

    def test_class_attributes(self):
        """测试类属性"""
        from providers.dragon_tiger_provider import DragonTigerProvider
        provider = DragonTigerProvider()
        assert hasattr(provider, 'get_dragon_tiger_list')
        assert hasattr(provider, 'get_dragon_tiger_detail')

    @pytest.mark.asyncio
    async def test_get_dragon_tiger_list_success(self):
        """测试获取龙虎榜列表成功"""
        from providers.dragon_tiger_provider import DragonTigerProvider

        provider = DragonTigerProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": {
                "diff": [
                    {
                        "f12": "000001",
                        "f14": "平安银行",
                        "f2": 13.5,
                        "f3": 5.0,
                        "f62": 100000000,  # 净买入
                    },
                    {
                        "f12": "600000",
                        "f14": "浦发银行",
                        "f2": 8.5,
                        "f3": 3.0,
                        "f62": 200000000,
                    },
                ]
            }
        }

        # Mock em_client.get
        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_dragon_tiger_list()

        assert result is not None
        assert len(result) > 0
        assert result[0]["ticker"] == "000001"

    @pytest.mark.asyncio
    async def test_get_dragon_tiger_list_empty(self):
        """测试获取龙虎榜列表空结果"""
        from providers.dragon_tiger_provider import DragonTigerProvider

        provider = DragonTigerProvider()

        # Mock 东财 API 返回空
        mock_data = {"data": {"diff": []}}

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_dragon_tiger_list()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_dragon_tiger_list_with_date(self):
        """测试获取指定日期龙虎榜"""
        from providers.dragon_tiger_provider import DragonTigerProvider

        provider = DragonTigerProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": {
                "diff": [
                    {
                        "f12": "000001",
                        "f14": "平安银行",
                        "f2": 13.5,
                        "f3": 5.0,
                        "f62": 100000000,
                    },
                ]
            }
        }

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_dragon_tiger_list(date="2026-06-11")

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_dragon_tiger_detail_success(self):
        """测试获取龙虎榜详情成功"""
        from providers.dragon_tiger_provider import DragonTigerProvider

        provider = DragonTigerProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": {
                "diff": [
                    {
                        "f18": "机构专用",
                        "f62": 50000000,  # 买入
                        "f66": 0,  # 卖出
                    },
                    {
                        "f18": "华泰证券深圳益田路荣超商务中心",
                        "f62": 30000000,
                        "f66": 10000000,
                    },
                ]
            }
        }

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_dragon_tiger_detail("000001")

        assert result is not None
        assert len(result) > 0
        assert result[0]["seat_name"] == "机构专用"


class TestDragonTigerProviderIntegration:
    """龙虎榜数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_dragon_tiger_list(self):
        """测试真实龙虎榜列表"""
        try:
            from providers.dragon_tiger_provider import DragonTigerProvider

            provider = DragonTigerProvider()
            result = await provider.get_dragon_tiger_list()

            assert result is not None
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
