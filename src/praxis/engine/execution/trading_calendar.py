"""交易日历 — chinese_calendar 集成

提供 A 股交易日判断、交易时段判断、确认日计算。
所有时间/日期判断使用北京时间（UTC+8）。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from praxis.core.logging_config import get_logger

logger = get_logger(__name__)

# 交易日历依赖（可选安装，缺失时降级为纯工作日判断）
try:
    from chinese_calendar import is_workday as _cn_is_workday
    from chinese_calendar import is_holiday as _cn_is_holiday

    _CN_CALENDAR_AVAILABLE = True
except ImportError:
    _CN_CALENDAR_AVAILABLE = False
    logger.info("chinese_calendar 未安装，交易日历降级为纯工作日判断")


# 交易时段定义（北京时间）
MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)


class TradingCalendar:
    """A 股交易日历

    集成 chinese_calendar 实现准确的节假日判断。
    如果 chinese_calendar 未安装，降级为纯工作日判断。

    Usage:
        cal = TradingCalendar()
        cal.is_trading_day(date.today())  # → True/False
        cal.is_trading_time(datetime.now())  # → True/False
        cal.get_confirm_date(date.today(), "stock")  # → 预计确认日
    """

    def __init__(self) -> None:
        """初始化交易日历"""
        self._calendar_available = _CN_CALENDAR_AVAILABLE

    # ── 交易日判断 ─────────────────────────────────────────────

    def is_trading_day(self, dt: date | datetime) -> bool:
        """判断是否为交易日

        规则：
        1. 工作日（周一至周五）
        2. 排除中国法定节假日
        3. 排除周末调休工作日（如果需要严格判断）

        Args:
            dt: 要检查的日期

        Returns:
            True 如果是交易日
        """
        if isinstance(dt, datetime):
            d = dt.date()
        else:
            d = dt

        # 周末一定不是交易日
        if d.weekday() >= 5:
            return False

        # 使用 chinese_calendar 精确判断
        if self._calendar_available:
            try:
                return _cn_is_workday(d)
            except Exception:
                pass

        # 降级：纯工作日判断（周一至周五）
        return True

    # ── 交易时段判断 ───────────────────────────────────────────

    def is_trading_time(self, dt: datetime | None = None) -> bool:
        """判断当前是否在交易时段内

        A 股交易时段：
        - 上午：9:30 - 11:30
        - 下午：13:00 - 15:00

        Args:
            dt: 要检查的时间，默认为当前时间

        Returns:
            True 如果在交易时段内
        """
        if dt is None:
            dt = datetime.now()

        # 交易日检查
        if not self.is_trading_day(dt):
            return False

        t = dt.time()

        # 上午时段
        if MORNING_START <= t <= MORNING_END:
            return True

        # 下午时段
        if AFTERNOON_START <= t <= AFTERNOON_END:
            return True

        return False

    def is_morning_session(self, dt: datetime | None = None) -> bool:
        """判断是否在上午交易时段（9:30-11:30）"""
        if dt is None:
            dt = datetime.now()
        if not self.is_trading_day(dt):
            return False
        t = dt.time()
        return MORNING_START <= t <= MORNING_END

    def is_afternoon_session(self, dt: datetime | None = None) -> bool:
        """判断是否在下午交易时段（13:00-15:00）"""
        if dt is None:
            dt = datetime.now()
        if not self.is_trading_day(dt):
            return False
        t = dt.time()
        return AFTERNOON_START <= t <= AFTERNOON_END

    # ── 确认日计算 ─────────────────────────────────────────────

    def get_confirm_date(
        self, dt: date | datetime, asset_type: str = "stock"
    ) -> date:
        """计算交易的预计确认日

        不同资产类型的确认规则：
        - stock/etf: T+1（下一个交易日）
        - offshore_fund: T+2~T+4（海外基金，实际按 T+3 估算）

        Args:
            dt: 交易日期
            asset_type: 资产类型 (stock/etf/offshore_fund/bond)

        Returns:
            预计确认日期
        """
        if isinstance(dt, datetime):
            d = dt.date()
        else:
            d = dt

        if asset_type in ("stock", "etf", "bond"):
            # T+1：下一个交易日
            return self._next_trading_day(d)
        elif asset_type == "offshore_fund":
            # T+3：海外基金确认较慢
            result = d
            for _ in range(3):
                result = self._next_trading_day(result)
            return result
        else:
            # 未知类型默认 T+1
            return self._next_trading_day(d)

    def _next_trading_day(self, d: date) -> date:
        """获取下一个交易日"""
        next_day = d + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
        return next_day

    # ── 距离最近交易日 ─────────────────────────────────────────

    def next_trading_day(self, dt: date | datetime | None = None) -> date:
        """获取下一个交易日（不含当天）

        Args:
            dt: 参考日期，默认为今天

        Returns:
            下一个交易日的日期
        """
        if dt is None:
            d = date.today()
        elif isinstance(dt, datetime):
            d = dt.date()
        else:
            d = dt

        return self._next_trading_day(d)

    def prev_trading_day(self, dt: date | datetime | None = None) -> date:
        """获取上一个交易日（不含当天）"""
        if dt is None:
            d = date.today()
        elif isinstance(dt, datetime):
            d = dt.date()
        else:
            d = dt

        prev = d - timedelta(days=1)
        while not self.is_trading_day(prev):
            prev -= timedelta(days=1)
        return prev

    # ── 交易时段名称 ───────────────────────────────────────────

    def get_session_name(self, dt: datetime | None = None) -> str:
        """获取当前所处的交易时段名称

        Returns:
            'morning' | 'afternoon' | 'closed' | 'non_trading_day'
        """
        if dt is None:
            dt = datetime.now()

        if not self.is_trading_day(dt):
            return "non_trading_day"

        t = dt.time()

        if MORNING_START <= t <= MORNING_END:
            return "morning"
        elif AFTERNOON_START <= t <= AFTERNOON_END:
            return "afternoon"
        else:
            return "closed"

    # ── 统计查询 ───────────────────────────────────────────────

    def trading_days_between(
        self, start: date, end: date
    ) -> int:
        """计算两个日期之间的交易日天数（含起止日）

        Args:
            start: 起始日期
            end: 结束日期

        Returns:
            交易日数量
        """
        if start > end:
            start, end = end, start

        count = 0
        current = start
        while current <= end:
            if self.is_trading_day(current):
                count += 1
            current += timedelta(days=1)
        return count

    def is_settlement_day(self, dt: date | datetime) -> bool:
        """判断是否为基金净值结算日

        规则：交易日 15:00 后算下一个交易日的净值。

        Args:
            dt: 要检查的日期时间

        Returns:
            True 如果是结算日
        """
        if not self.is_trading_day(dt):
            return False

        # 如果是交易日且在 15:00 之后，按下一个交易日结算
        if isinstance(dt, datetime) and dt.time() >= AFTERNOON_END:
            return False

        return True
