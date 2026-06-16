"""研报 MCP 工具层

暴露 2 个工具：
  - get_report_list      获取研报列表
  - get_consensus_eps    获取一致预期 EPS
"""
from __future__ import annotations

from typing import Any


async def get_report_list(
    ticker: str,
    limit: int = 20,
    rating: str | None = None,
) -> dict[str, Any]:
    """获取研报列表

    Args:
        ticker: 股票代码
        limit: 返回数量
        rating: 评级过滤（买入/增持/中性/减持/卖出）

    Returns:
        研报列表
    """
    from providers.research_report_provider import ResearchReportProvider

    provider = ResearchReportProvider()
    try:
        result = await provider.get_report_list(
            ticker,
            limit=limit,
            rating=rating,
        )
        return {
            "success": True,
            "data": {
                "ticker": ticker,
                "reports": result,
                "total": len(result),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_consensus_eps(ticker: str) -> dict[str, Any]:
    """获取一致预期 EPS

    Args:
        ticker: 股票代码

    Returns:
        一致预期 EPS 数据
    """
    from providers.research_report_provider import ResearchReportProvider

    provider = ResearchReportProvider()
    try:
        result = await provider.get_consensus_eps(ticker)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
