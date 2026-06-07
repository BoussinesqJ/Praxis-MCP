"""AI 决策漂移检测测试"""
import pytest
from datetime import datetime, timezone
from praxis.engine.drift_detector import AIDriftDetector, DriftCheckResult
from praxis.core.models.decision import DecisionRecord, DecisionStatus, ReviewSnapshot, TeamSignal


def test_ai_drift_normal():
    # 模拟标定优异的决策 (置信度高的预测全中，置信度低的错开)
    decisions = [
        DecisionRecord(
            decision_id="dc-1",
            ticker="600995",
            action="buy",
            confidence=0.9,
            review_5d=ReviewSnapshot(actual_return_pct=5.0)  # 获利 (outcome=1)
        ),
        DecisionRecord(
            decision_id="dc-2",
            ticker="600995",
            action="buy",
            confidence=0.1,
            review_5d=ReviewSnapshot(actual_return_pct=-3.0)  # 亏损 (outcome=0)
        )
    ]
    
    detector = AIDriftDetector()
    res = detector.detect_drift(decisions)
    
    assert isinstance(res, DriftCheckResult)
    assert res.status == "normal"
    assert res.total_samples == 2
    # Brier score = ((0.9-1.0)^2 + (0.1-0.0)^2) / 2 = (0.01 + 0.01) / 2 = 0.01
    assert res.brier_score == pytest.approx(0.01)
    # ECE (10 bins): 
    # bin 9: conf 0.9, acc 1.0, size 1 -> ece term = (1/2) * abs(1.0 - 0.9) = 0.05
    # bin 1: conf 0.1, acc 0.0, size 1 -> ece term = (1/2) * abs(0.0 - 0.1) = 0.05
    # ECE = 0.05 + 0.05 = 0.10
    assert res.ece == pytest.approx(0.10)
    assert res.high_conf_win_rate == 1.0


def test_ai_drift_warning():
    # 标定发生较小偏差的场景：ECE 触发 warning
    # 所有预测置信度均为 0.8，但实际获利的只有 50%
    decisions = []
    for i in range(10):
        # 5个获利，5个亏损
        ret = 2.0 if i < 5 else -2.0
        decisions.append(
            DecisionRecord(
                decision_id=f"dc-{i}",
                ticker="600995",
                action="buy",
                confidence=0.8,
                review_5d=ReviewSnapshot(actual_return_pct=ret)
            )
        )
        
    detector = AIDriftDetector(ece_threshold=0.20, brier_threshold=0.20)
    res = detector.detect_drift(decisions)
    
    # ECE: conf 0.8, acc 0.5 -> ece = abs(0.5 - 0.8) = 0.30 (超过 0.20 预警线)
    assert res.status == "warning"
    assert res.ece == pytest.approx(0.30)
    assert len(res.suggested_actions) > 0


def test_ai_drift_critical():
    # 置信度极高，但几乎全部亏损的场景 -> 触发 critical (风控介入)
    decisions = []
    for i in range(10):
        # 置信度 0.9，实际全部亏损
        decisions.append(
            DecisionRecord(
                decision_id=f"dc-{i}",
                ticker="600995",
                action="buy",
                confidence=0.9,
                review_5d=ReviewSnapshot(actual_return_pct=-3.0)
            )
        )
        
    detector = AIDriftDetector()
    res = detector.detect_drift(decisions)
    
    assert res.status == "critical"
    assert res.high_conf_win_rate == 0.0
    assert any("调减单标的持仓上限" in action for action in res.suggested_actions)
