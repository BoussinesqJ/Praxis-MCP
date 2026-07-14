"""RiskAgent — 风险评估与约束检查"""
from __future__ import annotations
from praxis.agents.base import BaseAgent, Tool
from praxis.tools import _schemas

class RiskAgent(BaseAgent):
    agent_name = "risk"
    description = "风险评估：哨兵雷达、估值分位、约束检查、摩擦成本"
    is_readonly = True

    def _register_tools(self) -> list[Tool]:
        from praxis.tools.sentinel_module import sentinel
        from praxis.tools.valuation_module import valuation
        from praxis.tools.engine import check_constraints
        from praxis.tools.friction import trading_friction

        return [
            Tool(name="sentinel", description="哨兵雷达扫描", input_schema=_schemas.SentinelInput,
                 handler=sentinel, agent_name=self.agent_name, tier="core"),
            Tool(name="valuation", description="指数估值分位", input_schema=_schemas.ValuationInput,
                 handler=valuation, agent_name=self.agent_name, tier="core"),
            Tool(name="check_constraints", description="交易约束检查", input_schema=_schemas.CheckConstraintsInput,
                 handler=check_constraints, agent_name=self.agent_name, tier="core"),
            Tool(name="trading_friction", description="交易摩擦成本", input_schema=_schemas.TradingFrictionInput,
                 handler=trading_friction, agent_name=self.agent_name, tier="core"),
        ]
