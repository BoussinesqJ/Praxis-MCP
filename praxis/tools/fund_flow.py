"""资金流向 MCP 工具层

暴露 3 个工具：
  - get_fund_flow_min      获取个股分钟级资金流向
  - get_fund_flow_daily    获取个股日度资金流向
  - get_fund_flow_all      获取全市场资金流向
"""
from __future__ import annotations

from typing import Any


async def get_fund_flow_min(ticker: str) -> dict[str, Any]:
    """获取个股分钟级资金流向

    Args:
        ticker: 股票代码

    Returns:
        分钟级资金流向数据
    """
    from providers.fund_flow_provider import FundFlowProvider

    provider = FundFlowProvider()
    try:
        result = await provider.get_fund_flow_min(ticker)
        return {
            "success": True,
            "data": {
                "ticker": ticker,
                "flow": result,
                "total": len(result),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_fund_flow_daily(
    ticker: str,
    days: int = 5,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """获取个股日度资金流向

    Args:
        ticker: 股票代码
        days: 获取天数
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）

    Returns:
        日度资金流向数据
    """
    from providers.fund_flow_provider import FundFlowProvider

    provider = FundFlowProvider()
    try:
        result = await provider.get_fund_flow_daily(
            ticker,
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "success": True,
            "data": {
                "ticker": ticker,
                "flow": result,
                "total": len(result),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_fund_flow_all(days: int = 1) -> dict[str, Any]:
    """获取全市场资金流向

    Args:
        days: 获取天数（1/5/10）

    Returns:
        全市场资金流向数据
    """
    from providers.fund_flow_provider import FundFlowProvider

    provider = FundFlowProvider()
    try:
        result = await provider.get_fund_flow_all(days=days)
        return {
            "success": True,
            "data": {
                "flow": result,
                "total": len(result),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
