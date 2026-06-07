"""交易日历测试（合并版）"""
import pytest
from datetime import datetime
from praxis.engine.execution.trading_calendar import TradingCalendar, TradingCalendarConfig


class TestTradingCalendar:
    """交易日历测试"""

    def setup_method(self):
        self.calendar = TradingCalendar()

    # ── 日期判断 ──

    def test_is_trading_day_weekday(self):
        """工作日是交易日"""
        assert self.calendar.is_trading_day("2026-06-08") is True

    def test_is_trading_day_weekend(self):
        """周末不是交易日"""
        assert self.calendar.is_trading_day("2026-06-06") is False  # 周六
        assert self.calendar.is_trading_day("2026-06-07") is False  # 周日

    def test_is_trading_day_holiday(self):
        """节假日不是交易日"""
        self.calendar._holidays.add("2026-06-08")
        assert self.calendar.is_trading_day("2026-06-08") is False

    def test_is_trading_day_datetime(self):
        """支持 datetime 参数"""
        dt = datetime(2026, 6, 8)  # 周一
        assert self.calendar.is_trading_day(dt) is True

    # ── 交易时段 ──

    def test_is_trading_time_morning(self):
        """上午交易时段（9:30-11:30）"""
        dt = datetime(2026, 6, 8, 10, 30)  # 周一 10:30
        assert self.calendar.is_trading_time(dt) is True

    def test_is_trading_time_afternoon(self):
        """下午交易时段（13:00-15:00）"""
        dt = datetime(2026, 6, 8, 14, 0)  # 周一 14:00
        assert self.calendar.is_trading_time(dt) is True

    def test_is_trading_time_lunch_break(self):
        """午休时间不是交易时间"""
        dt = datetime(2026, 6, 8, 12, 0)  # 周一 12:00
        assert self.calendar.is_trading_time(dt) is False

    def test_is_trading_time_before_open(self):
        """开盘前不是交易时间"""
        dt = datetime(2026, 6, 8, 9, 0)  # 周一 9:00
        assert self.calendar.is_trading_time(dt) is False

    def test_is_trading_time_weekend(self):
        """周末不是交易时间"""
        dt = datetime(2026, 6, 6, 10, 30)  # 周六 10:30
        assert self.calendar.is_trading_time(dt) is False

    def test_is_offshore_fund_trading_time(self):
        """场外基金交易时间"""
        dt = datetime(2026, 6, 8, 14, 50)  # 周一 14:50
        assert self.calendar.is_offshore_fund_trading_time(dt) is True

    def test_is_offshore_fund_trading_time_after_cutoff(self):
        """场外基金截止时间后不可交易"""
        dt = datetime(2026, 6, 8, 15, 10)  # 周一 15:10
        assert self.calendar.is_offshore_fund_trading_time(dt) is False

    # ── 日期计算 ──

    def test_next_trading_day(self):
        """下一个交易日（跨周末）"""
        result = self.calendar.next_trading_day("2026-06-05")
        assert result == "2026-06-08"

    def test_next_trading_day_skip_holiday(self):
        """下一个交易日（跳过节假日）"""
        self.calendar._holidays.add("2026-06-08")
        result = self.calendar.next_trading_day("2026-06-05")
        assert result == "2026-06-09"

    def test_prev_trading_day(self):
        """上一个交易日"""
        result = self.calendar.prev_trading_day("2026-06-08")
        assert result == "2026-06-05"

    def test_settlement_date(self):
        """T+1 交割日"""
        result = self.calendar.settlement_date("2026-06-05")
        assert result == "2026-06-08"

    def test_get_confirm_date_stock(self):
        """股票 T+1 确认日"""
        dt = datetime(2026, 6, 5)  # 周五
        result = self.calendar.get_confirm_date(dt, "stock")
        assert result == datetime(2026, 6, 8)  # 周一

    def test_get_confirm_date_offshore_fund(self):
        """场外基金 T+N 确认日"""
        dt = datetime(2026, 6, 5)  # 周五
        result = self.calendar.get_confirm_date(dt, "offshore_fund")
        # T+1 = 周一
        assert result == datetime(2026, 6, 8)

    def test_trading_days_between(self):
        """两个日期之间的交易日数"""
        result = self.calendar.trading_days_between("2026-06-05", "2026-06-08")
        assert result == 2  # 周五 + 周一

    def test_trading_days_between_same_day(self):
        """同一天的交易日数"""
        result = self.calendar.trading_days_between("2026-06-08", "2026-06-08")
        assert result == 1

    def test_default_holidays_loaded(self):
        """默认节假日已加载"""
        assert "2026-01-01" in self.calendar._holidays
        assert "2026-10-01" in self.calendar._holidays
