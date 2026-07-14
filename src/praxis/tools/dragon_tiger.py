"""MCP 工具 — 龙虎榜查询 (dragon_tiger)

支持今日/按日期/按股票查询龙虎榜数据。

数据源：DragonTigerProvider (engine/data/dragon_tiger.py)
依赖注入：_deps["dragon_tiger_provider"]
"""
from __future__ import annotations

from praxis.agents.base import Tool


async def dragon_tiger(
    action: str = "today",  # "today" | "date" | "stock"
    date: str = "",
    ticker: str = "",
    _deps: dict | None = None,
) -> dict:
    """龙虎榜查询

    Args:
        action: 操作类型 — today | date | stock
        date: 日期 YYYY-MM-DD（action=date 时必填）
        ticker: 股票代码（action=stock 时必填）
        _deps: 依赖注入字典 {"dragon_tiger_provider": DragonTigerProvider}

    Returns:
        {"success": bool, "data": [...], "error": str|None}
    """
    provider = _deps.get("dragon_tiger_provider") if _deps else None
    if provider is None:
        return {"success": False, "data": [], "error": "DragonTigerProvider 未注入"}

    try:
        if action == "today":
            data = await provider.get_today_list()
            return {"success": True, "data": data, "error": None}

        elif action == "date":
            if not date:
                return {"success": False, "data": [], "error": "action=date 需要 date 参数"}
            data = await provider.get_by_date(date)
            return {"success": True, "data": data, "error": None}

        elif action == "stock":
            if not ticker:
                return {"success": False, "data": [], "error": "action=stock 需要 ticker 参数"}
            data = await provider.get_by_stock(ticker)
            return {"success": True, "data": data, "error": None}

        else:
            return {"success": False, "data": [], "error": f"未知 action: {action}，支持 today/date/stock"}

    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}


def register(registry):
    registry.register(
        Tool(
            name="dragon_tiger",
            description="龙虎榜查询：今日上榜/按日期/按股票查询买卖席位",
            handler=dragon_tiger,
            agent_name="market",
            tier="core",
        )
    )
