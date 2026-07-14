"""E2E Guardrail 门控测试 — 三态状态机拦截验证

场景：
1. LOCKED：DecisionAgent 写操作被拦截 → 账本无新增
2. ACTIVE：写操作放行 → 账本有记录
3. AUDITING→LOCKED：状态切换后行为正确
"""

from __future__ import annotations

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from praxis.agents.base import AgentDependencies
from praxis.agents.decision import DecisionAgent
from praxis.agents.tests.conftest import FakeGuardrail
from praxis.core.guardrail import Guardrail, GuardrailState


@pytest.mark.asyncio
async def test_e2e_guardrail_three_states(tmp_path):
    """Guardrail 三态门控 E2E — LOCKED 拦截 / ACTIVE 放行 / AUDITING→LOCKED 流转

    验证点：
    1. LOCKED 状态下 trading 被拦截，模拟账本无新增
    2. ACTIVE 状态下 trading 放行，模拟账本有记录
    3. AUDITING 状态下写操作被拦截
    4. AUDITING→LOCKED 流转后行为一致
    """
    # ── 准备：Agent + Guardrail ──────────────────────────────
    mock_provider = MagicMock()
    mock_provider.get_realtime_quote = AsyncMock(return_value={})
    mock_provider.get_history_kline = AsyncMock(return_value=[])
    mock_provider.get_fund_nav = AsyncMock(return_value={})

    deps = AgentDependencies(data_provider=mock_provider, workspace=str(tmp_path))

    # 模拟账本
    ledger_entries = []

    async def mock_trading_handler(**params):
        """模拟 trading handler — 成功时写入账本"""
        action = params.get("action", "")
        if action == "add":
            entry = {
                "ticker": params.get("ticker", ""),
                "trade_action": params.get("trade_action", ""),
                "quantity": params.get("quantity", 0),
                "price": params.get("price", 0),
            }
            ledger_entries.append(entry)
            return {"success": True, "data": {"tx_id": f"tx-{len(ledger_entries):06d}"}}
        return {"success": True, "data": {}}

    # ── 场景1：LOCKED — 写操作被拦截 ────────────────────────
    deps.guardrail = FakeGuardrail(state="LOCKED")
    agent = DecisionAgent(deps=deps)
    agent._tool_map["trading"].handler = AsyncMock(side_effect=mock_trading_handler)

    ledger_before_locked = len(ledger_entries)
    result = await agent.execute("trading", {
        "action": "add",
        "ticker": "000001",
        "trade_action": "buy",
        "quantity": 100.0,
        "price": 12.5,
    })
    assert result.success is False, "LOCKED 状态应拦截写操作"
    assert "Guardrail" in result.error, f"错误信息应包含 Guardrail: {result.error}"
    assert result.metadata["guardrail_state"] == "LOCKED"
    assert len(ledger_entries) == ledger_before_locked, "LOCKED 状态账本不应增加"

    # ── 场景2：ACTIVE — 写操作放行 ─────────────────────────
    deps.guardrail = FakeGuardrail(state="ACTIVE")
    agent = DecisionAgent(deps=deps)
    agent._tool_map["trading"].handler = AsyncMock(side_effect=mock_trading_handler)

    result = await agent.execute("trading", {
        "action": "add",
        "ticker": "600519",
        "trade_action": "buy",
        "quantity": 50.0,
        "price": 1850.0,
    })
    assert result.success is True, "ACTIVE 状态应放行写操作"
    assert len(ledger_entries) == 1, "ACTIVE 状态账本应有 1 条新记录"
    assert ledger_entries[0]["ticker"] == "600519", "ticker 应正确"
    assert ledger_entries[0]["quantity"] == 50.0, "quantity 应正确"

    # ── 场景3：AUDITING — 写操作被拦截 ─────────────────────
    deps.guardrail = FakeGuardrail(state="AUDITING")
    agent = DecisionAgent(deps=deps)
    agent._tool_map["trading"].handler = AsyncMock(side_effect=mock_trading_handler)

    ledger_before_audit = len(ledger_entries)
    result = await agent.execute("trading", {
        "action": "add",
        "ticker": "159915",
        "trade_action": "buy",
        "quantity": 10000.0,
        "price": 2.35,
    })
    assert result.success is False, "AUDITING 状态应拦截写操作"
    assert "Guardrail" in result.error
    assert result.metadata["guardrail_state"] == "AUDITING"
    assert len(ledger_entries) == ledger_before_audit, "AUDITING 状态账本不应增加"

    # ── 场景3b：AUDITING→LOCKED 流转 ──────────────────────
    # 使用真实 Guardrail 验证状态流转（需要 SQLite db）
    db_path = tmp_path / "temp_guardrail.db"
    real_guardrail = Guardrail(db_path=str(db_path))
    await real_guardrail.initialize()

    # 初始应为 ACTIVE
    status = real_guardrail.get_status()
    assert status["is_active"], "初始状态应为 ACTIVE"

    # ACTIVE → AUDITING
    r = await real_guardrail.start_audit("开始复盘")
    assert r.allowed, f"ACTIVE → AUDITING 应成功: {r.reason}"
    status = real_guardrail.get_status()
    assert status["is_auditing"], "切换后应为 AUDITING"

    # AUDITING 下禁止写操作
    vr = await real_guardrail.verify_action("decision", "trading", {})
    assert not vr.allowed, "AUDITING 下应禁止 trading"

    # AUDITING → LOCKED (紧急锁定)
    r = await real_guardrail.lock("紧急锁定")
    assert r.allowed, "AUDITING → LOCKED 应允许"
    status = real_guardrail.get_status()
    assert status["is_locked"], "锁定后应为 LOCKED"

    # LOCKED 下禁止写操作
    vr = await real_guardrail.verify_action("decision", "trading", {})
    assert not vr.allowed, "LOCKED 下应禁止 trading"

    # 验证审计历史
    history = real_guardrail.get_history()
    assert len(history) >= 2, f"历史至少应有 2 条: {history}"

    await real_guardrail.close()


@pytest.mark.asyncio
async def test_e2e_guardrail_readonly_tools_unaffected(tmp_path):
    """验证 Guardrail LOCKED/AUDITING 不影响只读工具的 MarketAgent。

    即使 Guardrail=LOCKED，MarketAgent(get_market_data) 仍正常执行。
    """
    mock_provider = MagicMock()
    mock_provider.get_realtime_quote = AsyncMock(return_value={
        "000001": {"price": 12.5, "name": "平安银行"},
    })

    deps = AgentDependencies(data_provider=mock_provider, workspace=str(tmp_path))
    deps.guardrail = FakeGuardrail(state="LOCKED")  # 全局锁定

    from praxis.agents.market import MarketAgent
    agent = MarketAgent(deps=deps)

    async def mock_get_market_data(**params):
        return {"success": True, "data": {"quotes": {"000001": {"price": 12.5}}}}

    agent._tool_map["get_market_data"].handler = AsyncMock(
        side_effect=mock_get_market_data
    )

    result = await agent.execute("get_market_data", {"tickers": ["000001"]})
    assert result.success is True, (
        f"LOCKED 下只读 get_market_data 应放行: {result.error}"
    )
    assert "quotes" in result.data, "应返回行情数据"
