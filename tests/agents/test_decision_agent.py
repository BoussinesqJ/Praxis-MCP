"""测试 DecisionAgent — 决策创建与交易执行 (2 写工具, is_readonly=False)

核心 Guardrail 测试:
    - ACTIVE    → 写操作放行
    - LOCKED    → 写操作拦截
    - AUDITING  → 写操作拦截
    - None      → 写操作放行（无 guardrail）
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from praxis.core.guardrail import GuardrailState


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _mock_handlers(agent) -> dict[str, MagicMock]:
    """替换 DecisionAgent 全部 2 个工具 handler 为 MagicMock。

    DecisionAgent 的 2 个工具均为 is_readonly=False（写操作）。
    """
    mocks: dict[str, MagicMock] = {}
    tool_configs = [
        ("trading", {"success": True, "data": {"action": "ledger", "tx_id": "tx-001"}}),
        ("decision", {"success": True, "data": {"action": "buy", "decision_id": "d-001"}}),
    ]
    for name, default_return in tool_configs:
        mock = MagicMock(return_value=default_return)
        agent._tool_map[name].handler = mock
        mocks[name] = mock
    return mocks


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


class TestDecisionAgent:
    """DecisionAgent 单元测试 — Guardrail 门控核心"""

    # ── test_init ──────────────────────────────────────────────

    def test_init(self, decision_agent):
        """初始化验证：is_readonly==False, len(tools)==2"""
        assert decision_agent.agent_name == "decision"
        assert decision_agent.is_readonly is False
        assert len(decision_agent.tools) == 2
        # 验证两个工具都是写操作
        for tool in decision_agent.tools:
            assert tool.is_readonly is False

    # ── test_guardrail_active_allows_write ─────────────────────

    @pytest.mark.asyncio
    async def test_guardrail_active_allows_write(self, decision_agent, active_guardrail):
        """ACTIVE 状态写操作成功 — guardrail 放行"""
        decision_agent.deps.guardrail = active_guardrail
        _mock_handlers(decision_agent)

        result = await decision_agent.execute(
            "trading",
            {"action": "ledger", "ticker": "600995", "trade_action": "buy", "quantity": 100, "price": 50.0},
        )
        assert result.success is True
        assert result.data["action"] == "ledger"

    # ── test_guardrail_locked_blocks_write ─────────────────────

    @pytest.mark.asyncio
    async def test_guardrail_locked_blocks_write(self, decision_agent, locked_guardrail):
        """LOCKED → AgentResult(success=False, error含"Guardrail")"""
        decision_agent.deps.guardrail = locked_guardrail
        _mock_handlers(decision_agent)

        result = await decision_agent.execute(
            "trading",
            {"action": "ledger", "ticker": "600995", "trade_action": "buy"},
        )
        assert result.success is False
        assert "Guardrail" in result.error
        assert result.metadata.get("guardrail_state") == "LOCKED"

    # ── test_guardrail_auditing_blocks_write ───────────────────

    @pytest.mark.asyncio
    async def test_guardrail_auditing_blocks_write(self, decision_agent):
        """AUDITING → 拦截写操作"""
        from conftest import FakeGuardrail
        audit_guardrail = FakeGuardrail(state=GuardrailState.AUDITING)
        decision_agent.deps.guardrail = audit_guardrail
        _mock_handlers(decision_agent)

        result = await decision_agent.execute(
            "decision",
            {"ticker": "600995", "action": "buy", "confidence": 0.8, "reasoning": "测试"},
        )
        assert result.success is False
        assert "Guardrail" in result.error
        assert result.metadata.get("guardrail_state") == "AUDITING"

    # ── test_trading_route ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_trading_route(self, decision_agent, active_guardrail):
        """trading 工具路由验证：正常执行路径"""
        decision_agent.deps.guardrail = active_guardrail
        mocks = _mock_handlers(decision_agent)
        # 定制 trading handler 返回
        mocks["trading"].return_value = {"success": True, "data": {"action": "add", "tx_id": "tx-002"}}

        result = await decision_agent.execute(
            "trading",
            {"action": "add", "ticker": "510310", "trade_action": "buy", "quantity": 500, "price": 1.2},
        )
        assert result.success is True
        assert result.data["tx_id"] == "tx-002"

    # ── test_no_guardrail_allows_write ─────────────────────────

    @pytest.mark.asyncio
    async def test_no_guardrail_allows_write(self, decision_agent):
        """deps.guardrail=None → 放行（无 guardrail 时不检查）"""
        decision_agent.deps.guardrail = None
        _mock_handlers(decision_agent)

        result = await decision_agent.execute(
            "decision",
            {"ticker": "600995", "action": "sell", "confidence": 0.9, "reasoning": "止盈"},
        )
        assert result.success is True

    # ── test_nonexistent_tool ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_nonexistent_tool(self, decision_agent):
        """不存在的工具返回 AgentResult(success=False)"""
        _mock_handlers(decision_agent)
        result = await decision_agent.execute("nonexistent", {})
        assert result.success is False
        assert "nonexistent" in result.error

    # ── test_metadata_records_execution_time_ms ────────────────

    @pytest.mark.asyncio
    async def test_metadata_records_execution_time_ms(self, decision_agent, active_guardrail):
        """成功执行后 metadata 包含 execution_time_ms"""
        decision_agent.deps.guardrail = active_guardrail
        _mock_handlers(decision_agent)

        result = await decision_agent.execute(
            "decision",
            {"ticker": "600995", "action": "buy", "confidence": 0.7, "reasoning": "测试元数据"},
        )
        assert result.success is True
        assert "execution_time_ms" in result.metadata
        assert isinstance(result.metadata["execution_time_ms"], (int, float))
        assert result.metadata["execution_time_ms"] >= 0
