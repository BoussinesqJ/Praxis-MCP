"""DecisionAgent — 决策创建与交易执行"""
from __future__ import annotations
from praxis.agents.base import BaseAgent, Tool
from praxis.tools import _schemas

class DecisionAgent(BaseAgent):
    agent_name = "decision"
    description = "决策管理：创建决策、执行交易、修改组合配置"
    is_readonly = False

    def _register_tools(self) -> list[Tool]:
        from praxis.tools.ledger import trading
        from praxis.tools.decision_module import decision

        return [
            Tool(name="trading", description="交易管理", input_schema=_schemas.TradingInput,
                 handler=trading, agent_name=self.agent_name, tier="core", is_readonly=False),
            Tool(name="decision", description="决策创建", input_schema=_schemas.DecisionCreateInput,
                 handler=decision, agent_name=self.agent_name, tier="core", is_readonly=False),
        ]
