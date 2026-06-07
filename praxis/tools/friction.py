"""MCP 工具 - 交易摩擦计算

使用 engine/execution/ 下的多态费用/滑点/日历模型。
"""
from __future__ import annotations

from praxis.engine.execution.fee_model import get_fee_calculator
from praxis.engine.execution.slippage_model import SlippageCalculator, SlippageConfig
from praxis.engine.execution.trading_calendar import TradingCalendar, TradingCalendarConfig


def calculate_fee(
    ticker: str,
    asset_type: str,
    action: str,
    quantity: float,
    price: float,
    workspace: str = ".",
) -> dict:
    """计算交易费用

    Args:
        ticker: 标的代码
        asset_type: 资产类型（stock/etf/offshore_fund）
        action: 操作类型（buy/sell/subscribe/redeem）
        quantity: 数量
        price: 价格
    """
    try:
        calculator = get_fee_calculator(asset_type)
        result = calculator.calculate(action, quantity, price, ticker=ticker)
        return {"success": True, "data": result.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def calculate_slippage(
    price: float,
    action: str,
    volume: float | None = None,
    volatility: float | None = None,
    workspace: str = ".",
) -> dict:
    """计算滑点

    Args:
        price: 委托价格
        action: 操作类型（buy/sell）
        volume: 成交量（可选）
        volatility: 波动率（可选）
    """
    try:
        calculator = SlippageCalculator()
        result = calculator.estimate(
            action=action,
            quantity=1,  # 每单位滑点
            price=price,
            volume=volume or 0,
            volatility=volatility,
        )
        return {"success": True, "data": result.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_trading_time(
    timestamp: str | None = None,
    asset_type: str = "stock",
    workspace: str = ".",
) -> dict:
    """检查交易时间

    Args:
        timestamp: 时间戳（ISO 格式，可选，默认当前时间）
        asset_type: 资产类型（stock/etf/offshore_fund）
    """
    try:
        from datetime import datetime, timezone, timedelta

        calendar = TradingCalendar()
        beijing_tz = timezone(timedelta(hours=8))

        if timestamp:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=beijing_tz)
            else:
                dt = dt.astimezone(beijing_tz)
        else:
            dt = datetime.now(beijing_tz)

        is_trading_day = calendar.is_trading_day(dt)
        is_trading_time = calendar.is_trading_time(dt)
        is_offshore_fund_time = calendar.is_offshore_fund_trading_time(dt)

        return {
            "success": True,
            "data": {
                "timestamp": dt.isoformat(),
                "is_trading_day": is_trading_day,
                "is_trading_time": is_trading_time,
                "is_offshore_fund_trading_time": is_offshore_fund_time,
                "can_trade": is_trading_time if asset_type != "offshore_fund" else is_offshore_fund_time,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_confirm_date(
    trade_date: str,
    asset_type: str = "stock",
    workspace: str = ".",
) -> dict:
    """获取确认日期

    Args:
        trade_date: 交易日期（YYYY-MM-DD）
        asset_type: 资产类型（stock/etf/offshore_fund）
    """
    try:
        from datetime import datetime

        calendar = TradingCalendar()
        dt = datetime.strptime(trade_date, "%Y-%m-%d")
        confirm_date = calendar.get_confirm_date(dt, asset_type)

        return {
            "success": True,
            "data": {
                "trade_date": trade_date,
                "confirm_date": confirm_date.strftime("%Y-%m-%d"),
                "asset_type": asset_type,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
