"""ReviewAgent — 决策复盘与 Agent 追踪"""
from __future__ import annotations
from praxis.agents.base import BaseAgent, Tool
from praxis.tools import _schemas

class ReviewAgent(BaseAgent):
    agent_name = "review"
    description = "复盘追踪：决策复盘、级联复盘、Agent 行为追踪"
    is_readonly = True

    def _register_tools(self) -> list[Tool]:
        from praxis.tools.review_module import review, cascade_review, generate_market_weekly_review
        from praxis.tools.agent_tracker import agent_tracking
        from praxis.tools.full_review_module import full_review

        return [
            Tool(name="review", description="决策复盘", input_schema=_schemas.ReviewInput,
                 handler=review, agent_name=self.agent_name, tier="core"),
            Tool(name="cascade_review", description="级联复盘", input_schema=_schemas.CascadeReviewInput,
                 handler=cascade_review, agent_name=self.agent_name, tier="core"),
            Tool(name="generate_market_weekly_review", description="市场周报复盘生成",
                 input_schema=_schemas.MarketWeeklyReviewInput,
                 handler=generate_market_weekly_review, agent_name=self.agent_name, tier="core"),
            Tool(name="agent_tracking", description="Agent决策追踪", input_schema=_schemas.AgentTrackingInput,
                 handler=agent_tracking, agent_name=self.agent_name, tier="core"),
            Tool(name="full_review", description="全量复盘聚合",
                 input_schema=_schemas.FullReviewInput,
                 handler=full_review, agent_name=self.agent_name, tier="core"),
        ]
