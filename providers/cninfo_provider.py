"""巨潮公告数据源

基于 Gemini Phase 3 建议：
- 禁止下载庞大的 PDF 原文件全文
- 只需要"公告元数据"（发布时间、公告标题、摘要链接）
- 使用巨潮 /api/disc/queryAnnouncements HTTP 接口
- 1 小时 TTL 缓存

使用方式：
    from providers.cninfo_provider import CninfoProvider

    provider = CninfoProvider()
    
    # 获取公告列表
    announcements = await provider.get_announcements("000001")
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from praxis.core.cache import TTLCache, get_cache, CacheConfig

logger = logging.getLogger("praxis.provider.cninfo")

# 巨潮公告 API
CNINFO_ANNOUNCEMENTS_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

# 缓存配置（1小时）
CNINFO_CACHE_CONFIG = CacheConfig(
    default_ttl=3600,  # 1小时
    max_size=200,
    enable_persistence=True,
    cache_dir="cache/cninfo",
)


class CninfoProvider:
    """巨潮公告数据源

    特性：
    - 只获取公告元数据（不下载 PDF）
    - 1 小时 TTL 缓存
    - 低风险数据源
    """

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=8.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "http://www.cninfo.com.cn/",
                "Accept": "application/json",
            },
        )

        # 缓存
        self._cache = get_cache("cninfo", CNINFO_CACHE_CONFIG)

    async def get_announcements(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30,
    ) -> list[dict]:
        """获取公告列表（元数据）

        Args:
            ticker: 股票代码
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            limit: 返回数量

        Returns:
            公告元数据列表
        """
        # 构建缓存键
        cache_key = f"announcements:{ticker}:{start_date}:{end_date}:{limit}"

        # 检查缓存
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug(f"缓存命中: {cache_key}")
            return cached

        try:
            # 构建请求参数
            params = {
                "pageNum": "1",
                "pageSize": str(limit),
                "tabName": "fulltext",
                "plate": "",
                "stock": ticker,
                "searchkey": "",
                "secid": "",
                "category": "",
                "trade": "",
                "seDate": "",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            }

            # 添加日期范围
            if start_date and end_date:
                params["seDate"] = f"{start_date}~{end_date}"

            # 发送请求
            resp = await self._client.post(
                CNINFO_ANNOUNCEMENTS_URL,
                data=params,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or "announcements" not in data:
                return []

            announcements = data.get("announcements", [])
            if not announcements:
                return []

            result = []
            for item in announcements:
                # 构建 PDF 链接（不下载）
                adjunct_url = item.get("adjunctUrl", "")
                pdf_url = f"http://static.cninfo.com.cn/{adjunct_url}" if adjunct_url else ""

                result.append({
                    "id": item.get("announcementId", ""),
                    "title": item.get("announcementTitle", ""),
                    "time": item.get("announcementTime", ""),
                    "stock_code": item.get("secCode", ""),
                    "stock_name": item.get("secName", ""),
                    "pdf_url": pdf_url,
                    "has_pdf": bool(adjunct_url),
                })

            # 写入缓存（1小时）
            self._cache.set(cache_key, result, ttl=3600)

            return result

        except Exception as e:
            logger.warning(f"获取 {ticker} 公告失败: {e}")
            return []

    async def close(self) -> None:
        """关闭会话"""
        await self._client.aclose()
