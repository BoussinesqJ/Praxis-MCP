"""费用模型测试（合并版）"""
import pytest
from praxis.engine.execution.fee_model import (
    AShareFeeCalculator,
    ETFFeeCalculator,
    OffshoreFundFeeCalculator,
    FeeBreakdown,
    get_fee_calculator,
)


class TestAShareFeeCalculator:
    """A 股费用计算器测试"""

    def setup_method(self):
        self.calculator = AShareFeeCalculator()

    def test_buy_commission(self):
        """测试买入佣金（万 2.5，最低 5 元）"""
        result = self.calculator.calculate(action="buy", quantity=1000, price=10.0)
        # 金额=10000, 佣金=10000×0.00025=2.5→最低5元
        assert result.commission == 5.0
        assert result.stamp_tax == 0

    def test_sell_commission(self):
        """测试卖出佣金+印花税"""
        result = self.calculator.calculate(action="sell", quantity=1000, price=10.0)
        assert result.commission == 5.0
        # 印花税=10000×0.001=10.0
        assert result.stamp_tax == 10.0

    def test_minimum_commission(self):
        """测试最低佣金（5 元）"""
        result = self.calculator.calculate(action="buy", quantity=100, price=1.0)
        assert result.commission == 5.0

    def test_large_commission(self):
        """测试大额佣金按费率计算"""
        result = self.calculator.calculate(action="buy", quantity=10000, price=20.0)
        # 金额=200000, 佣金=200000×0.00025=50.0
        assert result.commission == 50.0

    def test_transfer_fee_shanghai(self):
        """测试沪市过户费（60 开头）"""
        result = self.calculator.calculate(
            action="buy", quantity=1000, price=10.0, ticker="000001"
        )
        # 过户费=10000×0.0001=1.0
        assert result.transfer_fee == 1.0

    def test_transfer_fee_shenzhen(self):
        """测试深市无过户费"""
        result = self.calculator.calculate(
            action="buy", quantity=1000, price=10.0, ticker="000001"
        )
        assert result.transfer_fee == 0

    def test_transfer_fee_no_ticker(self):
        """测试无 ticker 时无过户费"""
        result = self.calculator.calculate(action="buy", quantity=1000, price=10.0)
        assert result.transfer_fee == 0

    def test_total_fee(self):
        """测试总费用 = 佣金 + 印花税 + 过户费"""
        result = self.calculator.calculate(
            action="sell", quantity=1000, price=10.0, ticker="000001"
        )
        expected = result.commission + result.stamp_tax + result.transfer_fee
        assert result.total_fee == expected

    def test_net_amount_buy(self):
        """测试买入净金额 = 金额 + 费用"""
        result = self.calculator.calculate(action="buy", quantity=1000, price=10.0)
        assert result.net_amount == 10000 + result.total_fee

    def test_net_amount_sell(self):
        """测试卖出净金额 = 金额 - 费用"""
        result = self.calculator.calculate(action="sell", quantity=1000, price=10.0)
        assert result.net_amount == 10000 - result.total_fee


class TestETFFeeCalculator:
    """ETF 费用计算器测试"""

    def setup_method(self):
        self.calculator = ETFFeeCalculator()

    def test_buy_fee(self):
        """测试 ETF 买入（万 1.5，最低 5 元）"""
        result = self.calculator.calculate(action="buy", quantity=1000, price=10.0)
        assert result.stamp_tax == 0
        # 金额=10000, 佣金=10000×0.00015=1.5→最低5元
        assert result.commission == 5.0

    def test_sell_fee(self):
        """测试 ETF 卖出（无印花税）"""
        result = self.calculator.calculate(action="sell", quantity=1000, price=10.0)
        assert result.stamp_tax == 0
        assert result.commission == 5.0

    def test_transfer_fee_shanghai_etf(self):
        """测试沪市 ETF 过户费（51/58 开头）"""
        result = self.calculator.calculate(
            action="buy", quantity=1000, price=10.0, ticker="510050"
        )
        # 过户费=10000×0.0001=1.0
        assert result.transfer_fee == 1.0

    def test_no_transfer_fee_non_shanghai(self):
        """测试非沪市 ETF 无过户费"""
        result = self.calculator.calculate(
            action="buy", quantity=1000, price=10.0, ticker="159915"
        )
        assert result.transfer_fee == 0


class TestOffshoreFundFeeCalculator:
    """场外基金费用计算器测试"""

    def setup_method(self):
        self.calculator = OffshoreFundFeeCalculator()

    def test_subscribe_fee(self):
        """测试申购费（千 1.5）"""
        result = self.calculator.calculate(action="buy", quantity=1000, price=10.0)
        assert result.subscribe_fee == 15.0
        assert result.total_fee == 15.0
        assert result.net_amount == 10015.0

    def test_redeem_fee_short(self):
        """测试短期赎回费（<7 天，千 5）"""
        result = self.calculator.calculate(
            action="sell", quantity=1000, price=10.0, holding_days=5
        )
        assert result.redeem_fee == 50.0
        assert result.total_fee == 50.0
        assert result.net_amount == 9950.0

    def test_redeem_fee_long(self):
        """测试长期赎回费（≥7 天，免费）"""
        result = self.calculator.calculate(
            action="sell", quantity=1000, price=10.0, holding_days=30
        )
        assert result.redeem_fee == 0
        assert result.total_fee == 0
        assert result.net_amount == 10000.0


class TestGetFeeCalculator:
    """工厂函数测试"""

    def test_stock_calculator(self):
        calc = get_fee_calculator("stock")
        assert isinstance(calc, AShareFeeCalculator)

    def test_etf_calculator(self):
        calc = get_fee_calculator("etf")
        assert isinstance(calc, ETFFeeCalculator)

    def test_offshore_fund_calculator(self):
        calc = get_fee_calculator("offshore_fund")
        assert isinstance(calc, OffshoreFundFeeCalculator)

    def test_unknown_defaults_to_stock(self):
        calc = get_fee_calculator("unknown")
        assert isinstance(calc, AShareFeeCalculator)
