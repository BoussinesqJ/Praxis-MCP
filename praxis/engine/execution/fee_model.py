"""费用模型（合并版）

合并 engine/fee_model.py 的精确费率 + engine/execution/ 的多态架构。

费率基准（2026 年主流券商）：
- A 股佣金：万 2.5，最低 5 元
- ETF 佣金：万 1.5，最低 5 元
- 印花税：千 1（仅卖出）
- 过户费：沪市千 0.1（60/68 开头）
- 场外基金：申购千 1.5，赎回持有 <7 天千 5，≥7 天免费
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class FeeBreakdown(BaseModel):
    """费用明细"""
    commission: float = 0      # 佣金
    stamp_tax: float = 0       # 印花税
    transfer_fee: float = 0    # 过户费
    subscribe_fee: float = 0   # 申购费
    redeem_fee: float = 0      # 赎回费
    total_fee: float = 0       # 总费用
    net_amount: float = 0      # 净金额


class FeeCalculator(ABC):
    """费用计算器接口"""

    @abstractmethod
    def calculate(
        self, action: str, quantity: float, price: float, **kwargs
    ) -> FeeBreakdown:
        """计算费用"""
        ...


class AShareFeeCalculator(FeeCalculator):
    """A 股费用计算器"""

    COMMISSION_RATE = 0.00025    # 佣金费率（万 2.5）
    COMMISSION_MIN = 5.0         # 最低佣金
    STAMP_TAX_RATE = 0.001       # 印花税（千一，仅卖出）
    TRANSFER_FEE_RATE = 0.0001   # 过户费（沪市千 0.1）

    def calculate(
        self, action: str, quantity: float, price: float, **kwargs
    ) -> FeeBreakdown:
        amount = quantity * price
        ticker = kwargs.get("ticker", "")

        # 佣金
        commission = max(amount * self.COMMISSION_RATE, self.COMMISSION_MIN)

        # 印花税（仅卖出）
        stamp_tax = amount * self.STAMP_TAX_RATE if action == "sell" else 0

        # 过户费（沪市：60/68 开头）
        transfer_fee = 0
        if ticker.startswith(("60", "68")):
            transfer_fee = amount * self.TRANSFER_FEE_RATE

        total_fee = commission + stamp_tax + transfer_fee

        if action == "buy":
            net_amount = amount + total_fee
        else:
            net_amount = amount - total_fee

        return FeeBreakdown(
            commission=round(commission, 2),
            stamp_tax=round(stamp_tax, 2),
            transfer_fee=round(transfer_fee, 2),
            total_fee=round(total_fee, 2),
            net_amount=round(net_amount, 2),
        )


class ETFFeeCalculator(FeeCalculator):
    """ETF 费用计算器"""

    COMMISSION_RATE = 0.00015    # 佣金费率（万 1.5）
    COMMISSION_MIN = 5.0         # 最低佣金
    TRANSFER_FEE_RATE = 0.0001   # 过户费（沪市千 0.1）

    def calculate(
        self, action: str, quantity: float, price: float, **kwargs
    ) -> FeeBreakdown:
        amount = quantity * price
        ticker = kwargs.get("ticker", "")

        # 佣金
        commission = max(amount * self.COMMISSION_RATE, self.COMMISSION_MIN)

        # 过户费（沪市 ETF：51/58 开头）
        transfer_fee = 0
        if ticker.startswith(("51", "58")):
            transfer_fee = amount * self.TRANSFER_FEE_RATE

        total_fee = commission + transfer_fee

        if action == "buy":
            net_amount = amount + total_fee
        else:
            net_amount = amount - total_fee

        return FeeBreakdown(
            commission=round(commission, 2),
            stamp_tax=0,
            transfer_fee=round(transfer_fee, 2),
            total_fee=round(total_fee, 2),
            net_amount=round(net_amount, 2),
        )


class OffshoreFundFeeCalculator(FeeCalculator):
    """场外基金费用计算器"""

    SUBSCRIBE_RATE = 0.0015      # 申购费率（千 1.5）
    REDEEM_RATE_SHORT = 0.005    # 赎回费率（千 5，持有 <7 天）
    REDEEM_RATE_LONG = 0         # 赎回费率（持有 ≥7 天免费）

    def calculate(
        self, action: str, quantity: float, price: float, **kwargs
    ) -> FeeBreakdown:
        amount = quantity * price
        holding_days = kwargs.get("holding_days", 0)

        if action in ("buy", "subscribe"):
            subscribe_fee = round(amount * self.SUBSCRIBE_RATE, 2)
            return FeeBreakdown(
                subscribe_fee=subscribe_fee,
                total_fee=subscribe_fee,
                net_amount=round(amount + subscribe_fee, 2),
            )
        elif action in ("sell", "redeem"):
            rate = self.REDEEM_RATE_SHORT if holding_days < 7 else self.REDEEM_RATE_LONG
            redeem_fee = round(amount * rate, 2)
            return FeeBreakdown(
                redeem_fee=redeem_fee,
                total_fee=redeem_fee,
                net_amount=round(amount - redeem_fee, 2),
            )

        return FeeBreakdown()


def get_fee_calculator(asset_type: str) -> FeeCalculator:
    """获取费用计算器（工厂函数）"""
    calculators = {
        "stock": AShareFeeCalculator,
        "etf": ETFFeeCalculator,
        "offshore_fund": OffshoreFundFeeCalculator,
    }
    cls = calculators.get(asset_type, AShareFeeCalculator)
    return cls()
