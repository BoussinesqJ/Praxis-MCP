"""决策模块工具测试 — decision 函数."""
from __future__ import annotations

import pytest

from praxis.tools.decision_module import decision
from praxis.engine.tests.conftest import FakeDecisionRecorder
from praxis.core.models import DecisionRecord, DecisionStatus


def _make_deps(recorder=None):
    """构造 _deps 字典."""
    return {"decision_recorder": recorder}


class TestCreate:
    """create 测试."""

    @pytest.mark.asyncio
    async def test_create_basic(self):
        """创建决策 — 返回 decision_id."""
        recorder = FakeDecisionRecorder()
        result = await decision(
            action="create",
            ticker="600519",
            decision_action="buy",
            confidence=0.85,
            reasoning="技术面突破",
            investor="demo",
            portfolio="core",
            _deps=_make_deps(recorder),
        )
        assert result["success"] is True
        assert result["data"]["decision_id"].startswith("dec-")
        assert result["data"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_no_recorder(self):
        """_deps 缺 recorder → error."""
        result = await decision(
            action="create",
            ticker="600519",
            decision_action="buy",
            _deps=_make_deps(None),
        )
        assert result["success"] is False
        assert "未注入" in result["error"]


class TestGet:
    """get 测试."""

    @pytest.mark.asyncio
    async def test_get_existing(self):
        """已有决策，get 返回详情."""
        recorder = FakeDecisionRecorder()
        record = DecisionRecord(
            ticker="600519", action="buy", confidence=0.8,
            status=DecisionStatus.PENDING,
        )
        did = recorder.create(record)

        result = await decision(
            action="get",
            decision_id=did,
            _deps=_make_deps(recorder),
        )
        assert result["success"] is True
        assert result["data"]["ticker"] == "600519"
        assert result["data"]["action"] == "buy"

    @pytest.mark.asyncio
    async def test_get_not_found(self):
        """不存在 → error."""
        recorder = FakeDecisionRecorder()
        result = await decision(
            action="get",
            decision_id="dec-nonexistent",
            _deps=_make_deps(recorder),
        )
        assert result["success"] is False
        assert "不存在" in result["error"]


class TestList:
    """list 测试."""

    @pytest.mark.asyncio
    async def test_list_status_filter(self):
        """按状态过滤列表."""
        recorder = FakeDecisionRecorder()
        recorder.create(DecisionRecord(
            ticker="600519", action="buy", status=DecisionStatus.DRAFT,
        ))
        recorder.create(DecisionRecord(
            ticker="159915", action="sell", status=DecisionStatus.EXECUTED,
        ))

        result = await decision(
            action="list",
            status="executed",
            _deps=_make_deps(recorder),
        )
        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert result["data"]["decisions"][0]["ticker"] == "159915"


class TestUpdate:
    """update 测试."""

    @pytest.mark.asyncio
    async def test_update_status(self):
        """更新决策状态."""
        recorder = FakeDecisionRecorder()
        record = DecisionRecord(
            ticker="600519", action="buy", status=DecisionStatus.DRAFT,
        )
        did = recorder.create(record)

        result = await decision(
            action="update",
            decision_id=did,
            status="executed",
            _deps=_make_deps(recorder),
        )
        assert result["success"] is True
        assert result["data"]["status"] == "executed"

        fetched = recorder.get(did)
        assert fetched.status == DecisionStatus.EXECUTED


class TestLink:
    """link 测试."""

    @pytest.mark.asyncio
    async def test_link_transaction(self):
        """关联交易."""
        recorder = FakeDecisionRecorder()
        record = DecisionRecord(
            ticker="600519", action="buy", status=DecisionStatus.EXECUTED,
        )
        did = recorder.create(record)

        result = await decision(
            action="link",
            decision_id=did,
            tx_id="tx-000001",
            _deps=_make_deps(recorder),
        )
        assert result["success"] is True
        assert result["data"]["tx_id"] == "tx-000001"

        fetched = recorder.get(did)
        assert fetched.tx_id == "tx-000001"


class TestInvalidAction:
    """无效 action 测试."""

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """未知 action → error."""
        recorder = FakeDecisionRecorder()
        result = await decision(
            action="foobar",
            _deps=_make_deps(recorder),
        )
        assert result["success"] is False
        assert "未知" in result["error"]
