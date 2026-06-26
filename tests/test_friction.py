"""交易摩擦工具测试"""
import pytest
from praxis.tools.friction import (
    calculate_fee,
    calculate_slippage,
    check_trading_time,
    get_confirm_date,
)


class TestCalculateFee:
    """交易费用计算测试"""

    def test_stock_buy_fee(self):
        """股票买入费用"""
        result = calculate_fee(
            ticker="000001",
            asset_type="stock",
            action="buy",
            quantity=100,
            price=13.50,
        )
        assert result["success"] is True
        assert result["data"]["total_fee"] > 0
        assert result["data"]["commission"] > 0

    def test_stock_sell_fee(self):
        """股票卖出费用（含印花税）"""
        result = calculate_fee(
            ticker="000001",
            asset_type="stock",
            action="sell",
            quantity=100,
            price=13.50,
        )
        assert result["success"] is True
        assert result["data"]["stamp_tax"] > 0  # 卖出有印花税

    def test_etf_fee(self):
        """ETF费用（无印花税）"""
        result = calculate_fee(
            ticker="510050",
            asset_type="etf",
            action="buy",
            quantity=100,
            price=4.0,
        )
        assert result["success"] is True
        assert result["data"]["stamp_tax"] == 0  # ETF无印花税

    def test_minimum_commission(self):
        """最低佣金测试"""
        result = calculate_fee(
            ticker="000001",
            asset_type="stock",
            action="buy",
            quantity=10,
            price=1.0,
        )
        assert result["success"] is True
        assert result["data"]["commission"] >= 5.0  # 最低佣金5元


class TestCalculateSlippage:
    """滑点计算测试"""

    def test_buy_slippage(self):
        """买入滑点"""
        result = calculate_slippage(price=13.50, action="buy")
        assert result["success"] is True
        assert result["data"]["slippage_pct"] > 0

    def test_sell_slippage(self):
        """卖出滑点"""
        result = calculate_slippage(price=13.50, action="sell")
        assert result["success"] is True
        assert result["data"]["slippage_pct"] > 0


class TestCheckTradingTime:
    """交易时间检查测试"""

    def test_check_trading_time(self):
        """检查交易时间"""
        result = check_trading_time()
        assert result["success"] is True
        assert "can_trade" in result["data"]


class TestGetConfirmDate:
    """确认日期测试"""

    def test_stock_confirm_date(self):
        """股票确认日期（T+1）"""
        result = get_confirm_date(trade_date="2026-06-05", asset_type="stock")
        assert result["success"] is True
        assert result["data"]["confirm_date"] is not None

    def test_fund_confirm_date(self):
        """基金确认日期（T+2或T+3）"""
        result = get_confirm_date(trade_date="2026-06-05", asset_type="fund")
        assert result["success"] is True
        assert result["data"]["confirm_date"] is not None
