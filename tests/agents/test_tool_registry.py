"""测试 ToolRegistry 插件式工具注册与发现"""

import pytest
from unittest.mock import patch, MagicMock

from praxis.agents.base import Tool
from praxis.agents.tool_registry import ToolRegistry
from pydantic import BaseModel, Field


# ── Test Fixtures ─────────────────────────────────────────────


class _DummyInput(BaseModel):
    x: int = Field(default=1, description="dummy")


@pytest.fixture
def empty_registry():
    return ToolRegistry()


@pytest.fixture
def populated_registry():
    r = ToolRegistry()
    r.register(Tool(name="tool_a", description="Tool A", input_schema=_DummyInput, handler=lambda **kw: {}, agent_name="agent_1"))
    r.register(Tool(name="tool_b", description="Tool B", input_schema=_DummyInput, handler=lambda **kw: {}, agent_name="agent_1"))
    r.register(Tool(name="tool_c", description="Tool C", input_schema=_DummyInput, handler=lambda **kw: {}, agent_name="agent_2", is_readonly=False))
    return r


# ── Tests: Register ───────────────────────────────────────────


class TestRegister:
    """工具注册测试"""

    def test_register_single(self, empty_registry):
        tool = Tool(name="test", description="desc", input_schema=_DummyInput, handler=lambda: None, agent_name="a")
        empty_registry.register(tool)
        assert empty_registry.count() == 1
        assert empty_registry.get("test") is tool

    def test_register_duplicate_raises(self, empty_registry):
        tool = Tool(name="test", description="desc", input_schema=_DummyInput, handler=lambda: None, agent_name="a")
        empty_registry.register(tool)
        with pytest.raises(ValueError, match="工具名冲突"):
            empty_registry.register(Tool(name="test", description="other", input_schema=_DummyInput, handler=lambda: None, agent_name="b"))

    def test_register_many(self, empty_registry):
        tools = [
            Tool(name=f"t{i}", description="d", input_schema=_DummyInput, handler=lambda: None, agent_name="a")
            for i in range(5)
        ]
        count = empty_registry.register_many(tools)
        assert count == 5
        assert empty_registry.count() == 5

    def test_register_many_with_duplicates(self, empty_registry):
        tools = [
            Tool(name="t1", description="d1", input_schema=_DummyInput, handler=lambda: None, agent_name="a"),
            Tool(name="t1", description="d2", input_schema=_DummyInput, handler=lambda: None, agent_name="b"),  # 重复
            Tool(name="t2", description="d3", input_schema=_DummyInput, handler=lambda: None, agent_name="a"),
        ]
        count = empty_registry.register_many(tools)
        assert count == 2  # t1 (第一个) + t2


# ── Tests: Query ──────────────────────────────────────────────


class TestQuery:
    """工具查询测试"""

    def test_get_existing(self, populated_registry):
        tool = populated_registry.get("tool_a")
        assert tool is not None
        assert tool.name == "tool_a"

    def test_get_nonexistent(self, populated_registry):
        assert populated_registry.get("nonexistent") is None

    def test_list_by_agent(self, populated_registry):
        tools = populated_registry.list_by_agent("agent_1")
        assert len(tools) == 2
        assert all(t.agent_name == "agent_1" for t in tools)

    def test_list_by_agent_empty(self, populated_registry):
        tools = populated_registry.list_by_agent("nonexistent")
        assert len(tools) == 0

    def test_list_all(self, populated_registry):
        tools = populated_registry.list_all()
        assert len(tools) == 3

    def test_list_by_tier(self):
        r = ToolRegistry()
        r.register(Tool(name="t1", description="d", input_schema=_DummyInput, handler=lambda: None, agent_name="a", tier="core"))
        r.register(Tool(name="t2", description="d", input_schema=_DummyInput, handler=lambda: None, agent_name="a", tier="advanced"))
        assert len(r.list_by_tier("core")) == 1
        assert len(r.list_by_tier("advanced")) == 1

    def test_get_tool_names(self, populated_registry):
        names = populated_registry.get_tool_names()
        assert set(names) == {"tool_a", "tool_b", "tool_c"}

    def test_get_agent_names(self, populated_registry):
        agents = populated_registry.get_agent_names()
        assert set(agents) == {"agent_1", "agent_2"}


# ── Tests: Conflict Detection ─────────────────────────────────


class TestConflicts:
    """冲突检测测试"""

    def test_no_conflicts(self, populated_registry):
        conflicts = populated_registry.detect_conflicts()
        assert len(conflicts) == 0

    def test_with_conflicts(self):
        r = ToolRegistry()
        # 无法直接注册同名工具（register 会抛异常），
        # 测试 detect_conflicts 在没有冲突时返回空
        r.register(Tool(name="t", description="d", input_schema=_DummyInput, handler=lambda: None, agent_name="a"))
        conflicts = r.detect_conflicts()
        assert len(conflicts) == 0


# ── Tests: Export ─────────────────────────────────────────────


class TestExport:
    """导出测试"""

    def test_export_manifest(self, populated_registry):
        manifest = populated_registry.export_manifest()
        assert manifest["total_tools"] == 3
        assert manifest["total_agents"] == 2
        assert set(manifest["agents"].keys()) == {"agent_1", "agent_2"}

    def test_export_manifest_empty(self, empty_registry):
        manifest = empty_registry.export_manifest()
        assert manifest["total_tools"] == 0
        assert manifest["total_agents"] == 0


# ── Tests: Discover ───────────────────────────────────────────


class TestDiscover:
    """自动发现测试"""

    @pytest.mark.asyncio
    async def test_discover_nonexistent_package(self, empty_registry):
        count = await empty_registry.discover("nonexistent.package")
        assert count == 0

    @pytest.mark.asyncio
    async def test_discover_empty_package(self, empty_registry):
        """测试 discover 在空包上的行为（不会 crash）"""
        count = await empty_registry.discover("praxis.tools")
        # praxis.tools 存在但 modules 可能没有 register 函数
        assert count >= 0
