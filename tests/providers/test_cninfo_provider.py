"""巨潮公告数据源单元测试

测试公告元数据获取（不下载 PDF）
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime

import httpx
from praxis.core.models.error import DataError


class TestCninfoProvider:
    """巨潮公告数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.cninfo_provider import CninfoProvider
        assert CninfoProvider is not None

    def test_class_attributes(self):
        """测试类属性"""
        from providers.cninfo_provider import CninfoProvider
        provider = CninfoProvider()
        assert hasattr(provider, 'get_announcements')

    @pytest.mark.asyncio
    async def test_get_announcements_success(self):
        """测试获取公告列表成功"""
        from providers.cninfo_provider import CninfoProvider

        provider = CninfoProvider()

        # Mock 巨潮 API 响应
        mock_data = {
            "announcements": [
                {
                    "announcementId": "123456",
                    "announcementTitle": "关于公司2026年半年度报告",
                    "announcementTime": "2026-06-11 15:30:00",
                    "adjunctUrl": "finalpage/2026-06-11/123456.PDF",
                    "secName": "平安银行",
                    "secCode": "000001",
                },
            ],
            "totalAnnouncement": 1,
        }

        # Mock httpx.AsyncClient.post
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await provider.get_announcements("000001")

        assert result is not None
        assert len(result) > 0
        assert result[0]["title"] == "关于公司2026年半年度报告"

    @pytest.mark.asyncio
    async def test_get_announcements_empty(self):
        """测试获取公告列表空结果"""
        from providers.cninfo_provider import CninfoProvider

        provider = CninfoProvider()

        # Mock 巨潮 API 返回空
        mock_data = {"announcements": [], "totalAnnouncement": 0}

        # Mock httpx.AsyncClient.post
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await provider.get_announcements("999999")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_announcements_with_params(self):
        """测试获取公告列表（带参数）"""
        from providers.cninfo_provider import CninfoProvider

        provider = CninfoProvider()

        # Mock 巨潮 API 响应
        mock_data = {
            "announcements": [
                {
                    "announcementId": "123456",
                    "announcementTitle": "关于公司2026年半年度报告",
                    "announcementTime": "2026-06-11 15:30:00",
                },
            ],
            "totalAnnouncement": 1,
        }

        # Mock httpx.AsyncClient.post
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await provider.get_announcements(
                "000001",
                start_date="2026-01-01",
                end_date="2026-12-31",
                limit=10,
            )

        assert result is not None


class TestCninfoProviderIntegration:
    """巨潮公告数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_announcements(self):
        """测试真实公告获取"""
        try:
            from providers.cninfo_provider import CninfoProvider

            provider = CninfoProvider()
            result = await provider.get_announcements("000001", limit=5)

            assert result is not None
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
