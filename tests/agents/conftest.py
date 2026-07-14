"""PRAXIS Agent 层测试共享 Fixtures

提供:
    - FakeDataProvider / FakeGuardrail — 可控的 mock 依赖
    - 8 个 pytest fixtures — 覆盖所有 5 个 Agent 的依赖注入
"""

from __future__ import annotations

import pytest

from praxis.agents.base import AgentDependencies
from praxis.core.guardrail import GuardrailState, GuardrailResult


# ═══════════════════════════════════════════════════════════════════
# Fake Implementations
# ═══════════════════════════════════════════════════════════════════


class FakeDataProvider:
    """Fake DataProvider — 返回可预测的 mock 行情数据。

    实现 DataProvider 的全部 3 个抽象方法，
    可用于 Agent 层测试而无需真实数据源连接。
    """

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """返回固定 mock 行情"""
        return {
            t: {
                "price": 100.0,
                "change": 1.5,
                "change_pct": 1.52,
                "volume": 1_000_000,
                "high": 102.0,
                "low": 98.5,
            }
            for t in tickers
        }

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """返回固定 mock K线"""
        return [
            {
                "date": f"2024-01-{i:02d}",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 50000,
            }
            for i in range(1, count + 1)
        ]

    async def get_fund_nav(self, ticker: str) -> dict:
        """返回固定 mock 基金净值"""
        return {"nav": 1.50, "nav_date": "2024-01-15", "acc_nav": 2.00}


class FakeGuardrail:
    """Fake Guardrail — 可控状态的假纪律锁。

    用于测试 Agent 的 guardrail 门控逻辑：
        - ACTIVE:  放行所有操作
        - LOCKED:  拦截所有写操作
        - AUDITING: 拦截所有写操作
    """

    def __init__(self, state: GuardrailState = GuardrailState.ACTIVE):
        self.current_state: GuardrailState = state

    @property
    def state(self) -> str:
        """返回状态字符串值（兼容测试中的字符串比较）"""
        return self.current_state.value

    async def verify_action(
        self, agent_name: str, tool_name: str, params: dict | None = None
    ) -> GuardrailResult:
        """Mock 门控验证 — 只有 ACTIVE 放行"""
        if self.current_state == GuardrailState.ACTIVE:
            return GuardrailResult(allowed=True, current_state=self.current_state)

        if self.current_state == GuardrailState.LOCKED:
            return GuardrailResult(
                allowed=False,
                reason=f"系统已锁定，禁止写操作。Agent={agent_name}, Tool={tool_name}。"
                       f"如需解锁请使用 emergency_unlock。",
                current_state=self.current_state,
                required_state=GuardrailState.ACTIVE,
            )

        if self.current_state == GuardrailState.AUDITING:
            return GuardrailResult(
                allowed=False,
                reason=f"复盘审计中，禁止写操作。Agent={agent_name}, Tool={tool_name}。"
                       f"请完成复盘后切换回 ACTIVE 状态。",
                current_state=self.current_state,
                required_state=GuardrailState.ACTIVE,
            )

        return GuardrailResult(
            allowed=False,
            reason=f"未知状态: {self.current_state.value}",
            current_state=self.current_state,
        )


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def agent_deps() -> AgentDependencies:
    """全 mock 依赖容器 — 所有字段为 Fake 实现或 None。

    各 Agent 测试可按需替换特定字段。
    """
    return AgentDependencies(
        data_provider=FakeDataProvider(),
        workspace=".",
        guardrail=None,
        ledger=None,
        state_builder=None,
        constraint_checker=None,
        performance_calculator=None,
        benchmark_provider=None,
        state_store=None,
        memory_store=None,
        sentinel_engine=None,
        reconciliation_engine=None,
        decision_recorder=None,
        config_loader=None,
        review_filler=None,
        nav_tracker=None,
    )


@pytest.fixture
def active_guardrail() -> FakeGuardrail:
    """ACTIVE 状态的 Guardrail — 放行所有操作"""
    return FakeGuardrail(state=GuardrailState.ACTIVE)


@pytest.fixture
def locked_guardrail() -> FakeGuardrail:
    """LOCKED 状态的 Guardrail — 拦截写操作"""
    return FakeGuardrail(state=GuardrailState.LOCKED)


@pytest.fixture
def market_agent(agent_deps: AgentDependencies):
    """MarketAgent — 注入 agent_deps"""
    from praxis.agents.market import MarketAgent
    return MarketAgent(agent_deps)


@pytest.fixture
def risk_agent(agent_deps: AgentDependencies):
    """RiskAgent — 注入 agent_deps"""
    from praxis.agents.risk import RiskAgent
    return RiskAgent(agent_deps)


@pytest.fixture
def decision_agent(agent_deps: AgentDependencies, locked_guardrail: FakeGuardrail):
    """DecisionAgent — 注入 agent_deps + LOCKED guardrail。

    默认 LOCKED 状态，各测试可按需修改 guardrail 状态。
    """
    from praxis.agents.decision import DecisionAgent
    agent_deps.guardrail = locked_guardrail
    return DecisionAgent(agent_deps)


@pytest.fixture
def review_agent(agent_deps: AgentDependencies):
    """ReviewAgent — 注入 agent_deps"""
    from praxis.agents.review import ReviewAgent
    return ReviewAgent(agent_deps)


@pytest.fixture
def admin_agent(agent_deps: AgentDependencies):
    """AdminAgent — 注入 agent_deps"""
    from praxis.agents.admin import AdminAgent
    return AdminAgent(agent_deps)
