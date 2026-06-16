"""mootdx (通达信) 数据源插件

基于 a-stock-data 的设计原则：
- TCP 协议直连，不封 IP
- K线/盘口/五档/逐笔/财务快照
- 优先级 Tier 1（最高）

使用方式：
    from providers.mootdx_provider import MootdxProvider

    provider = MootdxProvider()
    result = await provider.get_realtime_quote(["000001"])
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError

logger = logging.getLogger("praxis.provider.mootdx")

# 优先级：最高（Tier 1）
PRIORITY = 1


class MootdxProvider(DataProvider):
    """mootdx 数据源（通达信 TCP 直连）"""

    priority = 1  # Tier 1 最高优先级

    def __init__(self):
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """初始化 mootdx 客户端"""
        try:
            from mootdx.quotes import Quotes

            # 创建客户端（自动选择最快的服务器）
            self._client = Quotes.factory(market='std')
            logger.info("mootdx 客户端初始化成功")
        except ImportError:
            logger.warning("mootdx 未安装，请运行: pip install mootdx")
            self._client = None
        except Exception as e:
            logger.error(f"mootdx 客户端初始化失败: {e}")
            self._client = None

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情

        使用 mootdx TCP 直连获取实时行情数据。

        Args:
            tickers: 股票代码列表

        Returns:
            实时行情数据字典

        Raises:
            DataError: 获取失败时抛出
        """
        if not tickers:
            return {}

        if self._client is None:
            raise DataError("mootdx 客户端未初始化", source="mootdx")

        try:
            result = {}

            for ticker in tickers:
                # mootdx 需要市场代码
                market = self._get_market(ticker)

                # 获取实时行情
                quotes = self._client.quotes(symbol=[ticker])

                if quotes is None or len(quotes) == 0:
                    logger.warning(f"mootdx 无法获取 {ticker} 行情")
                    continue

                quote = quotes[0] if isinstance(quotes, list) else quotes

                # 解析行情数据
                result[ticker] = {
                    "name": str(quote.get('name', '')),
                    "ticker": ticker,
                    "price": float(quote.get('price', 0) or 0),
                    "prev_close": float(quote.get('last_close', 0) or 0),
                    "open": float(quote.get('open', 0) or 0),
                    "volume": int(float(quote.get('volume', 0) or 0)),
                    "high": float(quote.get('high', 0) or 0),
                    "low": float(quote.get('low', 0) or 0),
                    "change": float(quote.get('price', 0) or 0) - float(quote.get('last_close', 0) or 0),
                    "change_pct": self._calc_change_pct(
                        float(quote.get('price', 0) or 0),
                        float(quote.get('last_close', 0) or 0)
                    ),
                    "amount": float(quote.get('amount', 0) or 0),
                    "bid1": float(quote.get('bid1', 0) or 0),
                    "ask1": float(quote.get('ask1', 0) or 0),
                    "timestamp": datetime.now().isoformat(),
                    "source": "mootdx",
                }

            if not result:
                raise DataError(f"mootdx 无法获取任何标的行情", source="mootdx")

            return result

        except DataError:
            raise
        except Exception as e:
            logger.error(f"mootdx 获取实时行情失败: {e}")
            raise DataError(f"mootdx 获取实时行情失败: {e}", source="mootdx")

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线

        Args:
            ticker: 股票代码
            period: K线周期 (day/week/month/5min/15min/30min/60min)
            count: K线数量

        Returns:
            K线数据列表
        """
        if self._client is None:
            return []

        try:
            # 转换周期参数
            ktype = self._convert_period(period)

            # 获取K线数据
            bars = self._client.bars(symbol=ticker, frequency=ktype, count=count)

            if bars is None or len(bars) == 0:
                return []

            result = []
            for bar in bars:
                result.append({
                    "date": str(bar.get('datetime', '')),
                    "open": float(bar.get('open', 0)),
                    "high": float(bar.get('high', 0)),
                    "low": float(bar.get('low', 0)),
                    "close": float(bar.get('close', 0)),
                    "volume": int(float(bar.get('volume', 0))),
                    "amount": float(bar.get('amount', 0)),
                    "source": "mootdx",
                })

            return result

        except Exception as e:
            logger.warning(f"mootdx 获取K线失败: {e}")
            return []

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值（mootdx 不支持）

        Raises:
            DataError: mootdx 不支持基金净值
        """
        raise DataError(f"mootdx 不支持基金净值: {ticker}", source="mootdx")

    def _get_market(self, ticker: str) -> int:
        """获取市场代码

        0: 深圳
        1: 上海
        """
        if ticker.startswith(('6', '5')):
            return 1  # 上海
        return 0  # 深圳

    def _convert_period(self, period: str) -> int:
        """转换K线周期

        mootdx 频率参数：
        0: 5分钟
        1: 15分钟
        2: 30分钟
        3: 60分钟
        4: 日K
        5: 周K
        6: 月K
        7: 1分钟
        8: 1小时
        9: 季K
        10: 年K
        """
        period_map = {
            '5min': 0,
            '15min': 1,
            '30min': 2,
            '60min': 3,
            'day': 4,
            'week': 5,
            'month': 6,
            '1min': 7,
            '1hour': 8,
            'quarter': 9,
            'year': 10,
        }
        return period_map.get(period, 4)  # 默认日K

    def _calc_change_pct(self, price: float, prev_close: float) -> float:
        """计算涨跌幅"""
        if prev_close and prev_close > 0:
            return round((price - prev_close) / prev_close * 100, 2)
        return 0.0

    async def close(self) -> None:
        """关闭连接"""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
