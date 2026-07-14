"""ReviewAgent 测试 — 5 工具（review / cascade_review / generate_market_weekly_review / agent_tracking / full_review），只读。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from praxis.agents.review import ReviewAgent


# ═══════════════════════════════════════════════════════════════════
# 场景1：agent_name
# ═══════════════════════════════════════════════════════════════════


def test_agent_name_is_review(review_agent: ReviewAgent) -> None:
    """agent_name 应为 "review"。"""
    assert review_agent.agent_name == "review"


# ═══════════════════════════════════════════════════════════════════
# 场景2：is_readonly
# ═══════════════════════════════════════════════════════════════════


def test_is_readonly_true(review_agent: ReviewAgent) -> None:
    """ReviewAgent 应为只读。"""
    assert review_agent.is_readonly is True


# ═══════════════════════════════════════════════════════════════════
# 场景3：tool registration
# ═══════════════════════════════════════════════════════════════════


def test_all_five_tools_registered(review_agent: ReviewAgent) -> None:
    """应注册 5 个工具。"""
    tool_names = [t.name for t in review_agent.tools]
    assert len(tool_names) == 5
    assert "review" in tool_names
    assert "cascade_review" in tool_names
    assert "generate_market_weekly_review" in tool_names
    assert "agent_tracking" in tool_names
    assert "full_review" in tool_names


def test_all_tools_are_readonly(review_agent: ReviewAgent) -> None:
    """所有工具 is_readonly 应为 True。"""
    for tool in review_agent.tools:
        assert tool.is_readonly is True, f"Tool {tool.name} should be readonly"


# ═══════════════════════════════════════════════════════════════════
# 场景4-7：execute 各工具
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_review(review_agent: ReviewAgent) -> None:
    """execute review 返回复盘结果。"""
    review_agent._tool_map["review"].handler = AsyncMock(
        return_value={"success": True, "data": {"review_id": "rev-001", "score": 85}}
    )
    result = await review_agent.execute("review", {"decision_id": "dec-001"})
    assert result.success is True
    assert result.data["review_id"] == "rev-001"


@pytest.mark.asyncio
async def test_execute_cascade_review(review_agent: ReviewAgent) -> None:
    """execute cascade_review 返回级联复盘结果。"""
    review_agent._tool_map["cascade_review"].handler = AsyncMock(
        return_value={"success": True, "data": {"chains": ["chain-a", "chain-b"]}}
    )
    result = await review_agent.execute("cascade_review", {"decision_id": "dec-001"})
    assert result.success is True
    assert len(result.data["chains"]) == 2


@pytest.mark.asyncio
async def test_execute_generate_market_weekly_review(review_agent: ReviewAgent) -> None:
    """execute generate_market_weekly_review 返回周报复盘。"""
    review_agent._tool_map["generate_market_weekly_review"].handler = AsyncMock(
        return_value={"success": True, "data": {"report": "Weekly summary", "week": 28}}
    )
    result = await review_agent.execute("generate_market_weekly_review", {"week": 28})
    assert result.success is True
    assert result.data["week"] == 28


@pytest.mark.asyncio
async def test_execute_agent_tracking(review_agent: ReviewAgent) -> None:
    """execute agent_tracking 返回 Agent 决策追踪。"""
    review_agent._tool_map["agent_tracking"].handler = AsyncMock(
        return_value={"success": True, "data": {"events": [{"agent": "decision", "action": "trade"}]}}
    )
    result = await review_agent.execute("agent_tracking", {"agent_name": "decision", "days": 7})
    assert result.success is True
    assert len(result.data["events"]) == 1


@pytest.mark.asyncio
async def test_execute_full_review(review_agent: ReviewAgent) -> None:
    """execute full_review 返回全量复盘聚合。"""
    review_agent._tool_map["full_review"].handler = AsyncMock(
        return_value={"success": True, "data": {"total_decisions": 12, "win_rate": 0.67}}
    )
    result = await review_agent.execute("full_review", {"period": "last_30d"})
    assert result.success is True
    assert result.data["total_decisions"] == 12


# ═══════════════════════════════════════════════════════════════════
# 场景8：list_tools / has_tool / get_tool 验证
# ═══════════════════════════════════════════════════════════════════


def test_list_tools_returns_all_tools(review_agent: ReviewAgent) -> None:
    """list_tools 应返回 5 个工具摘要。"""
    tools = review_agent.list_tools()
    assert len(tools) == 5
    names = [t["name"] for t in tools]
    assert "review" in names
    assert "full_review" in names
    assert "generate_market_weekly_review" in names


def test_has_tool_positive(review_agent: ReviewAgent) -> None:
    """已注册工具 has_tool 返回 True。"""
    assert review_agent.has_tool("review") is True
    assert review_agent.has_tool("cascade_review") is True


def test_has_tool_negative(review_agent: ReviewAgent) -> None:
    """未注册工具 has_tool 返回 False。"""
    assert review_agent.has_tool("nonexistent") is False


def test_get_tool_returns_tool_object(review_agent: ReviewAgent) -> None:
    """get_tool 返回正确的 Tool 对象。"""
    tool = review_agent.get_tool("agent_tracking")
    assert tool is not None
    assert tool.name == "agent_tracking"
    assert tool.agent_name == "review"


def test_get_tool_nonexistent_returns_none(review_agent: ReviewAgent) -> None:
    """get_tool 对不存在的工具返回 None。"""
    assert review_agent.get_tool("foobar") is None
