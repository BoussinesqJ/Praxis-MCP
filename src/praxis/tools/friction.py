"""摩擦成本 — trading_friction"""
from __future__ import annotations
from praxis.agents.base import Tool
from praxis.tools._schemas import TradingFrictionInput
from praxis.engine.execution.fee_model import FeeModel
from praxis.engine.execution.slippage_model import SlippageModel
from praxis.engine.execution.trading_calendar import TradingCalendar

async def trading_friction(action: str, ticker: str | None = None, asset_type: str | None = None,
                           trade_action: str | None = None, quantity: float | None = None,
                           price: float | None = None, volume: float | None = None,
                           volatility: float | None = None, timestamp: str | None = None,
                           trade_date: str | None = None, _deps: dict | None = None) -> dict:
    if action == "fee":
        if not all([ticker, trade_action, quantity, price]):
            return {"success": False, "error": "缺少必填参数"}
        result = FeeModel.calculate(ticker, asset_type or "stock", trade_action, quantity, price)
        return {"success": True, "data": result}
    elif action == "slippage":
        if not all([price, trade_action]):
            return {"success": False, "error": "缺少 price, trade_action"}
        model = SlippageModel()
        result = model.estimate(price, trade_action, volume or 0, volatility)
        return {"success": True, "data": result}
    elif action == "trading_time":
        cal = TradingCalendar()
        from datetime import datetime
        now = datetime.now()
        return {"success": True, "data": {"is_trading_time": cal.is_trading_time(now),
                                           "is_trading_day": cal.is_trading_day(now)}}
    elif action == "confirm_date":
        if not trade_date:
            return {"success": False, "error": "需要 trade_date"}
        cal = TradingCalendar()
        from datetime import datetime as dt
        d = dt.fromisoformat(trade_date)
        result = cal.get_confirm_date(d, asset_type or "stock")
        return {"success": True, "data": {"confirm_date": str(result)}}
    return {"success": False, "error": f"未知 action: {action}"}

def register(registry):
    registry.register(Tool(name="trading_friction", description="交易摩擦成本：费用/滑点/交易时间/确认日期",
                           input_schema=TradingFrictionInput, handler=trading_friction, agent_name="risk", tier="core"))
