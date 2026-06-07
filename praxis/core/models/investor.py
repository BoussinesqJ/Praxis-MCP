"""投资者画像模型"""
from __future__ import annotations

from pydantic import BaseModel, Field


class BannedMarket(BaseModel):
    """禁入板块"""
    id: str
    desc: str


class InvestorConstraints(BaseModel):
    """投资者约束"""
    banned_markets: list[BannedMarket] = Field(default_factory=list)
    banned_instruments: list[str] = Field(default_factory=list)
    etf_exemption: bool = True


class ExecutionConfig(BaseModel):
    """执行配置"""
    offshore_fund_window: str = "14:45-14:55"
    intraday_open_blackout_minutes: int = 15
    min_transaction_cny: float = 3000


class Philosophy(BaseModel):
    """投资哲学"""
    beliefs: list[str] = Field(default_factory=list)
    defenses: list[str] = Field(default_factory=list)


class InvestorProfile(BaseModel):
    """投资者画像"""
    name: str
    id: str
    capital_cny: float
    risk_level: str
    style: str
    max_drawdown_pct: float = 20
    constraints: InvestorConstraints = Field(default_factory=InvestorConstraints)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    philosophy: Philosophy = Field(default_factory=Philosophy)
