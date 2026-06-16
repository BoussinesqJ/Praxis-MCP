"""估值分位 MCP 工具层

暴露 2 个工具：
  - get_valuation_percentile  获取指数PE历史分位（Rule 23/24核心）
  - check_rule23_valuation    Rule 23 估值校验（PE<30%分位？）
"""
from __future__ import annotations

from typing import Any


async def get_valuation_percentile(index_code: str = "000300") -> dict[str, Any]:
    """获取指数PE-TTM历史分位

    Args:
        index_code: 指数代码（000300=沪深300, 000016=上证50, 000905=中证500, 000852=中证1000）

    Returns:
        PE当前值、全历史分位、近10年分位、30%/80%分位值
    """
    from praxis.engine.valuation import get_index_pe_percentile

    result = get_index_pe_percentile(index_code)
    if not result:
        return {"success": False, "error": f"无法获取 {index_code} 的PE数据"}

    return {
        "success": True,
        "data": {
            "index_code": result.index_code,
            "index_name": result.index_name,
            "current_pe": result.current_pe,
            "percentile_all_history": result.percentile_all,
            "percentile_10y": result.percentile_10y,
            "pe_30pct_threshold": result.pe_30pct,
            "pe_80pct_threshold": result.pe_80pct,
            "below_30pct": result.below_30pct,
            "above_80pct": result.above_80pct,
            "data_days": result.data_days,
            "rule23_check": "PASS（PE<30%分位，可触发情绪起爆）" if result.below_30pct else "FAIL（PE未到30%分位）",
            "rule24_check": "BLOCKED（PE>80%分位，刚性拦截）" if result.above_80pct else "PASS（PE未超80%分位）",
        },
    }


async def check_valuation_for_all_indices() -> dict[str, Any]:
    """获取所有支持指数的估值分位快照

    Returns:
        沪深300/上证50/中证500/中证1000 的PE分位数据
    """
    from praxis.engine.valuation import get_all_valuations

    results = get_all_valuations()
    if not results:
        return {"success": False, "error": "无法获取任何指数PE数据"}

    return {
        "success": True,
        "data": results,
    }
