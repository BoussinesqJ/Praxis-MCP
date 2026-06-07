"""AKShare 数据源适配器

依赖: pip install akshare
数据源: 东方财富/新浪/同花顺/巨潮等（AKShare 统一封装）
"""
from __future__ import annotations

import logging
from datetime import datetime

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError

logger = logging.getLogger("praxis.data.akshare")

try:
    import akshare as ak
    import pandas as pd
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False


def _ensure_akshare():
    if not HAS_AKSHARE:
        raise ImportError(
            "AKShare 未安装。请执行: pip install akshare 或 pip install praxis[akshare]"
        )


class AKShareDataProvider(DataProvider):
    """AKShare 数据源（多源聚合，零 API Key）"""

    def __init__(self):
        _ensure_akshare()

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情

        AKShare 使用东方财富的实时行情接口，一次性获取全市场数据。
        对于少量 ticker，从全量数据中筛选更高效。
        """
        if not tickers:
            return {}

        _ensure_akshare()
        try:
            # 获取 A 股实时行情（东方财富源）
            df = ak.stock_zh_a_spot_em()
        except Exception as e:
            raise DataError(f"AKShare 实时行情请求失败: {e}", source="akshare")

        result = {}
        for ticker in tickers:
            row = df[df["代码"] == ticker]
            if row.empty:
                continue
            row = row.iloc[0]
            try:
                result[ticker] = {
                    "name": str(row.get("名称", "")),
                    "ticker": ticker,
                    "price": float(row.get("最新价", 0) or 0),
                    "prev_close": float(row.get("昨收", 0) or 0),
                    "open": float(row.get("今开", 0) or 0),
                    "volume": int(float(row.get("成交量", 0) or 0)),
                    "high": float(row.get("最高", 0) or 0),
                    "low": float(row.get("最低", 0) or 0),
                    "change": float(row.get("涨跌额", 0) or 0),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                    "amount": float(row.get("成交额", 0) or 0),
                    "turnover": float(row.get("换手率", 0) or 0),
                    "pe_ratio": float(row.get("市盈率-动态", 0) or 0),
                    "market_cap": float(row.get("总市值", 0) or 0),
                    "timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "source": "akshare",
                }
            except (ValueError, TypeError) as e:
                logger.warning(f"AKShare 解析 {ticker} 失败: {e}")
                continue

        return result

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线"""
        _ensure_akshare()
        try:
            period_map = {"day": "daily", "week": "weekly", "month": "monthly"}
            ak_period = period_map.get(period, "daily")

            df = ak.stock_zh_a_hist(
                symbol=ticker,
                period=ak_period,
                adjust="qfq",  # 前复权
            )
        except Exception as e:
            raise DataError(f"AKShare K线请求失败: {e}", source="akshare")

        if df is None or df.empty:
            return []

        # 取最近 count 条
        df = df.tail(count)

        result = []
        for _, row in df.iterrows():
            try:
                result.append({
                    "date": str(row.get("日期", "")),
                    "open": float(row.get("开盘", 0)),
                    "close": float(row.get("收盘", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "volume": int(float(row.get("成交量", 0))),
                    "amount": float(row.get("成交额", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "source": "akshare",
                })
            except (ValueError, TypeError):
                continue

        return result

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取场外基金净值"""
        _ensure_akshare()
        try:
            df = ak.fund_open_fund_info_em(symbol=ticker, indicator="单位净值走势")
        except Exception as e:
            raise DataError(f"AKShare 基金净值请求失败: {e}", source="akshare")

        if df is None or df.empty:
            raise DataError(f"基金净值数据为空: {ticker}", source="akshare")

        latest = df.iloc[-1]
        return {
            "ticker": ticker,
            "name": "",
            "nav": float(latest.get("单位净值", 0)),
            "acc_nav": 0,
            "nav_date": str(latest.get("净值日期", "")),
            "change_pct": float(latest.get("日增长率", 0)),
            "source": "akshare",
        }

    async def close(self):
        """关闭（AKShare 无持久连接）"""
        pass
