"""哨兵雷达 MCP 工具层

暴露 4 个工具：
  - scan_sentinel_radar   执行哨兵雷达扫描（获取8个哨兵实时数据+MA20多空判定）
  - get_rule23_status     获取 Rule 23 情绪起爆器验证状态
  - get_sentinel_history  获取哨兵历史记录
"""
from __future__ import annotations

from typing import Any


async def scan_sentinel_radar(workspace: str = ".") -> dict[str, Any]:
    """执行哨兵雷达扫描

    获取 8 个哨兵 ETF 的实时价格 + 历史K线，计算 MA10/MA20/MA30/MA60，
    判定多空趋势，统计多头数，输出攻防状态和 Rule 23 验证结果。

    Returns:
        哨兵扫描结果，包含每个哨兵的多空状态、多头总数、攻防状态、Rule 23 连续天数
    """
    from praxis.engine.sentinel import SentinelEngine

    engine = SentinelEngine(workspace=workspace)
    snapshot = await engine.scan()

    # 构建分层结果
    macro_layer = []
    execution_layer = []
    for ticker, state_data in snapshot.sentinels.items():
        entry = {
            "ticker": ticker,
            "name": state_data["name"],
            "price": state_data["price"],
            "change_pct": round(state_data["change_pct"], 2),
            "ma20": round(state_data["ma20"], 4),
            "trend": state_data["trend"],
            "vol_desc": state_data["vol_desc"],
        }
        if state_data["layer"] == "macro":
            macro_layer.append(entry)
        else:
            execution_layer.append(entry)

    return {
        "success": True,
        "data": {
            "date": snapshot.date,
            "bullish_count": snapshot.bullish_count,
            "total": snapshot.total,
            "state": snapshot.state,
            "position_limit_pct": snapshot.position_limit_pct,
            "rule23": {
                "consecutive_days": snapshot.rule23_consecutive_days,
                "triggered": snapshot.rule23_triggered,
                "days_needed": max(0, 5 - snapshot.rule23_consecutive_days),
            },
            "macro_layer": macro_layer,
            "execution_layer": execution_layer,
        },
    }


async def get_rule23_status(workspace: str = ".") -> dict[str, Any]:
    """获取 Rule 23 情绪起爆器验证状态

    返回当前连续 ≤2 多头哨兵的天数、是否已触发、以及最近 5 天的历史记录。

    Returns:
        Rule 23 状态：连续天数、触发状态、最近历史
    """
    from praxis.engine.sentinel import SentinelEngine

    engine = SentinelEngine(workspace=workspace)
    status = engine.get_rule23_status()

    return {
        "success": True,
        "data": {
            "consecutive_days": status["consecutive_days"],
            "triggered": status["triggered"],
            "days_needed": max(0, 5 - status["consecutive_days"]),
            "latest": status.get("latest"),
            "recent_history": status.get("recent_history", []),
        },
    }


async def get_sentinel_history(days: int = 10, workspace: str = ".") -> dict[str, Any]:
    """获取哨兵历史记录

    Args:
        days: 返回最近 N 天的记录（默认 10）

    Returns:
        哨兵历史快照列表
    """
    from praxis.engine.sentinel import SentinelEngine

    engine = SentinelEngine(workspace=workspace)
    history = engine.get_history(days=days)

    return {
        "success": True,
        "data": {
            "records": history,
            "total_days": len(history),
        },
    }
