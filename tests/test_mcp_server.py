"""MCP Server v2.0 测试 — 工具精简 + 分层加载"""
import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock
from praxis.mcp_server import mcp, _log_tool_call, _TOOLS_TIER, _TIER_ORDER


class TestMCPServer:
    """MCP Server 基础测试"""

    def test_mcp_server_creation(self):
        """测试 MCP Server 创建"""
        assert mcp is not None
        assert mcp.name == "PRAXIS"

    def test_log_tool_call_sync(self):
        """测试同步工具调用日志"""
        def mock_func(**kwargs):
            return {"success": True, "data": "test"}
        result = asyncio.run(_log_tool_call("test_tool", mock_func, workspace="."))
        assert result["success"] is True

    def test_log_tool_call_async(self):
        """测试异步工具调用日志"""
        async def mock_func(**kwargs):
            return {"success": True, "data": "test"}
        result = asyncio.run(_log_tool_call("test_tool", mock_func, workspace="."))
        assert result["success"] is True

    def test_log_tool_call_error(self):
        """测试工具调用错误日志"""
        def mock_func(**kwargs):
            raise ValueError("test error")
        result = asyncio.run(_log_tool_call("test_tool", mock_func, workspace="."))
        assert result["success"] is False
        assert "test error" in result["error"]



class TestMergedToolActions:
    """合并工具 action 分发测试"""

    def test_ledger_tool_invalid_action(self):
        """测试 ledger_tool 无效 action 返回错误"""
        from praxis.mcp_server import ledger_tool
        result = asyncio.run(ledger_tool(action="invalid"))
        assert result["success"] is False
        assert "未知 action" in result["error"]

    def test_decision_tool_invalid_action(self):
        """测试 decision_tool 无效 action 返回错误"""
        from praxis.mcp_server import decision_tool
        result = asyncio.run(decision_tool(action="invalid"))
        assert result["success"] is False

    def test_sentinel_tool_invalid_action(self):
        """测试 sentinel_tool 无效 action 返回错误"""
        from praxis.mcp_server import sentinel_tool
        result = asyncio.run(sentinel_tool(action="invalid"))
        assert result["success"] is False

    def test_nav_tool_invalid_action(self):
        """测试 nav_tool 无效 action 返回错误"""
        from praxis.mcp_server import nav_tool
        result = asyncio.run(nav_tool(action="invalid"))
        assert result["success"] is False

    def test_news_tool_invalid_action(self):
        """测试 news_tool 无效 action 返回错误"""
        from praxis.mcp_server import news_tool
        result = asyncio.run(news_tool(action="invalid"))
        assert result["success"] is False

    def test_trading_friction_tool_invalid_action(self):
        """测试 trading_friction_tool 无效 action 返回错误"""
        from praxis.mcp_server import trading_friction_tool
        result = asyncio.run(trading_friction_tool(action="invalid"))
        assert result["success"] is False
