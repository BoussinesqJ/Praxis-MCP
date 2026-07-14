"""PRAXIS Agent 抽象框架 — BaseAgent + AgentResult + Tool + AgentDependencies

核心概念:
    BaseAgent      — 所有 Agent 的抽象基类（ABC）
    AgentResult    — 统一的工具执行返回值
    Tool           — 工具描述符（name/schema/handler）
    AgentDependencies — 依赖注入容器（渐进式注入）

设计原则:
    1. Agent 不关心依赖来源（通过 DI 容器注入）
    2. 容错设计：execute() 失败返回 AgentResult(success=False)
    3. 权限模型：is_readonly 属性控制写操作权限
    4. 可观测性：metadata 记录执行时间/缓存命中等
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel

from praxis.core.interfaces import (
    DataProvider,
    Ledger,
    StateBuilder,
    ConstraintChecker,
    PerformanceCalculator,
    BenchmarkProvider,
    StateStore,
)
from praxis.core.guardrail import Guardrail
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════
# AgentResult — 统一返回结构
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AgentResult:
    """Agent 工具执行的统一返回结构

    Attributes:
        success: 执行是否成功
        data: 返回数据（任意类型）
        error: 错误信息（仅 success=False 时有值）
        metadata: 元数据（tool_name, agent_name, execution_time_ms, etc.）
    """
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为标准 MCP 工具返回格式"""
        result: dict = {"success": self.success}
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        if self.metadata:
            result["_metadata"] = self.metadata
        return result


# ═══════════════════════════════════════════════════════════════════
# Tool — 工具描述符
# ═══════════════════════════════════════════════════════════════════


@dataclass
class Tool:
    """MCP 工具描述符

    Attributes:
        name: 工具名称（如 "sentinel", "get_market_data"）
        description: 工具描述（用于 LLM 工具选择）
        input_schema: 输入参数的 Pydantic model（用于 schema 校验）
        handler: 工具处理函数（async callable）
        agent_name: 所属 Agent 名称
        tier: 工具层级（core/advanced/admin）
        is_readonly: 是否只读（True=只读，False=可写）
    """
    name: str
    description: str
    input_schema: type[BaseModel]
    handler: Callable[..., Any]
    agent_name: str
    tier: str = "core"
    is_readonly: bool = True

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Tool):
            return self.name == other.name
        return False


# ═══════════════════════════════════════════════════════════════════
# AgentDependencies — 依赖注入容器
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AgentDependencies:
    """Agent 共享依赖注入容器

    渐进式注入策略:
        Phase 1: data_provider (必需)
        Phase 2: guardrail (可选)
        Phase 3: ledger, state_store (可选)
        Phase 4: memory_store (可选)

    Agent 不关心依赖来源，只需通过 self.deps.xxx 访问。
    """
    data_provider: DataProvider
    workspace: str = "."
    ledger: Ledger | None = None
    state_builder: StateBuilder | None = None
    constraint_checker: ConstraintChecker | None = None
    performance_calculator: PerformanceCalculator | None = None
    benchmark_provider: BenchmarkProvider | None = None
    state_store: StateStore | None = None
    guardrail: Guardrail | None = None
    memory_store: Any = None  # Phase 4
    # Engine instances (Phase 2)
    sentinel_engine: Any = None
    reconciliation_engine: Any = None
    decision_recorder: Any = None
    config_loader: Any = None
    review_filler: Any = None
    nav_tracker: Any = None


# ═══════════════════════════════════════════════════════════════════
# BaseAgent — 抽象基类
# ═══════════════════════════════════════════════════════════════════


