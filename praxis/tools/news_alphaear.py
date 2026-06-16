"""MCP 工具 - 财经新闻聚合（基于 AlphaEar / NewsNow API）

直接对接 NewsNow 公开 API，支持 10+ 信源实时热点抓取。
所有网络请求强制 10 秒超时，超时静默丢弃，绝不阻塞后续调用。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger("praxis.tools.news_alphaear")

# NewsNow API
NEWSNOW_BASE_URL = "https://newsnow.busiyi.world"

# Polymarket API
POLYMARKET_BASE_URL = "https://gamma-api.polymarket.com"

# 全局超时（秒）— CTO 要求 5-10 秒
REQUEST_TIMEOUT = 10

# 信源定义
SOURCES = {
    "cls": "财联社",
    "wallstreetcn": "华尔街见闻",
    "xueqiu": "雪球热榜",
    "weibo": "微博热搜",
    "zhihu": "知乎热榜",
    "baidu": "百度热搜",
    "toutiao": "今日头条",
    "douyin": "抖音热榜",
    "thepaper": "澎湃新闻",
    "36kr": "36氪",
    "ithome": "IT之家",
    "v2ex": "V2EX",
    "juejin": "掘金",
    "hackernews": "Hacker News",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 简易内存缓存: source_id -> {"time": timestamp, "data": list}
_cache: Dict[str, dict] = {}


def _fetch_source(source_id: str, count: int = 15) -> List[dict]:
    """从 NewsNow API 获取单个信源的热点新闻（带缓存 + 超时保护）"""
    cache_key = f"{source_id}_{count}"
    now = time.time()

    # 5 分钟缓存
    cached = _cache.get(cache_key)
    if cached and (now - cached["time"] < 300):
        logger.info(f"缓存命中: {source_id}")
        return cached["data"]

    try:
        url = f"{NEWSNOW_BASE_URL}/api/s?id={source_id}"
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning(f"NewsNow API {source_id} 返回 {resp.status_code}")
            return cached["data"] if cached else []

        data = resp.json()
        items = data.get("items", [])[:count]
        result = []
        for i, item in enumerate(items, 1):
            result.append({
                "source": source_id,
                "rank": i,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": "",
                "publish_time": item.get("publish_time"),
            })

        _cache[cache_key] = {"time": now, "data": result}
        logger.info(f"✅ 获取 {source_id}: {len(result)} 条")
        return result

    except Timeout:
        logger.warning(f"⏱️ {source_id} 超时 ({REQUEST_TIMEOUT}s)，静默丢弃")
        return cached["data"] if cached else []
    except RequestException as e:
        logger.warning(f"网络错误 {source_id}: {e}")
        return cached["data"] if cached else []
    except Exception as e:
        logger.warning(f"异常 {source_id}: {e}")
        return []


def get_finance_news(
    sources: Optional[List[str]] = None,
    count: int = 10,
    workspace: str = ".",
) -> dict:
    """获取实时财经新闻（AlphaEar / NewsNow）

    Args:
        sources: 新闻源列表，默认 cls/wallstreetcn/xueqiu
        count: 每个源获取条数
        workspace: 工作目录（未使用，保持接口兼容）

    Returns:
        标准化新闻结果 dict
    """
    if sources is None:
        sources = ["cls", "wallstreetcn", "xueqiu"]

    all_news: List[dict] = []
    for src in sources:
        items = _fetch_source(src, count)
        all_news.extend(items)

    if not all_news:
        return {"success": False, "error": "所有新闻源均不可用（超时或网络异常）"}

    return {
        "success": True,
        "data": all_news,
        "count": len(all_news),
        "sources": sources,
        "source": "alphaear-newsonow",
    }


def get_trends(
    sources: Optional[List[str]] = None,
    workspace: str = ".",
) -> dict:
    """获取热点趋势（复用 NewsNow）

    Args:
        sources: 数据源列表，默认 weibo/zhihu/wallstreetcn
        workspace: 工作目录（未使用）

    Returns:
        标准化趋势结果 dict
    """
    if sources is None:
        sources = ["weibo", "zhihu", "wallstreetcn"]

    all_trends: List[dict] = []
    for src in sources:
        items = _fetch_source(src, 10)
        for item in items:
            all_trends.append({
                "source": SOURCES.get(src, src),
                "keyword": item.get("title", ""),
                "hot": "高" if item.get("rank", 99) <= 5 else "中",
            })

    return {
        "success": bool(all_trends),
        "data": all_trends,
        "count": len(all_trends),
        "sources": sources,
        "source": "alphaear-newsonow",
    }


def get_polymarket_summary(
    limit: int = 10,
    workspace: str = ".",
) -> dict:
    """获取 Polymarket 预测市场摘要

    Args:
        limit: 获取数量
        workspace: 工作目录（未使用）

    Returns:
        预测市场报告
    """
    try:
        resp = requests.get(
            f"{POLYMARKET_BASE_URL}/markets",
            params={"active": "true", "closed": "false", "limit": limit},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return {"success": False, "error": f"Polymarket API 返回 {resp.status_code}"}

        markets = resp.json()
        report_lines = [
            f"# 🔮 Polymarket 热门预测 ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
        ]
        for i, m in enumerate(markets, 1):
            question = m.get("question", "Unknown")
            prices = m.get("outcomePrices", [])
            volume = m.get("volume", 0)
            line = f"**{i}. {question}**"
            if prices:
                line += f"\n   概率: {prices}"
            if volume:
                line += f"\n   交易量: ${float(volume):,.0f}"
            report_lines.append(line)

        return {
            "success": True,
            "data": {"report": "\n\n".join(report_lines), "count": len(markets)},
            "source": "alphaear-polymarket",
        }
    except Timeout:
        return {"success": False, "error": "Polymarket 请求超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}
