"""AdminAgent — 管理与运营养护"""
from __future__ import annotations
from praxis.agents.base import BaseAgent, Tool
from praxis.tools import _schemas

class AdminAgent(BaseAgent):
    agent_name = "admin"
    description = "组合管理：净值记录、对账、工作区发现、绩效计算"
    is_readonly = True

    def _register_tools(self) -> list[Tool]:
        from praxis.tools.portfolio import portfolio
        from praxis.tools.nav_module import nav
        from praxis.tools.engine import reconcile
        from praxis.tools.workspace import discover_workspace
        from praxis.tools.performance_module import performance
        from praxis.tools.memory_search import memory_search, MemorySearchInput
        from praxis.tools.orchestrator import orchestrator, WorkflowInput

        return [
            Tool(name="portfolio", description="组合管理(读)", input_schema=_schemas.PortfolioInput,
                 handler=portfolio, agent_name=self.agent_name, tier="core"),
            Tool(name="nav", description="净值管理", input_schema=_schemas.NavInput,
                 handler=nav, agent_name=self.agent_name, tier="core"),
            Tool(name="reconcile", description="对账计算", input_schema=_schemas.ReconcileInput,
                 handler=reconcile, agent_name=self.agent_name, tier="core"),
            Tool(name="discover_workspace", description="工作区发现", input_schema=_schemas.WorkspaceInput,
                 handler=discover_workspace, agent_name=self.agent_name, tier="core"),
            Tool(name="performance", description="绩效计算", input_schema=_schemas.PerformanceInput,
                 handler=performance, agent_name=self.agent_name, tier="core"),
            Tool(name="memory_search", description="语义检索历史记忆", input_schema=MemorySearchInput,
                 handler=memory_search, agent_name=self.agent_name, tier="core"),
            Tool(name="orchestrator", description="工作流编排：运行预设工作流（决策链/哨兵扫描/对账循环）",
                 input_schema=WorkflowInput,
                 handler=orchestrator, agent_name=self.agent_name, tier="advanced"),
        ]
