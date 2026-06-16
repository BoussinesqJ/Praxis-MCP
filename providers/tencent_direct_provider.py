"""腾讯财经直连数据源插件

基于 a-stock-data 的设计原则：
- HTTP 协议直连，不封 IP
- PE/PB/市值/换手率/涨跌停/ETF
- 优先级 Tier 2

使用方式：
    from providers.tencent_direct_provider import TencentDirectProvider

    provider = TencentDirectProvider()
    result = await provider.get_realtime_quote(["000001"])
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import httpx

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError

logger = logging.getLogger("praxis.provider.tencent_direct")

# 优先级：Tier 2
PRIORITY = 2

# 腾讯行情 API
TENCENT_QUOTE_URL = "http://qt.gtimg.cn/q="


class TencentDirectProvider(DataProvider):
    """腾讯财经直连数据源"""

    priority = 2  # Tier 2

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=8.0)

    def _build_ticker(self, ticker: str) -> str:
        """构建腾讯格式的股票代码

        000001 -> sz000001
        600000 -> sh600000
        510050 -> sh510050
        """
        if ticker.startswith(('6', '5')):
            return f"sh{ticker}"
        return f"sz{ticker}"

    def _parse_quote(self, data: str, ticker: str) -> Optional[dict]:
        """解析腾讯行情数据

        腾讯行情格式：
        v_sh510050="1~科创50ETF东财~510050~1.599~1.591~1.575~347797~..."
        """
        try:
            # 提取引号内的数据
            match = re.search(r'"([^"]*)"', data)
            if not match:
                return None

            content = match.group(1)
            if not content:
                return None

            fields = content.split('~')
            if len(fields) < 10:
                return None

            # 解析字段（腾讯行情格式，兼容不同字段数量）
            # 0: 市场(0:深圳 1:上海)
            # 1: 名称
            # 2: 代码
            # 3: 最新价
            # 4: 昨收
            # 5: 今开
            # 6: 成交量(手)
            # 30: 涨跌额
            # 31: 涨跌幅(%)
            # 32: 最高价
            # 33: 最低价

            price = float(fields[3]) if fields[3] else 0
            prev_close = float(fields[4]) if fields[4] else 0
            open_price = float(fields[5]) if fields[5] else 0
            volume = int(float(fields[6])) if fields[6] else 0

            # 涨跌额和涨跌幅（兼容不同字段数量）
            change = float(fields[31]) if len(fields) > 31 and fields[31] else (price - prev_close)
            change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else (
                round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
            )
            high = float(fields[33]) if len(fields) > 33 and fields[33] else 0
            low = float(fields[34]) if len(fields) > 34 and fields[34] else 0
            amount = float(fields[37]) if len(fields) > 37 and fields[37] else 0
            turnover = float(fields[38]) if len(fields) > 38 and fields[38] else 0
            pe_ratio = float(fields[39]) if len(fields) > 39 and fields[39] else 0

            return {
                "name": fields[1],
                "ticker": ticker,
                "price": price,
                "prev_close": prev_close,
                "open": open_price,
                "volume": volume,
                "high": high,
                "low": low,
                "change": change,
                "change_pct": change_pct,
                "amount": amount * 10000,  # 万 -> 元
                "turnover": turnover,
                "pe_ratio": pe_ratio,
                "timestamp": datetime.now().isoformat(),
                "source": "tencent",
            }

        except Exception as e:
            logger.warning(f"解析腾讯行情数据失败: {e}")
            return None

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情

        使用腾讯财经 HTTP 直连获取实时行情数据。

        Args:
            tickers: 股票代码列表

        Returns:
            实时行情数据字典

        Raises:
            DataError: 获取失败时抛出
        """
        if not tickers:
            return {}

        try:
            # 构建请求 URL
            tencent_tickers = [self._build_ticker(t) for t in tickers]
            url = TENCENT_QUOTE_URL + ",".join(tencent_tickers)

            # 发送请求
            resp = await self._client.get(url)
            resp.raise_for_status()

            # 解析响应：按响应中的ticker代码映射，而非位置
            lines = resp.text.strip().split('\n')
            result = {}

            for line in lines:
                match = re.search(r'"([^"]*)"', line)
                if not match:
                    continue
                fields = match.group(1).split('~')
                if len(fields) < 4:
                    continue
                resp_ticker = fields[2]  # 响应中的实际代码
                if not resp_ticker or resp_ticker not in tickers:
                    continue  # 跳过不在请求中的代码
                quote = self._parse_quote(line, resp_ticker)
                if quote and quote.get('price', 0) > 0:
                    result[resp_ticker] = quote

            if not result:
                raise DataError("腾讯无法获取任何标的行情", source="tencent")

            return result

        except DataError:
            raise
        except Exception as e:
            logger.error(f"腾讯获取实时行情失败: {e}")
            raise DataError(f"腾讯获取实时行情失败: {e}", source="tencent")

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线（腾讯不支持，返回空让系统降级到其他数据源）"""
        return []

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值（腾讯不支持）

        Raises:
            DataError: 腾讯不支持基金净值
        """
        raise DataError(f"腾讯不支持基金净值: {ticker}", source="tencent")

    async def close(self) -> None:
        """关闭会话"""
        await self._client.aclose()
