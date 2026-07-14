"""FeeModel 测试 — 6 场景

测试费用模型：佣金（万2.5，最低5元）、印花税（卖出单向0.1%）、过户费、0股处理、总费用、边界值。
"""
from __future__ import annotations

import pytest

from praxis.engine.execution.fee_model import (
    FeeModel,
    AShareFeeCalculator,
    ETFFeeCalculator,
    OffshoreFundFeeCalculator,
    get_fee_calculator,
)
from praxis.engine.execution.fee_model import FeeBreakdown


# ── Helpers ──────────────────────────────────────────────────────

def calc_buy(quantity: float, price: float, ticker: str = "600519") -> dict:
    """快速计算买入费用"""
    return FeeModel.calculate(ticker, "stock", "buy", quantity, price)


def calc_sell(quantity: float, price: float, ticker: str = "600519") -> dict:
    """快速计算卖出费用"""
    return FeeModel.calculate(ticker, "stock", "sell", quantity, price)


# ── 1. 佣金（万2.5，最低5元） ────────────────────────────────────

def test_commission_rate():
    """佣金按万2.5计算，不低于最低5元"""
    # 小额交易：1股*100元=100元，佣金=max(0.025, 5) = 5
    result_small = calc_buy(1, 100.0)
    assert result_small["breakdown"]["commission"] == 5.0

    # 大额交易：10000股*100元=1,000,000，佣金=250
    # 沪市(60开头)有过户费：1,000,000 * 0.0001 = 100
    result_large = calc_buy(10000, 100.0)
    assert result_large["breakdown"]["commission"] == 250.0
    assert result_large["breakdown"]["stamp_tax"] == 0.0  # 买入无印花税
    assert result_large["breakdown"]["transfer_fee"] == 100.0  # 沪市过户费
    assert result_large["total_fee"] == 350.0  # 250 + 100


# ── 2. 印花税（卖出单向0.1%） ───────────────────────────────────

def test_stamp_tax():
    """印花税仅卖出时收取，千分之1"""
    # 买入：无印花税
    result_buy = calc_buy(100, 20.0)
    assert result_buy["breakdown"]["stamp_tax"] == 0.0

    # 卖出：千1印花税
    # 100股*20元=2000，印花税=2.0
    result_sell = calc_sell(100, 20.0)
    assert result_sell["breakdown"]["stamp_tax"] == 2.0


# ── 3. 过户费 ───────────────────────────────────────────────────

def test_transfer_fee():
    """过户费仅沪市股票收取"""
    # 沪市(60开头)有过户费：2000*0.0001=0.2
    result_sh = calc_sell(100, 20.0, "600519")
    assert result_sh["breakdown"]["transfer_fee"] > 0

    # 深市(00开头)无过户费
    result_sz = calc_sell(100, 20.0, "000001")
    assert result_sz["breakdown"]["transfer_fee"] == 0.0


# ── 4. 0 股 ────────────────────────────────────────────────────

def test_zero_quantity():
    """0股交易费用为0"""
    result = calc_buy(0, 100.0)
    assert result["total_fee"] == 5.0  # 最低佣金5元仍适用
    assert result["net_amount"] == 5.0  # 买入成本含佣金


# ── 5. 总费用汇总 ───────────────────────────────────────────────

def test_total_fee_summary():
    """total_fee = commission + stamp_tax + transfer_fee"""
    # 卖出1000股*50元=50000元，沪市
    result = calc_sell(1000, 50.0, "600519")
    breakdown = result["breakdown"]

    commission = breakdown["commission"]  # 50000*0.00025=12.5
    stamp_tax = breakdown["stamp_tax"]    # 50000*0.001=50.0
    transfer_fee = breakdown["transfer_fee"]  # 50000*0.0001=5.0
    total = result["total_fee"]

    expected_total = round(commission + stamp_tax + transfer_fee, 2)
    assert total == expected_total


# ── 6. 边界值 ───────────────────────────────────────────────────

def test_edge_cases():
    """极小金额/极大金额边界"""
    # 极小金额：1股*0.01元=0.01元
    result_tiny = calc_buy(1, 0.01)
    assert result_tiny["total_fee"] == 5.0  # 最低5元

    # 极大金额
    result_huge = calc_buy(100000, 500.0)  # 5000万
    assert result_huge["total_fee"] > 0
    assert "net_amount" in result_huge


# ── ETF 费用 ────────────────────────────────────────────────────

def test_etf_fee():
    """ETF 无印花税，佣金万1.5"""
    result = FeeModel.calculate("510300", "etf", "sell", 10000, 4.0)
    assert result["breakdown"]["stamp_tax"] == 0.0


# ── 场外基金费用 ────────────────────────────────────────────────

def test_fund_fee():
    """场外基金申购费千1.5，赎回费根据持有天数"""
    # 申购
    buy = FeeModel.calculate("000001", "offshore_fund", "buy", 1000, 1.5)
    assert buy["breakdown"]["subscribe_fee"] > 0

    # 赎回（持有 <7天）
    sell_short = FeeModel.calculate("000001", "offshore_fund", "sell", 1000, 1.5)
    # 默认 holding_days=0，按短期赎回费率


# ── 工厂函数 ────────────────────────────────────────────────────

def test_get_fee_calculator():
    """get_fee_calculator 返回正确的计算器"""
    stock_calc = get_fee_calculator("stock")
    assert isinstance(stock_calc, AShareFeeCalculator)

    etf_calc = get_fee_calculator("etf")
    assert isinstance(etf_calc, ETFFeeCalculator)

    fund_calc = get_fee_calculator("offshore_fund")
    assert isinstance(fund_calc, OffshoreFundFeeCalculator)
