"""RiskAgent 测试 — 4 工具（sentinel / valuation / check_constraints / trading_friction），只读。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from praxis.agents.risk import RiskAgent


# ═══════════════════════════════════════════════════════════════════
# 场景1：agent_name
# ═══════════════════════════════════════════════════════════════════


def test_agent_name_is_risk(risk_agent: RiskAgent) -> None:
    """agent_name 应为 "risk"。"""
    assert risk_agent.agent_name == "risk"


# ═══════════════════════════════════════════════════════════════════
# 场景2：is_readonly
# ═══════════════════════════════════════════════════════════════════


def test_is_readonly_true(risk_agent: RiskAgent) -> None:
    """RiskAgent 应为只读。"""
    assert risk_agent.is_readonly is True


# ═══════════════════════════════════════════════════════════════════
# 场景3：tool registration
# ═══════════════════════════════════════════════════════════════════


def test_all_four_tools_registered(risk_agent: RiskAgent) -> None:
    """应注册 4 个工具。"""
    tool_names = [t.name for t in risk_agent.tools]
    assert len(tool_names) == 4
    assert "sentinel" in tool_names
    assert "valuation" in tool_names
    assert "check_constraints" in tool_names
    assert "trading_friction" in tool_names


def test_all_tools_are_readonly(risk_agent: RiskAgent) -> None:
    """所有工具 is_readonly 应为 True。"""
    for tool in risk_agent.tools:
        assert tool.is_readonly is True, f"Tool {tool.name} should be readonly"


# ═══════════════════════════════════════════════════════════════════
# 场景4-7：execute 各工具
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_sentinel(risk_agent: RiskAgent) -> None:
    """execute sentinel 返回哨兵扫描结果。"""
    risk_agent._tool_map["sentinel"].handler = AsyncMock(
        return_value={"success": True, "data": {"risk_level": "low", "signals": []}}
    )
    result = await risk_agent.execute("sentinel", {"portfolio_id": "port-01"})
    assert result.success is True
    assert result.data["risk_level"] == "low"


@pytest.mark.asyncio
async def test_execute_valuation(risk_agent: RiskAgent) -> None:
    """execute valuation 返回估值分位数据。"""
    risk_agent._tool_map["valuation"].handler = AsyncMock(
        return_value={"success": True, "data": {"pe_percentile": 45.2, "pb_percentile": 38.0}}
    )
    result = await risk_agent.execute("valuation", {"index_code": "000300"})
    assert result.success is True
    assert result.data["pe_percentile"] == 45.2


@pytest.mark.asyncio
async def test_execute_check_constraints(risk_agent: RiskAgent) -> None:
    """execute check_constraints 返回约束检查结果。"""
    risk_agent._tool_map["check_constraints"].handler = AsyncMock(
        return_value={"success": True, "data": {"passed": True, "violations": []}}
    )
    result = await risk_agent.execute("check_constraints", {"portfolio_id": "port-01"})
    assert result.success is True
    assert result.data["passed"] is True


@pytest.mark.asyncio
async def test_execute_trading_friction(risk_agent: RiskAgent) -> None:
    """execute trading_friction 返回摩擦成本评估。"""
    risk_agent._tool_map["trading_friction"].handler = AsyncMock(
        return_value={"success": True, "data": {"slippage_bps": 5.0, "fee_total": 12.5}}
    )
    result = await risk_agent.execute("trading_friction", {"ticker": "000001", "quantity": 100})
    assert result.success is True
    assert result.data["slippage_bps"] == 5.0


# ═══════════════════════════════════════════════════════════════════
# 场景8：list_tools / has_tool / get_tool 验证
# ═══════════════════════════════════════════════════════════════════


def test_list_tools_returns_all_tools(risk_agent: RiskAgent) -> None:
    """list_tools 应返回 4 个工具摘要。"""
    tools = risk_agent.list_tools()
    assert len(tools) == 4
    names = [t["name"] for t in tools]
    assert "sentinel" in names
    assert "trading_friction" in names


def test_has_tool_positive(risk_agent: RiskAgent) -> None:
    """已注册工具 has_tool 返回 True。"""
    assert risk_agent.has_tool("sentinel") is True
    assert risk_agent.has_tool("valuation") is True


def test_has_tool_negative(risk_agent: RiskAgent) -> None:
    """未注册工具 has_tool 返回 False。"""
    assert risk_agent.has_tool("nonexistent") is False


def test_get_tool_returns_tool_object(risk_agent: RiskAgent) -> None:
    """get_tool 返回正确的 Tool 对象。"""
    tool = risk_agent.get_tool("check_constraints")
    assert tool is not None
    assert tool.name == "check_constraints"
    assert tool.agent_name == "risk"


def test_get_tool_nonexistent_returns_none(risk_agent: RiskAgent) -> None:
    """get_tool 对不存在的工具返回 None。"""
    assert risk_agent.get_tool("foobar") is None
