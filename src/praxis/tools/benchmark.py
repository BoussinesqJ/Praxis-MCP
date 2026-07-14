"""基准指数 — benchmark"""
from __future__ import annotations
from praxis.agents.base import Tool
from praxis.tools._schemas import BenchmarkInput

BENCHMARKS = {"000300": "沪深300", "000905": "中证500", "399006": "创业板指", "000016": "上证50"}

async def benchmark(action: str, index_code: str | None = None, days: int = 60,
                    _deps: dict | None = None) -> dict:
    if action == "list":
        return {"success": True, "data": [{"code": k, "name": v} for k, v in BENCHMARKS.items()]}
    elif action == "data":
        if not index_code:
            return {"success": False, "error": "需要 index_code"}
        provider = _deps.get("data_provider") if _deps else None
        if provider:
            try:
                kline = await provider.get_history_kline(index_code, "day", days)
                return {"success": True, "data": kline}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "DataProvider未注入"}
    return {"success": False, "error": f"未知 action: {action}"}

def register(registry):
    registry.register(Tool(name="benchmark", description="基准指数数据：K线查询/指数列表",
                           input_schema=BenchmarkInput, handler=benchmark, agent_name="market", tier="core"))
