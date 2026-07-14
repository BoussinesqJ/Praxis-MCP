"""测试 AdminAgent — 管理与运营养护 (7 工具, is_readonly=True)"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _mock_handlers(agent) -> dict[str, MagicMock]:
    """替换 AdminAgent 全部 7 个工具 handler 为 MagicMock。"""
    mocks: dict[str, MagicMock] = {}
    tool_configs = [
        ("portfolio", {"success": True, "data": {"action": "summary", "investor": "demo", "holdings": []}}),
        ("nav", {"success": True, "data": {"action": "record", "nav": 1.05}}),
        ("reconcile", {"success": True, "data": {"action": "dry_run", "matched": True}}),
        ("discover_workspace", {"success": True, "data": {"workspace": ".", "files": []}}),
        ("performance", {"success": True, "data": {"investor": "demo", "sharpe_ratio": 1.2}}),
        ("memory_search", {"success": True, "data": {"query": "test", "results": []}}),
        ("orchestrator", {"success": True, "data": {"action": "plan", "team": "alpha"}}),
    ]
    for name, default_return in tool_configs:
        mock = MagicMock(return_value=default_return)
        agent._tool_map[name].handler = mock
        mocks[name] = mock
    return mocks


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


class TestAdminAgent:
    """AdminAgent 单元测试"""

    # ── test_init ──────────────────────────────────────────────

    def test_init(self, admin_agent):
        """初始化验证：agent_name=="admin", is_readonly==True, len(tools)==7"""
        assert admin_agent.agent_name == "admin"
        assert admin_agent.is_readonly is True
        assert len(admin_agent.tools) == 7

    # ── test_portfolio ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_portfolio(self, admin_agent):
        """portfolio 组合管理工具执行成功"""
        _mock_handlers(admin_agent)
        result = await admin_agent.execute(
            "portfolio",
            {"action": "summary", "investor": "demo", "portfolio": "core"},
        )
        assert result.success is True
        assert result.data["action"] == "summary"

    # ── test_nav ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_nav(self, admin_agent):
        """nav 净值管理工具执行成功"""
        _mock_handlers(admin_agent)
        result = await admin_agent.execute(
            "nav",
            {"action": "record", "investor": "demo", "portfolio": "core", "nav": 1.05},
        )
        assert result.success is True
        assert result.data["nav"] == 1.05

    # ── test_reconcile ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_reconcile(self, admin_agent):
        """reconcile 对账计算工具执行成功"""
        _mock_handlers(admin_agent)
        result = await admin_agent.execute(
            "reconcile",
            {"action": "dry_run", "investor": "demo", "portfolio": "core", "nav": 1.05},
        )
        assert result.success is True
        assert result.data["matched"] is True

    # ── test_discover_workspace ────────────────────────────────

    @pytest.mark.asyncio
    async def test_discover_workspace(self, admin_agent):
        """discover_workspace 工作区发现工具执行成功"""
        _mock_handlers(admin_agent)
        result = await admin_agent.execute("discover_workspace", {})
        assert result.success is True
        assert result.data["workspace"] == "."

    # ── test_performance ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_performance(self, admin_agent):
        """performance 绩效计算工具执行成功"""
        _mock_handlers(admin_agent)
        result = await admin_agent.execute(
            "performance",
            {"investor": "demo", "portfolio": "core"},
        )
        assert result.success is True
        assert result.data["sharpe_ratio"] == 1.2

    # ── test_memory_search ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_memory_search(self, admin_agent):
        """memory_search 语义检索工具执行成功"""
        _mock_handlers(admin_agent)
        result = await admin_agent.execute(
            "memory_search",
            {"query": "test query", "limit": 5},
        )
        assert result.success is True
        assert result.data["query"] == "test"

    # ── test_orchestrator ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_orchestrator(self, admin_agent):
        """orchestrator 工作流编排工具执行成功"""
        _mock_handlers(admin_agent)
        result = await admin_agent.execute(
            "orchestrator",
            {"action": "plan", "team": "alpha"},
        )
        assert result.success is True
        assert result.data["action"] == "plan"