class BaseAgent(ABC):
    """Agent 抽象基类

    所有具体 Agent 必须继承此类并实现:
        - agent_name: str (类属性)
        - description: str (类属性)
        - is_readonly: bool (类属性)
        - _register_tools() -> list[Tool] (抽象方法)

    Usage:
        class MarketAgent(BaseAgent):
            agent_name = "market"
            description = "市场数据获取与情绪分析"
            is_readonly = True

            def _register_tools(self) -> list[Tool]:
                return [Tool(...), ...]
    """

    # ── 子类必须定义 ──
    agent_name: str = ""
    description: str = ""
    is_readonly: bool = True
    tools: list[Tool] = []

    def __init__(self, deps: AgentDependencies):
        """初始化 Agent

        Args:
            deps: 依赖注入容器
        """
        self.deps = deps
        self.tools = self._register_tools()
        self._tool_map: dict[str, Tool] = {
            tool.name: tool for tool in self.tools
        }
        logger.info(
            "agent_initialized",
            agent_name=self.agent_name,
            tool_count=len(self.tools),
            is_readonly=self.is_readonly,
        )

    # ── 抽象方法 ───────────────────────────────────────────────

    @abstractmethod
    def _register_tools(self) -> list[Tool]:
        """注册该 Agent 管理的所有工具

        Returns:
            工具描述符列表
        """
        ...

    # ── 核心执行方法 ───────────────────────────────────────────

    async def execute(self, tool_name: str, params: dict) -> AgentResult:
        """执行指定工具

        Args:
            tool_name: 工具名称
            params: 工具参数（字典格式）

        Returns:
            AgentResult: 统一返回结构
        """
        start_time = time.time()

        # 1. 查找工具
        tool = self._tool_map.get(tool_name)
        if tool is None:
            return AgentResult(
                success=False,
                error=f"Agent '{self.agent_name}' 没有注册工具 '{tool_name}'。"
                       f"可用工具: {list(self._tool_map.keys())}",
                metadata={"agent_name": self.agent_name, "tool_name": tool_name},
            )

        # 2. Guardrail 前置门控（写操作）
        if not tool.is_readonly and self.deps.guardrail is not None:
            guardrail_result = await self.deps.guardrail.verify_action(
                self.agent_name, tool_name, params
            )
            if not guardrail_result.allowed:
                logger.warning(
                    "guardrail_blocked",
                    agent_name=self.agent_name,
                    tool_name=tool_name,
                    reason=guardrail_result.reason,
                )
                return AgentResult(
                    success=False,
                    error=f"Guardrail 拦截: {guardrail_result.reason}",
                    metadata={
                        "agent_name": self.agent_name,
                        "tool_name": tool_name,
                        "guardrail_state": guardrail_result.current_state.value,
                    },
                )

        # 3. Schema 校验（兼容模式：失败时记录 Warning 但放行）
        try:
            validated_params = tool.input_schema(**params)
            params_dict = validated_params.model_dump()
        except Exception as e:
            logger.warning(
                "schema_validation_warning",
                agent_name=self.agent_name,
                tool_name=tool_name,
                error=str(e),
            )
            params_dict = params

        # 3.5 注入 _deps（引擎实例传递给工具handler）
        # 执行前刷新内存缓存（外部可能修改了 JSONL 文件）
        for _obj, _name in [
            (self.deps.ledger, "ledger"),
            (self.deps.decision_recorder, "decision_recorder"),
        ]:
            if _obj is not None and hasattr(_obj, "reload"):
                _obj.reload()

        params_dict["_deps"] = {
            "data_provider": self.deps.data_provider,
            "workspace": self.deps.workspace,
            "ledger": self.deps.ledger,
            "constraint_checker": self.deps.constraint_checker,
            "performance_calculator": self.deps.performance_calculator,
            "guardrail": self.deps.guardrail,
            "sentinel_engine": self.deps.sentinel_engine,
            "reconciliation_engine": self.deps.reconciliation_engine,
            "decision_recorder": self.deps.decision_recorder,
            "config_loader": self.deps.config_loader,
            "review_filler": self.deps.review_filler,
            "nav_tracker": self.deps.nav_tracker,
            "memory_store": self.deps.memory_store,
        }

        # 4. 执行工具
        try:
            # 移除 _deps（如果 handler 不接受它）
            import inspect
            sig = inspect.signature(tool.handler)
            if "_deps" not in sig.parameters:
                params_dict.pop("_deps", None)
            # 判断 handler 是 async 还是 sync，分别调用
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**params_dict)
            else:
                result = tool.handler(**params_dict)
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                "tool_execution_failed",
                agent_name=self.agent_name,
                tool_name=tool_name,
                error=str(e),
                elapsed_ms=round(elapsed_ms, 2),
            )
            return AgentResult(
                success=False,
                error=f"工具执行异常: {str(e)}",
                metadata={
                    "agent_name": self.agent_name,
                    "tool_name": tool_name,
                    "execution_time_ms": round(elapsed_ms, 2),
                },
            )

        elapsed_ms = (time.time() - start_time) * 1000

        # 5. 构建返回结果
        if isinstance(result, dict):
            success = result.get("success", True)
            data = result.get("data", result)
            error = result.get("error")
            metadata = result.get("_metadata", {})
        elif isinstance(result, AgentResult):
            success = result.success
            data = result.data
            error = result.error
            metadata = result.metadata
        else:
            success = True
            data = result
            error = None
            metadata = {}

        metadata.update({
            "agent_name": self.agent_name,
            "tool_name": tool_name,
            "execution_time_ms": round(elapsed_ms, 2),
        })

        return AgentResult(
            success=success,
            data=data,
            error=error,
            metadata=metadata,
        )

    # ── 查询方法 ───────────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """列出所有工具（名称+描述+只读标记）"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "is_readonly": tool.is_readonly,
                "tier": tool.tier,
            }
            for tool in self.tools
        ]

    def has_tool(self, tool_name: str) -> bool:
        """检查是否注册了指定工具"""
        return tool_name in self._tool_map

    def get_tool(self, tool_name: str) -> Tool | None:
        """获取工具描述符"""
        return self._tool_map.get(tool_name)
