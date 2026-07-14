"""决策记录器单元测试 — FileDecisionRecorder 全方法."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.models import DecisionRecord, DecisionStatus


def _make_decision(
    decision_id: str = "",
    ticker: str = "600519",
    action: str = "buy",
    status: DecisionStatus = DecisionStatus.DRAFT,
    confidence: float = 0.8,
    created_at: str | None = None,
) -> DecisionRecord:
    """工厂: 创建测试用 DecisionRecord."""
    return DecisionRecord(
        decision_id=decision_id,
        investor_id="inv-test",
        portfolio_id="core",
        ticker=ticker,
        action=action,
        confidence=confidence,
        status=status,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
    )


class TestCreate:
    """create 测试."""

    def test_create_basic(self, tmp_path):
        """创建决策记录 — 自动生成 decision_id."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        record = _make_decision()
        did = recorder.create(record)
        assert did.startswith("dec-")
        assert record.decision_id == did
        assert recorder.get(did) is not None


class TestGet:
    """get 测试."""

    def test_get_existing(self, tmp_path):
        """获取已存在的决策."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        record = _make_decision()
        did = recorder.create(record)
        fetched = recorder.get(did)
        assert fetched is not None
        assert fetched.ticker == "600519"
        assert fetched.action == "buy"

    def test_get_nonexistent(self, tmp_path):
        """获取不存在的决策返回 None."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        assert recorder.get("dec-nonexistent") is None


class TestListPending:
    """list_pending 测试."""

    def test_list_pending(self, tmp_path):
        """列出待审批的决策 — DRAFT + PENDING."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        recorder.create(_make_decision(status=DecisionStatus.DRAFT))
        recorder.create(_make_decision(ticker="159915", status=DecisionStatus.PENDING))
        recorder.create(_make_decision(ticker="000001", status=DecisionStatus.EXECUTED))

        pending = recorder.list_pending()
        assert len(pending) == 2
        for p in pending:
            assert p.status in (DecisionStatus.DRAFT, DecisionStatus.PENDING)


class TestUpdateStatus:
    """update_status 测试."""

    def test_update_status(self, tmp_path):
        """更新决策状态."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        record = _make_decision(status=DecisionStatus.DRAFT)
        did = recorder.create(record)

        ok = recorder.update_status(did, "executed", review_result="passed")
        assert ok is True
        fetched = recorder.get(did)
        assert fetched.status == DecisionStatus.EXECUTED

    def test_update_status_invalid(self, tmp_path):
        """无效状态更新返回 False."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        record = _make_decision()
        did = recorder.create(record)

        ok = recorder.update_status(did, "INVALID_STATUS_XYZ")
        assert ok is False


class TestLinkTransaction:
    """link_transaction 测试."""

    def test_link_transaction(self, tmp_path):
        """关联决策与交易."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        record = _make_decision()
        did = recorder.create(record)

        ok = recorder.link_transaction(did, "tx-000001")
        assert ok is True
        fetched = recorder.get(did)
        assert fetched.tx_id == "tx-000001"


class TestUpdateReview:
    """update_review 测试."""

    def test_update_review(self, tmp_path):
        """回填复盘数据."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        record = _make_decision(status=DecisionStatus.EXECUTED)
        did = recorder.create(record)

        ok = recorder.update_review(did, "5d", {"actual_return_pct": 3.5})
        assert ok is True
        fetched = recorder.get(did)
        assert fetched.review_result is not None
        review_data = json.loads(fetched.review_result)
        assert review_data["type"] == "5d"
        assert review_data["actual_return_pct"] == 3.5


class TestList:
    """list 测试."""

    def test_list_status_filter(self, tmp_path):
        """状态过滤."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        recorder.create(_make_decision(status=DecisionStatus.DRAFT))
        recorder.create(_make_decision(ticker="159915", status=DecisionStatus.EXECUTED))
        recorder.create(_make_decision(ticker="000001", status=DecisionStatus.EXECUTED))

        executed = recorder.list(status="executed")
        assert len(executed) == 2

        draft = recorder.list(status="draft")
        assert len(draft) == 1

    def test_list_all(self, tmp_path):
        """无状态过滤返回全部."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        recorder.create(_make_decision())
        recorder.create(_make_decision(ticker="159915"))
        all_records = recorder.list()
        assert len(all_records) == 2


class TestGetExecuted:
    """get_executed 测试."""

    def test_get_executed_sort(self, tmp_path):
        """已执行决策按时间逆序排列."""
        path = tmp_path / "decisions.jsonl"
        recorder = FileDecisionRecorder(str(path))
        recorder.create(_make_decision(
            ticker="600519", status=DecisionStatus.EXECUTED,
            created_at="2024-01-01T10:00:00",
        ))
        recorder.create(_make_decision(
            ticker="159915", status=DecisionStatus.EXECUTED,
            created_at="2024-06-01T10:00:00",
        ))
        recorder.create(_make_decision(
            ticker="000001", status=DecisionStatus.DRAFT,
            created_at="2024-12-01T10:00:00",
        ))

        executed = recorder.get_executed()
        assert len(executed) == 2
        # 最新在前
        assert executed[0].ticker == "159915"
        assert executed[1].ticker == "600519"
