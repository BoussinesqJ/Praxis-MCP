"""同花顺北向资金数据源

基于 Gemini Phase 2 建议：
- 北向资金实时/历史数据
- 本地自缓存机制
- 低风险数据源（极低封IP风险）

使用方式：
    from providers.northbound_provider import NorthboundProvider

    provider = NorthboundProvider()
    
    # 获取实时北向资金
    realtime = await provider.get_northbound_realtime()
    
    # 获取历史北向资金
    history = await provider.get_northbound_history(days=5)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from praxis.core.cache import TTLCache, get_cache, THS_CACHE_CONFIG

logger = logging.getLogger("praxis.provider.northbound")

# 同花顺北向资金 API
THS_NORTHBOUND_URL = "https://dq.10jqka.com.cn/fuyao/hot_gn_bk/gn/GetNorthFlow"


class NorthboundProvider:
    """同花顺北向资金数据源

    特性：
    - 实时数据：同花顺 API
    - 历史数据：本地自缓存
    - 低风险：极低封IP风险
    """

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=8.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.10jqka.com.cn/",
            },
        )

        # 缓存
        self._cache = get_cache("ths_northbound", THS_CACHE_CONFIG)

        # 本地历史数据目录
        self._history_dir = Path("cache/northbound")
        self._history_dir.mkdir(parents=True, exist_ok=True)

    async def get_northbound_realtime(self) -> dict:
        """获取北向资金实时数据

        Returns:
            北向资金实时数据
        """
        cache_key = f"northbound_realtime:{datetime.now().strftime('%Y%m%d%H')}"

        # 检查缓存
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            # 请求同花顺 API
            resp = await self._client.get(THS_NORTHBOUND_URL)
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data:
                return {}

            s2n = data.get("data", {}).get("s2n", {})

            result = {
                "current": {
                    "net_buy": s2n.get("current", {}).get("net_buy", 0),
                    "buy": s2n.get("current", {}).get("buy", 0),
                    "sell": s2n.get("current", {}).get("sell", 0),
                },
                "minute": s2n.get("minute", []),
                "timestamp": datetime.now().isoformat(),
            }

            # 写入缓存
            self._cache.set(cache_key, result, ttl=300)  # 5分钟缓存

            # 保存到本地历史
            self._save_to_history(result)

            return result

        except Exception as e:
            logger.warning(f"获取北向资金实时数据失败: {e}")
            return {}

    async def get_northbound_history(self, days: int = 5) -> list[dict]:
        """获取北向资金历史数据

        Args:
            days: 获取天数

        Returns:
            历史数据列表
        """
        # 从本地加载历史数据
        history = self._load_history()

        # 返回最近 N 天
        return history[-days:] if len(history) >= days else history

    async def get_northbound_flow(self) -> dict:
        """获取北向资金流向（实时 + 历史）

        Returns:
            北向资金流向数据
        """
        realtime = await self.get_northbound_realtime()
        history = await self.get_northbound_history(days=5)

        return {
            "realtime": realtime,
            "history": history,
            "timestamp": datetime.now().isoformat(),
        }

    def _save_to_history(self, data: dict) -> None:
        """保存数据到本地历史"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            history_file = self._history_dir / f"{today}.json"

            # 读取现有数据
            existing = []
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)

            # 添加新数据
            existing.append({
                "time": datetime.now().strftime("%H:%M"),
                "data": data,
            })

            # 保存
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"保存北向资金历史数据失败: {e}")

    def _load_history(self) -> list[dict]:
        """从本地加载历史数据"""
        try:
            history = []

            # 遍历历史文件
            for history_file in sorted(self._history_dir.glob("*.json")):
                date_str = history_file.stem  # 2026-06-11

                with open(history_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)

                # 计算当日净流入
                if records:
                    last_record = records[-1]
                    current = last_record.get("data", {}).get("current", {})
                    history.append({
                        "date": date_str,
                        "net_buy": current.get("net_buy", 0),
                        "buy": current.get("buy", 0),
                        "sell": current.get("sell", 0),
                    })

            return history

        except Exception as e:
            logger.warning(f"加载北向资金历史数据失败: {e}")
            return []

    async def close(self) -> None:
        """关闭会话"""
        await self._client.aclose()
