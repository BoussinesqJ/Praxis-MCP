"""MCP 工具 — 进化引擎

从原版 tools/evolution.py 迁移，适配重构版接口。
"""
from __future__ import annotations

from praxis.engine.evolution import EvolutionEngine


async def evolution(
    action: str,
    strategy_name: str = "",
    investor_id: str = "",
    portfolio_id: str = "",
    limit: int = 20,
    _deps: dict | None = None,
) -> dict:
    """进化引擎工具

    Args:
        action: "evaluate" | "history" | "propose"
        strategy_name: 策略名称
        investor_id: 投资者 ID
        portfolio_id: 组合 ID
        limit: 返回历史记录数
        _deps: 依赖注入 {workspace, config_loader, performance_calculator}

    Returns:
        {success, data, error}
    """
    deps = _deps or {}
    workspace = deps.get("workspace", ".")

    engine = EvolutionEngine(str(workspace))

    if action == "evaluate":
        config_loader = deps.get("config_loader")
        calculator = deps.get("performance_calculator")
        if calculator is None:
            return {"success": False, "error": "未注入 performance_calculator"}

        result = engine.evaluate(
            strategy_name=strategy_name,
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            calculator=calculator,
            config_loader=config_loader,
        )
        return result

    elif action == "history":
        history = engine.get_history(strategy_name, limit=limit)
        return {
            "success": True,
            "data": {
                "records": history,
                "count": len(history),
            },
        }

    elif action == "propose":
        calculator = deps.get("performance_calculator")
        if calculator is None:
            return {"success": False, "error": "未注入 performance_calculator"}

        evaluation = engine.evaluate(
            strategy_name=strategy_name,
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            calculator=calculator,
        )

        if not evaluation.get("success"):
            return evaluation

        data = evaluation["data"]
        suggestions = data.get("evolution_suggestions", [])
        overall = data.get("overall_health", "healthy")

        if not suggestions:
            return {
                "success": True,
                "data": {
                    "status": "no_action_needed",
                    "overall_health": overall,
                    "message": "所有进化维度均在健康范围内",
                },
            }

        return {
            "success": True,
            "data": {
                "status": "proposals_generated",
                "overall_health": overall,
                "suggestions": suggestions,
                "message": f"生成 {len(suggestions)} 条进化建议",
            },
        }

    else:
        return {
            "success": False,
            "error": f"未知 action: {action}，支持 evaluate | history | propose",
        }
