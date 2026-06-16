"""MCP 工具 - AI 建议追踪"""
from __future__ import annotations

from pathlib import Path

from praxis.engine.ai_tracker import AITracker
from praxis.engine.decision_recorder import FileDecisionRecorder


def _get_tracker(workspace: str = ".") -> AITracker:
    """获取 AI 追踪器实例"""
    decisions_path = Path(workspace) / "data" / "decisions" / "decision_records.jsonl"
    recorder = FileDecisionRecorder(decisions_path)
    return AITracker(recorder)


def get_ai_tracking(team: str | None = None, workspace: str = ".") -> dict:
    """获取 AI 建议命中率"""
    try:
        tracker = _get_tracker(workspace)

        if team:
            # 查询单个团队
            tracking = tracker.calculate_team_tracking(team)
            return {
                "success": True,
                "data": tracking.model_dump(),
            }
        else:
            # 查询所有团队
            all_tracking = tracker.calculate_all_teams()
            return {
                "success": True,
                "data": {
                    team_name: tracking.model_dump()
                    for team_name, tracking in all_tracking.items()
                },
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_tracking(tracking_data: dict) -> str:
    """格式化追踪结果"""
    lines = ["=== AI 建议命中率 ==="]

    if "team" in tracking_data:
        # 单个团队
        t = tracking_data
        lines.append(f"团队: {t['team']}")
        lines.append(f"总建议数: {t['total_suggestions']}")
        lines.append(f"正确建议数: {t['correct_suggestions']}")
        lines.append(f"命中率: {t['hit_rate']:.1%}")
        lines.append(f"平均信心度: {t['avg_confidence']:.2f}")
        lines.append(f"信心度校准误差: {t['confidence_calibration']:.2f}")
        lines.append(f"过度交易倾向: {t['overtrading_tendency']:.1%}")
        lines.append(f"漏报风险次数: {t['missed_risks']}")
    else:
        # 所有团队
        for team_name, t in tracking_data.items():
            lines.append(f"\n--- {team_name} ---")
            lines.append(f"  命中率: {t['hit_rate']:.1%}")
            lines.append(f"  平均信心度: {t['avg_confidence']:.2f}")
            lines.append(f"  信心度校准误差: {t['confidence_calibration']:.2f}")

    return "\n".join(lines)
