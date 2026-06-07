"""MCP 工具 - 净值追踪"""
from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from praxis.core.ledger import FileLedger
from praxis.engine.nav_tracker import NavTracker, DailyNav
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.data.provider import CachedDataProvider


def _get_tracker(workspace: str = ".") -> NavTracker:
    """获取净值追踪器实例"""
    nav_path = Path(workspace) / "data" / "nav" / "default.jsonl"
    ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
    ledger = FileLedger(ledger_path)
    provider = CachedDataProvider()
    return NavTracker(nav_path, ledger, provider)


def record_nav(
    investor: str,
    portfolio: str,
    nav: float,
    total_assets: float,
    positions_value: float,
    cash: float,
    benchmark_nav: float | None = None,
    benchmark_code: str | None = None,
    workspace: str = ".",
) -> dict:
    """记录当日净值"""
    try:
        from datetime import datetime
        # Defensive: explicit None coercion for benchmark fields to handle
        # MCP clients that may not correctly pass Optional parameters.
        # See: docs/2026-06-06-praxis-mcp-real-test-report.md (Problem 1)
        _benchmark_nav = benchmark_nav if benchmark_nav is not None else None
        _benchmark_code = benchmark_code if benchmark_code is not None else None

        tracker = _get_tracker(workspace)
        daily_nav = DailyNav(
            date=datetime.now().strftime("%Y-%m-%d"),
            nav=nav,
            total_assets=total_assets,
            positions_value=positions_value,
            cash=cash,
            benchmark_nav=_benchmark_nav,
            benchmark_code=_benchmark_code,
        )
        result = tracker.record(daily_nav)
        return {"success": True, "data": {"message": result}}
    except ValidationError as e:
        # Provide actionable error message for MCP clients
        errors = e.errors()
        details = "; ".join(f"{err['loc'][0]}: {err['msg']}" for err in errors)
        return {
            "success": False,
            "error": f"参数校验失败: {details}. "
                     f"benchmark_nav/benchmark_code 是可选参数，传 null 或省略即可。",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_nav_snapshot(investor: str, portfolio: str, workspace: str = ".") -> dict:
    """获取净值快照"""
    tracker = _get_tracker(workspace)
    loader = YamlConfigLoader(workspace)
    try:
        nav = await tracker.snapshot(investor, portfolio, loader)
        return {
            "success": True,
            "data": nav.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_nav_history(investor: str, portfolio: str, days: int = 30, workspace: str = ".") -> dict:
    """获取净值历史"""
    try:
        tracker = _get_tracker(workspace)
        history = tracker.get_history(days)
        return {
            "success": True,
            "data": {
                "total": tracker.count(),
                "history": [nav.model_dump() for nav in history],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
