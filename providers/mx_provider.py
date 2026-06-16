"""妙想(MX) 数据源插件

集成东方财富妙想 API 的数据能力，作为 Praxis 主数据源。
通过 API + Key 获取数据，最准确。

使用方式：
- 自动注册为 providers/mx_provider.py
- 优先级 1（最高优先级）
- 主要用于 get_realtime_quote 和 get_fundamentals 功能
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError

logger = logging.getLogger("praxis.provider.mx")

# 优先级：最高优先级
PRIORITY = 1

# 妙想 API（数据查询）- 使用 query 端点
MX_API_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"


class MXProvider(DataProvider):
    """妙想数据源（实时行情 + 基本面数据）"""

    priority = 1  # 最高优先级

    def __init__(self):
        self._api_key = os.getenv("MX_APIKEY")
        self._client = httpx.AsyncClient(timeout=30.0, trust_env=False)

    async def _query_mx(self, query: str) -> dict:
        """调用妙想 API 查询数据"""
        if not self._api_key:
            raise DataError("MX_APIKEY 未设置", source="mx")

        headers = {
            "Content-Type": "application/json",
            "apikey": self._api_key,
        }
        data = {"toolQuery": query}

        resp = await self._client.post(MX_API_URL, headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情
        
        使用妙想 API 获取实时行情数据（并发异步查询）。
        """
        if not tickers:
            return {}

        if not self._api_key:
            logger.warning("MX_APIKEY 未设置，跳过 MX 数据源")
            raise DataError("MX_APIKEY 未设置", source="mx")

        result = {}
        
        async def fetch_ticker(ticker: str):
            try:
                # 查询实时行情数据
                query = f"{ticker} 最新报价 涨跌幅 涨跌额 换手率 最高价 最低价 今开 昨收 成交量 成交额"
                data = await self._query_mx(query)
                parsed = self._parse_realtime(data, ticker)
                if parsed:
                    result[ticker] = parsed
            except Exception as e:
                logger.warning(f"MX 获取 {ticker} 实时行情失败: {e}")

        # 并发执行所有行情请求
        await asyncio.gather(*(fetch_ticker(t) for t in tickers))

        if not result:
            raise DataError("MX 无法获取任何标的的实时行情", source="mx")

        return result

    def _parse_realtime(self, data: dict, ticker: str) -> dict | None:
        """解析妙想 API 返回的实时行情数据"""
        try:
            tables = (
                data.get("data", {})
                .get("data", {})
                .get("searchDataResultDTO", {})
                .get("dataTableDTOList", [])
            )

            for table in tables:
                table_data = table.get("table", {})
                name_map = table.get("nameMap", {})

                # 查找包含实时行情数据的表
                if "f2" in table_data:
                    price = self._parse_number(table_data.get("f2"))
                    if price and price > 0:
                        return {
                            "name": table.get("entityName", "").split("(")[0],
                            "ticker": ticker,
                            "price": price,
                            "change_pct": self._parse_number(table_data.get("f3")) or 0,
                            "change": self._parse_number(table_data.get("f4")) or 0,
                            "volume": int(self._parse_number(table_data.get("f5")) or 0),
                            "amount": self._parse_number(table_data.get("f6")) or 0,
                            "turnover": self._parse_number(table_data.get("f8")) or 0,
                            "high": self._parse_number(table_data.get("f15")) or 0,
                            "low": self._parse_number(table_data.get("f16")) or 0,
                            "open": self._parse_number(table_data.get("f17")) or 0,
                            "prev_close": self._parse_number(table_data.get("f18")) or 0,
                            "timestamp": datetime.now().isoformat(),
                            "source": "mx",
                        }

                # 备用：查找包含价格数据的表
                for key, value in table_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        first_val = value[0]
                        if isinstance(first_val, str) and "元" in first_val:
                            price = self._parse_number(first_val)
                            if price and price > 0:
                                return {
                                    "name": table.get("entityName", "").split("(")[0],
                                    "ticker": ticker,
                                    "price": price,
                                    "change_pct": 0,
                                    "change": 0,
                                    "volume": 0,
                                    "amount": 0,
                                    "turnover": 0,
                                    "high": 0,
                                    "low": 0,
                                    "open": 0,
                                    "prev_close": 0,
                                    "timestamp": datetime.now().isoformat(),
                                    "source": "mx",
                                }

            return None
        except Exception as e:
            logger.warning(f"解析实时行情失败: {e}")
            return None

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线（MX 不支持，返回空让系统降级到其他数据源）"""
        return []

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值（MX 不支持，返回空让系统降级到其他数据源）"""
        raise DataError(f"MX 不支持基金净值: {ticker}", source="mx")

    async def get_fundamentals(self, ticker: str) -> dict:
        """获取股票基本面数据（MX 独有功能）

        使用妙想 API 获取 PE、PB、营收、净利润等基本面数据。
        """
        if not self._api_key:
            logger.warning("MX_APIKEY 未设置，无法获取基本面数据")
            return {}

        try:
            query = f"{ticker} 最新报价 涨跌幅 换手率 PE PB 营收 净利润 ROE 负债率"
            data = await self._query_mx(query)
            return self._parse_fundamentals(data, ticker)
        except Exception as e:
            logger.warning(f"MX 基本面数据获取失败: {e}")
            return {}

    def _parse_fundamentals(self, data: dict, ticker: str) -> dict:
        """解析妙想 API 返回的基本面数据"""
        try:
            tables = (
                data.get("data", {})
                .get("data", {})
                .get("searchDataResultDTO", {})
                .get("dataTableDTOList", [])
            )

            fundamentals = {
                "ticker": ticker,
                "source": "mx",
                "timestamp": datetime.now().isoformat(),
            }

            for table in tables:
                table_data = table.get("table", {})

                # 解析实时行情表（包含 PE、PB、换手率等）
                if "f2" in table_data:
                    fundamentals["price"] = self._parse_number(table_data.get("f2"))
                    fundamentals["change_pct"] = self._parse_number(table_data.get("f3"))
                    fundamentals["turnover"] = self._parse_number(table_data.get("f8"))
                    fundamentals["pe_ratio"] = self._parse_number(table_data.get("f115"))
                    fundamentals["pb_ratio"] = self._parse_number(table_data.get("f23"))

                # 解析基本面数据表（包含营收、净利润等）
                if "100000000000189" in table_data:
                    revenue = table_data.get("100000000000189", [])
                    if revenue:
                        fundamentals["revenue"] = revenue[0]
                    net_profit = table_data.get("100000000000200", [])
                    if net_profit:
                        fundamentals["net_profit"] = net_profit[0]
                    roe = table_data.get("100000000004682", [])
                    if roe:
                        fundamentals["roe"] = roe[0]
                    debt_ratio = table_data.get("100000000044473", [])
                    if debt_ratio:
                        fundamentals["debt_ratio"] = debt_ratio[0]

            return fundamentals
        except Exception as e:
            logger.warning(f"解析基本面数据失败: {e}")
            return {}

    def _parse_number(self, value) -> float | None:
        """解析数值（支持百分比、亿元等格式）"""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, list):
                if len(value) > 0:
                    return self._parse_number(value[0])
                return None
            if isinstance(value, str):
                # 移除百分号、亿元等单位
                value = value.replace("%", "").replace("亿元", "").replace("倍", "").replace("元", "").strip()
                return float(value)
        except (ValueError, TypeError):
            pass
        return None

    async def close(self):
        """关闭会话"""
        await self._client.aclose()

