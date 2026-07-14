"""测试 RiskAgent — 风险评估与约束检查 (4 工具, is_readonly=True)"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _mock_handlers(agent) -> dict[str, MagicMock]:
    """替换 RiskAgent 全部 4 个工具 handler 为 MagicMock。"""
    mocks: dict[str, MagicMock] = {}
    tool_configs = [
        ("sentinel", {"success": True, "data": {"action": "scan", "alerts": []}}),
        ("valuation", {"success": True, "data": {"action": "percentile", "index_code": "000300", "percentile": 45.0}}),
        ("check_constraints", {"success": True, "data": {"passed": True, "checks": []}}),
        ("trading_friction", {"success": True, "data": {"action": "fee", "fee": 0.0003}}),
    ]
    for name, default_return in tool_configs:
        mock = MagicMock(return_value=default_return)
        agent._tool_map[name].handler = mock
        mocks[name] = mock
    return mocks


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


class TestRiskAgent:
    """RiskAgent 单元测试"""

    # ── test_init ──────────────────────────────────────────────

    def test_init(self, risk_agent):
        """初始化验证：agent_name=="risk", is_readonly==True, len(tools)==4"""
        assert risk_agent.agent_name == "risk"
        assert risk_agent.is_readonly is True
        assert len(risk_agent.tools) == 4

    # ── test_sentinel ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_sentinel(self, risk_agent):
        """sentinel 哨兵雷达扫描执行成功"""
        _mock_handlers(risk_agent)
        result = await risk_agent.execute("sentinel", {"action": "scan", "days": 10})
        assert result.success is True
        assert result.data["action"] == "scan"

    # ── test_valuation ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_valuation(self, risk_agent):
        """valuation 指数估值分位执行成功"""
        _mock_handlers(risk_agent)
        result = await risk_agent.execute("valuation", {"action": "percentile", "index_code": "000300"})
        assert result.success is True
        assert result.data["percentile"] == 45.0

    # ── test_check_constraints ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_constraints(self, risk_agent):
        """check_constraints 交易约束检查执行成功"""
        _mock_handlers(risk_agent)
        result = await risk_agent.execute(
            "check_constraints",
            {"investor": "demo", "portfolio": "core", "action": "buy", "ticker": "600995", "amount": 10000},
        )
        assert result.success is True
        assert result.data["passed"] is True

    # ── test_trading_friction ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_trading_friction(self, risk_agent):
        """trading_friction 摩擦成本工具执行成功"""
        _mock_handlers(risk_agent)
        result = await risk_agent.execute(
            "trading_friction",
            {"action": "fee", "ticker": "600995", "quantity": 100, "price": 50.0},
        )
        assert result.success is True
        assert result.data["fee"] == 0.0003

    # ── test_nonexistent_tool ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_nonexistent_tool(self, risk_agent):
        """不存在的工具返回 AgentResult(success=False)"""
        _mock_handlers(risk_agent)
        result = await risk_agent.execute("nonexistent", {})
        assert result.success is False
        assert "nonexistent" in result.error

    # ── test_list_tools ────────────────────────────────────────

    def test_list_tools(self, risk_agent):
        """工具列表：list_tools / has_tool / get_tool"""
        tools = risk_agent.list_tools()
        assert len(tools) == 4
        tool_names = {t["name"] for t in tools}
        expected = {"sentinel", "valuation", "check_constraints", "trading_friction"}
        assert tool_names == expected

        assert risk_agent.has_tool("sentinel") is True
        assert risk_agent.has_tool("ghost") is False

        tool = risk_agent.get_tool("trading_friction")
        assert tool is not None
        assert tool.agent_name == "risk"

    # ── test_guardrail_no_block_readonly ───────────────────────

    @pytest.mark.asyncio
    async def test_guardrail_no_block_readonly(self, risk_agent, locked_guardrail):
        """LOCKED 状态下只读工具仍应通过 — guardrail 不拦截 is_readonly=True 工具"""
        # 注入 LOCKED guardrail
        risk_agent.deps.guardrail = locked_guardrail
        _mock_handlers(risk_agent)
        # RiskAgent 所有工具都是只读的，LOCKED 不应拦截
        result = await risk_agent.execute("sentinel", {"action": "scan", "days": 10})
        assert result.success is True
        assert result.data["action"] == "scan"
