"""MCP 工具 - 财经新闻聚合（基于 AlphaEar）

集成 AlphaEar 的新闻获取能力，支持 10+ 信源实时热点。
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("praxis.tools.news")

# 新闻源定义
NEWS_SOURCES = {
    # 金融类
    "cls": "财联社",
    "wallstreetcn": "华尔街见闻",
    "xueqiu": "雪球热榜",
    # 综合/社交
    "weibo": "微博热搜",
    "zhihu": "知乎热榜",
    "baidu": "百度热搜",
    "toutiao": "今日头条",
    "douyin": "抖音热榜",
    "thepaper": "澎湃新闻",
    # 科技类
    "36kr": "36氪",
    "ithome": "IT之家",
    "v2ex": "V2EX",
    "juejin": "掘金",
    "hackernews": "Hacker News",
}

# 金融相关信源（默认使用）
FINANCE_SOURCES = ["cls", "wallstreetcn", "xueqiu"]


def _get_news_tools():
    """延迟加载 AlphaEar 新闻工具"""
    import sys
    from pathlib import Path

    # 添加 AlphaEar skills 路径
    alphaear_path = Path.home() / "Desktop" / "Praxis management" / ".agent" / "skills" / "AF" / "skills" / "alphaear-news" / "scripts"
    if alphaear_path.exists() and str(alphaear_path.parent) not in sys.path:
        sys.path.insert(0, str(alphaear_path.parent))

    try:
        from scripts.news_tools import NewsNowTools, PolymarketTools
        from scripts.database_manager import DatabaseManager
        db = DatabaseManager()
        return NewsNowTools(db), PolymarketTools(db)
    except ImportError as e:
        logger.warning(f"AlphaEar 新闻工具导入失败: {e}")
        return None, None


def get_finance_news(
    sources: list[str] | None = None,
    count: int = 10,
    workspace: str = ".",
) -> dict:
    """获取实时财经新闻

    Args:
        sources: 新闻源列表（默认: cls/wallstreetcn/xueqiu）
        count: 每个源获取的新闻数量
        workspace: 工作目录

    Returns:
        新闻列表，按源分组
    """
    try:
        news_tools, _ = _get_news_tools()
        if not news_tools:
            return {"success": False, "error": "AlphaEar 新闻工具未安装，请检查 skills 目录"}

        sources = sources or FINANCE_SOURCES
        all_news = []

        for source_id in sources:
            if source_id not in NEWS_SOURCES:
                continue
            items = news_tools.fetch_hot_news(source_id, count=count)
            for item in items:
                item["source_name"] = NEWS_SOURCES.get(source_id, source_id)
            all_news.extend(items)

        return {
            "success": True,
            "data": {
                "total": len(all_news),
                "sources": sources,
                "news": all_news,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_unified_trends_report(
    sources: list[str] | None = None,
    workspace: str = ".",
) -> dict:
    """获取多平台综合热点报告

    Args:
        sources: 新闻源列表（默认: weibo/zhihu/wallstreetcn）
        workspace: 工作目录

    Returns:
        格式化的 Markdown 热点汇总报告
    """
    try:
        news_tools, _ = _get_news_tools()
        if not news_tools:
            return {"success": False, "error": "AlphaEar 新闻工具未安装"}

        sources = sources or ["weibo", "zhihu", "wallstreetcn"]
        report = news_tools.get_unified_trends(sources)

        return {
            "success": True,
            "data": {
                "report": report,
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_polymarket_summary(
    limit: int = 10,
    workspace: str = ".",
) -> dict:
    """获取 Polymarket 预测市场摘要

    Args:
        limit: 获取的市场数量
        workspace: 工作目录

    Returns:
        预测市场报告
    """
    try:
        _, polymarket_tools = _get_news_tools()
        if not polymarket_tools:
            return {"success": False, "error": "AlphaEar 新闻工具未安装"}

        report = polymarket_tools.get_market_summary(limit)

        return {
            "success": True,
            "data": {
                "report": report,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_news_sources() -> dict:
    """列出所有支持的新闻源"""
    return {
        "success": True,
        "data": {
            "sources": NEWS_SOURCES,
            "finance_sources": FINANCE_SOURCES,
            "total": len(NEWS_SOURCES),
        },
    }
