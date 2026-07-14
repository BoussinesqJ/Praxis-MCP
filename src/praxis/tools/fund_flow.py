"""MCP 工具 — 资金流向查询 (fund_flow)

支持个股/板块/全市场资金流向查询。

数据源：FundFlowProvider (engine/data/fund_flow.py)
依赖注入：_deps["fund_flow_provider"]
"""
from __future__ import annotations

from praxis.agents.base import Tool


async def fund_flow(
    action: str = "stock",  # "stock" | "sector" | "market"
    ticker: str = "",
    sector: str = "",
    days: int = 5,
    _deps: dict | None = None,
) -> dict:
    """资金流向查询

    Args:
        action: 操作类型 — stock | sector | market
        ticker: 股票代码（action=stock 时必填）
        sector: 板块名称（action=sector 时必填）
        days: 查询天数（默认 5）
        _deps: 依赖注入字典 {"fund_flow_provider": FundFlowProvider}

    Returns:
        {"success": bool, "data": dict, "error": str|None}
    """
    provider = _deps.get("fund_flow_provider") if _deps else None
    if provider is None:
        return {"success": False, "data": None, "error": "FundFlowProvider 未注入"}

    try:
        if action == "stock":
            if not ticker:
                return {"success": False, "data": None, "error": "action=stock 需要 ticker 参数"}
            return await provider.get_stock_fund_flow(ticker, days=days)

        elif action == "sector":
            if not sector:
                return {"success": False, "data": None, "error": "action=sector 需要 sector 参数"}
            return await provider.get_sector_fund_flow(sector)

        elif action == "market":
            return await provider.get_market_fund_flow()

        else:
            return {"success": False, "data": None, "error": f"未知 action: {action}，支持 stock/sector/market"}

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def register(registry):
    registry.register(
        Tool(
            name="fund_flow",
            description="资金流向查询：个股/板块/全市场主力资金净流入",
            handler=fund_flow,
            agent_name="market",
            tier="core",
        )
    )
