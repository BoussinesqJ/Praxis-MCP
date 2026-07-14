"""DecisionAgent 测试 — 2 写工具（trading / decision），is_readonly=False，Guardrail 集成。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from praxis.agents.base import AgentDependencies
from praxis.agents.decision import DecisionAgent
from praxis.agents.tests.conftest import FakeGuardrail


# ═══════════════════════════════════════════════════════════════════
# 场景1：agent_name
# ═══════════════════════════════════════════════════════════════════


def test_agent_name_is_decision(decision_agent: DecisionAgent) -> None:
    """agent_name 应为 "decision"。"""
    assert decision_agent.agent_name == "decision"


# ═══════════════════════════════════════════════════════════════════
# 场景2：is_readonly
# ═══════════════════════════════════════════════════════════════════


def test_is_readonly_false(decision_agent: DecisionAgent) -> None:
    """DecisionAgent 应为非只读（可写）。"""
    assert decision_agent.is_readonly is False


# ═══════════════════════════════════════════════════════════════════
# 场景3：tool registration — 2 写工具
# ═══════════════════════════════════════════════════════════════════


def test_all_two_tools_registered(decision_agent: DecisionAgent) -> None:
    """应注册 2 个工具（均为写工具）。"""
    tool_names = [t.name for t in decision_agent.tools]
    assert len(tool_names) == 2
    assert "trading" in tool_names
    assert "decision" in tool_names


def test_all_tools_are_write_tools(decision_agent: DecisionAgent) -> None:
    """两个工具 is_readonly 均应为 False。"""
    for tool in decision_agent.tools:
        assert tool.is_readonly is False, f"Tool {tool.name} should be writable"


# ═══════════════════════════════════════════════════════════════════
# 场景4：ACTIVE Guardrail — 写操作放行
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_trading_with_active_guardrail(agent_deps: AgentDependencies) -> None:
    """ACTIVE Guardrail 应放行 trading 写操作。"""
    agent_deps.guardrail = FakeGuardrail(state="ACTIVE")
    agent = DecisionAgent(deps=agent_deps)
    agent._tool_map["trading"].handler = AsyncMock(
        return_value={"success": True, "data": {"tx_id": "tx-001"}}
    )
    result = await agent.execute("trading", {"action": "buy", "ticker": "000001", "quantity": 100})
    assert result.success is True
    assert result.data["tx_id"] == "tx-001"


@pytest.mark.asyncio
async def test_execute_decision_with_active_guardrail(agent_deps: AgentDependencies) -> None:
    """ACTIVE Guardrail 应放行 decision 写操作。"""
    agent_deps.guardrail = FakeGuardrail(state="ACTIVE")
    agent = DecisionAgent(deps=agent_deps)
    agent._tool_map["decision"].handler = AsyncMock(
        return_value={"success": True, "data": {"decision_id": "dec-001"}}
    )
    result = await agent.execute("decision", {"action": "create", "ticker": "600519"})
    assert result.success is True
    assert result.data["decision_id"] == "dec-001"


# ═══════════════════════════════════════════════════════════════════
# 场景5：LOCKED Guardrail — 写操作拦截
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_trading_blocked_by_locked_guardrail(agent_deps: AgentDependencies) -> None:
    """LOCKED Guardrail 应拦截 trading 写操作。"""
    agent_deps.guardrail = FakeGuardrail(state="LOCKED")
    agent = DecisionAgent(deps=agent_deps)
    agent._tool_map["trading"].handler = AsyncMock(
        return_value={"success": True, "data": {}}
    )
    result = await agent.execute("trading", {"action": "buy", "ticker": "000001", "quantity": 100})
    assert result.success is False
    assert "Guardrail" in result.error
    assert result.metadata["guardrail_state"] == "LOCKED"


@pytest.mark.asyncio
async def test_execute_decision_blocked_by_locked_guardrail(agent_deps: AgentDependencies) -> None:
    """LOCKED Guardrail 应拦截 decision 写操作。"""
    agent_deps.guardrail = FakeGuardrail(state="LOCKED")
    agent = DecisionAgent(deps=agent_deps)
    agent._tool_map["decision"].handler = AsyncMock(
        return_value={"success": True, "data": {}}
    )
    result = await agent.execute("decision", {"action": "create", "ticker": "000001"})
    assert result.success is False
    assert "Guardrail" in result.error


# ═══════════════════════════════════════════════════════════════════
# 场景6：AUDITING Guardrail — 写操作拦截
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_trading_blocked_by_auditing_guardrail(agent_deps: AgentDependencies) -> None:
    """AUDITING Guardrail 应拦截 trading 写操作。"""
    agent_deps.guardrail = FakeGuardrail(state="AUDITING")
    agent = DecisionAgent(deps=agent_deps)
    agent._tool_map["trading"].handler = AsyncMock(
        return_value={"success": True, "data": {}}
    )
    result = await agent.execute("trading", {"action": "buy", "ticker": "000001", "quantity": 100})
    assert result.success is False
    assert "Guardrail" in result.error
    assert result.metadata["guardrail_state"] == "AUDITING"


# ═══════════════════════════════════════════════════════════════════
# 场景7：Guardrail=None — 无门控放行
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_trading_without_guardrail(agent_deps: AgentDependencies) -> None:
    """无 Guardrail（None）时写操作应直接放行。"""
    agent_deps.guardrail = None
    agent = DecisionAgent(deps=agent_deps)
    agent._tool_map["trading"].handler = AsyncMock(
        return_value={"success": True, "data": {"tx_id": "tx-002"}}
    )
    result = await agent.execute("trading", {"action": "sell", "ticker": "600519", "quantity": 50})
    assert result.success is True
    assert result.data["tx_id"] == "tx-002"


@pytest.mark.asyncio
async def test_execute_decision_without_guardrail(agent_deps: AgentDependencies) -> None:
    """无 Guardrail（None）时 decision 操作应直接放行。"""
    agent_deps.guardrail = None
    agent = DecisionAgent(deps=agent_deps)
    agent._tool_map["decision"].handler = AsyncMock(
        return_value={"success": True, "data": {"decision_id": "dec-003"}}
    )
    result = await agent.execute("decision", {"action": "update", "decision_id": "dec-001"})
    assert result.success is True
    assert result.data["decision_id"] == "dec-003"


# ═══════════════════════════════════════════════════════════════════
# 场景8：list_tools / has_tool / get_tool 验证
# ═══════════════════════════════════════════════════════════════════


def test_list_tools_returns_all_tools(decision_agent: DecisionAgent) -> None:
    """list_tools 应返回 2 个工具摘要。"""
    tools = decision_agent.list_tools()
    assert len(tools) == 2
    names = [t["name"] for t in tools]
    assert "trading" in names
    assert "decision" in names
    for tool in tools:
        assert tool["is_readonly"] is False


def test_has_tool_positive(decision_agent: DecisionAgent) -> None:
    """已注册工具 has_tool 返回 True。"""
    assert decision_agent.has_tool("trading") is True
    assert decision_agent.has_tool("decision") is True


def test_has_tool_negative(decision_agent: DecisionAgent) -> None:
    """未注册工具 has_tool 返回 False。"""
    assert decision_agent.has_tool("nonexistent") is False


def test_get_tool_returns_tool_object(decision_agent: DecisionAgent) -> None:
    """get_tool 返回正确的 Tool 对象。"""
    tool = decision_agent.get_tool("trading")
    assert tool is not None
    assert tool.name == "trading"
    assert tool.agent_name == "decision"
    assert tool.is_readonly is False


def test_get_tool_nonexistent_returns_none(decision_agent: DecisionAgent) -> None:
    """get_tool 对不存在的工具返回 None。"""
    assert decision_agent.get_tool("foobar") is None
