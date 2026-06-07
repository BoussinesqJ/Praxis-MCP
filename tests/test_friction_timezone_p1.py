"""P1 - 交易时间检查跨时区与北京时间校验测试"""
from datetime import datetime, timezone, timedelta
from praxis.tools.friction import check_trading_time


def test_check_trading_time_utc_conversion():
    """测试将 UTC 传入时间，正确转换为北京时间 (+08:00) 进行交易时段校验"""
    # 假设传入的 UTC 时间是 2026-06-08T02:00:00Z (星期一)
    # 对应的北京时间是 2026-06-08T10:00:00+08:00 (在 A 股上午交易时段 09:30-11:30 内)
    result = check_trading_time(
        timestamp="2026-06-08T02:00:00Z",
        asset_type="stock"
    )
    
    assert result["success"] is True
    data = result["data"]
    
    # 验证最终转换输出的时间是 +08:00 时区
    dt_out = datetime.fromisoformat(data["timestamp"])
    assert dt_out.tzinfo is not None
    assert dt_out.tzinfo.utcoffset(dt_out) == timedelta(hours=8)
    
    # 因为 10:00 是交易时段，应该可以通过交易时间校验
    assert data["is_trading_day"] is True
    assert data["is_trading_time"] is True
    assert data["can_trade"] is True


def test_check_trading_time_naive_assumed_beijing():
    """测试传入 naive 的时间戳，直接视作北京时间并正确解析时区"""
    # 传入 "2026-06-08T10:00:00"
    result = check_trading_time(
        timestamp="2026-06-08T10:00:00",
        asset_type="stock"
    )
    
    assert result["success"] is True
    data = result["data"]
    
    dt_out = datetime.fromisoformat(data["timestamp"])
    assert dt_out.tzinfo.utcoffset(dt_out) == timedelta(hours=8)
    assert data["is_trading_time"] is True
