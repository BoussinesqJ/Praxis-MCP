"""估值分位引擎 — Rule 23/24 核心数据源

支持的指数: 000300(沪深300), 000016(上证50), 000905(中证500), 000852(中证1000)
数据源: AKShare stock_index_pe_lg → PE-TTM 历史分位
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from praxis.core.logging_config import get_logger

logger = get_logger(__name__)

INDEX_PE_SYMBOLS = {
    "000300": "沪深300",
    "000016": "上证50",
    "000905": "中证500",
    "000852": "中证1000",
}


@dataclass
class PEPercentile:
    """PE历史分位结果"""
    index_code: str
    index_name: str
    current_pe: float
    percentile_all: float
    percentile_10y: float
    pe_30pct: float
    pe_80pct: float
    data_days: int
    below_30pct: bool
    above_80pct: bool


async def get_index_pe_percentile(index_code: str = "000300") -> Optional[dict]:
    """获取指数PE-TTM历史分位

    Args:
        index_code: 指数代码

    Returns:
        PE分位结果字典，数据源不可用时返回 None
    """
    if index_code not in INDEX_PE_SYMBOLS:
        logger.error(f"valuation_unsupported_index", index_code=index_code)
        return None

    try:
        import akshare as ak
        symbol_name = INDEX_PE_SYMBOLS.get(index_code, index_code)
        df = ak.stock_index_pe_lg(symbol=symbol_name)
        if df is None or len(df) == 0:
            logger.warning(f"valuation_no_data", index_code=index_code)
            return None

        # 使用"滚动市盈率"(PE-TTM)列，更准确地反映当前估值水平
        pe_col = "滚动市盈率" if "滚动市盈率" in df.columns else ("PE" if "PE" in df.columns else df.columns[2])
        current_pe = float(df[pe_col].iloc[-1])
        pe_values = df[pe_col].dropna().astype(float).values

        if len(pe_values) < 20:
            return None

        percentile_all = (pe_values < current_pe).sum() / len(pe_values) * 100
        recent_10y = pe_values[-2500:] if len(pe_values) > 2500 else pe_values
        percentile_10y = (recent_10y < current_pe).sum() / len(recent_10y) * 100

        pe_sorted = sorted(pe_values)
        pe_30 = pe_sorted[int(len(pe_sorted) * 0.3)]
        pe_80 = pe_sorted[int(len(pe_sorted) * 0.8)]

        return {
            "index_code": index_code,
            "index_name": INDEX_PE_SYMBOLS.get(index_code, index_code),
            "current_pe": round(current_pe, 2),
            "percentile_all": round(percentile_all, 1),
            "percentile_10y": round(percentile_10y, 1),
            "pe_30pct": round(pe_30, 2),
            "pe_80pct": round(pe_80, 2),
            "data_days": len(pe_values),
            "below_30pct": percentile_all < 30,
            "above_80pct": percentile_all > 80,
            "valuation_level": "undervalued" if percentile_all < 30 else ("overvalued" if percentile_all > 80 else "fair"),
        }
    except ImportError:
        logger.warning("valuation_akshare_not_installed")
        return None
    except Exception as e:
        logger.error(f"valuation_fetch_error", index_code=index_code, error=str(e))
        return None


async def get_valuation_percentile(index_code: str = "000300") -> dict:
    """获取单指数PE分位"""
    result = await get_index_pe_percentile(index_code)
    if result is None:
        return {"success": False, "error": f"无法获取 {index_code} 的PE分位数据。请确认 akshare 已安装且网络正常。"}
    return {"success": True, "data": result}


async def check_valuation_for_all_indices() -> dict:
    """获取所有支持指数的估值快照"""
    results = {}
    errors = []
    for code, name in INDEX_PE_SYMBOLS.items():
        result = await get_index_pe_percentile(code)
        if result:
            results[code] = result
        else:
            errors.append(code)

    return {
        "success": len(errors) == 0,
        "data": {
            "indices": results,
            "timestamp": "",
            "summary": {
                "total": len(INDEX_PE_SYMBOLS),
                "available": len(results),
                "errors": errors,
            },
        },
    }
