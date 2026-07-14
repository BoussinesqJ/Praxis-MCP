"""测试 MarketAgent — 市场数据获取与情绪分析 (5 工具, is_readonly=True)"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _mock_handlers(agent) -> dict[str, MagicMock]:
    """替换 MarketAgent 全部 5 个工具 handler 为 MagicMock。

    返回 handler 字典以便各测试按需定制 return_value。
    """
    mocks: dict[str, MagicMock] = {}
    tool_configs = [
        ("get_market_data", {"success": True, "data": {"tickers": ["600995"], "quotes": {}}}),
        ("market_data_ext", {"success": True, "data": {"action": "fund_flow", "results": []}}),
        ("benchmark", {"success": True, "data": {"index_code": "000300", "kline": []}}),
        ("news", {"success": True, "data": {"action": "finance", "items": []}}),
        ("sentiment", {"success": True, "data": {"action": "analyze", "sentiment": "neutral"}}),
    ]
    for name, default_return in tool_configs:
        mock = MagicMock(return_value=default_return)
        agent._tool_map[name].handler = mock
        mocks[name] = mock
    return mocks


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


class TestMarketAgent:
    """MarketAgent 单元测试"""

    # ── test_init ──────────────────────────────────────────────

    def test_init(self, market_agent):
        """初始化验证：agent_name, is_readonly, tools 数量"""
        assert market_agent.agent_name == "market"
        assert market_agent.is_readonly is True
        assert len(market_agent.tools) == 5

    # ── test_get_market_data ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_market_data(self, market_agent):
        """get_market_data 工具执行成功"""
        _mock_handlers(market_agent)
        result = await market_agent.execute("get_market_data", {"tickers": ["600995"]})
        assert result.success is True
        assert result.data["tickers"] == ["600995"]
        assert "execution_time_ms" in result.metadata

    # ── test_market_data_ext ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_market_data_ext(self, market_agent):
        """market_data_ext 工具执行成功"""
        _mock_handlers(market_agent)
        result = await market_agent.execute("market_data_ext", {"action": "fund_flow", "ticker": "600995"})
        assert result.success is True
        assert result.data["action"] == "fund_flow"

    # ── test_benchmark ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_benchmark(self, market_agent):
        """benchmark 工具执行成功"""
        _mock_handlers(market_agent)
        result = await market_agent.execute("benchmark", {"action": "data", "index_code": "000300"})
        assert result.success is True
        assert result.data["index_code"] == "000300"

    # ── test_news ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_news(self, market_agent):
        """news 工具执行成功"""
        _mock_handlers(market_agent)
        result = await market_agent.execute("news", {"action": "finance", "count": 5})
        assert result.success is True
        assert result.data["action"] == "finance"

    # ── test_sentiment ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_sentiment(self, market_agent):
        """sentiment 工具执行成功"""
        _mock_handlers(market_agent)
        result = await market_agent.execute("sentiment", {"action": "analyze", "text": "市场情绪乐观"})
        assert result.success is True
        assert result.data["sentiment"] == "neutral"

    # ── test_nonexistent_tool ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_nonexistent_tool(self, market_agent):
        """不存在的工具返回 AgentResult(success=False)"""
        _mock_handlers(market_agent)
        result = await market_agent.execute("nonexistent", {})
        assert result.success is False
        assert "nonexistent" in result.error
        assert "market" in result.error

    # ── test_list_tools_has_tool_get_tool ──────────────────────

    def test_list_tools_has_tool_get_tool(self, market_agent):
        """工具查询方法：list_tools / has_tool / get_tool"""
        tools = market_agent.list_tools()
        assert len(tools) == 5
        tool_names = {t["name"] for t in tools}
        expected = {"get_market_data", "market_data_ext", "benchmark", "news", "sentiment"}
        assert tool_names == expected
        for t in tools:
            assert t["is_readonly"] is True
            assert t["tier"] == "core"

        assert market_agent.has_tool("get_market_data") is True
        assert market_agent.has_tool("nonexistent") is False

        tool = market_agent.get_tool("benchmark")
        assert tool is not None
        assert tool.name == "benchmark"
        assert tool.agent_name == "market"

        assert market_agent.get_tool("nonexistent") is None
