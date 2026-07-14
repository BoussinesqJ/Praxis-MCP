"""MarketAgent — 市场数据获取与情绪分析"""

from __future__ import annotations
from pydantic import BaseModel, Field
from praxis.agents.base import BaseAgent, Tool
from praxis.tools import _schemas


class MarketAgent(BaseAgent):
    agent_name = "market"
    description = "市场数据获取：实时行情、扩展数据、基准指数、新闻情报、情感分析"
    is_readonly = True

    def _register_tools(self) -> list[Tool]:
        from praxis.tools.market import get_market_data
        from praxis.tools.market_ext import market_data_ext
        from praxis.tools.benchmark import benchmark
        from praxis.tools.news import news
        from praxis.tools.sentiment import sentiment

        return [
            Tool(name="get_market_data", description="实时行情数据", input_schema=_schemas.GetMarketDataInput,
                 handler=get_market_data, agent_name=self.agent_name, tier="core"),
            Tool(name="market_data_ext", description="扩展行情：资金流向/龙虎榜/研报", input_schema=_schemas.MarketDataExtInput,
                 handler=market_data_ext, agent_name=self.agent_name, tier="core"),
            Tool(name="benchmark", description="基准指数数据", input_schema=_schemas.BenchmarkInput,
                 handler=benchmark, agent_name=self.agent_name, tier="core"),
            Tool(name="news", description="新闻情报", input_schema=_schemas.NewsInput,
                 handler=news, agent_name=self.agent_name, tier="core"),
            Tool(name="sentiment", description="金融文本情感分析", input_schema=_schemas.SentimentInput,
                 handler=sentiment, agent_name=self.agent_name, tier="core"),
        ]
