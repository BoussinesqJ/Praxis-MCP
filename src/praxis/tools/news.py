"""新闻情报 — news (财联社/华尔街见闻/雪球 + 热点趋势 + Polymarket)

分层实现：
  L1 财经快讯: cls（财联社）/ wallstreetcn（华尔街见闻）/ xueqiu（雪球）
  L2 热搜趋势: weibo（微博热搜）/ zhihu（知乎热榜）
  L3 预测市场: polymarket（暂留占位）

每个数据源独立 try/except，一个失败不影响其他。
使用共享 httpx.AsyncClient 连接池复用。
"""
from __future__ import annotations

import httpx

from praxis.agents.base import Tool
from praxis.tools._schemas import NewsInput

# ── 数据源 URL 配置 ──────────────────────────────────────────────

_SOURCE_URLS = {
    "cls": "https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=8.4.6",
    "wallstreetcn": "https://api-one.wallstcn.com/apiv1/content/lives",
    "xueqiu": "https://xueqiu.com/v4/statuses/public_timeline_by_category.json",
    "weibo": "https://weibo.com/ajax/side/hotSearch",
    "zhihu": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
}

_SOURCE_LABELS = {
    "cls": "财联社",
    "wallstreetcn": "华尔街见闻",
    "xueqiu": "雪球",
    "weibo": "微博热搜",
    "zhihu": "知乎热榜",
    "polymarket": "预测市场",
}

_REQ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

_REQ_TIMEOUT = 10.0


# ── 数据源解析 ──────────────────────────────────────────────────


def _parse_cls(data: dict | list, count: int) -> list[dict]:
    """解析财联社 API 响应

    财联社 /api/sw 返回格式:
      {"data": {"roll_data": [{"title": "...", "ctime": 123456, "id": 123}, ...]}}
    """
    items: list[dict] = []
    try:
        if isinstance(data, dict):
            roll_data = data.get("data", {}).get("roll_data", [])
        elif isinstance(data, list):
            roll_data = data
        else:
            return items

        for item in roll_data[:count]:
            if isinstance(item, dict):
                items.append({
                    "title": item.get("title", ""),
                    "url": f"https://www.cls.cn/detail/{item.get('id', '')}",
                    "time": item.get("ctime", ""),
                    "source": "cls",
                })
    except Exception:
        pass
    return items


def _parse_wallstreetcn(data: dict, count: int) -> list[dict]:
    """解析华尔街见闻 API 响应

    见闻 /apiv1/content/lives 返回格式:
      {"data": {"items": [{"title": "...", "id": 123, "display_time": 123456}, ...]}}
    """
    items: list[dict] = []
    try:
        raw_items = data.get("data", {}).get("items", [])
        for item in raw_items[:count]:
            if isinstance(item, dict):
                items.append({
                    "title": item.get("title", ""),
                    "url": f"https://wallstreetcn.com/livenews/{item.get('id', '')}",
                    "time": item.get("display_time", ""),
                    "source": "wallstreetcn",
                })
    except Exception:
        pass
    return items


def _parse_xueqiu(data: dict, count: int) -> list[dict]:
    """解析雪球 API 响应

    雪球 timeline API 返回格式:
      {"list": [{"title": "...", "target": "...", "created_at": 123456}, ...]}
    """
    items: list[dict] = []
    try:
        raw_items = data.get("list", [])
        for item in raw_items[:count]:
            if isinstance(item, dict):
                items.append({
                    "title": item.get("title", item.get("text", ""))[:200],
                    "url": f"https://xueqiu.com{item.get('target', '')}",
                    "time": item.get("created_at", ""),
                    "source": "xueqiu",
                })
    except Exception:
        pass
    return items


def _parse_weibo(data: dict, count: int) -> list[dict]:
    """解析微博热搜 API 响应

    微博 /ajax/side/hotSearch 返回格式:
      {"data": {"realtime": [{"word": "...", "word_scheme": "#...", "rank": 1}, ...]}}
    """
    items: list[dict] = []
    try:
        realtime = data.get("data", {}).get("realtime", [])
        for item in realtime[:count]:
            if isinstance(item, dict):
                word = item.get("word", "")
                scheme = item.get("word_scheme", "")
                items.append({
                    "title": word,
                    "url": f"https://s.weibo.com/weibo?q={scheme.replace('#', '%23')}" if scheme else "",
                    "time": "",
                    "source": "weibo",
                    "rank": item.get("rank", 0),
                    "hot_value": item.get("num", 0),
                })
    except Exception:
        pass
    return items


