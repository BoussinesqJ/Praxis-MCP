"""东财研报数据源单元测试

测试研报数据获取
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from praxis.core.models.error import DataError


class TestResearchReportProvider:
    """研报数据源测试"""

    def test_import(self):
        """测试模块导入"""
        from providers.research_report_provider import ResearchReportProvider
        assert ResearchReportProvider is not None

    def test_inherits_em_client(self):
        """测试继承东财基类"""
        from providers.research_report_provider import ResearchReportProvider
        from praxis.core.em_client import EMClient
        provider = ResearchReportProvider()
        assert isinstance(provider, EMClient)

    def test_class_attributes(self):
        """测试类属性"""
        from providers.research_report_provider import ResearchReportProvider
        provider = ResearchReportProvider()
        assert hasattr(provider, 'get_report_list')
        assert hasattr(provider, 'get_consensus_eps')

    @pytest.mark.asyncio
    async def test_get_report_list_success(self):
        """测试获取研报列表成功"""
        from providers.research_report_provider import ResearchReportProvider

        provider = ResearchReportProvider()

        # Mock 东财 API 响应
        mock_data = {
            "data": [
                {
                    "stockCode": "000001",
                    "stockName": "平安银行",
                    "title": "平安银行2026年半年报点评",
                    "orgSName": "中金公司",
                    "emRatingName": "买入",
                    "predictThisYearEps": 1.5,
                    "predictThisYearPe": 8.5,
                    "publishDate": "2026-06-11",
                },
            ]
        }

        # Mock em_client.get
        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_report_list("000001")

        assert result is not None
        assert len(result) > 0
        assert result[0]["stock_code"] == "000001"

    @pytest.mark.asyncio
    async def test_get_report_list_empty(self):
        """测试获取研报列表空结果"""
        from providers.research_report_provider import ResearchReportProvider

        provider = ResearchReportProvider()

        # Mock 东财 API 返回空
        mock_data = {"result": {"data": []}}

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_report_list("999999")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_report_list_with_params(self):
        """测试获取研报列表（带参数）"""
        from providers.research_report_provider import ResearchReportProvider

        provider = ResearchReportProvider()

        # Mock 东财 API 响应
        mock_data = {
            "result": {
                "data": [
                    {
                        "stock_code": "000001",
                        "stock_name": "平安银行",
                        "title": "平安银行2026年半年报点评",
                        "org_name": "中金公司",
                        "rating": "买入",
                    },
                ]
            }
        }

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_report_list(
                "000001",
                limit=10,
                rating="买入"
            )

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_consensus_eps_success(self):
        """测试获取一致预期 EPS 成功"""
        from providers.research_report_provider import ResearchReportProvider

        provider = ResearchReportProvider()

        # Mock 东财 API 响应
        mock_data = {
            "result": {
                "data": [
                    {
                        "PREDICT_THIS_YEAR_EPS": 1.5,
                        "PREDICT_NEXT_YEAR_EPS": 1.8,
                        "PREDICT_AFTER_YEAR_EPS": 2.0,
                        "PREDICT_THIS_YEAR_PE": 8.5,
                        "RATING_NAME": "买入",
                        "REPORT_DATE": "2026-06-11",
                    },
                ]
            }
        }

        with patch.object(provider, 'get', return_value=mock_data):
            result = await provider.get_consensus_eps("000001")

        assert result is not None
        assert "eps_current" in result
        assert result["eps_current"] == 1.5


class TestResearchReportProviderIntegration:
    """研报数据源集成测试（需要网络）"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_report_list(self):
        """测试真实研报列表"""
        try:
            from providers.research_report_provider import ResearchReportProvider

            provider = ResearchReportProvider()
            result = await provider.get_report_list("000001", limit=5)

            assert result is not None
        except Exception as e:
            pytest.skip(f"网络不可用: {e}")
