"""测试 BaseAgent 抽象基类 + AgentResult + Tool + AgentDependencies"""

import pytest

from praxis.agents.base import (
    BaseAgent,
    AgentResult,
    Tool,
    AgentDependencies,
)
from pydantic import BaseModel, Field


# ── 测试用的具体 Agent ────────────────────────────────────────


class _TestInput(BaseModel):
    name: str = Field(default="test", description="测试参数")


class TestAgent(BaseAgent):
    """用于测试的具体 Agent 实现"""
    agent_name = "test_agent"
    description = "Test Agent for unit testing"
    is_readonly = True

    def _register_tools(self) -> list[Tool]:
        return [
            Tool(
                name="say_hello",
                description="Say hello",
                input_schema=_TestInput,
                handler=self._say_hello,
                agent_name=self.agent_name,
            ),
            Tool(
                name="raise_error",
                description="Always raise an error",
                input_schema=_TestInput,
                handler=self._raise_error,
                agent_name=self.agent_name,
            ),
        ]

    async def _say_hello(self, name: str = "test") -> dict:
        return {"success": True, "data": {"greeting": f"Hello, {name}!"}}

    async def _raise_error(self, name: str = "test") -> dict:
        raise RuntimeError("Intentional test error")


# ── Test Fixtures ─────────────────────────────────────────────


@pytest.fixture
def mock_deps():
    """创建最小化的 AgentDependencies"""
    from praxis.engine.data_provider import CachedDataProvider
    provider = CachedDataProvider(workspace=".", cache_ttl_seconds=1, auto_discover=False)
    return AgentDependencies(data_provider=provider, workspace=".")


@pytest.fixture
def test_agent(mock_deps):
    return TestAgent(mock_deps)


# ── Tests: AgentResult ────────────────────────────────────────


class TestAgentResult:
    """AgentResult 数据类测试"""

    def test_success_result(self):
        result = AgentResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_error_result(self):
        result = AgentResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"

    def test_to_dict_success(self):
        result = AgentResult(success=True, data={"a": 1}, metadata={"ms": 42})
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"a": 1}
        assert d["_metadata"]["ms"] == 42
        assert "error" not in d

    def test_to_dict_error(self):
        result = AgentResult(success=False, error="fail")
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "fail"

    def test_metadata_default(self):
        result = AgentResult(success=True)
        assert result.metadata == {}


# ── Tests: Tool ───────────────────────────────────────────────


class TestTool:
    """Tool 数据类测试"""

    def test_create_tool(self):
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=_TestInput,
            handler=lambda **kw: {"ok": True},
            agent_name="test_agent",
        )
        assert tool.name == "test_tool"
        assert tool.agent_name == "test_agent"
        assert tool.tier == "core"
        assert tool.is_readonly is True

    def test_tool_equality(self):
        t1 = Tool(name="foo", description="desc", input_schema=_TestInput, handler=lambda: None, agent_name="a")
        t2 = Tool(name="foo", description="other", input_schema=_TestInput, handler=lambda: None, agent_name="b")
        t3 = Tool(name="bar", description="desc", input_schema=_TestInput, handler=lambda: None, agent_name="a")
        assert t1 == t2  # 同名即相等
        assert t1 != t3
        assert hash(t1) == hash(t2)

    def test_write_tool(self):
        tool = Tool(
            name="write_tool",
            description="A write tool",
            input_schema=_TestInput,
            handler=lambda **kw: {"ok": True},
            agent_name="decision",
            is_readonly=False,
        )
        assert tool.is_readonly is False


# ── Tests: BaseAgent ──────────────────────────────────────────


class TestBaseAgent:
    """BaseAgent 抽象基类测试"""

    def test_cannot_instantiate_abstract(self, mock_deps):
        """BaseAgent 不能直接实例化"""
        with pytest.raises(TypeError):
            BaseAgent(mock_deps)  # type: ignore

    def test_agent_initialization(self, test_agent):
        """Agent 正确初始化"""
        assert test_agent.agent_name == "test_agent"
        assert test_agent.description == "Test Agent for unit testing"
        assert test_agent.is_readonly is True
        assert len(test_agent.tools) == 2

    def test_list_tools(self, test_agent):
        """列出工具"""
        tools = test_agent.list_tools()
        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert "say_hello" in tool_names
        assert "raise_error" in tool_names

    def test_has_tool(self, test_agent):
        """检查工具是否存在"""
        assert test_agent.has_tool("say_hello") is True
        assert test_agent.has_tool("nonexistent") is False

    def test_get_tool(self, test_agent):
        """获取工具描述符"""
        tool = test_agent.get_tool("say_hello")
        assert tool is not None
        assert tool.name == "say_hello"
        assert tool.agent_name == "test_agent"

    def test_get_tool_nonexistent(self, test_agent):
        """获取不存在的工具返回 None"""
        assert test_agent.get_tool("nonexistent") is None

    @pytest.mark.asyncio
    async def test_execute_success(self, test_agent):
        """成功执行工具"""
        result = await test_agent.execute("say_hello", {"name": "World"})
        assert result.success is True
        assert result.data["greeting"] == "Hello, World!"
        assert "execution_time_ms" in result.metadata
        assert result.metadata["agent_name"] == "test_agent"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, test_agent):
        """执行不存在的工具"""
        result = await test_agent.execute("nonexistent", {})
        assert result.success is False
        assert "没有注册工具" in result.error

    @pytest.mark.asyncio
    async def test_execute_raises_error(self, test_agent):
        """工具抛出异常时返回 error"""
        result = await test_agent.execute("raise_error", {"name": "test"})
        assert result.success is False
        assert "Intentional test error" in result.error
        assert result.metadata["agent_name"] == "test_agent"


# ── Tests: AgentDependencies ──────────────────────────────────


class TestAgentDependencies:
    """依赖注入容器测试"""

    def test_minimal_deps(self):
        from praxis.engine.data_provider import CachedDataProvider
        provider = CachedDataProvider(workspace=".", auto_discover=False)
        deps = AgentDependencies(data_provider=provider, workspace=".")
        assert deps.data_provider is provider
        assert deps.workspace == "."
        assert deps.ledger is None
        assert deps.guardrail is None
        assert deps.state_store is None
        assert deps.memory_store is None

    def test_full_deps(self):
        """渐进式注入测试"""
        from praxis.engine.data_provider import CachedDataProvider
        from praxis.core.guardrail import Guardrail

        provider = CachedDataProvider(workspace=".", auto_discover=False)
        guardrail = Guardrail(db_path=":memory:")
        deps = AgentDependencies(
            data_provider=provider,
            guardrail=guardrail,
        )
        assert deps.guardrail is guardrail
