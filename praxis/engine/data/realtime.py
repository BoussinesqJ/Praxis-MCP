"""腾讯财经实时行情数据源"""
from __future__ import annotations

import re
from datetime import datetime

import httpx

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError


# 腾讯财经 ticker 前缀映射
TENCENT_PREFIX = {
    "6": "sh",    # 上交所股票
    "5": "sh",    # 上交所ETF
    "0": "sz",    # 深交所股票/ETF
    "1": "sz",    # 深交所ETF/基金
    "3": "sz",    # 创业板
}


def _to_tencent_ticker(ticker: str) -> str:
    """转换为腾讯财经 ticker 格式"""
    if "." in ticker:
        return ticker
    prefix = TENCENT_PREFIX.get(ticker[0], "sh")
    return f"{prefix}{ticker}"


class TencentDataProvider(DataProvider):
    """腾讯财经数据源（零 API Key）"""

    REALTIME_URL = "https://qt.gtimg.cn/q="
    HISTORY_URL = "https://web.ifzq.gtimg.cn/appnew/tech/history"
    FUND_NAV_URL = "https://qt.gtimg.cn/q="

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情"""
        if not tickers:
            return {}

        tencent_tickers = [_to_tencent_ticker(t) for t in tickers]
        url = f"{self.REALTIME_URL}{','.join(tencent_tickers)}"

        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            raise DataError(f"腾讯行情请求失败: {e}", source="tencent")

        return self._parse_realtime(text, tickers)

    def _parse_realtime(self, text: str, original_tickers: list[str]) -> dict[str, dict]:
        """解析腾讯行情数据"""
        result = {}
        lines = text.strip().split("\n")

        for i, line in enumerate(lines):
            if i >= len(original_tickers):
                break
            ticker = original_tickers[i]

            # 格式: v_shSTOCK_A="1~示例股票A~STOCK_A~13.38~13.45~..."
            match = re.search(r'"(.+)"', line)
            if not match:
                continue

            fields = match.group(1).split("~")
            if len(fields) < 45:
                continue

            try:
                result[ticker] = {
                    "name": fields[1],
                    "ticker": fields[2],
                    "price": float(fields[3]) if fields[3] else 0,
                    "prev_close": float(fields[4]) if fields[4] else 0,
                    "open": float(fields[5]) if fields[5] else 0,
                    "volume": int(fields[6]) if fields[6] else 0,
                    "high": float(fields[33]) if fields[33] else 0,
                    "low": float(fields[34]) if fields[34] else 0,
                    "change": float(fields[31]) if fields[31] else 0,
                    "change_pct": float(fields[32]) if fields[32] else 0,
                    "amount": float(fields[37]) if fields[37] else 0,
                    "timestamp": fields[30] if fields[30] else "",
                    "source": "tencent",
                }
            except (ValueError, IndexError):
                continue

        return result

    async def get_history_kline(self, ticker: str, period: str = "day", count: int = 60) -> list[dict]:
        """获取历史K线"""
        # 简化实现，返回空列表（R1 阶段不需要历史K线）
        return []

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值"""
        tencent_ticker = _to_tencent_ticker(ticker)
        url = f"{self.FUND_NAV_URL}{tencent_ticker}"

        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            raise DataError(f"基金净值请求失败: {e}", source="tencent")

        match = re.search(r'"(.+)"', text)
        if not match:
            raise DataError(f"无法解析基金净值: {ticker}", source="tencent")

        fields = match.group(1).split("~")
        if len(fields) < 10:
            raise DataError(f"基金净值数据不完整: {ticker}", source="tencent")

        try:
            return {
                "ticker": ticker,
                "nav": float(fields[3]) if fields[3] else 0,
                "acc_nav": float(fields[4]) if fields[4] else 0,
                "nav_date": fields[30] if fields[30] else "",
                "source": "tencent",
            }
        except (ValueError, IndexError) as e:
            raise DataError(f"基金净值解析错误: {e}", source="tencent")

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()
