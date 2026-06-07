"""MCP 工具 - 基准指数"""
from __future__ import annotations

from datetime import datetime, timedelta

from praxis.engine.data.benchmark import TencentBenchmarkProvider


async def get_benchmark_data(index_code: str, days: int = 60) -> dict:
    """获取基准指数数据"""
    provider = TencentBenchmarkProvider()
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        kline = await provider.get_daily_kline(index_code, start_date, end_date)
        latest = await provider.get_latest_price(index_code)
        return {
            "success": True,
            "data": {
                "index_code": index_code,
                "latest": latest,
                "kline_count": len(kline),
                "kline": kline[-10:],
                "date_range": {"start": start_date, "end": end_date},
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await provider.close()


def list_benchmarks() -> dict:
    """列出支持的基准指数"""
    provider = TencentBenchmarkProvider()
    indices = provider.get_supported_indices()
    return {
        "success": True,
        "data": {"benchmarks": indices},
    }
