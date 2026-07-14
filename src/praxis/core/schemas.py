"""PRAXIS Core — 外部数据 Pydantic 模型

定义 WorkBuddy → praxis-mcp 数据交换格式。
用于 P0 外部数据支持：接收外部传入的K线/行情/组合/市场数据。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class KlineItem(BaseModel):
    """单条K线数据"""
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: Optional[float] = None


class KlinesPayload(BaseModel):
    """外部K线数据载荷"""
    etf_klines: dict[str, dict] = {}
    schema_version: str = "1.0"


class QuoteItem(BaseModel):
    """单条行情报价"""
    price: float
    change_pct: Optional[float] = None
    name: Optional[str] = None


class QuotesPayload(BaseModel):
    """外部行情数据载荷"""
    quotes: dict[str, QuoteItem] = {}
    schema_version: str = "1.0"


class PortfolioPayload(BaseModel):
    """外部组合数据载荷"""
    investor: Optional[str] = "default"
    portfolio: Optional[str] = "core"
    cash: dict = Field(default_factory=dict)
    positions: list[dict] = Field(default_factory=list)
    schema_version: str = "1.0"


class MarketDataPayload(BaseModel):
    """外部市场数据载荷（用于市场周报）"""
    week_ending: Optional[str] = None
    index_code: Optional[str] = "000300"
    date_range: Optional[dict] = None
    dimensions: dict[str, dict] = Field(default_factory=dict)
    schema_version: str = "1.0"


class ExternalDataPayload(BaseModel):
    """通用外部数据载荷（用于级联复盘/全量复盘）"""
    mode: Optional[str] = None
    period: Optional[str] = None
    sentinel: Optional[dict] = None
    portfolio: Optional[dict] = None
    quotes: Optional[dict] = None
    klines: Optional[dict] = None
    valuation: Optional[dict] = None
    performance: Optional[dict] = None
    schema_version: str = "1.0"
