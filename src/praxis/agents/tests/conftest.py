"""Agent 层测试专用 fixtures 和 FakeGuardrail。

提供:
    - FakeGuardrail: 可控制状态的测试用 Guardrail 替代品
    - 8 个 fixture: agent_deps, active_guardrail, locked_guardrail,
      market_agent, risk_agent, decision_agent, review_agent, admin_agent
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from praxis.agents.base import AgentDependencies
from praxis.agents.market import MarketAgent
from praxis.agents.risk import RiskAgent
from praxis.agents.decision import DecisionAgent
from praxis.agents.review import ReviewAgent
from praxis.agents.admin import AdminAgent
from praxis.core.guardrail import GuardrailState


# ═══════════════════════════════════════════════════════════════════
# GuardrailResult 仿真
# ═══════════════════════════════════════════════════════════════════


@dataclass
class _FakeGuardrailResult:
    """模拟 GuardrailResult 返回结构。

    current_state 使用 GuardrailState 枚举，确保 .value 属性可用。
    BaseAgent.execute() 通过 guardrail_result.current_state.value 访问状态。
    """

    allowed: bool
    reason: str = ""
    current_state: GuardrailState = GuardrailState.ACTIVE
    required_state: GuardrailState | None = None


# ═══════════════════════════════════════════════════════════════════
# FakeGuardrail
# ═══════════════════════════════════════════════════════════════════


class FakeGuardrail:
    """测试用 Guardrail 替代品，不依赖 SQLite。

    行为规则（与真实 Guardrail 一致）:
        - ACTIVE:    所有操作放行
        - LOCKED:    写工具拦截，只读工具放行
        - AUDITING:  写工具拦截，只读工具放行

    Attributes:
        state: 当前状态字符串（ACTIVE/LOCKED/AUDITING）
    """

    # 写操作工具清单（与真实 Guardrail.WRITE_TOOLS 一致）
    WRITE_TOOLS: set[str] = {
        "trading",
        "decision",
        "portfolio",
        "nav",
        "investor",
    }

    def __init__(self, state: str = "ACTIVE") -> None:
        """初始化 FakeGuardrail。

        Args:
            state: 初始状态，可选 ACTIVE/LOCKED/AUDITING
        """
        self._state = state

    @property
    def state(self) -> str:
        """返回当前状态字符串。"""
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        """设置当前状态。"""
        self._state = value

    async def verify_action(
        self, agent_name: str, tool_name: str, params: dict | None = None
    ) -> _FakeGuardrailResult:
        """门控检查 — 与真实 Guardrail.verify_action 行为一致。

        Args:
            agent_name: Agent 名称
            tool_name: 工具名称
            params: 工具参数（可选）

        Returns:
            _FakeGuardrailResult: 验证结果
        """
        # 读操作无需检查
        if tool_name not in self.WRITE_TOOLS:
            return _FakeGuardrailResult(
                allowed=True,
                current_state=self._to_enum(),
            )

        # ACTIVE 状态允许所有操作
        if self._state == "ACTIVE":
            return _FakeGuardrailResult(
                allowed=True,
                current_state=self._to_enum(),
            )

        # AUDITING 状态禁止写操作
        if self._state == "AUDITING":
            return _FakeGuardrailResult(
                allowed=False,
                reason=f"复盘审计中，禁止写操作。Agent={agent_name}, Tool={tool_name}。",
                current_state=self._to_enum(),
                required_state=GuardrailState.ACTIVE,
            )

        # LOCKED 状态禁止所有写操作
        if self._state == "LOCKED":
            return _FakeGuardrailResult(
                allowed=False,
                reason=f"系统已锁定，禁止写操作。Agent={agent_name}, Tool={tool_name}。",
                current_state=self._to_enum(),
                required_state=GuardrailState.ACTIVE,
            )

        return _FakeGuardrailResult(
            allowed=False,
            reason=f"未知状态: {self._state}",
            current_state=self._to_enum(),
        )

    def _to_enum(self) -> GuardrailState:
        """将内部字符串状态映射为 GuardrailState 枚举。"""
        return GuardrailState(self._state)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def agent_deps() -> AgentDependencies:
    """创建最小 AgentDependencies，含 Mock DataProvider。

    作用域: function
    Returns:
        AgentDependencies: data_provider 已设为 AsyncMock
    """
    mock_data_provider = MagicMock()
    mock_data_provider.get_realtime_quote = AsyncMock(return_value={})
    mock_data_provider.get_history_kline = AsyncMock(return_value=[])
    mock_data_provider.get_fund_nav = AsyncMock(return_value={})
    return AgentDependencies(data_provider=mock_data_provider, workspace="test_workspace")


@pytest.fixture
def active_guardrail() -> FakeGuardrail:
    """ACTIVE 状态 Guardrail — 所有操作放行。

    作用域: function
    Returns:
        FakeGuardrail: state="ACTIVE"
    """
    return FakeGuardrail(state="ACTIVE")


@pytest.fixture
def locked_guardrail() -> FakeGuardrail:
    """LOCKED 状态 Guardrail — 写操作全部拦截。

    作用域: function
    Returns:
        FakeGuardrail: state="LOCKED"
    """
    return FakeGuardrail(state="LOCKED")


@pytest.fixture
def auditing_guardrail() -> FakeGuardrail:
    """AUDITING 状态 Guardrail — 写操作被审计拦截。

    作用域: function
    Returns:
        FakeGuardrail: state="AUDITING"
    """
    return FakeGuardrail(state="AUDITING")


@pytest.fixture
def market_agent(agent_deps: AgentDependencies) -> MarketAgent:
    """已初始化的 MarketAgent（5 工具，只读）。

    作用域: function
    Returns:
        MarketAgent: deps 已注入
    """
    return MarketAgent(deps=agent_deps)


@pytest.fixture
def risk_agent(agent_deps: AgentDependencies) -> RiskAgent:
    """已初始化的 RiskAgent（4 工具，只读）。

    作用域: function
    Returns:
        RiskAgent: deps 已注入
    """
    return RiskAgent(deps=agent_deps)


@pytest.fixture
def decision_agent(agent_deps: AgentDependencies) -> DecisionAgent:
    """已初始化的 DecisionAgent（2 写工具，非只读）。

    作用域: function
    Returns:
        DecisionAgent: deps 已注入
    """
    return DecisionAgent(deps=agent_deps)


@pytest.fixture
def review_agent(agent_deps: AgentDependencies) -> ReviewAgent:
    """已初始化的 ReviewAgent（5 工具，只读）。

    作用域: function
    Returns:
        ReviewAgent: deps 已注入
    """
    return ReviewAgent(deps=agent_deps)


@pytest.fixture
def admin_agent(agent_deps: AgentDependencies) -> AdminAgent:
    """已初始化的 AdminAgent（7 工具，只读）。

    作用域: function
    Returns:
        AdminAgent: deps 已注入
    """
    return AdminAgent(deps=agent_deps)
