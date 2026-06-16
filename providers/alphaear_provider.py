"""AlphaEar 数据源插件（实时行情 + 历史K线）

集成 AlphaEar 的股票数据能力，作为 Praxis 数据源的补充。
主要用于 A 股/港股/美股的实时行情和历史K线数据。

使用方式：
- 自动注册为 providers/alphaear_provider.py
- 优先级 3（在腾讯(5) 之前，最高优先级）
- 主要用于 get_realtime_quote 和 get_history_kline 功能
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError

logger = logging.getLogger("praxis.provider.alphaear")

# 优先级：最高优先级（在腾讯之前）
PRIORITY = 3


def _get_stock_tools():
    """延迟加载 AlphaEar 股票工具"""
    import sys

    alphaear_path = Path.home() / "Desktop" / "Praxis management" / ".agent" / "skills" / "AF" / "skills" / "alphaear-stock" / "scripts"
    if alphaear_path.exists() and str(alphaear_path.parent) not in sys.path:
        sys.path.insert(0, str(alphaear_path.parent))

    try:
        from scripts.stock_tools import StockTools
        from scripts.database_manager import DatabaseManager
        db = DatabaseManager()
        return StockTools(db)
    except ImportError as e:
        logger.warning(f"AlphaEar 股票工具导入失败: {e}")
        return None


class AlphaEarProvider(DataProvider):
    """AlphaEar 数据源（实时行情 + 历史K线）"""

    priority = 90  # 禁用

    def __init__(self):
        self._stock_tools = None

    def _ensure_tools(self):
        if not self._stock_tools:
            self._stock_tools = _get_stock_tools()
            if not self._stock_tools:
                raise DataError("AlphaEar 股票工具未安装", source="alphaear")

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情

        AlphaEar 使用 akshare 获取实时行情数据。
        """
        try:
            self._ensure_tools()
            import akshare as ak

            # 获取 A 股实时行情（东方财富源）线程池隔离
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)

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
                        "volume_ratio": float(row.get("量比", 0) or 0),
                        "timestamp": datetime.now().isoformat(),
                        "source": "alphaear",
                    }
                except Exception as e:
                    logger.warning(f"解析 {ticker} 数据失败: {e}")
                    continue

            return result
        except Exception as e:
            logger.warning(f"AlphaEar 实时行情获取失败: {e}")
            raise DataError(f"AlphaEar 实时行情请求失败: {e}", source="alphaear")

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线"""
        try:
            self._ensure_tools()

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=count * 3)).strftime("%Y-%m-%d")

            df = await asyncio.to_thread(
                self._stock_tools.get_stock_price, ticker, start_date, end_date
            )
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.get("date", "")),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": int(float(row.get("volume", 0))),
                    "source": "alphaear",
                })

            return result[-count:] if count else result
        except Exception as e:
            logger.warning(f"AlphaEar K线获取失败: {e}")
            return []

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值（AlphaEar 不支持）"""
        raise DataError(f"AlphaEar 不支持基金净值: {ticker}", source="alphaear")

    async def close(self):
        """关闭（AlphaEar 无持久连接）"""
        pass
