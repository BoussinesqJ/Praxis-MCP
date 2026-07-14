"""测试 ReviewAgent — 决策复盘与 Agent 追踪 (5 工具, is_readonly=True)"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _mock_handlers(agent) -> dict[str, MagicMock]:
    """替换 ReviewAgent 全部 5 个工具 handler 为 MagicMock。"""
    mocks: dict[str, MagicMock] = {}
    tool_configs = [
        ("review", {"success": True, "data": {"action": "fill", "team": "alpha", "filled": True}}),
        ("cascade_review", {"success": True, "data": {"mode": "monthly", "results": []}}),
        ("generate_market_weekly_review", {"success": True, "data": {"week_ending": "2024-01-12", "report": "..."}}),
        ("agent_tracking", {"success": True, "data": {"action": "consensus", "agents": 3}}),
        ("full_review", {"success": True, "data": {"investor": "demo", "aggregated": True}}),
    ]
    for name, default_return in tool_configs:
        mock = MagicMock(return_value=default_return)
        agent._tool_map[name].handler = mock
        mocks[name] = mock
    return mocks


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


class TestReviewAgent:
    """ReviewAgent 单元测试"""

    # ── test_init ──────────────────────────────────────────────

    def test_init(self, review_agent):
        """初始化验证：agent_name=="review", is_readonly==True, len(tools)==5"""
        assert review_agent.agent_name == "review"
        assert review_agent.is_readonly is True
        assert len(review_agent.tools) == 5

    # ── test_review ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_review(self, review_agent):
        """review 决策复盘工具执行成功"""
        _mock_handlers(review_agent)
        result = await review_agent.execute("review", {"action": "fill", "team": "alpha"})
        assert result.success is True
        assert result.data["action"] == "fill"

    # ── test_cascade_review ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cascade_review(self, review_agent):
        """cascade_review 级联复盘工具执行成功"""
        _mock_handlers(review_agent)
        result = await review_agent.execute(
            "cascade_review",
            {"mode": "monthly", "investor": "demo", "portfolio": "core", "period": "2024-01"},
        )
        assert result.success is True
        assert result.data["mode"] == "monthly"

    # ── test_generate_market_weekly_review ─────────────────────

    @pytest.mark.asyncio
    async def test_generate_market_weekly_review(self, review_agent):
        """generate_market_weekly_review 市场周报复盘执行成功"""
        _mock_handlers(review_agent)
        result = await review_agent.execute(
            "generate_market_weekly_review",
            {"week_ending": "2024-01-12", "index_code": "000300"},
        )
        assert result.success is True
        assert result.data["week_ending"] == "2024-01-12"

    # ── test_agent_tracking ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_agent_tracking(self, review_agent):
        """agent_tracking Agent 决策追踪工具执行成功"""
        _mock_handlers(review_agent)
        result = await review_agent.execute(
            "agent_tracking",
            {"action": "consensus", "ticker": "600995", "min_agents": 2},
        )
        assert result.success is True
        assert result.data["action"] == "consensus"

    # ── test_full_review ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_full_review(self, review_agent):
        """full_review 全量复盘聚合工具执行成功"""
        _mock_handlers(review_agent)
        result = await review_agent.execute(
            "full_review",
            {"investor": "demo", "portfolio": "core", "week_ending": "2024-01-12"},
        )
        assert result.success is True
        assert result.data["aggregated"] is True

    # ── test_nonexistent_tool ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_nonexistent_tool(self, review_agent):
        """不存在的工具返回 AgentResult(success=False)"""
        _mock_handlers(review_agent)
        result = await review_agent.execute("nonexistent", {})
        assert result.success is False
        assert "nonexistent" in result.error

    # ── test_tools_match_definition ────────────────────────────

    def test_tools_match_definition(self, review_agent):
        """工具列表与 ReviewAgent 源码定义一致"""
        tools = review_agent.list_tools()
        tool_names = {t["name"] for t in tools}
        expected = {
            "review",
            "cascade_review",
            "generate_market_weekly_review",
            "agent_tracking",
            "full_review",
        }
        assert tool_names == expected
        # 全部为只读 + core tier
        for t in tools:
            assert t["is_readonly"] is True

        # has_tool / get_tool
        assert review_agent.has_tool("full_review") is True
        assert review_agent.has_tool("missing") is False
        tool = review_agent.get_tool("agent_tracking")
        assert tool is not None
        assert tool.agent_name == "review"
