"""东财龙虎榜数据源

基于 Gemini Phase 2 建议：
- 继承 EMClient 基类（自动限流 + 缓存 + UA 伪装）
- 龙虎榜数据 12 小时内不重复请求
- 东财 datacenter API

使用方式：
    from providers.dragon_tiger_provider import DragonTigerProvider

    provider = DragonTigerProvider()
    
    # 获取龙虎榜列表
    dragon_tiger = await provider.get_dragon_tiger_list()
    
    # 获取龙虎榜详情
    detail = await provider.get_dragon_tiger_detail("000001")
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from praxis.core.em_client import EMClient, EMClientConfig

logger = logging.getLogger("praxis.provider.dragon_tiger")

# 东财龙虎榜 API
EM_DRAGON_TIGER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EM_DRAGON_TIGER_DETAIL_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


class DragonTigerProvider(EMClient):
    """东财龙虎榜数据源

    继承 EMClient，自动获得：
    - 限流器保护
    - TTL 缓存（12小时）
    - User-Agent 伪装
    - Session 复用
    - 自动重试
    """

    def __init__(self, config: Optional[EMClientConfig] = None):
        super().__init__(config)

    async def get_dragon_tiger_list(
        self,
        date: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """获取龙虎榜列表

        Args:
            date: 日期（YYYY-MM-DD），None 为今日
            limit: 返回数量

        Returns:
            龙虎榜列表
        """
        # 构建缓存键
        cache_key = f"dragon_tiger_list:{date or 'today'}:{limit}"

        # 构建请求参数
        params = {
            "sortColumns": "SECURITY_CODE",
            "sortTypes": "1",
            "pageSize": str(limit),
            "pageNumber": "1",
            "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
        }

        # 添加日期过滤
        if date:
            params["filter"] = f'(TRADE_DATE=\'{date}\')'

        try:
            data = await self.get(
                EM_DRAGON_TIGER_URL,
                params=params,
                cache_key=cache_key,
                cache_ttl=43200,  # 12小时缓存
            )

            if not data:
                return []

            # 兼容两种响应格式
            items = []
            if "result" in data:
                result_data = data.get("result", {})
                if result_data:
                    items = result_data.get("data", [])
            elif "data" in data:
                data_inner = data.get("data", {})
                if data_inner:
                    items = data_inner.get("diff", [])

            if not items:
                return []

            result = []
            for item in items:
                result.append({
                    "ticker": item.get("SECURITY_CODE", item.get("f12", "")),
                    "name": item.get("SECURITY_NAME_ABBR", item.get("f14", "")),
                    "price": float(item.get("CLOSE_PRICE", item.get("f2", 0)) or 0),
                    "change_pct": float(item.get("CHANGE_RATE", item.get("f3", 0)) or 0),
                    "net_buy": float(item.get("BILLBOARD_NET_AMT", item.get("f62", 0)) or 0),
                    "buy_amount": float(item.get("BILLBOARD_BUY_AMT", 0) or 0),
                    "sell_amount": float(item.get("BILLBOARD_SELL_AMT", 0) or 0),
                    "reason": item.get("EXPLAIN", ""),
                    "date": item.get("TRADE_DATE", ""),
                })

            return result

        except Exception as e:
            logger.warning(f"获取龙虎榜列表失败: {e}")
            return []

    async def get_dragon_tiger_detail(self, ticker: str) -> list[dict]:
        """获取龙虎榜详情（买卖席位）

        Args:
            ticker: 股票代码

        Returns:
            龙虎榜详情列表
        """
        # 构建缓存键
        cache_key = f"dragon_tiger_detail:{ticker}:{datetime.now().strftime('%Y%m%d')}"

        # 构建请求参数
        params = {
            "sortColumns": "BUY_AMT",
            "sortTypes": "-1",
            "pageSize": "20",
            "pageNumber": "1",
            "reportName": "RPT_BILLBOARD_DAILYDETAILSBUY",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(SECURITY_CODE=\'{ticker}\')',
        }

        try:
            data = await self.get(
                EM_DRAGON_TIGER_DETAIL_URL,
                params=params,
                cache_key=cache_key,
                cache_ttl=43200,  # 12小时缓存
            )

            if not data:
                return []

            # 兼容两种响应格式
            items = []
            if "result" in data:
                result_data = data.get("result", {})
                if result_data:
                    items = result_data.get("data", [])
            elif "data" in data:
                data_inner = data.get("data", {})
                if data_inner:
                    items = data_inner.get("diff", [])

            if not items:
                return []

            result = []
            for item in items:
                result.append({
                    "seat_name": item.get("BUYER_NAME", item.get("f18", "")),
                    "buy_amount": float(item.get("BUY_AMT", item.get("f62", 0)) or 0),
                    "sell_amount": float(item.get("SELL_AMT", item.get("f66", 0)) or 0),
                    "net_amount": float(item.get("NET_AMT", 0) or 0),
                    "reason": item.get("EXPLAIN", ""),
                    "date": item.get("TRADE_DATE", ""),
                })

            return result

        except Exception as e:
            logger.warning(f"获取龙虎榜详情失败: {e}")
            return []
