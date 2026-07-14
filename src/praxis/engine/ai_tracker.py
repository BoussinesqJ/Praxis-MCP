"""AI 建议命中率统计 — AI 团队建议 vs 实际结果"""
from __future__ import annotations

from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.models import DecisionRecord, DecisionStatus
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class AITracker:
    """AI 建议命中率统计器"""

    def __init__(self, recorder: FileDecisionRecorder):
        self._recorder = recorder

    def calculate_team_tracking(self, team_name: str) -> dict:
        """计算某团队的命中率"""
        decisions = self._recorder.get_executed()

        total = correct = 0
        confidences = []

        for d in decisions:
            if not d.review_result:
                continue

            signals = d.team_signals if hasattr(d, 'team_signals') else []
            for signal in signals:
                if hasattr(signal, 'team_name') and signal.team_name == team_name:
                    total += 1
                    confidences.append(signal.confidence)
                    if signal.action == d.action:
                        correct += 1

        hit_rate = correct / total if total > 0 else 0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {"success": True, "data": {
            "team": team_name,
            "total_suggestions": total,
            "correct_suggestions": correct,
            "hit_rate": round(hit_rate, 4),
            "avg_confidence": round(avg_confidence, 4),
        }}

    def calculate_all_teams(self) -> dict:
        """计算所有团队的命中率"""
        teams = {"asrg", "masters", "trading"}
        results = {}
        for team in teams:
            result = self.calculate_team_tracking(team)
            if result["success"]:
                results[team] = result["data"]
        return {"success": True, "data": results}
