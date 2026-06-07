"""组合状态模型（可重建的缓存）"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .asset import AssetType, AssetCategory


class PositionState(BaseModel):
    """持仓状态"""
    ticker: str
    name: str
    type: AssetType
    category: AssetCategory
    quantity: float
    avg_cost: float
    current_price: float = 0
    market_value: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    target_weight_pct: float = 0
    actual_weight_pct: float = 0


class CashState(BaseModel):
    """现金状态"""
    total_assets: float = 0
    total_positions_value: float = 0
    available_cash: float = 0
    cash_ratio: float = 0
    frozen_amount: float = 0


class GridState(BaseModel):
    """网格状态（单标的）"""
    ticker: str
    triggers: list[dict] = Field(default_factory=list)
    stop_loss: dict | None = None
    take_profit: list[dict] = Field(default_factory=list)
    moving_stop: dict | None = None


class PortfolioState(BaseModel):
    """组合状态（可从 ledger + 行情 + config 重建）"""
    investor_id: str
    portfolio_id: str
    snapshot_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    positions: list[PositionState] = Field(default_factory=list)
    cash: CashState = Field(default_factory=CashState)
    grids: list[GridState] = Field(default_factory=list)
    risk_metrics: dict = Field(default_factory=dict)
    data_source: str = "computed"  # "computed" | "cached"
    is_stale: bool = False


class PerformanceMetrics(BaseModel):
    """绩效指标（增强版）"""
    # 收益指标
    total_return: float = 0
    annualized_return: float = 0
    benchmark_return: float = 0
    excess_return: float = 0            # 超额收益

    # 风险指标
    max_drawdown: float = 0             # 最大回撤
    max_drawdown_duration: int = 0      # 最大回撤持续天数
    volatility: float = 0               # 年化波动率
    downside_volatility: float = 0      # 下行波动率

    # 风险调整收益
    sharpe_ratio: float = 0             # 夏普比率
    calmar_ratio: float = 0             # 卡玛比率
    sortino_ratio: float = 0            # 索提诺比率
    information_ratio: float = 0        # 信息比率

    # 交易指标
    win_rate: float = 0
    profit_loss_ratio: float = 0
    turnover_rate: float = 0
    total_fee: float = 0
    buy_count: int = 0
    sell_count: int = 0
    realized_pnl: float = 0
    total_dividend: float = 0
