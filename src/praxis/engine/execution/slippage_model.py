"""滑点模型 — 三维滑点估算（固定 + 流动性 + 波动率）"""
from __future__ import annotations

from pydantic import BaseModel


class SlippageConfig(BaseModel):
    """滑点配置"""
    fixed_slippage_pct: float = 0.001
    liquidity_threshold: float = 100000
    liquidity_slippage_pct: float = 0.002
    volatility_multiplier: float = 0.5


class SlippageEstimate(BaseModel):
    """滑点估算"""
    expected_price: float
    actual_price: float
    slippage_amount: float
    slippage_pct: float
    total_cost: float
    fixed_slippage: float = 0
    liquidity_slippage: float = 0
    volatility_slippage: float = 0


class SlippageModel:
    """滑点计算器（三维模型：固定 + 流动性 + 波动率）"""

    def __init__(self, config: SlippageConfig | None = None):
        self._config = config or SlippageConfig()

    def estimate(self, price: float, trade_action: str,
                 volume: float = 0, volatility: float | None = None) -> dict:
        """估算滑点

        Args:
            price: 预期价格
            trade_action: buy/sell
            volume: 当日成交量（可选）
            volatility: 波动率（可选）

        Returns:
            {slippage_pct, slippage_price, adjusted_price, total_cost, breakdown}
        """
        quantity = 1.0  # per-unit calculation

        fixed_slippage = price * self._config.fixed_slippage_pct

        liquidity_slippage = 0.0
        if volume > 0 and volume < self._config.liquidity_threshold:
            liquidity_slippage = price * self._config.liquidity_slippage_pct

        if volume > 0 and quantity * price > volume * 0.01:
            fixed_slippage *= 2

        volatility_slippage = 0.0
        if volatility is not None:
            volatility_slippage = price * volatility * self._config.volatility_multiplier

        total_slippage = fixed_slippage + liquidity_slippage + volatility_slippage

        if trade_action == "buy":
            adjusted_price = price + total_slippage
        else:
            adjusted_price = price - total_slippage

        slippage_amount = abs(adjusted_price - price)
        slippage_pct = slippage_amount / price if price > 0 else 0

        return {
            "slippage_pct": round(slippage_pct, 6),
            "slippage_price": round(slippage_amount, 4),
            "adjusted_price": round(adjusted_price, 4),
            "total_cost": round(slippage_amount, 4),
            "expected_price": round(price, 4),
            "breakdown": {
                "fixed_slippage": round(fixed_slippage, 4),
                "liquidity_slippage": round(liquidity_slippage, 4),
                "volatility_slippage": round(volatility_slippage, 4),
            },
        }
