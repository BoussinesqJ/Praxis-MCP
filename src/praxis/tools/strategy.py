"""MCP 工具 — 策略管理

支持列出所有策略、查看策略详情、查看版本历史。
"""
from __future__ import annotations

from pathlib import Path

from praxis.agents.base import Tool
from praxis.engine.config_loader import YamlConfigLoader


async def strategy(
    action: str,  # "list" | "info" | "versions"
    strategy_name: str = "",
    _deps: dict | None = None,
) -> dict:
    """策略管理

    Args:
        action: 操作类型 — list | info | versions
        strategy_name: 策略名称（info/versions 时必填）
        _deps: 依赖注入字典，需包含 'workspace'

    Returns:
        {"success": bool, "data": ..., "error": str|None}
    """
    ws = _deps.get("workspace", ".") if _deps else "."
    strategies_dir = Path(ws) / "config" / "strategies"

    if action == "list":
        try:
            if not strategies_dir.exists():
                return {"success": True, "data": {"strategies": []}}

            strategies = []
            for f in sorted(strategies_dir.glob("*.yaml")):
                strategies.append(f.stem)

            return {"success": True, "data": {"strategies": strategies, "count": len(strategies)}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    elif action == "info":
        if not strategy_name:
            return {"success": False, "error": "action=info 需要 strategy_name 参数"}

        try:
            loader = YamlConfigLoader(ws)
            st = loader.load_strategy(strategy_name)
            return {"success": True, "data": st.model_dump()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    elif action == "versions":
        if not strategy_name:
            return {"success": False, "error": "action=versions 需要 strategy_name 参数"}

        try:
            versions_dir = strategies_dir / "versions" / strategy_name
            if not versions_dir.exists():
                return {"success": True, "data": {"strategy_name": strategy_name, "versions": []}}

            versions = []
            for f in sorted(versions_dir.glob("*.yaml")):
                versions.append({"version": f.stem, "path": str(f)})

            return {
                "success": True,
                "data": {"strategy_name": strategy_name, "versions": versions},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(
        Tool(
            name="strategy",
            description="策略管理：list/info/versions — 列出策略、查看详情、查看版本历史",
            handler=strategy,
            agent_name="admin",
            tier="core",
        )
    )
