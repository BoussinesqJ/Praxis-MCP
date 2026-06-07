"""MCP 工具 - 市场数据"""
from __future__ import annotations

from praxis.engine.data.provider import CachedDataProvider


async def get_market_data(tickers: list[str]) -> dict:
    """获取行情数据"""
    provider = CachedDataProvider()
    try:
        result = await provider.get_realtime_quote(tickers)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await provider.close()
