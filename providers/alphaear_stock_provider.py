"""AlphaEar 股票数据源插件

集成 AlphaEar 的股票搜索和行情能力，作为 Praxis 数据源的补充。
主要用于 A 股/港股/美股的基本面数据和股票搜索。

使用方式：
- 自动注册为 providers/alphaear_stock_provider.py
- 优先级 40（在腾讯(5)、AKShare(10)、Baostock(30) 之后，东方财富(50) 之前）
- 主要用于 get_fundamentals 和 search 功能
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError

logger = logging.getLogger("praxis.provider.alphaear_stock")

# 优先级：在腾讯/AKShare/Baostock 之后，东方财富之前
PRIORITY = 40


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


class AlphaEarStockProvider(DataProvider):
    """AlphaEar 股票数据源（补充基本面数据和搜索）"""

    def __init__(self):
        self._stock_tools = None

    def _ensure_tools(self):
        if not self._stock_tools:
            self._stock_tools = _get_stock_tools()
            if not self._stock_tools:
                raise DataError("AlphaEar 股票工具未安装", source="alphaear_stock")

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情

        AlphaEar 主要用于基本面数据，实时行情优先使用其他数据源。
        此方法返回空字典，让系统使用腾讯/AKShare 等。
        """
        # AlphaEar 不适合做实时行情，返回空让系统降级到其他数据源
        return {}

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线"""
        try:
            self._ensure_tools()
            from datetime import timedelta

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
                    "source": "alphaear_stock",
                })

            return result[-count:] if count else result
        except Exception as e:
            logger.warning(f"AlphaEar K线获取失败: {e}")
            return []

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值（AlphaEar 不支持）"""
        raise DataError(f"AlphaEar 不支持基金净值: {ticker}", source="alphaear_stock")

    async def search_ticker(self, query: str) -> list[dict]:
        """搜索股票代码（AlphaEar 独有功能）"""
        try:
            self._ensure_tools()
            results = await asyncio.to_thread(self._stock_tools.search_ticker, query)
            return results if results else []
        except Exception as e:
            logger.warning(f"AlphaEar 股票搜索失败: {e}")
            return []

    async def get_fundamentals(self, ticker: str) -> dict:
        """获取股票基本面数据（AlphaEar 独有功能）"""
        try:
            self._ensure_tools()
            result = await asyncio.to_thread(self._stock_tools.get_stock_fundamentals, ticker)
            return result if result else {}
        except Exception as e:
            logger.warning(f"AlphaEar 基本面获取失败: {e}")
            return {}

    async def close(self):
        """关闭（AlphaEar 无持久连接）"""
        pass
