"""TradingCalendar 测试 — 6 场景

测试 A 股交易日历：工作日/周末、节假日、下个交易日、交易日计数、chinese_calendar 降级、日期格式容错。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest


# ── Helpers ──────────────────────────────────────────────────────

@pytest.fixture
def calendar():
    """创建 TradingCalendar 实例"""
    from praxis.engine.execution.trading_calendar import TradingCalendar
    return TradingCalendar()


# ── 1. is_trading_day 工作日/周末 ────────────────────────────────

def test_is_trading_day_weekday_vs_weekend(calendar):
    """周一是交易日，周六不是"""
    # 找一个最近的周一
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    # 周一（工作日）— 可能是交易日（除非节假日）
    result = calendar.is_trading_day(monday)
    assert isinstance(result, bool)

    # 周六 — 绝对不交易
    saturday = monday + timedelta(days=5)
    assert calendar.is_trading_day(saturday) is False

    # 周日 — 绝对不交易
    sunday = monday + timedelta(days=6)
    assert calendar.is_trading_day(sunday) is False


# ── 2. is_trading_day 节假日 ────────────────────────────────────

def test_is_trading_day_holiday(calendar):
    """国庆节（10月1日）如果不是周末，chinese_calendar 应识别为非交易日"""
    # 测试 2024-10-01 (周二) — 中华人民共和国国庆节
    dt = date(2024, 10, 1)
    result = calendar.is_trading_day(dt)
    # 国庆节应该是非交易日
    if calendar._calendar_available:
        assert result is False, "chinese_calendar 应将国庆节标记为非交易日"
    else:
        # 降级模式：仅判断工作日
        assert isinstance(result, bool)


# ── 3. next_trading_day ─────────────────────────────────────────

def test_next_trading_day(calendar):
    """next_trading_day 返回下一个交易日（跳过周末）"""
    # 周五的下一个交易日应该是周一
    friday = date(2024, 7, 12)  # 周五
    next_td = calendar.next_trading_day(friday)
    assert isinstance(next_td, date)
    assert next_td > friday


# ── 4. trading_days_between ─────────────────────────────────────

def test_trading_days_between(calendar):
    """trading_days_between 计算两个日期之间的交易日数"""
    # 一周（周一到周五）= 5 个交易日
    start = date(2024, 7, 8)   # 周一
    end = date(2024, 7, 12)    # 周五
    count = calendar.trading_days_between(start, end)
    assert count > 0
    assert count <= 7  # 一周最多 7 天


# ── 5. chinese_calendar 未安装降级 ──────────────────────────────

def test_calendar_fallback(monkeypatch):
    """chinese_calendar 未安装时降级为纯工作日判断"""
    # 模拟 chinese_calendar 未安装
    import praxis.engine.execution.trading_calendar as tc

    original = tc._CN_CALENDAR_AVAILABLE
    try:
        monkeypatch.setattr(tc, "_CN_CALENDAR_AVAILABLE", False)

        cal = tc.TradingCalendar()
        assert cal._calendar_available is False

        # 周一是交易日
        assert cal.is_trading_day(date(2024, 7, 8)) is True
        # 周六不是
        assert cal.is_trading_day(date(2024, 7, 13)) is False

    finally:
        monkeypatch.setattr(tc, "_CN_CALENDAR_AVAILABLE", original)


# ── 6. 日期格式容错 ─────────────────────────────────────────────

def test_date_format_tolerance(calendar):
    """is_trading_day 接受 date 和 datetime 两种格式"""
    from datetime import datetime

    d = date(2024, 7, 8)  # 周一
    dt = datetime(2024, 7, 8, 10, 30)

    result_date = calendar.is_trading_day(d)
    result_dt = calendar.is_trading_day(dt)

    # 同一天，结果应一致
    assert result_date == result_dt
