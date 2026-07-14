"""AdminAgent 测试 — 7 工具（portfolio / nav / reconcile / discover_workspace / performance / memory_search / orchestrator），只读。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from praxis.agents.admin import AdminAgent


# ═══════════════════════════════════════════════════════════════════
# 场景1：agent_name
# ═══════════════════════════════════════════════════════════════════


def test_agent_name_is_admin(admin_agent: AdminAgent) -> None:
    """agent_name 应为 "admin"。"""
    assert admin_agent.agent_name == "admin"


# ═══════════════════════════════════════════════════════════════════
# 场景2：is_readonly
# ═══════════════════════════════════════════════════════════════════


def test_is_readonly_true(admin_agent: AdminAgent) -> None:
    """AdminAgent 应为只读。"""
    assert admin_agent.is_readonly is True


# ═══════════════════════════════════════════════════════════════════
# 场景3：tool registration
# ═══════════════════════════════════════════════════════════════════


def test_all_seven_tools_registered(admin_agent: AdminAgent) -> None:
    """应注册 7 个工具。"""
    tool_names = [t.name for t in admin_agent.tools]
    assert len(tool_names) == 7
    assert "portfolio" in tool_names
    assert "nav" in tool_names
    assert "reconcile" in tool_names
    assert "discover_workspace" in tool_names
    assert "performance" in tool_names
    assert "memory_search" in tool_names
    assert "orchestrator" in tool_names


def test_all_tools_are_readonly(admin_agent: AdminAgent) -> None:
    """所有工具 is_readonly 应为 True。"""
    for tool in admin_agent.tools:
        assert tool.is_readonly is True, f"Tool {tool.name} should be readonly"


# ═══════════════════════════════════════════════════════════════════
# 场景4-7：execute 各工具
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_portfolio(admin_agent: AdminAgent) -> None:
    """execute portfolio 返回组合管理数据。"""
    admin_agent._tool_map["portfolio"].handler = AsyncMock(
        return_value={"success": True, "data": {"assets": [], "total_value": 100000.0}}
    )
    result = await admin_agent.execute("portfolio", {"action": "view", "portfolio_id": "port-01"})
    assert result.success is True
    assert result.data["total_value"] == 100000.0


@pytest.mark.asyncio
async def test_execute_nav(admin_agent: AdminAgent) -> None:
    """execute nav 返回净值数据。"""
    admin_agent._tool_map["nav"].handler = AsyncMock(
        return_value={"success": True, "data": {"nav": 1.25, "date": "2026-07-13"}}
    )
    result = await admin_agent.execute("nav", {"action": "query", "portfolio_id": "port-01"})
    assert result.success is True
    assert result.data["nav"] == 1.25


@pytest.mark.asyncio
async def test_execute_reconcile(admin_agent: AdminAgent) -> None:
    """execute reconcile 返回对账结果。"""
    admin_agent._tool_map["reconcile"].handler = AsyncMock(
        return_value={"success": True, "data": {"matched": True, "diff": 0.0}}
    )
    result = await admin_agent.execute("reconcile", {"portfolio_id": "port-01"})
    assert result.success is True
    assert result.data["matched"] is True


@pytest.mark.asyncio
async def test_execute_discover_workspace(admin_agent: AdminAgent) -> None:
    """execute discover_workspace 返回工作区发现结果。"""
    admin_agent._tool_map["discover_workspace"].handler = AsyncMock(
        return_value={"success": True, "data": {"investors": [], "portfolios": []}}
    )
    result = await admin_agent.execute("discover_workspace", {"action": "discover"})
    assert result.success is True
    assert "investors" in result.data


@pytest.mark.asyncio
async def test_execute_performance(admin_agent: AdminAgent) -> None:
    """execute performance 返回绩效计算结果。"""
    admin_agent._tool_map["performance"].handler = AsyncMock(
        return_value={"success": True, "data": {"cagr": 0.15, "sharpe": 1.2}}
    )
    result = await admin_agent.execute("performance", {"portfolio_id": "port-01"})
    assert result.success is True
    assert result.data["cagr"] == 0.15


@pytest.mark.asyncio
async def test_execute_memory_search(admin_agent: AdminAgent) -> None:
    """execute memory_search 返回语义检索结果。"""
    admin_agent._tool_map["memory_search"].handler = AsyncMock(
        return_value={"success": True, "data": {"results": [{"id": "mem-001", "similarity": 0.95}]}}
    )
    result = await admin_agent.execute("memory_search", {"query": "test query", "limit": 5})
    assert result.success is True
    assert len(result.data["results"]) == 1


@pytest.mark.asyncio
async def test_execute_orchestrator(admin_agent: AdminAgent) -> None:
    """execute orchestrator 返回工作流编排结果。"""
    admin_agent._tool_map["orchestrator"].handler = AsyncMock(
        return_value={"success": True, "data": {"workflow": "decision_chain", "status": "completed"}}
    )
    result = await admin_agent.execute("orchestrator", {"workflow_name": "decision_chain"})
    assert result.success is True
    assert result.data["status"] == "completed"


# ═══════════════════════════════════════════════════════════════════
# 场景8：list_tools / has_tool / get_tool 验证
# ═══════════════════════════════════════════════════════════════════


def test_list_tools_returns_all_tools(admin_agent: AdminAgent) -> None:
    """list_tools 应返回 7 个工具摘要。"""
    tools = admin_agent.list_tools()
    assert len(tools) == 7
    names = [t["name"] for t in tools]
    assert "portfolio" in names
    assert "orchestrator" in names
    assert "memory_search" in names


def test_has_tool_positive(admin_agent: AdminAgent) -> None:
    """已注册工具 has_tool 返回 True。"""
    assert admin_agent.has_tool("portfolio") is True
    assert admin_agent.has_tool("nav") is True


def test_has_tool_negative(admin_agent: AdminAgent) -> None:
    """未注册工具 has_tool 返回 False。"""
    assert admin_agent.has_tool("nonexistent") is False


def test_get_tool_returns_tool_object(admin_agent: AdminAgent) -> None:
    """get_tool 返回正确的 Tool 对象。"""
    tool = admin_agent.get_tool("reconcile")
    assert tool is not None
    assert tool.name == "reconcile"
    assert tool.agent_name == "admin"


def test_get_tool_nonexistent_returns_none(admin_agent: AdminAgent) -> None:
    """get_tool 对不存在的工具返回 None。"""
    assert admin_agent.get_tool("foobar") is None
