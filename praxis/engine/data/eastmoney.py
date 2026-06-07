"""东方财富数据源（零 API Key）

API 端点：
- 实时行情: push2.eastmoney.com/api/qt/stock/get
- 历史K线: push2his.eastmoney.com/api/qt/stock/kline/get
- 基金净值: api.fund.eastmoney.com/f10/lsjz
"""
from __future__ import annotations

import re
from datetime import datetime

import httpx

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError


# ── Ticker 格式转换 ──

def _detect_market(ticker: str) -> int:
    """检测市场代码: 1=沪市, 0=深市"""
    if ticker.startswith(("6", "5")):
        return 1  # 沪市: 60xxxx股票, 68xxxx科创, 51xxxx ETF, 58xxxx ETF
    return 0  # 深市: 00xxxx股票, 30xxxx创业板, 15xxxx ETF, 01/16xxxx基金


def _to_eastmoney_secid(ticker: str) -> str:
    """转换为东方财富 secid 格式: {market}.{code}"""
    if "." in ticker:
        return ticker
    market = _detect_market(ticker)
    return f"{market}.{ticker}"


def _is_fund(ticker: str) -> bool:
    """判断是否为场外基金"""
    return ticker.startswith(("01", "16"))


# ── 东方财富数据源 ──

class EastMoneyDataProvider(DataProvider):
    """东方财富数据源（零 API Key，JSON 响应）"""

    BASE_URL = "http://push2.eastmoney.com"
    HIST_URL = "http://push2his.eastmoney.com"
    FUND_URL = "http://api.fund.eastmoney.com"

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情"""
        if not tickers:
            return {}

        result = {}
        # 逐个查询（东方财富单股查询更可靠）
        for ticker in tickers:
            try:
                quote = await self._get_single_quote(ticker)
                if quote:
                    result[ticker] = quote
            except Exception:
                continue  # 单个失败不影响其他

        return result

    async def _get_single_quote(self, ticker: str) -> dict | None:
        """获取单只股票/ETF/基金的实时行情"""
        if _is_fund(ticker):
            return await self._get_fund_quote(ticker)

        secid = _to_eastmoney_secid(ticker)
        url = f"{self.BASE_URL}/api/qt/stock/get"
        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f60,f116,f117,f170",
            "ut": "fa5fd1943c7b386f172d6893dbbd1031",
        }

        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise DataError(f"东方财富行情请求失败: {e}", source="eastmoney")

        if not data or data.get("data") is None:
            return None

        d = data["data"]

        # 东方财富价格字段返回整数，需要根据标的小数位数还原
        # 股票: 2 位小数 (÷100); ETF: 3 位小数 (÷1000)
        divisor = 1000 if ticker.startswith(("51", "15", "58")) else 100

        def _price(val) -> float:
            if val is None or val == "-":
                return 0
            return float(val) / divisor

        return {
            "name": d.get("f58", ""),
            "ticker": d.get("f57", ticker),
            "price": _price(d.get("f43")),
            "prev_close": _price(d.get("f60")),
            "open": _price(d.get("f46")),
            "volume": int(d.get("f47", 0)),
            "high": _price(d.get("f44")),
            "low": _price(d.get("f45")),
            "change": _price(d.get("f50")),
            "change_pct": float(d.get("f170", 0)) / 100 if d.get("f170") else 0,
            "amount": float(d.get("f48", 0)),
            "market_cap": float(d.get("f116", 0)),
            "float_cap": float(d.get("f117", 0)),
            "timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
            "source": "eastmoney",
        }

    async def _get_fund_quote(self, ticker: str) -> dict | None:
        """获取场外基金净值"""
        try:
            nav_data = await self.get_fund_nav(ticker)
            return {
                "name": nav_data.get("name", ""),
                "ticker": ticker,
                "price": nav_data.get("nav", 0),
                "prev_close": 0,
                "open": 0,
                "volume": 0,
                "high": 0,
                "low": 0,
                "change": 0,
                "change_pct": nav_data.get("change_pct", 0),
                "amount": 0,
                "nav_date": nav_data.get("nav_date", ""),
                "acc_nav": nav_data.get("acc_nav", 0),
                "timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
                "source": "eastmoney",
            }
        except Exception:
            return None

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线

        Args:
            ticker: 标的代码
            period: K线周期 (day/week/month)
            count: 获取条数
        """
        secid = _to_eastmoney_secid(ticker)
        klt_map = {"day": 101, "week": 102, "month": 103}
        klt = klt_map.get(period, 101)

        url = f"{self.HIST_URL}/api/qt/stock/kline/get"
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": klt,
            "fqt": 1,  # 前复权
            "lmt": count,
            "end": "20500101",
            "ut": "fa5fd1943c7b386f172d6893dbbd1031",
        }

        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise DataError(f"东方财富K线请求失败: {e}", source="eastmoney")

        if not data or not data.get("data") or not data["data"].get("klines"):
            return []

        result = []
        for line in data["data"]["klines"]:
            # 格式: "日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
            fields = line.split(",")
            if len(fields) < 7:
                continue
            try:
                result.append({
                    "date": fields[0],
                    "open": float(fields[1]),
                    "close": float(fields[2]),
                    "high": float(fields[3]),
                    "low": float(fields[4]),
                    "volume": int(float(fields[5])),
                    "amount": float(fields[6]),
                    "change_pct": float(fields[8]) if len(fields) > 8 else 0,
                    "source": "eastmoney",
                })
            except (ValueError, IndexError):
                continue

        return result

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取场外基金净值"""
        url = f"{self.FUND_URL}/f10/lsjz"
        params = {
            "fundCode": ticker,
            "pageIndex": 1,
            "pageSize": 1,
        }
        headers = {"Referer": "http://fund.eastmoney.com/"}

        try:
            resp = await self._client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise DataError(f"东方财富基金净值请求失败: {e}", source="eastmoney")

        if not data or not data.get("Data") or not data["Data"].get("LSJZList"):
            raise DataError(f"基金净值数据为空: {ticker}", source="eastmoney")

        fund_data = data["Data"]
        records = fund_data["LSJZList"]
        if not records:
            raise DataError(f"基金净值记录为空: {ticker}", source="eastmoney")

        latest = records[0]

        return {
            "ticker": ticker,
            "name": fund_data.get("FundType", ""),
            "nav": float(latest.get("DWJZ", 0)),
            "acc_nav": float(latest.get("LJJZ", 0)),
            "nav_date": latest.get("FSRQ", ""),
            "change_pct": float(latest.get("JZZZL", 0)) if latest.get("JZZZL") else 0,
            "source": "eastmoney",
        }

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()
