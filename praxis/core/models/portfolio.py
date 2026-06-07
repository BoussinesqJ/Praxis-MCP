"""投资组合模型"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .asset import AssetType, AssetCategory


class GridLevel(BaseModel):
    """网格档位"""
    trigger: float | None = None
    trigger_pct: float | None = None
    actual_trigger: float | None = None
    shares: int = 0
    amount_cny: float | None = None
    status: str = "active"
    label: str | None = None
    filled_at: str | None = None


class StopLoss(BaseModel):
    """止损配置"""
    type: str = "fixed"
    trigger: float | None = None
    trigger_pct: float | None = None


class TakeProfit(BaseModel):
    """止盈配置"""
    trigger: float
    sell_pct: float | None = None
    action: str | None = None


class MovingStop(BaseModel):
    """移动止损"""
    activate_above: float
    trail_pct: float = 8


class AssetEntry(BaseModel):
    """组合中的资产条目"""
    ticker: str
    name: str
    type: AssetType
    category: AssetCategory
    target_weight_pct: float = 0
    grid: list[GridLevel] = Field(default_factory=list)
    stop_loss: StopLoss | None = None
    take_profit: list[TakeProfit] = Field(default_factory=list)
    moving_stop: MovingStop | None = None
    base_price: float | None = None
    sentinel: str | None = None
    daily_limit_cny: float | None = None
    nav_base: float | None = None
    cost_protection: dict | None = None
    dynamic_rules: list[dict] = Field(default_factory=list)
    dividend: dict | None = None
    note: str | None = None


class SentinelEntry(BaseModel):
    """哨兵标的条目"""
    ticker: str
    name: str
    role: str
    blocks: str | None = None  # 被拦截的标的 ticker


class Sentinels(BaseModel):
    """哨兵配置"""
    macro_layer: list[SentinelEntry] = Field(default_factory=list)
    execution_layer: list[SentinelEntry] = Field(default_factory=list)


class Portfolio(BaseModel):
    """投资组合配置"""
    strategy_type: str
    strategy_template: str
    base_currency: str = "CNY"
    created_at: str
    version: str
    description: str | None = None
    assets: list[AssetEntry] = Field(default_factory=list)
    sentinels: Sentinels = Field(default_factory=Sentinels)
    idle_cash_allocation: dict | None = None
