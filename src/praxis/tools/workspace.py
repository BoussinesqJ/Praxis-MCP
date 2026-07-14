"""工作区发现 — discover_workspace"""
from __future__ import annotations
from pathlib import Path
import yaml
from praxis.agents.base import Tool
from praxis.tools._schemas import WorkspaceInput

_PROFILE_TEMPLATE = {
    "investor_id": "",
    "name": "",
    "capital_cny": 100000.0,
    "risk_level": "C3",
    "style": "balanced",
    "max_drawdown_pct": 20.0,
    "constraints": {
        "max_single_position_pct": 30.0,
        "max_trades_per_day": 5,
        "min_cash_pct": 5.0,
    },
}

_REQUIRED_FILES = [
    "config/investors",
    "config/portfolios",
    "data/ledger.jsonl",
    "data/nav.jsonl",
]


async def discover_workspace(action: str = "discover",
                             investor_name: str = "",
                             capital: float = 100000.0,
                             _deps: dict | None = None) -> dict:
    """工作区管理：discover | init | validate

    Args:
        action: 操作类型 — discover | init | validate
        investor_name: 投资者名称（init 时必填）
        capital: 初始资金（init 时使用，默认 100000.0）
        _deps: 依赖注入字典，需包含 'workspace'（discover 使用）

    Returns:
        {"success": bool, "data": ..., "error": str|None}
    """
    ws_path = _deps.get("workspace", ".") if _deps else "."

    if action == "discover":
        ws = Path(ws_path)
        investors = (
            list((ws / "config" / "investors").glob("*/profile.yaml"))
            if (ws / "config" / "investors").exists()
            else []
        )
        portfolios = (
            list((ws / "config" / "portfolios").glob("*.yaml"))
            if (ws / "config" / "portfolios").exists()
            else []
        )
        return {
            "success": True,
            "data": {
                "workspace": str(ws),
                "investors": [i.parent.name for i in investors],
                "portfolios": [p.stem for p in portfolios],
                "has_ledger": (ws / "data" / "ledger.jsonl").exists(),
                "has_nav": (ws / "data" / "nav.jsonl").exists(),
            },
        }

    elif action == "init":
        if not investor_name:
            return {"success": False, "error": "init 需要 investor_name 参数"}
        ws = Path(ws_path)
        # 创建目录结构
        investor_dir = ws / "config" / "investors" / investor_name
        portfolio_dir = ws / "config" / "portfolios"
        data_dir = ws / "data"
        for d in [investor_dir, portfolio_dir, data_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 写入 profile.yaml 模板
        profile = dict(_PROFILE_TEMPLATE)
        profile["investor_id"] = investor_name
        profile["name"] = investor_name
        profile["capital_cny"] = capital

        profile_path = investor_dir / "profile.yaml"
        with open(profile_path, "w", encoding="utf-8") as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)

        return {
            "success": True,
            "data": {
                "investor_name": investor_name,
                "profile_path": str(profile_path),
                "capital": capital,
            },
        }

    elif action == "validate":
        ws = Path(ws_path)
        missing = []
        for rel_path in _REQUIRED_FILES:
            fp = ws / rel_path
            if rel_path.endswith((".jsonl", ".yaml")):
                if not fp.is_file():
                    missing.append(rel_path)
            else:
                if not fp.is_dir():
                    missing.append(rel_path)

        if missing:
            return {
                "success": False,
                "error": f"缺少文件/目录: {', '.join(missing)}",
                "data": {"missing": missing},
            }
        return {"success": True, "data": {"workspace": str(ws), "all_present": True}}

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(name="discover_workspace", description="工作区发现：列出投资者/组合/数据状态",
                           input_schema=WorkspaceInput, handler=discover_workspace, agent_name="admin", tier="core"))