def _parse_zhihu(data: dict, count: int) -> list[dict]:
    """解析知乎热榜 API 响应

    知乎 hot-lists 返回格式:
      {"data": [{"target": {"title": "...", "id": 123, "url": "..."}}, ...]}
    """
    items: list[dict] = []
    try:
        raw_data = data.get("data", [])
        for item in raw_data[:count]:
            if isinstance(item, dict):
                target = item.get("target", {})
                items.append({
                    "title": target.get("title", ""),
                    "url": target.get("url", f"https://www.zhihu.com/question/{target.get('id', '')}"),
                    "time": item.get("updated", ""),
                    "source": "zhihu",
                    "detail_text": target.get("excerpt", ""),
                })
    except Exception:
        pass
    return items


# ── 数据源请求 ──────────────────────────────────────────────────


async def _fetch_finance_sources(
    client: httpx.AsyncClient, sources: list[str], count: int
) -> dict[str, list[dict]]:
    """并行拉取财经新闻源（独立容错）"""
    import asyncio

    async def fetch_one(src: str) -> list[dict]:
        url = _SOURCE_URLS.get(src, "")
        if not url:
            return []

        try:
            resp = await client.get(url, headers=_REQ_HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                if src == "cls":
                    return _parse_cls(data, count)
                elif src == "wallstreetcn":
                    return _parse_wallstreetcn(data, count)
                elif src == "xueqiu":
                    return _parse_xueqiu(data, count)
            return []
        except Exception:
            return []

    results = {}
    for src in sources:
        results[src] = await fetch_one(src)
    return results


async def _fetch_trends_sources(
    client: httpx.AsyncClient, sources: list[str], count: int
) -> dict[str, list[dict]]:
    """并行拉取热搜趋势源（独立容错）"""
    import asyncio

    async def fetch_one(src: str) -> list[dict]:
        url = _SOURCE_URLS.get(src, "")
        if not url:
            return []

        try:
            resp = await client.get(url, headers=_REQ_HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                if src == "weibo":
                    return _parse_weibo(data, count)
                elif src == "zhihu":
                    return _parse_zhihu(data, count)
            return []
        except Exception:
            return []

    results = {}
    for src in sources:
        results[src] = await fetch_one(src)
    return results


# ── 主入口 ──────────────────────────────────────────────────────


async def news(
    action: str = "finance",
    sources: list[str] | None = None,
    count: int = 10,
    limit: int = 10,
    _deps: dict | None = None,
) -> dict:
    """新闻情报统一入口

    Args:
        action: finance / trends / polymarket / list_sources
        sources: 数据源列表，finance 默认 cls/wallstreetcn/xueqiu，
                 trends 默认 weibo/zhihu
        count: 每个数据源返回条数
        limit: 兼容参数（同 count）
        _deps: 依赖注入（预留）

    Returns:
        {"success": True/False, "data": {...}} 或 {"success": False, "error": "..."}
    """
    # ── list_sources：直接返回 ──
    if action == "list_sources":
        return {
            "success": True,
            "data": [
                "cls (财联社)",
                "wallstreetcn (华尔街见闻)",
                "xueqiu (雪球)",
                "weibo (微博热搜)",
                "zhihu (知乎热榜)",
                "polymarket (预测市场)",
            ],
        }

    # ── httpx 可用性检查 ──
    try:
        import httpx as _htx_check  # noqa: F811
    except ImportError:
        return {"success": False, "error": "httpx未安装，无法获取在线新闻数据"}

    # ── 创建共享连接池 ──
    async with httpx.AsyncClient(timeout=_REQ_TIMEOUT) as client:
        try:
            # ── finance ──
            if action == "finance":
                srcs = sources or ["cls", "wallstreetcn", "xueqiu"]
                results = await _fetch_finance_sources(client, srcs, count or limit)

                if any(v for v in results.values()):
                    return {"success": True, "data": results}

                return {"success": False, "error": "所有新闻源获取失败"}

            # ── trends ──
            elif action == "trends":
                srcs = sources or ["weibo", "zhihu"]
                results = await _fetch_trends_sources(client, srcs, count or limit)

                if any(v for v in results.values()):
                    return {"success": True, "data": results}

                return {"success": False, "error": "所有热搜源获取失败"}

            # ── polymarket ──
            elif action == "polymarket":
                return {
                    "success": True,
                    "data": {"message": "Polymarket API需代理访问，请通过外部工具获取预测市场数据"},
                }

            else:
                return {"success": False, "error": f"未知 action: {action}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


def register(registry):
    registry.register(
        Tool(
            name="news",
            description="新闻情报：财经新闻/热点趋势/预测市场",
            input_schema=NewsInput,
            handler=news,
            agent_name="market",
            tier="core",
        )
    )
