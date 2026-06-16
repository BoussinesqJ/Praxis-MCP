"""MCP 工具 - 市场数据"""
from __future__ import annotations

from praxis.engine.data.provider import CachedDataProvider


async def get_market_data(tickers: list[str], workspace: str = ".") -> dict:
    """获取实时行情数据

    Args:
        tickers: 标的代码列表
        workspace: 工作目录路径

    Returns:
        实时行情数据（优先使用腾讯/akshare，失败时降级到其他数据源）
    """
    provider = CachedDataProvider(workspace=workspace)
    try:
        result = await provider.get_realtime_quote(tickers)
        # 标记数据新鲜度
        for ticker, data in result.items():
            if "timestamp" in data:
                data["is_realtime"] = True
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await provider.close()
