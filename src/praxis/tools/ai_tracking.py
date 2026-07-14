"""AI 追踪工具 — AI 团队建议命中率统计

包装 engine/ai_tracker.py 中的 AITracker 类。
"""
from __future__ import annotations

from praxis.agents.base import Tool
from praxis.tools._schemas import AgentTrackingInput
from praxis.engine.ai_tracker import AITracker
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


async def ai_tracking(
    action: str,
    team_name: str = "",
    _deps: dict | None = None,
) -> dict:
    """AI 建议命中率追踪

    Args:
        action: "team" 计算单团队 / "all" 计算全团队
        team_name: 团队名称（action="team" 时必填）
        _deps: 依赖注入 {"recorder": DecisionRecorder 实例}

    Returns:
        {success: bool, data: dict, error: str | None}
    """
    recorder = _deps.get("recorder") if _deps else None
    if recorder is None:
        return {"success": False, "data": None, "error": "DecisionRecorder 未注入"}

    try:
        tracker = AITracker(recorder)
    except Exception as e:
        logger.error(f"创建 AITracker 失败: {e}")
        return {"success": False, "data": None, "error": f"创建 AITracker 失败: {e}"}

    if action == "team":
        if not team_name:
            return {"success": False, "data": None, "error": "action=team 时需提供 team_name"}
        try:
            result = tracker.calculate_team_tracking(team_name)
            result.setdefault("error", None)  # 统一格式
            return result
        except Exception as e:
            logger.error(f"计算团队 {team_name} 追踪失败: {e}")
            return {"success": False, "data": None, "error": str(e)}

    elif action == "all":
        try:
            result = tracker.calculate_all_teams()
            result.setdefault("error", None)  # 统一格式
            return result
        except Exception as e:
            logger.error(f"计算全团队追踪失败: {e}")
            return {"success": False, "data": None, "error": str(e)}

    return {"success": False, "data": None, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(
        name="ai_tracking",
        description="AI 团队建议命中率统计：分析各AI团队(asrg/masters/trading)的建议准确率、信心度校准等。",
        input_schema=AgentTrackingInput,
        handler=ai_tracking,
        agent_name="review",
        tier="advanced",
        is_readonly=True,
    ))
