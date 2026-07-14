"""PRAXIS 统一数据模型 — Pydantic v2

合并自原 praxis/core/models/ 和 praxis/models/ 双目录。
单一真相源，消除 import 歧义。

每个模型都包含：
- 完整的字段定义和类型注解
- Field description 用于 MCP tool schema 自动生成
- 合理默认值
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class AssetType(str, enum.Enum):
    """资产类型"""
    STOCK = "stock"
    ETF = "etf"
    OFFSHORE_FUND = "offshore_fund"
    BOND = "bond"
    CASH = "cash"


class AssetCategory(str, enum.Enum):
    """资产类别（投研维度）"""
    LARGE_CAP = "large_cap"
    SMALL_CAP = "small_cap"
    GROWTH = "growth"
    VALUE = "value"
    DEFENSIVE = "defensive"
    CYCLICAL = "cyclical"
    BROAD_MARKET = "broad_market"
    SECTOR = "sector"
    BOND = "bond"


class TransactionType(str, enum.Enum):
    """交易类型"""
    BUY = "buy"
    SELL = "sell"
    SUBSCRIBE = "subscribe"    # 基金申购
    REDEEM = "redeem"          # 基金赎回
    DIVIDEND = "dividend"      # 分红
    REVERSE = "reverse"        # 冲销


class TransactionStatus(str, enum.Enum):
    """交易状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    REVERSED = "reversed"


