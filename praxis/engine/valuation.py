"""估值分位引擎 (Valuation Percentile Engine)

Rule 23/24 核心数据源：
  - 指数 PE-TTM 历史分位（乐咕乐股 via AKShare）
  - 个股实时 PE 查询（腾讯行情）
  - 估值底线校验（PE < 30%分位 = 可买 / PE > 80%分位 = 拦截）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("praxis.engine.valuation")

# 支持的指数映射（AKShare stock_index_pe_lg 的 symbol 参数）
INDEX_PE_SYMBOLS = {
    "000300": "沪深300",
    "000016": "上证50",
    "000905": "中证500",
    "000852": "中证1000",
}

# 哨兵ETF对应的宏观指数（用于Rule 23 PE分位判定）
SENTINEL_INDEX_MAP = {
    "510300": "000300",  # 沪深300ETF → 沪深300指数
    "159915": "399006",  # 创业板ETF → 创业板指（暂不支持PE分位）
    "512000": "000300",  # 券商ETF → 沪深300（近似）
    "159601": "000300",  # 恒生科技 → 沪深300（近似）
}


@dataclass
class PEPercentile:
    """PE历史分位结果"""
    index_code: str
    index_name: str
    current_pe: float
    percentile_all: float  # 全历史分位 (%)
    percentile_10y: float  # 近10年分位 (%)
    pe_30pct: float  # 30%分位值
    pe_80pct: float  # 80%分位值
    data_days: int
    below_30pct: bool  # Rule 23 条件：PE < 30%分位
    above_80pct: bool  # Rule 24 条件：PE > 80%分位


def get_index_pe_percentile(index_code: str = "000300") -> Optional[PEPercentile]:
    """获取指数PE-TTM历史分位

    Args:
        index_code: 指数代码（000300/000016/000905/000852）

    Returns:
        PEPercentile 或 None（如果数据不可用）
    """
    index_name = INDEX_PE_SYMBOLS.get(index_code)
    if not index_name:
        logger.warning(f"不支持的指数代码: {index_code}，支持: {list(INDEX_PE_SYMBOLS.keys())}")
        return None

    try:
        import akshare as ak
        df = ak.stock_index_pe_lg(symbol=index_name)
    except Exception as e:
        logger.error(f"获取 {index_name} PE数据失败: {e}")
        return None

    if df is None or len(df) == 0:
        return None

    pe_series = df["滚动市盈率"].dropna()
    if len(pe_series) < 100:
        logger.warning(f"{index_name} PE数据不足: {len(pe_series)} 天")
        return None

    current_pe = float(pe_series.iloc[-1])

    # 全历史分位
    percentile_all = float((pe_series < current_pe).sum() / len(pe_series) * 100)

    # 近10年分位（约2500个交易日）
    recent_10y = pe_series.tail(2500)
    percentile_10y = float((recent_10y < current_pe).sum() / len(recent_10y) * 100)

    # 分位值
    pe_30pct = float(pe_series.quantile(0.3))
    pe_80pct = float(pe_series.quantile(0.8))

    return PEPercentile(
        index_code=index_code,
        index_name=index_name,
        current_pe=current_pe,
        percentile_all=round(percentile_all, 1),
        percentile_10y=round(percentile_10y, 1),
        pe_30pct=round(pe_30pct, 2),
        pe_80pct=round(pe_80pct, 2),
        data_days=len(pe_series),
        below_30pct=current_pe < pe_30pct,
        above_80pct=current_pe > pe_80pct,
    )


def check_rule23_valuation(index_code: str = "000300") -> dict:
    """Rule 23 估值校验：PE < 30% 历史分位？

    Returns:
        {met: bool, pe: float, percentile: float, threshold_30pct: float, index_name: str}
    """
    result = get_index_pe_percentile(index_code)
    if not result:
        return {"met": False, "error": f"无法获取 {index_code} PE数据"}

    return {
        "met": result.below_30pct,
        "index_name": result.index_name,
        "current_pe": result.current_pe,
        "percentile": result.percentile_10y,
        "threshold_30pct": result.pe_30pct,
        "data_days": result.data_days,
    }


def check_rule24_valuation(index_code: str = "000300") -> dict:
    """Rule 24 估值底线校验：PE > 80% 历史分位？

    Returns:
        {blocked: bool, pe: float, percentile: float, threshold_80pct: float, index_name: str}
    """
    result = get_index_pe_percentile(index_code)
    if not result:
        return {"blocked": False, "error": f"无法获取 {index_code} PE数据"}

    return {
        "blocked": result.above_80pct,
        "index_name": result.index_name,
        "current_pe": result.current_pe,
        "percentile": result.percentile_10y,
        "threshold_80pct": result.pe_80pct,
        "data_days": result.data_days,
    }


def get_all_valuations() -> dict:
    """获取所有支持指数的估值分位"""
    results = {}
    for code, name in INDEX_PE_SYMBOLS.items():
        result = get_index_pe_percentile(code)
        if result:
            results[code] = {
                "name": result.index_name,
                "pe": result.current_pe,
                "pct_all": result.percentile_all,
                "pct_10y": result.percentile_10y,
                "pe_30pct": result.pe_30pct,
                "pe_80pct": result.pe_80pct,
                "below_30": result.below_30pct,
                "above_80": result.above_80pct,
            }
    return results
