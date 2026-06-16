"""龙虎榜 MCP 工具层

暴露 2 个工具：
  - get_dragon_tiger_list    获取龙虎榜列表
  - get_dragon_tiger_detail  获取龙虎榜详情
"""
from __future__ import annotations

from typing import Any


async def get_dragon_tiger_list(
    date: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """获取龙虎榜列表

    Args:
        date: 日期（YYYY-MM-DD），None 为今日
        limit: 返回数量

    Returns:
        龙虎榜列表
    """
    from providers.dragon_tiger_provider import DragonTigerProvider

    provider = DragonTigerProvider()
    try:
        result = await provider.get_dragon_tiger_list(date=date, limit=limit)
        return {
            "success": True,
            "data": {
                "date": date,
                "list": result,
                "total": len(result),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_dragon_tiger_detail(ticker: str) -> dict[str, Any]:
    """获取龙虎榜详情（买卖席位）

    Args:
        ticker: 股票代码

    Returns:
        龙虎榜详情
    """
    from providers.dragon_tiger_provider import DragonTigerProvider

    provider = DragonTigerProvider()
    try:
        result = await provider.get_dragon_tiger_detail(ticker)
        return {
            "success": True,
            "data": {
                "ticker": ticker,
                "seats": result,
                "total": len(result),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
