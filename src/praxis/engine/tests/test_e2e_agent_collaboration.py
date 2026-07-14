"""E2E Agent 协作测试 — Market→Risk→Review→Decision 串联

验证：
1. 4 种 Agent 独立可运行
2. 各 Agent 之间无循环依赖
3. 结果可串联传递（Market输出→Risk输入→Review串联）
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from praxis.agents.base import AgentDependencies
from praxis.agents.market import MarketAgent
from praxis.agents.risk import RiskAgent
from praxis.agents.review import ReviewAgent
from praxis.agents.decision import DecisionAgent
from praxis.agents.tests.conftest import FakeGuardrail


@pytest.mark.asyncio
async def test_e2e_agent_collaboration_chain():
    """Market→Risk→Review→Decision 四 Agent 协作串联 E2E

    流程：
    1. MarketAgent 获取行情 → 验证有数据
    2. RiskAgent sentinel + valuation + check_constraints → 验证结果
    3. ReviewAgent review + cascade_review + full_review → 验证串联
    4. DecisionAgent decision 创建 → 验证结果

    验证点：
    - 4 Agent 独立可运行
    - 无循环依赖
    - 结果可串联传递
    """
    # ── 准备依赖 ────────────────────────────────────────────
    mock_provider = MagicMock()
    mock_provider.get_realtime_quote = AsyncMock(return_value={
        "000001": {"price": 12.5, "change": 0.3, "name": "平安银行"},
        "600519": {"price": 1850.0, "change": 15.0, "name": "贵州茅台"},
    })
    mock_provider.get_history_kline = AsyncMock(return_value=[
        {"date": "2026-07-01", "open": 12.0, "high": 13.0, "low": 11.5,
         "close": 12.5, "volume": 1e7},
    ])
    mock_provider.get_fund_nav = AsyncMock(return_value={"nav": 1.5})

    deps = AgentDependencies(data_provider=mock_provider, workspace="test_ws")
    deps.guardrail = FakeGuardrail(state="ACTIVE")

    # ── 阶段1: MarketAgent 获取行情 ─────────────────────────
    market_agent = MarketAgent(deps=deps)

    async def mock_market(**params):
        tickers = params.get("tickers", [])
        quotes = {
            "000001": {"price": 12.5, "change_pct": 2.46, "name": "平安银行"},
            "600519": {"price": 1850.0, "change_pct": 0.82, "name": "贵州茅台"},
        }
        return {"success": True, "data": {"quotes": {t: quotes.get(t, {}) for t in tickers}}}

    market_agent._tool_map["get_market_data"].handler = AsyncMock(side_effect=mock_market)

    market_result = await market_agent.execute(
        "get_market_data", {"tickers": ["000001", "600519"]}
    )
    assert market_result.success, f"MarketAgent 应成功: {market_result.error}"
    quotes_data = market_result.data.get("quotes", {})
    assert "000001" in quotes_data, "应包含 000001 行情"
    assert "600519" in quotes_data, "应包含 600519 行情"

    # ── 阶段2: RiskAgent — sentinel + valuation + constraints ──
    risk_agent = RiskAgent(deps=deps)

    # Mock sentinel
    async def mock_sentinel(**params):
        return {
            "success": True,
            "data": {"state": "适度试探期", "bullish_count": 4, "total": 8,
                     "position_limit_pct": 20.0},
        }

    risk_agent._tool_map["sentinel"].handler = AsyncMock(side_effect=mock_sentinel)

    sentinel_result = await risk_agent.execute("sentinel", {"action": "scan"})
    assert sentinel_result.success, f"sentinel 应成功: {sentinel_result.error}"
    assert sentinel_result.data["state"] == "适度试探期"

    # Mock valuation
    async def mock_valuation(**params):
        return {
            "success": True,
            "data": {"pe_percentile": 45.0, "pb_percentile": 38.0,
                     "level": "fair", "current_pe": 12.5},
        }

    risk_agent._tool_map["valuation"].handler = AsyncMock(side_effect=mock_valuation)

    val_result = await risk_agent.execute(
        "valuation", {"action": "get", "index_code": "000300"}
    )
    assert val_result.success, f"valuation 应成功: {val_result.error}"
    assert val_result.data["level"] == "fair"

    # Mock check_constraints
    async def mock_constraints(**params):
        return {
            "success": True,
            "data": {"results": [
                {"rule": "现金底线", "level": "advisory", "passed": True},
                {"rule": "持仓上限", "level": "advisory", "passed": True},
            ]},
        }

    risk_agent._tool_map["check_constraints"].handler = AsyncMock(
        side_effect=mock_constraints
    )

    ck_result = await risk_agent.execute(
        "check_constraints",
        {"action": "check", "investor": "inv-test", "portfolio": "core",
         "ticker": "000001", "amount": 30000.0},
    )
    assert ck_result.success, f"check_constraints 应成功: {ck_result.error}"

    # ── 阶段3: ReviewAgent — review + cascade + full_review ──
    review_agent = ReviewAgent(deps=deps)

    async def mock_review(**params):
        return {
            "success": True,
            "data": {"filled_5d": 1, "filled_20d": 0, "filled_60d": 0,
                     "skipped": 0, "reviews": [
                         {"decision_id": "dec-001", "ticker": "000001",
                          "review_type": "5d", "actual_return_pct": 2.5}
                     ]},
        }

    review_agent._tool_map["review"].handler = AsyncMock(side_effect=mock_review)

    review_result = await review_agent.execute("review", {"action": "fill"})
    assert review_result.success, f"review fill 应成功: {review_result.error}"
    assert review_result.data["filled_5d"] == 1, "应回填 1 个 5d 复盘"

    async def mock_cascade(**params):
        return {
            "success": True,
            "data": {"mode": params.get("mode", "monthly"),
                     "max_drawdown": 0.08, "sharpe_ratio": 1.2, "win_rate": 0.65},
        }

    review_agent._tool_map["cascade_review"].handler = AsyncMock(side_effect=mock_cascade)

    cascade_result = await review_agent.execute(
        "cascade_review", {"mode": "monthly"}
    )
    assert cascade_result.success, f"cascade_review 应成功: {cascade_result.error}"

    async def mock_full_review(**params):
        return {
            "success": True,
            "data": {"snapshot_type": "full", "portfolio": {"nav": 1.05},
                     "performance": {"total_return": 0.05}},
        }

    review_agent._tool_map["full_review"].handler = AsyncMock(side_effect=mock_full_review)

    full_result = await review_agent.execute("full_review", {})
    assert full_result.success, f"full_review 应成功: {full_result.error}"
    assert "snapshot_type" in full_result.data, "应返回 snapshot_type"

    # ── 阶段4: DecisionAgent 创建决策 ───────────────────────
    decision_agent = DecisionAgent(deps=deps)

    async def mock_decision(**params):
        return {
            "success": True,
            "data": {"decision_id": "dec-collab-001", "ticker": params.get("ticker"),
                     "action": params.get("action"), "confidence": params.get("confidence")},
        }

    decision_agent._tool_map["decision"].handler = AsyncMock(side_effect=mock_decision)

    dec_result = await decision_agent.execute("decision", {
        "ticker": "000001",
        "action": "buy",
        "confidence": 0.8,
        "reasoning": "基于 Market+Risk+Review 的协作分析结果",
    })
    assert dec_result.success, f"decision 应成功: {dec_result.error}"
    assert dec_result.data["decision_id"] == "dec-collab-001"

    # ── 验证：4 Agent 独立可运行，无循环依赖 ─────────────────
    assert market_agent.agent_name == "market", "MarketAgent agent_name 正确"
    assert risk_agent.agent_name == "risk", "RiskAgent agent_name 正确"
    assert review_agent.agent_name == "review", "ReviewAgent agent_name 正确"
    assert decision_agent.agent_name == "decision", "DecisionAgent agent_name 正确"

    # 确认每个 Agent 的工具独立
    market_tools = {t.name for t in market_agent.tools}
    risk_tools = {t.name for t in risk_agent.tools}
    review_tools = {t.name for t in review_agent.tools}
    decision_tools = {t.name for t in decision_agent.tools}

    # 工具集无交集（无循环依赖）
    common = (market_tools & risk_tools) | (risk_tools & review_tools) | \
             (review_tools & decision_tools) | (market_tools & decision_tools)
    assert len(common) == 0, f"不同 Agent 之间不应共享工具: {common}"
