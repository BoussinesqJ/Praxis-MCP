"""E1.9 — 决策记录器测试"""
import pytest
import tempfile
from pathlib import Path

from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.models.decision import DecisionRecord, DecisionStatus


@pytest.fixture
def temp_recorder(tmp_path):
    """创建临时决策记录器"""
    decisions_path = tmp_path / "test_decisions.jsonl"
    return FileDecisionRecorder(decisions_path)


@pytest.fixture
def sample_decision():
    """示例决策"""
    return DecisionRecord(
        decision_id="",
        ticker="600995",
        action="buy",
        confidence=0.75,
        reasoning="网格触发",
    )


class TestDecisionCreate:
    """创建决策测试"""

    def test_create_basic(self, temp_recorder, sample_decision):
        """基本创建测试"""
        decision_id = temp_recorder.create(sample_decision)
        assert decision_id.startswith("dc-")
        assert temp_recorder.count() == 1

    def test_create_with_custom_id(self, temp_recorder):
        """自定义 ID 创建"""
        record = DecisionRecord(
            decision_id="dc-custom-001",
            ticker="600995",
            action="buy",
            confidence=0.75,
            reasoning="测试",
        )
        decision_id = temp_recorder.create(record)
        assert decision_id == "dc-custom-001"

    def test_create_multiple(self, temp_recorder):
        """创建多个决策"""
        for i in range(5):
            record = DecisionRecord(
                decision_id=f"dc-test-{i:03d}",
                ticker="600995",
                action="buy",
                confidence=0.75,
                reasoning=f"测试 {i}",
            )
            temp_recorder.create(record)

        assert temp_recorder.count() == 5


class TestDecisionQuery:
    """查询决策测试"""

    def test_get_by_id(self, temp_recorder, sample_decision):
        """按 ID 查询"""
        decision_id = temp_recorder.create(sample_decision)
        result = temp_recorder.get(decision_id)
        assert result is not None
        assert result.ticker == "600995"

    def test_get_nonexistent(self, temp_recorder):
        """查询不存在的决策"""
        result = temp_recorder.get("dc-nonexistent")
        assert result is None

    def test_list_pending(self, temp_recorder):
        """列出待审批决策"""
        # 创建一个待审批决策
        record = DecisionRecord(
            decision_id="dc-pending-001",
            ticker="600995",
            action="buy",
            confidence=0.75,
            reasoning="测试",
            status=DecisionStatus.PENDING_APPROVAL,
        )
        temp_recorder.create(record)

        # 创建一个已审批决策
        record2 = DecisionRecord(
            decision_id="dc-approved-001",
            ticker="600995",
            action="buy",
            confidence=0.75,
            reasoning="测试",
            status=DecisionStatus.APPROVED,
        )
        temp_recorder.create(record2)

        pending = temp_recorder.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == "dc-pending-001"

    def test_get_by_ticker(self, temp_recorder):
        """按标的查询"""
        for i, ticker in enumerate(["600995", "510310", "600995"]):
            record = DecisionRecord(
                decision_id=f"dc-{ticker}-{i:03d}",
                ticker=ticker,
                action="buy",
                confidence=0.75,
                reasoning="测试",
            )
            temp_recorder.create(record)

        results = temp_recorder.get_by_ticker("600995")
        assert len(results) == 2


class TestDecisionUpdate:
    """更新决策测试"""

    def test_update_status(self, temp_recorder, sample_decision):
        """更新决策状态"""
        decision_id = temp_recorder.create(sample_decision)
        result = temp_recorder.update_status(
            decision_id,
            "approved",
            approved_by="示例投资者",
        )
        assert result is True

    def test_link_transaction(self, temp_recorder, sample_decision):
        """关联决策与交易"""
        decision_id = temp_recorder.create(sample_decision)
        result = temp_recorder.link_transaction(decision_id, "tx-20260601-001")
        assert result is True

    def test_update_nonexistent(self, temp_recorder):
        """更新不存在的决策"""
        result = temp_recorder.update_status("dc-nonexistent", "approved")
        assert result is False
