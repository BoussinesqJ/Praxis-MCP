"""MarketAgent 测试 — 5 工具（get_market_data / market_data_ext / benchmark / news / sentiment），只读。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from praxis.agents.market import MarketAgent


# ═══════════════════════════════════════════════════════════════════
# 场景1：agent_name
# ═══════════════════════════════════════════════════════════════════


def test_agent_name_is_market(market_agent: MarketAgent) -> None:
    """agent_name 应为 "market"。"""
    assert market_agent.agent_name == "market"


# ═══════════════════════════════════════════════════════════════════
# 场景2：is_readonly
# ═══════════════════════════════════════════════════════════════════


def test_is_readonly_true(market_agent: MarketAgent) -> None:
    """MarketAgent 应为只读。"""
    assert market_agent.is_readonly is True


# ═══════════════════════════════════════════════════════════════════
# 场景3：tool registration
# ═══════════════════════════════════════════════════════════════════


def test_all_five_tools_registered(market_agent: MarketAgent) -> None:
    """应注册 5 个工具。"""
    tool_names = [t.name for t in market_agent.tools]
    assert len(tool_names) == 5
    assert "get_market_data" in tool_names
    assert "market_data_ext" in tool_names
    assert "benchmark" in tool_names
    assert "news" in tool_names
    assert "sentiment" in tool_names


def test_all_tools_are_readonly(market_agent: MarketAgent) -> None:
    """所有工具 is_readonly 应为 True。"""
    for tool in market_agent.tools:
        assert tool.is_readonly is True, f"Tool {tool.name} should be readonly"


# ═══════════════════════════════════════════════════════════════════
# 场景4-7：execute 各工具
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_get_market_data(market_agent: MarketAgent) -> None:
    """execute get_market_data 返回成功。"""
    market_agent._tool_map["get_market_data"].handler = AsyncMock(
        return_value={"success": True, "data": {"ticker": "000001", "price": 12.5}}
    )
    result = await market_agent.execute("get_market_data", {"ticker": "000001"})
    assert result.success is True
    assert result.data["ticker"] == "000001"


@pytest.mark.asyncio
async def test_execute_market_data_ext(market_agent: MarketAgent) -> None:
    """execute market_data_ext 返回扩展行情数据。"""
    market_agent._tool_map["market_data_ext"].handler = AsyncMock(
        return_value={"success": True, "data": {"fund_flow": {}, "lhb": [], "reports": []}}
    )
    result = await market_agent.execute("market_data_ext", {"ticker": "600519", "ext_type": "fund_flow"})
    assert result.success is True
    assert "fund_flow" in result.data


@pytest.mark.asyncio
async def test_execute_benchmark(market_agent: MarketAgent) -> None:
    """execute benchmark 返回基准指数数据。"""
    market_agent._tool_map["benchmark"].handler = AsyncMock(
        return_value={"success": True, "data": {"index": "000300", "price": 4000.0}}
    )
    result = await market_agent.execute("benchmark", {"index_code": "000300"})
    assert result.success is True
    assert result.data["index"] == "000300"


@pytest.mark.asyncio
async def test_execute_news(market_agent: MarketAgent) -> None:
    """execute news 返回新闻情报。"""
    market_agent._tool_map["news"].handler = AsyncMock(
        return_value={"success": True, "data": {"articles": [{"title": "Test News"}]}}
    )
    result = await market_agent.execute("news", {"ticker": "000001", "limit": 5})
    assert result.success is True
    assert len(result.data["articles"]) == 1


# ═══════════════════════════════════════════════════════════════════
# 场景8：list_tools / has_tool / get_tool 验证
# ═══════════════════════════════════════════════════════════════════


def test_list_tools_returns_all_tools(market_agent: MarketAgent) -> None:
    """list_tools 应返回 5 个工具摘要。"""
    tools = market_agent.list_tools()
    assert len(tools) == 5
    names = [t["name"] for t in tools]
    assert "get_market_data" in names
    assert "sentiment" in names


def test_has_tool_positive(market_agent: MarketAgent) -> None:
    """已注册工具 has_tool 返回 True。"""
    assert market_agent.has_tool("get_market_data") is True
    assert market_agent.has_tool("benchmark") is True


def test_has_tool_negative(market_agent: MarketAgent) -> None:
    """未注册工具 has_tool 返回 False。"""
    assert market_agent.has_tool("nonexistent") is False


def test_get_tool_returns_tool_object(market_agent: MarketAgent) -> None:
    """get_tool 返回正确的 Tool 对象。"""
    tool = market_agent.get_tool("sentiment")
    assert tool is not None
    assert tool.name == "sentiment"
    assert tool.agent_name == "market"


def test_get_tool_nonexistent_returns_none(market_agent: MarketAgent) -> None:
    """get_tool 对不存在的工具返回 None。"""
    assert market_agent.get_tool("foobar") is None
