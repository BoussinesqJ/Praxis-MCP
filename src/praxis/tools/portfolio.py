"""组合管理(读) — portfolio"""
from __future__ import annotations

import json

from praxis.agents.base import Tool
from praxis.tools._schemas import PortfolioInput


def _summary_external(portfolio_json: str) -> dict:
    """使用外部组合数据计算摘要

    Args:
        portfolio_json: PortfolioPayload JSON 字符串

    Returns:
        组合摘要 dict
    """
    if not portfolio_json or not portfolio_json.strip():
        return {"success": False, "error": "缺少外部组合数据"}

    try:
        raw = json.loads(portfolio_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}"}

    from praxis.core.schemas import PortfolioPayload

    try:
        payload = PortfolioPayload.model_validate(raw)
    except Exception as e:
        return {"success": False, "error": f"组合数据校验失败: {e}"}

    total_assets = payload.cash.get("total_assets", 0) if isinstance(payload.cash, dict) else 0
    available_cash = payload.cash.get("available_cash", 0) if isinstance(payload.cash, dict) else 0
    cash_ratio = (available_cash / total_assets * 100) if total_assets > 0 else 0.0

    return {
        "success": True,
        "data": {
            "investor": payload.investor,
            "portfolio": payload.portfolio,
            "total_assets": total_assets,
            "available_cash": available_cash,
            "cash_ratio_pct": round(cash_ratio, 2),
            "positions_count": len(payload.positions),
            "source": "external",
        },
    }


def _state_external(portfolio_json: str) -> dict:
    """使用外部组合数据计算状态

    Args:
        portfolio_json: PortfolioPayload JSON 字符串

    Returns:
        组合状态 dict
    """
    if not portfolio_json or not portfolio_json.strip():
        return {"success": False, "error": "缺少外部组合数据"}

    try:
        raw = json.loads(portfolio_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}"}

    from praxis.core.schemas import PortfolioPayload

    try:
        payload = PortfolioPayload.model_validate(raw)
    except Exception as e:
        return {"success": False, "error": f"组合数据校验失败: {e}"}

    positions_detail = []
    for pos in payload.positions:
        if isinstance(pos, dict):
            positions_detail.append({
                "ticker": pos.get("ticker", ""),
                "name": pos.get("name", ""),
                "shares": pos.get("shares", 0),
                "cost": pos.get("cost", 0),
                "current_price": pos.get("current_price", 0),
                "market_value": pos.get("market_value", 0),
                "profit_pct": pos.get("profit_pct", 0),
            })

    cash = payload.cash if isinstance(payload.cash, dict) else {}
    total_assets = cash.get("total_assets", 0)

    return {
        "success": True,
        "data": {
            "investor": payload.investor,
            "portfolio": payload.portfolio,
            "total_assets": total_assets,
            "cash": cash,
            "positions": positions_detail,
            "source": "external",
        },
    }


async def portfolio(action: str, investor: str, portfolio: str, ticker: str = "",
                    portfolio_json: str = "", _deps: dict | None = None) -> dict:
    if action == "summary_external":
        return _summary_external(portfolio_json)
    elif action == "state_external":
        return _state_external(portfolio_json)
    loader = _deps.get("config_loader") if _deps else None
    if loader is None:
        return {"success": False, "error": "ConfigLoader未注入"}
    try:
        if action == "config":
            pf = loader.load_portfolio(investor, portfolio)
            return {"success": True, "data": pf.model_dump()}
        elif action == "detail":
            detail = loader.load_asset_detail(investor, portfolio, ticker)
            return {"success": True, "data": detail}
        elif action == "summary":
            pf = loader.load_portfolio(investor, portfolio)
            inv = loader.load_investor(investor)
            return {"success": True, "data": {
                "investor": inv.name, "portfolio": pf.portfolio_id,
                "assets": len(pf.assets), "capital": inv.capital_cny}}
        elif action == "state":
            from praxis.core.models import PortfolioState
            state = PortfolioState(investor_id=investor, portfolio_id=portfolio)
            return {"success": True, "data": state.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}
    return {"success": False, "error": f"未知 action: {action}"}

def register(registry):
    registry.register(Tool(name="portfolio", description="组合管理(读)：config/detail/summary/state",
                           input_schema=PortfolioInput, handler=portfolio, agent_name="admin", tier="core"))
