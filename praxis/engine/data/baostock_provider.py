"""Baostock 数据源适配器

依赖: pip install baostock
数据源: 交易所直连，历史数据质量最高（支持复权/拆股/分红）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError

logger = logging.getLogger("praxis.data.baostock")

try:
    import baostock as bs
    HAS_BAOSTOCK = True
except ImportError:
    HAS_BAOSTOCK = False


def _ensure_baostock():
    if not HAS_BAOSTOCK:
        raise ImportError(
            "Baostock 未安装。请执行: pip install baostock 或 pip install praxis[baostock]"
        )


def _to_bs_code(ticker: str) -> str:
    """转换为 Baostock 代码格式: sh.600995 / sz.000001"""
    if "." in ticker:
        return ticker
    if ticker.startswith(("6", "5")):
        return f"sh.{ticker}"
    return f"sz.{ticker}"


class BaostockProvider(DataProvider):
    """Baostock 数据源（交易所直连，历史数据最干净）"""

    def __init__(self):
        _ensure_baostock()
        self._connected = False

    def _ensure_connected(self):
        if not self._connected:
            result = bs.login()
            if result.error_code != "0":
                raise DataError(f"Baostock 登录失败: {result.error_msg}", source="baostock")
            self._connected = True

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情

        注意：Baostock 主要提供历史数据，不支持真正的实时行情。
        此方法返回空字典，强制系统使用其他数据源（如 Tencent）获取实时数据。
        """
        # Baostock 不支持实时行情，返回空让系统降级到其他数据源
        return {}

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线（Baostock 最强项）"""
        _ensure_baostock()
        self._ensure_connected()

        freq_map = {"day": "d", "week": "w", "month": "m"}
        freq = freq_map.get(period, "d")

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=count * 3)).strftime("%Y-%m-%d")

        try:
            bs_code = _to_bs_code(ticker)
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency=freq,
                adjustflag="2",  # 前复权
            )
            if rs.error_code != "0":
                raise DataError(f"Baostock K线请求失败: {rs.error_msg}", source="baostock")
        except DataError:
            raise
        except Exception as e:
            raise DataError(f"Baostock K线请求失败: {e}", source="baostock")

        result = []
        while rs.next():
            row = rs.get_row_data()
            try:
                result.append({
                    "date": row[0],
                    "open": float(row[1]) if row[1] else 0,
                    "high": float(row[2]) if row[2] else 0,
                    "low": float(row[3]) if row[3] else 0,
                    "close": float(row[4]) if row[4] else 0,
                    "volume": int(float(row[5])) if row[5] else 0,
                    "amount": float(row[6]) if row[6] else 0,
                    "change_pct": float(row[7]) if row[7] else 0,
                    "source": "baostock",
                })
            except (ValueError, IndexError):
                continue

        return result[-count:] if count else result

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值

        Baostock 的基金数据接口：query FundNavFromSina
        简化实现：使用 K 线数据的 close 作为净值近似
        """
        _ensure_baostock()
        self._ensure_connected()

        try:
            bs_code = _to_bs_code(ticker)
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,close",
                start_date=start,
                end_date=end,
                frequency="d",
            )
            if rs.error_code != "0":
                raise DataError(f"Baostock 基金净值请求失败: {rs.error_msg}", source="baostock")

            rows = []
            while rs.next():
                rows.append(rs.get_row_data())

            if not rows:
                raise DataError(f"基金净值数据为空: {ticker}", source="baostock")

            latest = rows[-1]
            return {
                "ticker": ticker,
                "name": "",
                "nav": float(latest[1]) if latest[1] else 0,
                "acc_nav": 0,
                "nav_date": latest[0],
                "change_pct": 0,
                "source": "baostock",
            }
        except DataError:
            raise
        except Exception as e:
            raise DataError(f"Baostock 基金净值请求失败: {e}", source="baostock")

    async def close(self):
        """关闭 Baostock 连接"""
        if self._connected:
            try:
                bs.logout()
            except Exception:
                pass
            self._connected = False
