"""净值管理 — nav"""
from __future__ import annotations
from praxis.agents.base import Tool
from praxis.tools._schemas import NavInput

async def nav(action: str,
              investor: str | None = None,
              portfolio: str | None = None,
              nav: float | None = None,
              total_assets: float | None = None,
              positions_value: float | None = None,
              cash: float | None = None,
              benchmark_nav: float | None = None,
              benchmark_code: str | None = None,
              days: int = 30,
              _deps: dict | None = None) -> dict:
    """净值管理：record | snapshot | history | latest

    Args:
        action: 操作类型 — record | snapshot | history | latest
        investor: 投资者 ID（snapshot 时使用）
        portfolio: 组合 ID（snapshot 时使用）
        nav: 净值（record 时必填）
        total_assets: 总资产（record 时必填）
        positions_value: 持仓市值（record 时必填）
        cash: 现金（record 时必填）
        benchmark_nav: 基准净值（record 可选）
        benchmark_code: 基准代码（record 可选）
        days: 历史天数（history 时使用，默认 30）
        _deps: 依赖注入字典，需包含 'nav_tracker'

    Returns:
        {"success": bool, "data": ..., "error": str|None}
    """
    tracker = _deps.get("nav_tracker") if _deps else None
    if tracker is None:
        return {"success": False, "error": "NavTracker未注入"}

    if action == "record":
        if nav is None or total_assets is None or positions_value is None or cash is None:
            return {"success": False, "error": "record 需要 nav, total_assets, positions_value, cash 四个必填参数"}
        return tracker.record(nav, total_assets, positions_value, cash, benchmark_nav, benchmark_code)

    elif action == "snapshot":
        return await tracker.snapshot(investor or "", portfolio or "")

    elif action == "history":
        return tracker.get_history(days)

    elif action == "latest":
        history = tracker.get_history(days=1)
        if not history.get("success"):
            return {"success": False, "error": "获取净值历史失败"}
        records = history.get("data", {}).get("records", [])
        if not records:
            return {"success": False, "error": "无净值记录"}
        return {"success": True, "data": records[-1]}

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(name="nav", description="净值管理：record/snapshot/history/latest",
                           input_schema=NavInput, handler=nav, agent_name="admin", tier="core"))
