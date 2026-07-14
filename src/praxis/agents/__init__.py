"""PRAXIS Agent 层 — Agent 抽象框架 + 5 个具体 Agent 实现"""

from praxis.agents.base import BaseAgent, AgentResult, Tool, AgentDependencies
from praxis.agents.tool_registry import ToolRegistry
from praxis.agents.market import MarketAgent
from praxis.agents.risk import RiskAgent
from praxis.agents.decision import DecisionAgent
from praxis.agents.review import ReviewAgent
from praxis.agents.admin import AdminAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "Tool",
    "AgentDependencies",
    "ToolRegistry",
    "MarketAgent",
    "RiskAgent",
    "DecisionAgent",
    "ReviewAgent",
    "AdminAgent",
]
