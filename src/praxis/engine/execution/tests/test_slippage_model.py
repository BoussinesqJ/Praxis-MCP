"""SlippageModel 测试 — 6 场景

测试三维滑点模型：默认参数、波动率影响、成交量影响、方向影响、极端行情、零波动率。
"""
from __future__ import annotations

import pytest

from praxis.engine.execution.slippage_model import SlippageModel, SlippageConfig


# ── Helpers ──────────────────────────────────────────────────────

@pytest.fixture
def model():
    """默认配置的 SlippageModel"""
    return SlippageModel()


def _round_result(result: dict) -> dict:
    """对浮点值做兼容处理"""
    return result


# ── 1. estimate_slippage 默认参数 ────────────────────────────────

def test_estimate_slippage_default(model):
    """默认参数下的基本滑点估算"""
    result = model.estimate(price=100.0, trade_action="buy")

    assert "slippage_pct" in result
    assert "adjusted_price" in result
    assert "breakdown" in result

    # 固定滑点: 100 * 0.001 = 0.1
    breakdown = result["breakdown"]
    assert breakdown["fixed_slippage"] == 0.1

    # 无成交量 → 无流动性滑点
    assert breakdown["liquidity_slippage"] == 0.0

    # 无波动率 → 无波动率滑点
    assert breakdown["volatility_slippage"] == 0.0


# ── 2. 波动率影响 ───────────────────────────────────────────────

def test_volatility_impact(model):
    """波动率增加滑点"""
    no_vol = model.estimate(price=100.0, trade_action="buy")
    with_vol = model.estimate(price=100.0, trade_action="buy", volatility=0.03)

    # 有波动率时滑点更大
    assert with_vol["slippage_pct"] > no_vol["slippage_pct"]

    # 波动率滑点: 100 * 0.03 * 0.5 = 1.5
    assert with_vol["breakdown"]["volatility_slippage"] == 1.5


# ── 3. 成交量影响 ───────────────────────────────────────────────

def test_volume_impact(model):
    """低成交量触发流动性滑点"""
    no_vol_result = model.estimate(price=100.0, trade_action="buy")

    # 成交量低于阈值(100000) → 触发流动性滑点
    low_vol_result = model.estimate(price=100.0, trade_action="buy", volume=10000)

    assert low_vol_result["slippage_pct"] > no_vol_result["slippage_pct"]
    # 流动性滑点: 100 * 0.002 = 0.2
    assert low_vol_result["breakdown"]["liquidity_slippage"] == 0.2

    # 成交量高于阈值 → 不触发流动性滑点
    high_vol_result = model.estimate(price=100.0, trade_action="buy", volume=500000)
    assert high_vol_result["breakdown"]["liquidity_slippage"] == 0.0


# ── 4. 方向影响（买/卖） ────────────────────────────────────────

def test_direction_impact(model):
    """买入和卖出对 adjusted_price 影响方向不同"""
    result_buy = model.estimate(price=100.0, trade_action="buy")
    result_sell = model.estimate(price=100.0, trade_action="sell")

    # 买入：adjusted = price + slippage
    assert result_buy["adjusted_price"] > 100.0

    # 卖出：adjusted = price - slippage
    assert result_sell["adjusted_price"] < 100.0


# ── 5. 极端行情高滑点 ───────────────────────────────────────────

def test_extreme_market():
    """高波动率 + 低成交量 = 高滑点"""
    config = SlippageConfig(
        fixed_slippage_pct=0.002,
        liquidity_threshold=500000,
        liquidity_slippage_pct=0.005,
        volatility_multiplier=1.0,
    )
    model = SlippageModel(config)

    result = model.estimate(
        price=100.0,
        trade_action="buy",
        volume=10000,   # 远低于阈值
        volatility=0.05,  # 5% 波动率
    )

    # 固定: 100*0.002=0.2, 流动性: 100*0.005=0.5, 波动率: 100*0.05*1.0=5.0
    assert result["breakdown"]["liquidity_slippage"] == 0.5
    assert result["breakdown"]["volatility_slippage"] == 5.0
    assert result["slippage_pct"] > 0.05  # >5%


# ── 6. 零波动率 → 最小滑点 ──────────────────────────────────────

def test_zero_volatility(model):
    """波动率为0时只有固定滑点"""
    result = model.estimate(price=100.0, trade_action="buy", volatility=0.0)

    breakdown = result["breakdown"]
    assert breakdown["volatility_slippage"] == 0.0
    assert breakdown["liquidity_slippage"] == 0.0
    assert breakdown["fixed_slippage"] > 0
