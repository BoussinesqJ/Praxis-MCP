"""东财研报数据源

基于 Gemini Phase 2 建议：
- 继承 EMClient 基类（自动限流 + 缓存 + UA 伪装）
- 研报数据 12 小时内不重复请求
- 东财 reportapi API

使用方式：
    from providers.research_report_provider import ResearchReportProvider

    provider = ResearchReportProvider()
    
    # 获取研报列表
    reports = await provider.get_report_list("000001")
    
    # 获取一致预期 EPS
    eps = await provider.get_consensus_eps("000001")
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from praxis.core.em_client import EMClient, EMClientConfig

logger = logging.getLogger("praxis.provider.research_report")

# 东财研报 API
EM_REPORT_LIST_URL = "https://reportapi.eastmoney.com/report/list"
EM_CONSENSUS_EPS_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


class ResearchReportProvider(EMClient):
    """东财研报数据源

    继承 EMClient，自动获得：
    - 限流器保护
    - TTL 缓存（12小时）
    - User-Agent 伪装
    - Session 复用
    - 自动重试
    """

    def __init__(self, config: Optional[EMClientConfig] = None):
        super().__init__(config)

    async def get_report_list(
        self,
        ticker: str,
        limit: int = 20,
        rating: Optional[str] = None,
    ) -> list[dict]:
        """获取研报列表

        Args:
            ticker: 股票代码
            limit: 返回数量
            rating: 评级过滤（买入/增持/中性/减持/卖出）

        Returns:
            研报列表
        """
        # 构建缓存键
        cache_key = f"report_list:{ticker}:{limit}:{rating}"

        # 构建请求参数
        params = {
            "industryCode": "*",
            "pageSize": str(limit),
            "industry": "*",
            "rating": rating or "*",
            "ratingChange": "*",
            "beginTime": "",
            "endTime": "",
            "pageNo": "1",
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": ticker,
            "rcode": "",
            "p": "1",
            "pageNum": "1",
            "pageNumber": "1",
        }

        try:
            data = await self.get(
                EM_REPORT_LIST_URL,
                params=params,
                cache_key=cache_key,
                cache_ttl=43200,  # 12小时缓存
            )

            if not data or "data" not in data:
                return []

            items = data.get("data", [])
            if not items:
                return []

            result = []
            for item in items:
                result.append({
                    "stock_code": item.get("stockCode", ""),
                    "stock_name": item.get("stockName", ""),
                    "title": item.get("title", ""),
                    "org_name": item.get("orgSName", ""),
                    "rating": item.get("emRatingName", ""),
                    "eps_current": float(item.get("predictThisYearEps", 0) or 0),
                    "eps_next": float(item.get("predictNextYearEps", 0) or 0),
                    "pe_current": float(item.get("predictThisYearPe", 0) or 0),
                    "pe_next": float(item.get("predictNextYearPe", 0) or 0),
                    "publish_date": item.get("publishDate", ""),
                    "researcher": item.get("researcher", ""),
                })

            return result

        except Exception as e:
            logger.warning(f"获取研报列表失败: {e}")
            return []

    async def get_consensus_eps(self, ticker: str) -> dict:
        """获取一致预期 EPS

        Args:
            ticker: 股票代码

        Returns:
            一致预期 EPS 数据
        """
        # 构建缓存键
        cache_key = f"consensus_eps:{ticker}:{datetime.now().strftime('%Y%m%d')}"

        # 构建请求参数
        params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "1",
            "pageNumber": "1",
            "reportName": "RPT_CONSENSUS_FORECAST",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(SECURITY_CODE=\'{ticker}\')',
        }

        try:
            data = await self.get(
                EM_CONSENSUS_EPS_URL,
                params=params,
                cache_key=cache_key,
                cache_ttl=43200,  # 12小时缓存
            )

            if not data or "result" not in data:
                return {}

            result_data = data.get("result", {})
            if not result_data:
                return {}

            items = result_data.get("data", [])
            if not items:
                return {}

            item = items[0]
            return {
                "stock_code": ticker,
                "eps_current": float(item.get("PREDICT_THIS_YEAR_EPS", 0) or 0),
                "eps_next": float(item.get("PREDICT_NEXT_YEAR_EPS", 0) or 0),
                "eps_future": float(item.get("PREDICT_AFTER_YEAR_EPS", 0) or 0),
                "pe_current": float(item.get("PREDICT_THIS_YEAR_PE", 0) or 0),
                "pe_next": float(item.get("PREDICT_NEXT_YEAR_PE", 0) or 0),
                "rating": item.get("RATING_NAME", ""),
                "report_date": item.get("REPORT_DATE", ""),
            }

        except Exception as e:
            logger.warning(f"获取一致预期 EPS 失败: {e}")
            return {}
