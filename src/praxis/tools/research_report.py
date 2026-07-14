"""MCP 工具 — 研报查询 (research_report)

支持最新/按股票/按机构查询研报数据。

数据源：ResearchReportProvider (engine/data/research_report.py)
依赖注入：_deps["research_report_provider"]
"""
from __future__ import annotations

from praxis.agents.base import Tool


async def research_report(
    action: str = "latest",  # "latest" | "ticker" | "org"
    ticker: str = "",
    org: str = "",
    days: int = 30,
    _deps: dict | None = None,
) -> dict:
    """研报查询

    Args:
        action: 操作类型 — latest | ticker | org
        ticker: 股票代码（action=ticker 时必填）
        org: 机构名称（action=org 时必填）
        days: 最近天数（默认 30）
        _deps: 依赖注入字典 {"research_report_provider": ResearchReportProvider}

    Returns:
        {"success": bool, "data": [...], "error": str|None}
    """
    provider = _deps.get("research_report_provider") if _deps else None
    if provider is None:
        return {"success": False, "data": [], "error": "ResearchReportProvider 未注入"}

    try:
        if action == "latest":
            data = await provider.get_latest(days=days)
            return {"success": True, "data": data, "error": None}

        elif action == "ticker":
            if not ticker:
                return {"success": False, "data": [], "error": "action=ticker 需要 ticker 参数"}
            data = await provider.get_by_ticker(ticker, days=days)
            return {"success": True, "data": data, "error": None}

        elif action == "org":
            if not org:
                return {"success": False, "data": [], "error": "action=org 需要 org 参数"}
            data = await provider.get_by_org(org, days=days)
            return {"success": True, "data": data, "error": None}

        else:
            return {"success": False, "data": [], "error": f"未知 action: {action}，支持 latest/ticker/org"}

    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}


def register(registry):
    registry.register(
        Tool(
            name="research_report",
            description="研报查询：最新研报/按股票/按机构获取评级及目标价",
            handler=research_report,
            agent_name="market",
            tier="core",
        )
    )
