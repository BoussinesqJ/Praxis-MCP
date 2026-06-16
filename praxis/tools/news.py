"""MCP 工具 - 财经新闻聚合（AlphaEar 优先级链）

优先级链: AlphaEar (NewsNow API) → 妙想 API → akshare 占位
所有网络请求强制 10 秒超时保护。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("praxis.tools.news")

# 信源定义（与 AlphaEar 保持一致）
NEWS_SOURCES = {
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

FINANCE_SOURCES = ["cls", "wallstreetcn", "xueqiu"]


def _try_alphaear_news(sources, count):
    """尝试 AlphaEar / NewsNow API（第一优先级）"""
    try:
        from praxis.tools.news_alphaear import get_finance_news
        result = get_finance_news(sources, count)
        if result.get("success"):
            logger.info("✅ 使用 AlphaEar NewsNow 新闻源")
            return result
        logger.warning(f"AlphaEar 新闻获取失败: {result.get('error')}")
    except ImportError as e:
        logger.warning(f"AlphaEar 新闻模块导入失败: {e}")
    except Exception as e:
        logger.warning(f"AlphaEar 新闻异常: {e}")
    return None


def _try_mx_news(sources, count):
    """尝试妙想 API（第二优先级）"""
    try:
        import os
        if not os.getenv("MX_APIKEY"):
            logger.warning("MX_APIKEY 未设置，跳过妙想")
            return None
        from praxis.tools.news_mx import get_finance_news
        result = get_finance_news(sources, count)
        if result.get("success"):
            logger.info("✅ 使用妙想 API 新闻源")
            return result
        logger.warning(f"妙想新闻获取失败: {result.get('error')}")
    except ImportError as e:
        logger.warning(f"妙想新闻模块导入失败: {e}")
    except Exception as e:
        logger.warning(f"妙想新闻异常: {e}")
    return None


def _try_akshare_news(sources, count):
    """尝试 akshare（最终降级 — 返回安全占位数据）"""
    try:
        from praxis.tools.news_akshare import get_finance_news
        result = get_finance_news(sources, count)
        logger.info("使用 akshare 占位新闻（安全降级）")
        return result
    except ImportError:
        logger.error("akshare 新闻工具也无法导入")
    return None


def get_finance_news(
    sources: Optional[List[str]] = None,
    count: int = 10,
    workspace: str = ".",
) -> dict:
    """获取实时财经新闻（优先级链自动降级）

    Args:
        sources: 新闻源列表（默认 cls/wallstreetcn/xueqiu）
        count: 每个源获取条数
        workspace: 工作目录

    Returns:
        标准化新闻结果
    """
    if sources is None:
        sources = FINANCE_SOURCES

    # 优先级链: AlphaEar → MX → akshare
    for try_fn in [_try_alphaear_news, _try_mx_news, _try_akshare_news]:
        result = try_fn(sources, count)
        if result is not None:
            return result

    return {"success": False, "error": "所有新闻工具都不可用"}


def get_unified_trends_report(
    sources: Optional[List[str]] = None,
    workspace: str = ".",
) -> dict:
    """获取多平台综合热点报告

    Args:
        sources: 数据源列表（默认 weibo/zhihu/wallstreetcn）
        workspace: 工作目录

    Returns:
        格式化热点报告
    """
    try:
        # 优先 AlphaEar
        try:
            from praxis.tools.news_alphaear import get_trends
            result = get_trends(sources)
            if result.get("success") and result.get("data"):
                # 转换为 Markdown 报告
                report = f"# 实时全网热点汇总 ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
                actual_sources = sources or ["weibo", "zhihu", "wallstreetcn"]
                for src in actual_sources:
                    src_name = NEWS_SOURCES.get(src, src)
                    report += f"### 🔥 {src_name}\n"
                    src_items = [t for t in result["data"] if t.get("source") == src_name]
                    for item in src_items[:10]:
                        report += f"- {item.get('keyword', '')}\n"
                    report += "\n"
                return {
                    "success": True,
                    "data": {"report": report, "sources": actual_sources, "timestamp": datetime.now().isoformat()},
                }
        except Exception as e:
            logger.warning(f"AlphaEar 趋势获取失败: {e}")

        # 降级到 akshare
        from praxis.tools.news_akshare import get_trends
        sources = sources or ["weibo", "zhihu", "wallstreetcn"]
        result = get_trends(sources)
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_polymarket_summary(
    limit: int = 10,
    workspace: str = ".",
) -> dict:
    """获取 Polymarket 预测市场摘要"""
    try:
        from praxis.tools.news_alphaear import get_polymarket_summary as _pm
        return _pm(limit, workspace)
    except ImportError:
        return {"success": False, "error": "AlphaEar 新闻模块未安装"}
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
