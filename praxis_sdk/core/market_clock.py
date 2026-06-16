"""
Praxis 交易时钟 (Market Clock)
自动核检系统当前时间，标注市场状态

用法：
  from praxis_sdk.core.market_clock import MarketClock, get_market_clock
  
  clock = get_market_clock()
  print(clock.get_status_label())  # [盘前/盘中/午休/收盘]
"""

from datetime import datetime, time
from typing import Optional
import pytz


class MarketClock:
    """交易时钟"""
    
    # A股交易时间（北京时间）
    MARKET_TZ = pytz.timezone("Asia/Shanghai")
    
    MORNING_OPEN = time(9, 30)
    MORNING_CLOSE = time(11, 30)
    AFTERNOON_OPEN = time(13, 0)
    AFTERNOON_CLOSE = time(15, 0)
    
    # 盘前/盘后
    PRE_MARKET_START = time(9, 15)
    POST_MARKET_END = time(15, 30)
    
    def __init__(self):
        self._now = None
        self._update_time()
    
    def _update_time(self):
        """更新当前时间"""
        self._now = datetime.now(self.MARKET_TZ)
    
    @property
    def now(self) -> datetime:
        """当前北京时间"""
        self._update_time()
        return self._now
    
    @property
    def current_time(self) -> time:
        """当前时间（时分秒）"""
        return self.now.time()
    
    @property
    def is_weekday(self) -> bool:
        """是否工作日"""
        return self.now.weekday() < 5  # 0-4 = 周一到周五
    
    @property
    def market_phase(self) -> str:
        """
        获取市场阶段。
        
        Returns:
            "pre_market" | "morning_session" | "lunch_break" | "afternoon_session" | "post_market" | "closed"
        """
        if not self.is_weekday:
            return "closed"
        
        t = self.current_time
        
        if t < self.PRE_MARKET_START:
            return "closed"
        elif t < self.MORNING_OPEN:
            return "pre_market"
        elif t < self.MORNING_CLOSE:
            return "morning_session"
        elif t < self.AFTERNOON_OPEN:
            return "lunch_break"
        elif t < self.AFTERNOON_CLOSE:
            return "afternoon_session"
        elif t < self.POST_MARKET_END:
            return "post_market"
        else:
            return "closed"
    
    @property
    def is_trading(self) -> bool:
        """是否在交易时段"""
        return self.market_phase in ("morning_session", "afternoon_session")
    
    @property
    def is_lunch_break(self) -> bool:
        """是否午休"""
        return self.market_phase == "lunch_break"
    
    @property
    def is_closed(self) -> bool:
        """是否收盘"""
        return self.market_phase in ("closed", "post_market")
    
    def get_status_label(self) -> str:
        """
        获取状态标签。
        
        Returns:
            "[盘前]" | "[盘中]" | "[午休]" | "[收盘]"
        """
        phase = self.market_phase
        
        if phase == "pre_market":
            return "[盘前]"
        elif phase == "morning_session":
            return "[盘中]"
        elif phase == "lunch_break":
            return "[午间休市]"
        elif phase == "afternoon_session":
            return "[盘中]"
        elif phase == "post_market":
            return "[收盘]"
        else:
            return "[非交易日]"
    
    def get_status_label_with_time(self) -> str:
        """
        获取带时间的状态标签。
        
        Returns:
            "[盘中 10:30]" | "[午间休市 12:10]" | "[收盘 15:00]"
        """
        label = self.get_status_label()
        time_str = self.now.strftime("%H:%M")
        return f"{label} {time_str}"
    
    def get_last_close_time(self) -> datetime:
        """
        获取最近一次收盘时间。
        
        Returns:
            最近收盘时间的 datetime 对象
        """
        now = self.now
        
        if self.is_trading:
            # 盘中，返回今天上午收盘或昨天下午收盘
            if self.market_phase == "morning_session":
                # 上午盘中，返回昨天收盘
                return now.replace(hour=15, minute=0, second=0, microsecond=0) - \
                       __import__('datetime').timedelta(days=1)
            else:
                # 下午盘中，返回今天上午收盘
                return now.replace(hour=11, minute=30, second=0, microsecond=0)
        elif self.is_lunch_break:
            # 午休，返回今天上午收盘
            return now.replace(hour=11, minute=30, second=0, microsecond=0)
        else:
            # 收盘或非交易日，返回最近收盘
            if now.hour >= 15:
                return now.replace(hour=15, minute=0, second=0, microsecond=0)
            else:
                return now.replace(hour=15, minute=0, second=0, microsecond=0) - \
                       __import__('datetime').timedelta(days=1)
    
    def get_last_close_label(self) -> str:
        """
        获取最近收盘时间标签。
        
        Returns:
            "11:30 收盘确权" | "15:00 收盘确权"
        """
        close_time = self.get_last_close_time()
        return f"{close_time.strftime('%H:%M')} 收盘确权"
    
    def should_use_realtime(self) -> bool:
        """
        是否应该使用实时数据。
        
        Returns:
            True 如果在交易时段，False 如果在非交易时段
        """
        return self.is_trading
    
    def should_use_cache(self) -> bool:
        """
        是否应该使用缓存数据。
        
        Returns:
            True 如果在非交易时段（午休/收盘），False 如果在交易时段
        """
        return not self.is_trading
    
    def get_report_header(self) -> str:
        """
        获取报告头部。
        
        Returns:
            带时间状态的报告头部
        """
        label = self.get_status_label_with_time()
        
        if self.is_trading:
            return f"**数据时效**：{label} | 实时数据"
        elif self.is_lunch_break:
            return f"**数据时效**：{label} | 价格参考 {self.get_last_close_label()}"
        else:
            return f"**数据时效**：{label} | 价格参考 {self.get_last_close_label()}"
    
    def validate_conclusion(self, conclusion: str) -> tuple[bool, str]:
        """
        验证结论是否符合时钟约束。
        
        Args:
            conclusion: 结论文本
        
        Returns:
            (is_valid, reason)
        """
        # 禁止在非交易时段使用"实时脉冲"、"盘中确权"等字眼
        forbidden_phrases = ["实时脉冲", "盘中确权", "实时信号", "盘中异动"]
        
        if not self.is_trading:
            for phrase in forbidden_phrases:
                if phrase in conclusion:
                    return False, f"非交易时段禁止使用 '{phrase}'"
        
        return True, ""


# 全局实例
_global_clock = MarketClock()


def get_market_clock() -> MarketClock:
    """获取全局交易时钟实例"""
    return _global_clock
