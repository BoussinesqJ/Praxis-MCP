"""市场数据工具 — get_market_data"""
from __future__ import annotations

from praxis.agents.base import Tool
from praxis.tools._schemas import GetMarketDataInput


async def get_market_data(tickers: list[str], _deps: dict | None = None) -> dict:
    """获取实时行情数据"""
    provider = _deps.get("data_provider") if _deps else None
    if provider is None:
        return {"success": False, "error": "DataProvider 未注入"}
    try:
        result = await provider.get_realtime_quote(tickers)
        for _ticker, data in result.items():
            if "timestamp" in data:
                data["is_realtime"] = True
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register(registry):
    registry.register(Tool(
        name="get_market_data",
        description="获取实时行情数据：价格/涨跌幅/成交量。多源容错（腾讯→akshare→baostock）。",
        input_schema=GetMarketDataInput,
        handler=get_market_data,
        agent_name="market",
        tier="core",
    ))
