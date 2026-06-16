"""滑点模型测试（合并版）"""
import pytest
from praxis.engine.execution.slippage_model import (
    SlippageCalculator,
    SlippageEstimate,
    SlippageConfig,
)


class TestSlippageCalculator:
    """滑点计算器测试"""

    def setup_method(self):
        self.calculator = SlippageCalculator()

    def test_buy_slippage(self):
        """测试买入滑点（价格上升）"""
        result = self.calculator.estimate(action="buy", quantity=1000, price=10.0)
        assert result.actual_price > result.expected_price
        assert result.slippage_amount > 0
        assert result.slippage_pct > 0

    def test_sell_slippage(self):
        """测试卖出滑点（价格下降）"""
        result = self.calculator.estimate(action="sell", quantity=1000, price=10.0)
        assert result.actual_price < result.expected_price
        assert result.slippage_amount > 0

    def test_fixed_slippage(self):
        """测试固定滑点（千 1）"""
        result = self.calculator.estimate(action="buy", quantity=100, price=10.0)
        # 固定滑点=10×0.001=0.01
        assert abs(result.fixed_slippage - 0.01) < 0.001

    def test_liquidity_slippage(self):
        """测试流动性滑点（成交量低于阈值）"""
        # 高流动性
        result_high = self.calculator.estimate(
            action="buy", quantity=100, price=10.0, volume=500000
        )
        # 低流动性
        result_low = self.calculator.estimate(
            action="buy", quantity=100, price=10.0, volume=50000
        )
        assert result_low.liquidity_slippage > result_high.liquidity_slippage

    def test_volatility_slippage(self):
        """测试波动性滑点"""
        result = self.calculator.estimate(
            action="buy", quantity=100, price=10.0, volatility=0.02
        )
        # 波动性滑点=10×0.02×0.5=0.1
        assert abs(result.volatility_slippage - 0.1) < 0.001

    def test_large_order_slippage(self):
        """测试大单滑点翻倍"""
        result_normal = self.calculator.estimate(
            action="buy", quantity=100, price=10.0, volume=1000000
        )
        result_large = self.calculator.estimate(
            action="buy", quantity=50000, price=10.0, volume=1000000
        )
        assert result_large.fixed_slippage > result_normal.fixed_slippage

    def test_total_cost(self):
        """测试滑点总成本 = 滑点金额 × 数量"""
        result = self.calculator.estimate(action="buy", quantity=1000, price=10.0)
        expected_cost = result.slippage_amount * 1000
        assert abs(result.total_cost - expected_cost) < 0.01

    def test_custom_config(self):
        """测试自定义配置"""
        config = SlippageConfig(fixed_slippage_pct=0.002)
        calculator = SlippageCalculator(config=config)
        result = calculator.estimate(action="buy", quantity=100, price=10.0)
        assert abs(result.fixed_slippage - 0.02) < 0.001

    def test_zero_price(self):
        """测试零价格边界"""
        result = self.calculator.estimate(action="buy", quantity=100, price=0.0)
        assert result.slippage_pct == 0
        assert result.total_cost == 0
