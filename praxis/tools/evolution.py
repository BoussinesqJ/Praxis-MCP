"""MCP 工具 - 进化引擎"""
from __future__ import annotations

from praxis.engine.evolution import EvolutionEngine


def evaluate_evolution(
    strategy_name: str,
    investor: str,
    portfolio: str,
    workspace: str = ".",
) -> dict:
    """评估进化维度"""
    try:
        engine = EvolutionEngine(workspace)
        result = engine.evaluate(strategy_name, investor, portfolio)
        if result["success"]:
            result["data"]["formatted"] = engine.format_evaluation(result)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def evolve_strategy(
    strategy_name: str,
    investor: str,
    portfolio: str,
    workspace: str = ".",
) -> dict:
    """进化策略（需审批，GPT 架构底线）

    流程：
    1. 评估进化维度
    2. 生成进化建议
    3. 备份策略文件
    4. 返回修改预览（需人工审批后写入）
    """
    try:
        engine = EvolutionEngine(workspace)

        # 1. 评估
        evaluation = engine.evaluate(strategy_name, investor, portfolio)
        if not evaluation["success"]:
            return evaluation

        # 添加格式化输出
        evaluation["data"]["formatted"] = engine.format_evaluation(evaluation)

        # 2. 备份
        backup_path = engine.backup_strategy(strategy_name)

        # 3. 返回修改预览
        return {
            "success": True,
            "data": {
                "status": "pending_approval",
                "evaluation": evaluation["data"],
                "backup_path": backup_path,
                "message": "进化评估完成，策略文件已备份。需人工审批后执行修改。",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
