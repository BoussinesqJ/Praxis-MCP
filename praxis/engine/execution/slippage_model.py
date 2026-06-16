"""滑点模型（合并版）

合并 engine/slippage_model.py 的三维模型（固定+流动性+波动率）+ Pydantic 配置。
"""
from __future__ import annotations

from pydantic import BaseModel


class SlippageConfig(BaseModel):
    """滑点配置"""
    fixed_slippage_pct: float = 0.001            # 固定滑点（千 1）
    liquidity_threshold: float = 100000          # 流动性阈值（成交量）
    liquidity_slippage_pct: float = 0.002        # 流动性滑点（千 2）
    volatility_multiplier: float = 0.5           # 波动性滑点乘数


class SlippageEstimate(BaseModel):
    """滑点估算"""
    expected_price: float    # 预期价格
    actual_price: float      # 实际价格
    slippage_amount: float   # 滑点金额（绝对值，每单位）
    slippage_pct: float      # 滑点比例
    total_cost: float        # 滑点总成本
    fixed_slippage: float = 0         # 固定滑点金额
    liquidity_slippage: float = 0     # 流动性滑点金额
    volatility_slippage: float = 0    # 波动性滑点金额


class SlippageCalculator:
    """滑点计算器（三维模型：固定 + 流动性 + 波动率）"""

    def __init__(self, config: SlippageConfig | None = None):
        self._config = config or SlippageConfig()

    def estimate(
        self,
        action: str,
        quantity: float,
        price: float,
        volume: float = 0,
        volatility: float | None = None,
    ) -> SlippageEstimate:
        """估算滑点

        Args:
            action: 操作类型（buy/sell）
            quantity: 数量
            price: 预期价格
            volume: 当日成交量（可选，用于流动性+大单滑点）
            volatility: 波动率（可选）

        Returns:
            SlippageEstimate
        """
        # 1. 固定滑点
        fixed_slippage = price * self._config.fixed_slippage_pct

        # 2. 流动性滑点（成交量低于阈值时增加）
        liquidity_slippage = 0
        if volume > 0 and volume < self._config.liquidity_threshold:
            liquidity_slippage = price * self._config.liquidity_slippage_pct

        # 3. 大单滑点（交易金额超过成交量的 1%，滑点翻倍）
        if volume > 0 and quantity * price > volume * 0.01:
            fixed_slippage *= 2

        # 4. 波动性滑点
        volatility_slippage = 0
        if volatility is not None:
            volatility_slippage = price * volatility * self._config.volatility_multiplier

        # 总滑点
        total_slippage = fixed_slippage + liquidity_slippage + volatility_slippage

        # 买入时价格上升，卖出时价格下降
        if action == "buy":
            actual_price = price + total_slippage
        else:
            actual_price = price - total_slippage

        slippage_amount = abs(actual_price - price)
        slippage_pct = slippage_amount / price if price > 0 else 0
        total_cost = slippage_amount * quantity

        return SlippageEstimate(
            expected_price=round(price, 4),
            actual_price=round(actual_price, 4),
            slippage_amount=round(slippage_amount, 4),
            slippage_pct=round(slippage_pct, 6),
            total_cost=round(total_cost, 4),
            fixed_slippage=round(fixed_slippage, 4),
            liquidity_slippage=round(liquidity_slippage, 4),
            volatility_slippage=round(volatility_slippage, 4),
        )