class DecisionStatus(str, enum.Enum):
    """决策状态"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    REVIEWED = "reviewed"       # 已复盘
    EXPIRED = "expired"         # 超期未执行


class AuditEventType(str, enum.Enum):
    """审计事件类型"""
    TRADE = "trade"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    STATE_CHANGE = "state_change"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"
    GUARDRAIL = "guardrail"


# ═══════════════════════════════════════════════════════════════════
# 投资者模型
# ═══════════════════════════════════════════════════════════════════


class InvestorConstraints(BaseModel):
    """投资者约束条件"""
    max_single_position_pct: float = Field(
        default=30.0, ge=0, le=100,
        description="单标的最大仓位占比（%）"
    )
    max_sector_exposure_pct: float = Field(
        default=50.0, ge=0, le=100,
        description="单一板块最大暴露（%）"
    )
    min_cash_reserve_pct: float = Field(
        default=5.0, ge=0, le=100,
        description="最低现金保留比例（%）"
    )
    max_daily_trades: int = Field(
        default=5, ge=0,
        description="每日最大交易笔数"
    )


class ExecutionConfig(BaseModel):
    """执行配置"""
    default_fee_rate_pct: float = Field(
        default=0.03, ge=0, le=1,
        description="默认手续费率（%）"
    )
    slippage_bps: float = Field(
        default=5.0, ge=0, le=100,
        description="滑点估计（基点）"
    )
    enable_stop_loss: bool = Field(
        default=True,
        description="是否启用止损"
    )
    stop_loss_pct: float = Field(
        default=10.0, ge=0, le=50,
        description="止损线（%）"
    )


class InvestorProfile(BaseModel):
    """投资者画像"""
    investor_id: str = Field(..., description="投资者唯一标识")
    name: str = Field(..., description="投资者名称")
    capital_cny: float = Field(..., gt=0, description="初始资金（元）")
    risk_level: str = Field(
        default="C3", pattern=r"^C[1-5]$",
        description="风险等级 C1-C5"
    )
    style: str = Field(default="balanced", description="投资风格")
    max_drawdown_pct: float = Field(default=20.0, ge=0, le=100, description="最大回撤容忍度（%）")
    constraints: InvestorConstraints = Field(default_factory=InvestorConstraints)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════
# 组合模型
# ═══════════════════════════════════════════════════════════════════


class AssetEntry(BaseModel):
    """组合中的资产条目"""
    ticker: str = Field(..., description="标的代码")
    name: str = Field(default="", description="标的名称")
    asset_type: AssetType = Field(default=AssetType.STOCK, description="资产类型")
    category: AssetCategory = Field(default=AssetCategory.LARGE_CAP, description="资产类别")
    target_weight_pct: float = Field(default=0.0, ge=0, le=100, description="目标权重（%）")


class SentinelEntry(BaseModel):
    """哨兵 ETF 配置"""
    ticker: str = Field(..., description="哨兵 ETF 代码")
    name: str = Field(default="", description="哨兵 ETF 名称")
    layer: str = Field(default="macro", description="层级: macro/execution")
    role: str = Field(default="", description="角色说明")
    weight: float = Field(default=1.0, description="权重")


class Portfolio(BaseModel):
    """投资组合配置"""
    portfolio_id: str = Field(..., description="组合唯一标识")
    investor_id: str = Field(..., description="所属投资者")
    name: str = Field(default="", description="组合名称")
    strategy_type: str = Field(default="grid_value", description="策略类型")
    strategy_template: str = Field(default="grid_value", description="策略模板名称")
    description: str = Field(default="", description="组合描述")
    benchmark: str = Field(default="000300", description="基准指数代码")
    assets: list[AssetEntry] = Field(default_factory=list)
    sentinels: list[SentinelEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════
# 策略模型
# ═══════════════════════════════════════════════════════════════════


class RuleEntry(BaseModel):
    """交易规则条目"""
    rule_id: str = Field(..., description="规则 ID")
    name: str = Field(..., description="规则名称")
    description: str = Field(default="", description="规则描述")
    level: str = Field(default="soft_warning", description="级别: hard_block/soft_warning/advisory")
    enabled: bool = Field(default=True, description="是否启用")
    params: dict = Field(default_factory=dict, description="规则参数")


class AITeamConfig(BaseModel):
    """AI 分析团队配置"""
    team_name: str = Field(..., description="团队名称")
    members: list[str] = Field(default_factory=list, description="成员 ID 列表")
    model_hint: str = Field(default="deep", description="模型级别: deep/quick")
    enabled: bool = Field(default=True)


class StrategyTemplate(BaseModel):
    """策略模板"""
    strategy_name: str = Field(..., description="策略名称")
    version: str = Field(default="1.0.0", description="版本号")
    description: str = Field(default="", description="策略描述")
    rules: list[RuleEntry] = Field(default_factory=list, description="规则列表")
    ai_teams: list[AITeamConfig] = Field(default_factory=list, description="AI 团队配置")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════
# 交易与决策模型
# ═══════════════════════════════════════════════════════════════════


class Transaction(BaseModel):
    """交易记录（append-only）"""
    tx_id: str = Field(default="", description="交易 ID（自动生成）")
    investor_id: str = Field(default="", description="投资者 ID")
    portfolio_id: str = Field(default="", description="组合 ID")
    ticker: str = Field(..., description="标的代码")
    tx_type: TransactionType = Field(..., description="交易类型")
    quantity: float = Field(..., gt=0, description="数量")
    price: float = Field(..., gt=0, description="价格")
    fee: float = Field(default=0.0, ge=0, description="手续费")
    asset_type: AssetType = Field(default=AssetType.STOCK, description="资产类型")
    status: TransactionStatus = Field(default=TransactionStatus.PENDING, description="状态")
    idempotency_key: str = Field(default="", description="幂等键")
    tags: list[str] = Field(default_factory=list, description="标签")
    decision_id: str = Field(default="", description="关联决策 ID")
    reason: str = Field(default="", description="原因说明")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class TeamSignal(BaseModel):
    """团队分析信号"""
    team_name: str = Field(..., description="团队名称")
    member_id: str = Field(default="", description="成员 ID")
    action: str = Field(default="hold", description="建议动作: buy/sell/hold/watch")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reasoning: str = Field(default="", description="决策理由")
    price_target: float | None = Field(default=None, description="目标价")
    stop_price: float | None = Field(default=None, description="止损价")


class DecisionRecord(BaseModel):
    """决策记录"""
    model_config = {"populate_by_name": True}

    decision_id: str = Field(default="", description="决策 ID（自动生成）")
    investor_id: str = Field(default="", description="投资者 ID")
    portfolio_id: str = Field(default="", description="组合 ID")
    ticker: str = Field(..., description="标的代码")
    action: str = Field(..., description="决策动作: buy/sell/hold/watch")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reasoning: str = Field(default="", description="决策理由")
    status: DecisionStatus = Field(default=DecisionStatus.DRAFT, description="状态")
    team_signals: list[TeamSignal] = Field(default_factory=list, description="团队信号")
    tx_id: str = Field(default="", alias="execution_tx_id", description="关联交易 ID")
    review_result: str | None = Field(default=None, alias="review_result", description="复盘结果")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), alias="timestamp")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════
# 状态模型
# ═══════════════════════════════════════════════════════════════════


class PositionState(BaseModel):
    """单个持仓状态"""
    ticker: str = Field(..., description="标的代码")
    name: str = Field(default="", description="标的名称")
    asset_type: AssetType = Field(default=AssetType.STOCK)
    quantity: float = Field(default=0.0, description="持仓数量")
    avg_cost: float = Field(default=0.0, description="平均成本")
    current_price: float = Field(default=0.0, description="当前价格")
    market_value: float = Field(default=0.0, description="市值")
    unrealized_pnl: float = Field(default=0.0, description="未实现盈亏")
    realized_pnl: float = Field(default=0.0, description="已实现盈亏")
    weight_pct: float = Field(default=0.0, description="仓位占比（%）")
    today_change_pct: float = Field(default=0.0, description="今日涨跌幅（%）")


class CashState(BaseModel):
    """现金状态"""
    total_cash: float = Field(default=0.0, description="总现金")
    available_cash: float = Field(default=0.0, description="可用现金")
    frozen_cash: float = Field(default=0.0, description="冻结资金")


class PortfolioState(BaseModel):
    """组合状态快照（从 ledger 重建）"""
    investor_id: str = Field(..., description="投资者 ID")
    portfolio_id: str = Field(..., description="组合 ID")
    total_assets: float = Field(default=0.0, description="总资产")
    total_market_value: float = Field(default=0.0, description="持仓总市值")
    cash: CashState = Field(default_factory=CashState, description="现金状态")
    positions: list[PositionState] = Field(default_factory=list, description="持仓列表")
    nav: float = Field(default=1.0, description="单位净值")
    benchmark_nav: float | None = Field(default=None, description="基准净值")
    total_return_pct: float = Field(default=0.0, description="累计收益率（%）")
    snapshot_time: str = Field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════
# 审计模型
# ═══════════════════════════════════════════════════════════════════


class AuditEvent(BaseModel):
    """审计事件"""
    event_id: str = Field(default="", description="事件 ID（自动生成）")
    event_type: AuditEventType = Field(..., description="事件类型")
    actor: str = Field(default="system", description="操作主体")
    target: str = Field(default="", description="操作目标")
    details: dict = Field(default_factory=dict, description="事件详情")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════
# 哨兵模型
# ═══════════════════════════════════════════════════════════════════


class SentinelSignal(BaseModel):
    """哨兵信号"""
    ticker: str = Field(..., description="哨兵 ETF 代码")
    name: str = Field(default="", description="名称")
    price: float = Field(default=0.0, description="当前价格")
    change_pct: float = Field(default=0.0, description="涨跌幅（%）")
    ma5: float | None = Field(default=None, description="5日均线")
    ma20: float | None = Field(default=None, description="20日均线")
    ma60: float | None = Field(default=None, description="60日均线")
    signal: str = Field(default="neutral", description="信号: bullish/bearish/neutral")


class SentinelSnapshot(BaseModel):
    """哨兵扫描快照"""
    scan_time: str = Field(default_factory=lambda: datetime.now().isoformat())
    signals: list[SentinelSignal] = Field(default_factory=list)
    overall_signal: str = Field(default="neutral", description="综合信号")
    attack_defense: str = Field(default="defense", description="攻防状态: attack/defense/watch")
    rule23_active: bool = Field(default=False, description="Rule 23 情绪起爆器是否激活")


# ═══════════════════════════════════════════════════════════════════
# 估值模型
# ═══════════════════════════════════════════════════════════════════


class ValuationPercentile(BaseModel):
    """指数估值分位"""
    index_code: str = Field(..., description="指数代码")
    index_name: str = Field(default="", description="指数名称")
    pe_ttm: float | None = Field(default=None, description="PE-TTM")
    pe_percentile: float | None = Field(default=None, ge=0, le=100, description="PE 历史分位（%）")
    pb: float | None = Field(default=None, description="市净率")
    pb_percentile: float | None = Field(default=None, ge=0, le=100, description="PB 历史分位（%）")
    dividend_yield: float | None = Field(default=None, description="股息率（%）")
    valuation_level: str = Field(default="fair", description="估值水平: undervalued/fair/overvalued")
    update_date: str = Field(default="", description="数据更新日期")


# ═══════════════════════════════════════════════════════════════════
# 绩效模型
# ═══════════════════════════════════════════════════════════════════


class PerformanceMetrics(BaseModel):
    """绩效指标"""
    total_return: float = Field(default=0.0, description="累计收益率")
    annualized_return: float = Field(default=0.0, description="年化收益率")
    benchmark_return: float = Field(default=0.0, description="基准收益率")
    excess_return: float = Field(default=0.0, description="超额收益")
    max_drawdown: float = Field(default=0.0, description="最大回撤")
    volatility: float = Field(default=0.0, description="波动率")
    sharpe_ratio: float | None = Field(default=None, description="夏普比率")
    calmar_ratio: float | None = Field(default=None, description="卡尔玛比率")
    win_rate: float = Field(default=0.0, description="胜率")
    profit_loss_ratio: float | None = Field(default=None, description="盈亏比")
    turnover_rate: float = Field(default=0.0, description="换手率")
    total_fee: float = Field(default=0.0, description="总费用")


# ═══════════════════════════════════════════════════════════════════
# 统一复盘数据模型 (Review Data Models)
# ═══════════════════════════════════════════════════════════════════


class ReviewPeriod(BaseModel):
    """复盘周期"""
    model_config = {"extra": "ignore"}

    start: str = Field(default="", description="起始日期 YYYY-MM-DD")
    end: str = Field(default="", description="结束日期 YYYY-MM-DD")
    label: str = Field(default="", description="周期标签，如 '2026-W28' / '2026-07' / '2026-Q2'")


class SectorItem(BaseModel):
    """板块条目"""
    model_config = {"extra": "ignore"}

    name: str = Field(description="板块名称")
    code: str = Field(default="", description="板块代码")
    change_pct: float = Field(default=0.0, description="涨跌幅（%）")


class SectorData(BaseModel):
    """板块轮动数据"""
    model_config = {"extra": "ignore"}

    top_gainers: list[SectorItem] = Field(default_factory=list, description="领涨板块")
    top_losers: list[SectorItem] = Field(default_factory=list, description="领跌板块")
    consecutive_hot: list[SectorItem] = Field(default_factory=list, description="持续热门板块")


class ETFInflowItem(BaseModel):
    """ETF 资金流入条目"""
    model_config = {"extra": "ignore"}

    code: str = Field(description="ETF 代码")
    name: str = Field(description="ETF 名称")
    net_inflow: float = Field(default=0.0, description="净流入（亿元）")


class FundFlowData(BaseModel):
    """资金流向数据"""
    model_config = {"extra": "ignore"}

    main_force_net: float | None = Field(default=None, description="主力净额（亿元）")
    north_bound_net: float | None = Field(default=None, description="北向净额（亿元）")
    etf_inflow_top5: list[ETFInflowItem] = Field(default_factory=list, description="ETF 净流入 Top5")


class SentimentData(BaseModel):
    """市场情绪数据"""
    model_config = {"extra": "ignore"}

    avg_limit_up_down_ratio: float | None = Field(default=None, description="平均涨跌停比")
    avg_turnover: float | None = Field(default=None, description="平均成交额（亿元）")
    weekly_volatility: float | None = Field(default=None, description="周度波动率（%）")


class MacroEvent(BaseModel):
    """宏观事件"""
    model_config = {"extra": "ignore"}

    date: str = Field(default="", description="事件日期 YYYY-MM-DD")
    title: str = Field(default="", description="事件标题")
    summary: str = Field(default="", description="事件摘要")


class MarketDimension(BaseModel):
    """市场维度"""
    model_config = {"extra": "ignore"}

    index_code: str = Field(default="000300", description="指数代码")
    weekly_change_pct: float | None = Field(default=None, description="周涨跌幅（%）")
    volume_trend: str | None = Field(default=None, description="成交量趋势: 放量|缩量|持平")
    ma_positions: dict[str, str] = Field(default_factory=dict, description="均线位置，如 {'MA5':'上方'}")
    sector_rotation: SectorData | None = Field(default=None, description="板块轮动")
    fund_flow: FundFlowData | None = Field(default=None, description="资金流向")
    sentiment: SentimentData | None = Field(default=None, description="市场情绪")
    macro_events: list[MacroEvent] = Field(default_factory=list, description="宏观事件列表")


class PortfolioDimension(BaseModel):
    """组合维度"""
    model_config = {"extra": "ignore"}

    total_assets: float = Field(default=0.0, description="总资产")
    nav: float = Field(default=1.0, description="单位净值")
    positions: int = Field(default=0, description="持仓数量")
    cash_ratio_pct: float = Field(default=0.0, description="现金占比（%）")
    holdings: list[dict] = Field(default_factory=list, description="持仓明细: [{ticker,name,qty,price,mkt_value}]")


class SentinelDimension(BaseModel):
    """哨兵维度"""
    model_config = {"extra": "ignore"}

    overall_signal: str = Field(default="", description="综合信号: 绝对防守期|攻防转换期|进攻期")
    bullish_count: int = Field(default=0, description="看多哨兵数量")
    total: int = Field(default=0, description="哨兵总数")
    position_limit_pct: float = Field(default=0.0, description="仓位上限（%）")
    sentinel_details: list[dict] = Field(default_factory=list, description="哨兵详情列表")


class PerformanceDimension(BaseModel):
    """绩效维度"""
    model_config = {"extra": "ignore"}

    total_return: float = Field(default=0.0, description="累计收益率")
    annualized_return: float = Field(default=0.0, description="年化收益率")
    benchmark_return: float = Field(default=0.0, description="基准收益率")
    excess_return: float = Field(default=0.0, description="超额收益")
    max_drawdown: float = Field(default=0.0, description="最大回撤")
    volatility: float = Field(default=0.0, description="波动率")
    sharpe_ratio: float | None = Field(default=None, description="夏普比率")
    calmar_ratio: float | None = Field(default=None, description="卡尔玛比率")
    win_rate: float | None = Field(default=None, description="胜率（无卖出时为 None）")
    profit_loss_ratio: float | None = Field(default=None, description="盈亏比")


class SingleDecisionReview(BaseModel):
    """单条决策复盘"""
    model_config = {"extra": "ignore"}

    decision_id: str = Field(default="", description="决策 ID")
    ticker: str = Field(default="", description="标的代码")
    action: str = Field(default="", description="决策动作")
    review_type: str = Field(default="", description="复盘类型: 5d|20d|60d")
    actual_return_pct: float | None = Field(default=None, description="实际收益率（%）")
    benchmark_return_pct: float | None = Field(default=None, description="基准收益率（%）")
    alpha_pct: float | None = Field(default=None, description="超额收益（%）")
    notes: str = Field(default="", description="备注")


class DecisionReviewDimension(BaseModel):
    """决策复盘维度"""
    model_config = {"extra": "ignore"}

    total_decisions: int = Field(default=0, description="总决策数")
    filled_count: int = Field(default=0, description="已成交数")
    pending_5d: int = Field(default=0, description="待复盘 5 日数")
    pending_20d: int = Field(default=0, description="待复盘 20 日数")
    pending_60d: int = Field(default=0, description="待复盘 60 日数")
    avg_actual_return_5d: float | None = Field(default=None, description="5 日平均实际收益（%）")
    avg_alpha_5d: float | None = Field(default=None, description="5 日平均超额收益（%）")
    reviews: list[SingleDecisionReview] = Field(default_factory=list, description="决策复盘列表")


class ValuationDimension(BaseModel):
    """估值维度"""
    model_config = {"extra": "ignore"}

    pe_percentile: float | None = Field(default=None, description="PE 历史分位（%）")
    pb_percentile: float | None = Field(default=None, description="PB 历史分位（%）")
    dividend_yield: float | None = Field(default=None, description="股息率（%）")
    level: str | None = Field(default=None, description="估值水平: undervalued|fair|overvalued")
    current_pe: float | None = Field(default=None, description="当前 PE")
    pe_30pct: float | None = Field(default=None, description="PE 历史 30% 分位值")
    pe_80pct: float | None = Field(default=None, description="PE 历史 80% 分位值")


class CascadeDimension(BaseModel):
    """级联回测维度"""
    model_config = {"extra": "ignore"}

    mode: str = Field(default="", description="回测模式: monthly|quarterly|annual")
    max_drawdown: float | None = Field(default=None, description="最大回撤")
    sharpe_ratio: float | None = Field(default=None, description="夏普比率")
    calmar_ratio: float | None = Field(default=None, description="卡尔玛比率")
    win_rate: float | None = Field(default=None, description="胜率")
    profit_loss_ratio: float | None = Field(default=None, description="盈亏比")
    holding_period_dist: dict[str, int] = Field(default_factory=dict, description="持仓周期分布，如 {'<3天':1}")
    risk_quality_report: str | None = Field(default=None, description="风险质量报告 (Markdown)")
    discipline_report: str | None = Field(default=None, description="纪律报告 (Markdown，不含 risk_quality)")


class ReviewSnapshot(BaseModel):
    """统一复盘快照 — 所有复盘工具返回此结构或其子集"""
    model_config = {"extra": "ignore"}

    snapshot_type: str = Field(description="快照类型: full|market_weekly|cascade_monthly|decision_review")
    generated_at: str = Field(default="", description="生成时间 ISO 8601")
    period: ReviewPeriod = Field(default_factory=ReviewPeriod, description="复盘周期")
    portfolio: PortfolioDimension | None = Field(default=None, description="组合维度")
    market: MarketDimension | None = Field(default=None, description="市场维度")
    sentinel: SentinelDimension | None = Field(default=None, description="哨兵维度")
    performance: PerformanceDimension | None = Field(default=None, description="绩效维度")
    decision_reviews: DecisionReviewDimension | None = Field(default=None, description="决策复盘维度")
    valuation: ValuationDimension | None = Field(default=None, description="估值维度")
    cascade: CascadeDimension | None = Field(default=None, description="级联回测维度")


__all__ = [name for name, obj in globals().items() if isinstance(obj, type) and issubclass(obj, (BaseModel, enum.Enum))]
