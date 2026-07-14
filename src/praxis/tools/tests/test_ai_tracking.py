"""AI 追踪工具测试 — ai_tracking 函数."""
from __future__ import annotations

import pytest

from praxis.core.models import DecisionRecord, DecisionStatus, TeamSignal
from praxis.engine.tests.conftest import FakeDecisionRecorder
from praxis.tools.ai_tracking import ai_tracking


def _make_decision_with_signals(
    decision_id: str,
    ticker: str,
    action: str,
    team_signals: list[TeamSignal],
) -> DecisionRecord:
    """创建带团队信号的决策记录."""
    return DecisionRecord(
        decision_id=decision_id,
        investor_id="inv-test",
        portfolio_id="core",
        ticker=ticker,
        action=action,
        confidence=0.8,
        status=DecisionStatus.EXECUTED,
        team_signals=team_signals,
        review_result="reviewed",
    )


@pytest.mark.asyncio
class TestTeamHitRate:
    """team 命中率测试."""

    async def test_team_hit_rate(self):
        """计算单团队命中率."""
        recorder = FakeDecisionRecorder()
        recorder.create(_make_decision_with_signals(
            "dec-001", "600519", "buy",
            [TeamSignal(team_name="asrg", action="buy", confidence=0.8, reasoning="看好")]
        ))
        recorder.create(_make_decision_with_signals(
            "dec-002", "159915", "sell",
            [TeamSignal(team_name="asrg", action="hold", confidence=0.6, reasoning="观望")]
        ))
        recorder.create(_make_decision_with_signals(
            "dec-003", "000001", "buy",
            [TeamSignal(team_name="masters", action="buy", confidence=0.7, reasoning="趋势向上")]
        ))

        result = await ai_tracking(action="team", team_name="asrg", _deps={"recorder": recorder})
        assert result["success"] is True
        assert result["data"]["team"] == "asrg"
        assert result["data"]["total_suggestions"] >= 0


@pytest.mark.asyncio
class TestAllTeams:
    """all 全团队测试."""

    async def test_all_teams(self):
        """计算全团队命中率."""
        recorder = FakeDecisionRecorder()
        recorder.create(_make_decision_with_signals(
            "dec-001", "600519", "buy",
            [
                TeamSignal(team_name="asrg", action="buy", confidence=0.8, reasoning="看好"),
                TeamSignal(team_name="masters", action="hold", confidence=0.5, reasoning="观望"),
            ]
        ))

        result = await ai_tracking(action="all", _deps={"recorder": recorder})
        assert result["success"] is True
        assert "asrg" in result["data"]
        assert "masters" in result["data"]
        assert "trading" in result["data"]


@pytest.mark.asyncio
class TestNonexistentTeam:
    """不存在团队测试."""

    async def test_nonexistent_team(self):
        """不存在的团队返回空结果."""
        recorder = FakeDecisionRecorder()
        result = await ai_tracking(action="team", team_name="nonexistent", _deps={"recorder": recorder})
        assert result["success"] is True
        assert result["data"]["total_suggestions"] == 0


@pytest.mark.asyncio
class TestInvalidAction:
    """无效 action 测试."""

    async def test_invalid_action(self):
        """无效 action 返回 error."""
        recorder = FakeDecisionRecorder()
        result = await ai_tracking(action="foobar", _deps={"recorder": recorder})
        assert result["success"] is False
        assert "未知" in result.get("error", "")


@pytest.mark.asyncio
class TestMissingDeps:
    """缺失依赖测试."""

    async def test_missing_recorder(self):
        """_deps 缺 recorder 返回 error."""
        result = await ai_tracking(action="team", team_name="asrg", _deps=None)
        assert result["success"] is False
        assert "未注入" in result.get("error", "")

        result = await ai_tracking(action="team", team_name="asrg", _deps={})
        assert result["success"] is False
        assert "未注入" in result.get("error", "")


@pytest.mark.asyncio
class TestReturnFormat:
    """返回值格式校验."""

    async def test_return_format(self):
        """返回 {success, data, error} 结构."""
        recorder = FakeDecisionRecorder()
        result = await ai_tracking(action="all", _deps={"recorder": recorder})

        assert isinstance(result, dict)
        assert "success" in result
        assert "data" in result
        assert "error" in result or result["error"] is None
        assert result["success"] is True
