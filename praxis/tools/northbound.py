"""北向资金 MCP 工具层

暴露 2 个工具：
  - get_northbound_realtime  获取北向资金实时数据
  - get_northbound_history   获取北向资金历史数据
"""
from __future__ import annotations

from typing import Any


async def get_northbound_realtime() -> dict[str, Any]:
    """获取北向资金实时数据

    Returns:
        北向资金实时数据
    """
    from providers.northbound_provider import NorthboundProvider

    provider = NorthboundProvider()
    try:
        result = await provider.get_northbound_realtime()
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_northbound_history(days: int = 5) -> dict[str, Any]:
    """获取北向资金历史数据

    Args:
        days: 获取天数

    Returns:
        北向资金历史数据
    """
    from providers.northbound_provider import NorthboundProvider

    provider = NorthboundProvider()
    try:
        result = await provider.get_northbound_history(days=days)
        return {
            "success": True,
            "data": {
                "history": result,
                "total_days": len(result),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_northbound_flow() -> dict[str, Any]:
    """获取北向资金流向（实时 + 历史）

    Returns:
        北向资金流向数据
    """
    from providers.northbound_provider import NorthboundProvider

    provider = NorthboundProvider()
    try:
        result = await provider.get_northbound_flow()
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
