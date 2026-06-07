"""AI 建议命中率统计

统计 AI 团队建议 vs 实际结果，回答"AI 是否有帮助"。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.models.decision import DecisionRecord, DecisionStatus


class AITracking(BaseModel):
    """AI 建议追踪"""
    team: str                      # asrg/masters/trading
    total_suggestions: int         # 总建议数
    correct_suggestions: int       # 正确建议数
    hit_rate: float                # 命中率
    avg_confidence: float          # 平均信心度
    confidence_calibration: float  # 信心度校准误差
    overtrading_tendency: float    # 过度交易倾向
    missed_risks: int              # 漏报风险次数


class AITracker:
    """AI 建议命中率统计器"""

    def __init__(self, recorder: FileDecisionRecorder):
        self._recorder = recorder

    def calculate_team_tracking(self, team_name: str) -> AITracking:
        """计算某团队的命中率"""
        decisions = self._recorder.get_executed()

        # 统计该团队的建议
        team_suggestions = []
        for d in decisions:
            if team_name in d.ai_team_signals:
                signal = d.ai_team_signals[team_name]
                team_suggestions.append({
                    "recommendation": signal.recommendation,
                    "confidence": signal.confidence,
                    "actual_outcome": self._get_outcome(d),
                    "invalid_if": signal.invalid_if,
                })

        # 计算命中率
        total = len(team_suggestions)
        correct = sum(
            1 for s in team_suggestions
            if self._is_correct(s["recommendation"], s["actual_outcome"])
        )

        # 计算平均信心度
        avg_confidence = sum(s["confidence"] for s in team_suggestions) / total if total > 0 else 0

        # 计算信心度校准误差
        confidence_calibration = self._calculate_calibration(team_suggestions)

        # 计算过度交易倾向
        overtrading_tendency = self._calculate_overtrading(team_suggestions)

        # 计算漏报风险次数
        missed_risks = self._count_missed_risks(team_suggestions)

        return AITracking(
            team=team_name,
            total_suggestions=total,
            correct_suggestions=correct,
            hit_rate=correct / total if total > 0 else 0,
            avg_confidence=avg_confidence,
            confidence_calibration=confidence_calibration,
            overtrading_tendency=overtrading_tendency,
            missed_risks=missed_risks,
        )

    def _get_outcome(self, decision: DecisionRecord) -> str:
        """获取决策的实际结果"""
        # 从复盘数据获取
        if decision.review_5d and decision.review_5d.actual_return_pct is not None:
            return "profit" if decision.review_5d.actual_return_pct > 0 else "loss"
        return "unknown"

    def _is_correct(self, recommendation: str, outcome: str) -> bool:
        """判断建议是否正确"""
        if outcome == "unknown":
            return False
        if recommendation == "buy" and outcome == "profit":
            return True
        if recommendation == "sell" and outcome == "loss":
            return True
        if recommendation == "hold":
            return True  # hold 通常不算错
        return False

    def _calculate_calibration(self, suggestions: list[dict]) -> float:
        """计算信心度校准误差

        校准误差 = 平均信心度 - 实际命中率
        误差越小，信心度越准确
        """
        if not suggestions:
            return 0

        avg_confidence = sum(s["confidence"] for s in suggestions) / len(suggestions)

        known_outcomes = [s for s in suggestions if s["actual_outcome"] != "unknown"]
        if not known_outcomes:
            return 0

        hit_rate = sum(
            1 for s in known_outcomes
            if self._is_correct(s["recommendation"], s["actual_outcome"])
        ) / len(known_outcomes)

        return avg_confidence - hit_rate

    def _calculate_overtrading(self, suggestions: list[dict]) -> float:
        """计算过度交易倾向

        过度交易倾向 = buy/sell 建议占比
        占比越高，越倾向于交易
        """
        if not suggestions:
            return 0

        active_suggestions = sum(
            1 for s in suggestions
            if s["recommendation"] in ("buy", "sell")
        )

        return active_suggestions / len(suggestions)

    def _count_missed_risks(self, suggestions: list[dict]) -> int:
        """计算漏报风险次数

        漏报风险：建议 buy/hold，但实际亏损
        """
        missed = 0
        for s in suggestions:
            if s["actual_outcome"] == "loss" and s["recommendation"] in ("buy", "hold"):
                missed += 1
        return missed

    def calculate_all_teams(self) -> dict[str, AITracking]:
        """计算所有团队的命中率"""
        results = {}
        for team_name in ["asrg", "masters", "trading"]:
            results[team_name] = self.calculate_team_tracking(team_name)
        return results
