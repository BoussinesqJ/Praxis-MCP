"""东财资金流向数据源

基于 Gemini Phase 2 建议：
- 继承 EMClient 基类（自动限流 + 缓存 + UA 伪装）
- 资金流向数据 12 小时内不重复请求
- 东财 push2 API

使用方式：
    from providers.fund_flow_provider import FundFlowProvider

    provider = FundFlowProvider()
    
    # 获取分钟级资金流向
    flow_min = await provider.get_fund_flow_min("000001")
    
    # 获取日度资金流向
    flow_daily = await provider.get_fund_flow_daily("000001", days=5)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from praxis.core.em_client import EMClient, EMClientConfig

logger = logging.getLogger("praxis.provider.fund_flow")

# 东财资金流向 API
EM_FUND_FLOW_MIN_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
EM_FUND_FLOW_DAILY_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
EM_FUND_FLOW_ALL_URL = "https://push2.eastmoney.com/api/qt/clist/get"


class FundFlowProvider(EMClient):
    """东财资金流向数据源

    继承 EMClient，自动获得：
    - 限流器保护
    - TTL 缓存（12小时）
    - User-Agent 伪装
    - Session 复用
    - 自动重试
    """

    def __init__(self, config: Optional[EMClientConfig] = None):
        super().__init__(config)

    async def get_fund_flow_min(self, ticker: str) -> list[dict]:
        """获取个股分钟级资金流向

        Args:
            ticker: 股票代码

        Returns:
            分钟级资金流向数据列表
        """
        # 构建缓存键
        cache_key = f"fund_flow_min:{ticker}:{datetime.now().strftime('%Y%m%d')}"

        # 构建请求参数
        secid = self._get_secid(ticker)
        params = {
            "lmt": "0",
            "klt": "101",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "secid": secid,
        }

        try:
            data = await self.get(
                EM_FUND_FLOW_MIN_URL,
                params=params,
                cache_key=cache_key,
                cache_ttl=60,  # 1分钟缓存
            )

            if not data or "data" not in data:
                return []

            klines = data.get("data", {}).get("klines", [])
            if not klines:
                return []

            result = []
            for line in klines:
                fields = line.split(",")
                if len(fields) >= 6:
                    result.append({
                        "time": fields[0],
                        "main_net": int(float(fields[1])),  # 主力净流入
                        "small_net": int(float(fields[2])),  # 小单净流入
                        "mid_net": int(float(fields[3])),  # 中单净流入
                        "large_net": int(float(fields[4])),  # 大单净流入
                        "super_net": int(float(fields[5])),  # 超大单净流入
                    })

            return result

        except Exception as e:
            logger.warning(f"获取 {ticker} 分钟级资金流向失败: {e}")
            return []

    async def get_fund_flow_daily(
        self,
        ticker: str,
        days: int = 5,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """获取个股日度资金流向

        Args:
            ticker: 股票代码
            days: 获取天数
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）

        Returns:
            日度资金流向数据列表
        """
        # 构建缓存键
        cache_key = f"fund_flow_daily:{ticker}:{days}"

        # 构建请求参数
        secid = self._get_secid(ticker)
        params = {
            "lmt": str(days),
            "klt": "101",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "secid": secid,
        }

        try:
            data = await self.get(
                EM_FUND_FLOW_DAILY_URL,
                params=params,
                cache_key=cache_key,
                cache_ttl=43200,  # 12小时缓存
            )

            if not data or "data" not in data:
                return []

            klines = data.get("data", {}).get("klines", [])
            if not klines:
                return []

            result = []
            for line in klines:
                fields = line.split(",")
                if len(fields) >= 6:
                    date_str = fields[0]

                    # 日期过滤
                    if start_date and date_str < start_date:
                        continue
                    if end_date and date_str > end_date:
                        continue

                    result.append({
                        "date": date_str,
                        "main_net": int(float(fields[1])),  # 主力净流入
                        "small_net": int(float(fields[2])),  # 小单净流入
                        "mid_net": int(float(fields[3])),  # 中单净流入
                        "large_net": int(float(fields[4])),  # 大单净流入
                        "super_net": int(float(fields[5])),  # 超大单净流入
                    })

            return result

        except Exception as e:
            logger.warning(f"获取 {ticker} 日度资金流向失败: {e}")
            return []

    async def get_fund_flow_all(self, days: int = 1) -> list[dict]:
        """获取全市场资金流向

        Args:
            days: 获取天数（1/5/10）

        Returns:
            全市场资金流向数据列表
        """
        # 构建缓存键
        cache_key = f"fund_flow_all:{days}:{datetime.now().strftime('%Y%m%d')}"

        # 构建请求参数
        params = {
            "pn": "1",
            "pz": "5000",
            "po": "1",
            "np": "1",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fltt": "2",
            "invt": "2",
            "fid": "f62",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87",
        }

        try:
            data = await self.get(
                EM_FUND_FLOW_ALL_URL,
                params=params,
                cache_key=cache_key,
                cache_ttl=300,  # 5分钟缓存
            )

            if not data or "data" not in data:
                return []

            diff = data.get("data", {}).get("diff", [])
            if not diff:
                return []

            result = []
            for item in diff:
                result.append({
                    "ticker": item.get("f12", ""),
                    "name": item.get("f14", ""),
                    "price": float(item.get("f2", 0) or 0),
                    "change_pct": float(item.get("f3", 0) or 0),
                    "main_net": int(float(item.get("f62", 0) or 0)),
                    "main_pct": float(item.get("f184", 0) or 0),
                    "super_net": int(float(item.get("f66", 0) or 0)),
                    "super_pct": float(item.get("f69", 0) or 0),
                    "large_net": int(float(item.get("f72", 0) or 0)),
                    "large_pct": float(item.get("f75", 0) or 0),
                    "mid_net": int(float(item.get("f78", 0) or 0)),
                    "mid_pct": float(item.get("f81", 0) or 0),
                    "small_net": int(float(item.get("f84", 0) or 0)),
                    "small_pct": float(item.get("f87", 0) or 0),
                })

            return result

        except Exception as e:
            logger.warning(f"获取全市场资金流向失败: {e}")
            return []

    def _get_secid(self, ticker: str) -> str:
        """获取东财 secid 格式

        000001 -> 0.000001
        600000 -> 1.600000
        """
        if ticker.startswith(('6', '5')):
            return f"1.{ticker}"
        return f"0.{ticker}"
