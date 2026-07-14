"""PRAXIS Tools — 工具 Schema 定义

所有 28 个 MCP 工具的 Pydantic input/output schema。
用于 ToolRegistry 自动发现和 LLM 工具选择。

每个 Schema 遵循: 明确的字段类型 + Field description + 合理默认值
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# 通用输出 Schema
# ═══════════════════════════════════════════════════════════════════


class ToolOutput(BaseModel):
    """标准工具输出"""
    success: bool = Field(default=True, description="执行是否成功")
    data: dict | list | None = Field(default=None, description="返回数据")
    error: str | None = Field(default=None, description="错误信息")


class ErrorOutput(BaseModel):
    """错误输出"""
    success: bool = Field(default=False)
    error: str = Field(..., description="错误描述")
    error_code: str = Field(default="UNKNOWN", description="错误码")


# ═══════════════════════════════════════════════════════════════════
# Market Agent 工具 Schema
# ═══════════════════════════════════════════════════════════════════


class GetMarketDataInput(BaseModel):
    """获取实时行情"""
    tickers: list[str] = Field(
        ..., min_length=1, max_length=20,
        description="标的代码列表，如 ['600995', '510310']",
    )


class MarketDataExtInput(BaseModel):
    """扩展行情数据"""
    action: str = Field(
        ..., description="操作类型: fund_flow/dragon_tiger/research",
    )
    ticker: str = Field(default="", description="标的代码")
    days: int = Field(default=5, ge=1, le=365, description="历史天数")
    limit: int = Field(default=20, ge=1, le=100, description="返回数量")
    rating: str = Field(default="", description="评级过滤")


class BenchmarkInput(BaseModel):
    """基准指数"""
    action: str = Field(..., description="操作: data/list")
    index_code: str | None = Field(default=None, description="指数代码")
    days: int = Field(default=60, ge=1, le=365, description="历史天数")


class NewsInput(BaseModel):
    """新闻情报"""
    action: str = Field(default="finance", description="操作: finance/trends/polymarket/list_sources")
    sources: list[str] | None = Field(default=None, description="新闻源列表")
    count: int = Field(default=10, ge=1, le=100, description="新闻数量")
    limit: int = Field(default=10, ge=1, le=50, description="市场数量")


class SentimentInput(BaseModel):
    """情感分析"""
    action: str = Field(..., description="操作: analyze/batch")
    text: str | None = Field(default=None, description="单条文本")
    texts: list[str] | None = Field(default=None, description="文本列表")


# ═══════════════════════════════════════════════════════════════════
# Risk Agent 工具 Schema
# ═══════════════════════════════════════════════════════════════════


class SentinelInput(BaseModel):
    """哨兵雷达"""
    action: str = Field(..., description="操作: scan/rule23_status/history/scan_external")
    days: int = Field(default=10, ge=1, le=365, description="历史天数")
    klines_json: str = Field(default="", description="KlinesPayload JSON")


class ValuationInput(BaseModel):
    """估值分位"""
    action: str = Field(..., description="操作: percentile/all")
    index_code: str = Field(default="000300", description="指数代码: 000300/000016/000905/000852")


class CheckConstraintsInput(BaseModel):
    """约束检查"""
    investor: str = Field(..., description="投资者 ID")
    portfolio: str = Field(..., description="组合 ID")
    action: str = Field(..., description="交易方向: buy/sell/hold")
    ticker: str = Field(..., description="标的代码")
    amount: float = Field(default=0.0, ge=0, description="金额")


class TradingFrictionInput(BaseModel):
    """摩擦成本"""
    action: str = Field(..., description="操作: fee/slippage/trading_time/confirm_date")
    ticker: str | None = None
    asset_type: str | None = None
    trade_action: str | None = None
    quantity: float | None = None
    price: float | None = None
    volume: float | None = None
    volatility: float | None = None
    timestamp: str | None = None
    trade_date: str | None = None


# ═══════════════════════════════════════════════════════════════════
# Decision Agent 工具 Schema
# ═══════════════════════════════════════════════════════════════════


class TradingInput(BaseModel):
    """交易管理"""
    action: str = Field(..., description="操作: ledger/add/reverse/approve/reject/decision")
    ticker: str = Field(default="", description="标的代码")
    trade_action: str = Field(default="", description="交易方向")
    quantity: float = Field(default=0.0, description="数量")
    price: float = Field(default=0.0, description="价格")
    fee: float = Field(default=0.0, ge=0, description="手续费")
    asset_type: str = Field(default="", description="资产类型")
    tx_id: str = Field(default="", description="交易ID")
    reason: str = Field(default="", description="原因")
    decision_action: str = Field(default="", description="决策动作")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reasoning: str = Field(default="", description="决策理由")
    limit: int = Field(default=100, ge=1, le=1000, description="返回条数")
    status: str = Field(default="", description="状态过滤")


class DecisionCreateInput(BaseModel):
    """创建决策"""
    ticker: str = Field(..., description="标的代码")
    action: str = Field(..., description="决策动作: buy/sell/hold/watch")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    reasoning: str = Field(..., description="决策理由")
    investor: str = Field(default="demo", description="投资者 ID")
    portfolio: str = Field(default="core", description="组合 ID")


# ═══════════════════════════════════════════════════════════════════
# Review Agent 工具 Schema
# ═══════════════════════════════════════════════════════════════════


class ReviewInput(BaseModel):
    """决策复盘"""
    action: str = Field(..., description="操作: fill/summary/calibration")
    team: str | None = Field(default=None, description="团队名称")


class CascadeReviewInput(BaseModel):
    """级联复盘"""
    mode: str = Field(..., description="复盘模式: monthly/quarterly/annual")
    investor: str = Field(default="demo", description="投资者 ID")
    portfolio: str = Field(default="core", description="组合 ID")
    period: str = Field(default="", description="时间范围")
    external_data_json: str = Field(default="", description="ExternalDataPayload JSON")


class MarketWeeklyReviewInput(BaseModel):
    """市场环境周度复盘"""
    week_ending: str = Field(..., description="周结束日期 YYYY-MM-DD")
    index_code: str = Field(default="000300", description="大盘基准指数")
    transport: str | None = Field(default=None, description="Transport 注入（内部参数）")
    market_data_json: str = Field(default="", description="MarketDataPayload JSON")


class FullReviewInput(BaseModel):
    """全量复盘聚合"""
    investor: str = Field(default="", description="投资者 ID")
    portfolio: str = Field(default="", description="组合 ID")
    week_ending: str = Field(default="", description="周结束日期 YYYY-MM-DD，默认最新周五")
    index_code: str = Field(default="000300", description="基准指数代码")
    external_data_json: str = Field(default="", description="ExternalDataPayload JSON")


class AgentTrackingInput(BaseModel):
    """Agent 追踪"""
    action: str = Field(..., description="操作: record/consensus/rank")
    agent_id: str | None = Field(default=None, description="Agent 标识")
    ticker: str | None = Field(default=None, description="标的代码")
    decision_action: str | None = Field(default=None, description="建议动作")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="置信度")
    reasoning: str | None = Field(default=None, description="决策理由")
    min_agents: int = Field(default=2, ge=1, le=10, description="最低共识Agent数")


# ═══════════════════════════════════════════════════════════════════
# Admin Agent 工具 Schema
# ═══════════════════════════════════════════════════════════════════


class PortfolioInput(BaseModel):
    """组合管理（读）"""
    action: str = Field(..., description="操作: summary/detail/state/config/summary_external/state_external")
    investor: str = Field(..., description="投资者 ID")
    portfolio: str = Field(..., description="组合 ID")
    ticker: str = Field(default="", description="标的代码")
    portfolio_json: str = Field(default="", description="PortfolioPayload JSON")


class NavInput(BaseModel):
    """净值管理"""
    action: str = Field(..., description="操作: record/snapshot/history")
    investor: str | None = None
    portfolio: str | None = None
    nav: float | None = None
    total_assets: float | None = None
    positions_value: float | None = None
    cash: float | None = None
    benchmark_nav: float | None = None
    benchmark_code: str | None = None
    days: int = Field(default=30, ge=1, le=365, description="历史天数")


class ReconcileInput(BaseModel):
    """对账"""
    action: str = Field(default="dry_run", description="dry_run/external")
    investor: str = Field(..., description="投资者 ID")
    portfolio: str = Field(..., description="组合 ID")
    nav: float | None = Field(default=None, description="净值")
    quotes_json: str = Field(default="", description="QuotesPayload JSON")


class PerformanceInput(BaseModel):
    """绩效"""
    investor: str = Field(..., description="投资者 ID")
    portfolio: str = Field(..., description="组合 ID")
    exclude_reversed: bool = Field(default=False, description="排除已冲销")
    exclude_tags: list[str] | None = None
    include_tags: list[str] | None = None
    ticker: str | None = None


# ═══════════════════════════════════════════════════════════════════
# Advanced 工具 Schema
# ═══════════════════════════════════════════════════════════════════


class StrategyInput(BaseModel):
    """策略管理"""
    action: str = Field(..., description="操作: get/list/compare")
    strategy_name: str = Field(default="", description="策略名称")
    strategy_a: str = Field(default="", description="策略A")
    strategy_b: str = Field(default="", description="策略B")


class EvolutionInput(BaseModel):
    """进化管理"""
    action: str = Field(..., description="操作: evaluate/auto/memory/adaptive")
    investor: str = Field(default="", description="投资者 ID")
    portfolio: str = Field(default="", description="组合 ID")
    strategy_name: str = Field(default="", description="策略名称")


class BacktestInput(BaseModel):
    """回测"""
    strategy_name: str = Field(..., description="策略名称")
    investor: str = Field(..., description="投资者 ID")
    portfolio: str = Field(..., description="组合 ID")
    days: int = Field(default=90, ge=1, le=3650, description="回测天数")


class OrchestratorInput(BaseModel):
    """编排器"""
    action: str = Field(..., description="操作: plan/member_prompt/compile_prompt")
    team: str | None = None
    member_id: str | None = None
    ticker: str | None = None
    model_hint: str = Field(default="deep", description="模型级别: deep/quick")


# ═══════════════════════════════════════════════════════════════════
# 工作区发现
# ═══════════════════════════════════════════════════════════════════


class WorkspaceInput(BaseModel):
    """工作区发现 — 零参数"""
    pass
