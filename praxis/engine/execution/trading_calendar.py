"""交易日历（合并版）

合并 engine/trading_calendar.py 的交易时段判断 + engine/execution/ 的 YAML 节假日加载。
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path

import yaml

from pydantic import BaseModel


class TradingCalendarConfig(BaseModel):
    """交易日历配置"""
    market_open_am: str = "09:30"
    market_close_am: str = "11:30"
    market_open_pm: str = "13:00"
    market_close_pm: str = "15:00"
    offshore_fund_cutoff: str = "15:00"   # 场外基金申购截止时间
    offshore_fund_confirm_days: int = 1   # 场外基金确认天数（T+N）


class TradingCalendar:
    """A 股交易日历"""

    # 2026 年法定节假日
    DEFAULT_HOLIDAYS_2026 = [
        "2026-01-01", "2026-01-02", "2026-01-03",          # 元旦
        "2026-01-26", "2026-01-27", "2026-01-28",          # 春节
        "2026-01-29", "2026-01-30",
        "2026-04-04", "2026-04-05", "2026-04-06",          # 清明节
        "2026-05-01", "2026-05-02", "2026-05-03",          # 劳动节
        "2026-05-04", "2026-05-05",
        "2026-06-19", "2026-06-20", "2026-06-21",          # 端午节
        "2026-10-01", "2026-10-02", "2026-10-03",          # 国庆节
        "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07",
    ]

    def __init__(
        self,
        config: TradingCalendarConfig | None = None,
        holidays_path: str | Path | None = None,
    ):
        self._config = config or TradingCalendarConfig()
        self._holidays: set[str] = set(self.DEFAULT_HOLIDAYS_2026)
        if holidays_path:
            self._load_holidays(holidays_path)

    def _load_holidays(self, path: str | Path):
        """从 YAML 文件加载额外节假日"""
        path = Path(path)
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and "holidays" in data:
            for holiday in data["holidays"]:
                if isinstance(holiday, str):
                    self._holidays.add(holiday)
                elif isinstance(holiday, dict) and "date" in holiday:
                    self._holidays.add(holiday["date"])

    # ── 日期判断 ──

    def is_trading_day(self, date: str | datetime) -> bool:
        """判断是否为交易日"""
        if isinstance(date, datetime):
            date_str = date.strftime("%Y-%m-%d")
        else:
            date_str = date
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt.weekday() >= 5:
            return False
        if date_str in self._holidays:
            return False
        return True

    def is_trading_time(self, dt: datetime) -> bool:
        """判断是否在交易时间内（含午休判断）"""
        if not self.is_trading_day(dt):
            return False
        t = dt.time()
        am_start = time(*map(int, self._config.market_open_am.split(":")))
        am_end = time(*map(int, self._config.market_close_am.split(":")))
        pm_start = time(*map(int, self._config.market_open_pm.split(":")))
        pm_end = time(*map(int, self._config.market_close_pm.split(":")))
        return (am_start <= t <= am_end) or (pm_start <= t <= pm_end)

    def is_offshore_fund_trading_time(self, dt: datetime) -> bool:
        """判断是否在场外基金交易时间内"""
        if not self.is_trading_day(dt):
            return False
        t = dt.time()
        cutoff = time(*map(int, self._config.offshore_fund_cutoff.split(":")))
        return t <= cutoff

    # ── 日期计算 ──

    def next_trading_day(self, date: str | datetime) -> str:
        """获取下一个交易日"""
        if isinstance(date, datetime):
            dt = date
        else:
            dt = datetime.strptime(date, "%Y-%m-%d")
        while True:
            dt += timedelta(days=1)
            if self.is_trading_day(dt):
                return dt.strftime("%Y-%m-%d")

    def prev_trading_day(self, date: str | datetime) -> str:
        """获取上一个交易日"""
        if isinstance(date, datetime):
            dt = date
        else:
            dt = datetime.strptime(date, "%Y-%m-%d")
        while True:
            dt -= timedelta(days=1)
            if self.is_trading_day(dt):
                return dt.strftime("%Y-%m-%d")

    def settlement_date(self, trade_date: str | datetime) -> str:
        """获取交割日（T+1）"""
        return self.next_trading_day(trade_date)

    def get_confirm_date(self, trade_date: datetime, asset_type: str) -> datetime:
        """获取确认日期

        股票/ETF: T+1（跳过非交易日）
        场外基金: T+N（可配置）
        """
        if asset_type == "offshore_fund":
            confirm_days = self._config.offshore_fund_confirm_days
            current = trade_date
            added = 0
            while added < confirm_days:
                current += timedelta(days=1)
                if self.is_trading_day(current):
                    added += 1
            return current
        else:
            current = trade_date + timedelta(days=1)
            while not self.is_trading_day(current):
                current += timedelta(days=1)
            return current

    def trading_days_between(self, start: str | datetime, end: str | datetime) -> int:
        """计算两个日期之间的交易日数"""
        if isinstance(start, datetime):
            start_dt = start
        else:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
        if isinstance(end, datetime):
            end_dt = end
        else:
            end_dt = datetime.strptime(end, "%Y-%m-%d")

        count = 0
        current = start_dt
        while current <= end_dt:
            if self.is_trading_day(current):
                count += 1
            current += timedelta(days=1)
        return count
