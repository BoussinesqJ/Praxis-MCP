"""AI 决策漂移与标定检查器"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from praxis.core.models.decision import DecisionRecord, DecisionStatus


class DriftCheckResult(BaseModel):
    """漂移检测结果"""
    status: str  # "normal" | "warning" | "critical"
    ece: float
    brier_score: float
    high_conf_win_rate: float | None = None  # 置信度 > 0.8 的实际胜率
    total_samples: int
    message: str
    suggested_actions: list[str] = Field(default_factory=list)


class AIDriftDetector:
    """AI 决策漂移检测器，计算 ECE 与 Brier 分数，并执行风险预警"""

    def __init__(
        self,
        ece_threshold: float = 0.25,
        brier_threshold: float = 0.20,
        high_conf_threshold: float = 0.80,
        min_high_conf_win_rate: float = 0.40,
    ):
        self.ece_threshold = ece_threshold
        self.brier_threshold = brier_threshold
        self.high_conf_threshold = high_conf_threshold
        self.min_high_conf_win_rate = min_high_conf_win_rate

    def detect_drift(self, decisions: list[DecisionRecord], team_name: str | None = None) -> DriftCheckResult:
        """评估决策记录列表，计算标定偏差，并给出状态预警"""
        samples: list[tuple[float, float]] = []  # (confidence, outcome)
        
        for d in decisions:
            # 1. 确定决策实际表现（1=获利/胜，0=亏损/负）
            outcome = None
            for snapshot in (d.review_5d, d.review_20d, d.review_60d):
                if snapshot and snapshot.actual_return_pct is not None:
                    outcome = 1.0 if snapshot.actual_return_pct > 0 else 0.0
                    break
            
            if outcome is None:
                continue  # 跳过没有复盘结果的决策

            # 2. 获取置信度
            if team_name is not None:
                if d.ai_team_signals and team_name in d.ai_team_signals:
                    conf = d.ai_team_signals[team_name].confidence
                    samples.append((conf, outcome))
            else:
                samples.append((d.confidence, outcome))

        total_samples = len(samples)
        if total_samples == 0:
            return DriftCheckResult(
                status="normal",
                ece=0.0,
                brier_score=0.0,
                high_conf_win_rate=None,
                total_samples=0,
                message="没有可用的复盘决策样本进行漂移分析",
                suggested_actions=[],
            )

        # 计算 Brier Score
        brier_sum = sum((conf - outcome) ** 2 for conf, outcome in samples)
        brier_score = brier_sum / total_samples

        # 计算 ECE (10 bins)
        num_bins = 10
        bins: list[list[tuple[float, float]]] = [[] for _ in range(num_bins)]
        for conf, outcome in samples:
            # 限制在 [0, 1] 范围内
            c = max(0.0, min(1.0, conf))
            bin_idx = int(c * num_bins)
            if bin_idx == num_bins:
                bin_idx = num_bins - 1
            bins[bin_idx].append((c, outcome))

        ece = 0.0
        for b in bins:
            if not b:
                continue
            bin_size = len(b)
            avg_conf = sum(c for c, _ in b) / bin_size
            avg_acc = sum(o for _, o in b) / bin_size
            ece += (bin_size / total_samples) * abs(avg_acc - avg_conf)

        # 计算置信度 > 0.8 的胜率
        high_conf_samples = [o for c, o in samples if c >= self.high_conf_threshold]
        high_conf_win_rate = None
        if high_conf_samples:
            high_conf_win_rate = sum(high_conf_samples) / len(high_conf_samples)

        # 判断状态
        status = "normal"
        suggested_actions = []
        messages = []

        # 检查 Critical 条件
        if high_conf_win_rate is not None and high_conf_win_rate < self.min_high_conf_win_rate:
            status = "critical"
            messages.append(f"高置信度（>= {self.high_conf_threshold:.0%}）胜率过低: {high_conf_win_rate:.1%}")
            suggested_actions.extend([
                "【风控】建议调减单标的持仓上限 (例如降低至 5%)",
                "【风控】立即降低总体策略头寸，增加现金底线比例",
                "【优化】暂停高风险策略，对 AI 团队提示词与知识库进行重新标定",
            ])
        # 检查 Warning 条件
        elif ece > self.ece_threshold or brier_score > self.brier_threshold:
            status = "warning"
            if ece > self.ece_threshold:
                messages.append(f"标定误差 ECE ({ece:.3f}) 超过预警阈值 ({self.ece_threshold})")
            if brier_score > self.brier_threshold:
                messages.append(f"Brier 分数 ({brier_score:.3f}) 超过预警阈值 ({self.brier_threshold})")
            suggested_actions.extend([
                "建议对高置信度决策增加二次人工复核",
                "建议收集近期的偏差样本进行策略微调",
            ])
        else:
            messages.append("AI 决策标定良好，未检测到显著漂移")

        return DriftCheckResult(
            status=status,
            ece=ece,
            brier_score=brier_score,
            high_conf_win_rate=high_conf_win_rate,
            total_samples=total_samples,
            message="; ".join(messages),
            suggested_actions=suggested_actions,
        )
