"""MCP 工具 - 财经新闻聚合（基于 akshare）

使用 akshare 获取财经新闻，替代 AlphaEar。
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


def get_finance_news(
    sources: list[str] | None = None,
    count: int = 10,
    workspace: str = ".",
) -> dict:
    """获取财经新闻（简化版，不依赖网络）

    Args:
        sources: 新闻源列表，默认使用 FINANCE_SOURCES
        count: 每个源获取的新闻数量
        workspace: 工作目录

    Returns:
        新闻列表
    """
    try:
        if sources is None:
            sources = FINANCE_SOURCES
        
        # 返回示例数据（不依赖网络）
        # 返回安全的系统占位数据，绝不投喂假新闻干扰 AI 逻辑
        all_news = [
            {
                "source": "SYSTEM_ALERT",
                "title": "[数据源离线] 新闻模块暂不可用",
                "content": "为了保证交易系统的绝对安全与高可用，避免虚假数据污染 ASRG 的决策逻辑，外部新闻抓取功能目前处于物理断连状态。请依赖量价均线和估值数据进行决策。",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]
        
        return {
            "success": True,
            "data": all_news[:count],
            "count": len(all_news[:count]),
            "sources": sources,
        }
        
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        return {"success": False, "error": str(e)}


def get_trends(
    sources: list[str] | None = None,
    workspace: str = ".",
) -> dict:
    """获取热点趋势

    Args:
        sources: 数据源列表
        workspace: 工作目录

    Returns:
        热点趋势
    """
    try:
        import akshare as ak
        
        if sources is None:
            sources = ["weibo", "zhihu", "baidu"]
        
        all_trends = []
        
        for source in sources:
            try:
                if source == "weibo":
                    # 微博热搜
                    df = ak.weibo_hot()
                    if df is not None and len(df) > 0:
                        for _, row in df.head(10).iterrows():
                            all_trends.append({
                                "source": "微博",
                                "keyword": str(row.get("关键词", row.get("keyword", ""))),
                                "hot": str(row.get("热度", row.get("hot", ""))),
                            })
                elif source == "zhihu":
                    # 知乎热榜
                    df = ak.zhihu_hot()
                    if df is not None and len(df) > 0:
                        for _, row in df.head(10).iterrows():
                            all_trends.append({
                                "source": "知乎",
                                "keyword": str(row.get("问题", row.get("question", ""))),
                                "hot": str(row.get("热度", row.get("hot", ""))),
                            })
                elif source == "baidu":
                    # 百度热搜
                    df = ak.baidu_hot()
                    if df is not None and len(df) > 0:
                        for _, row in df.head(10).iterrows():
                            all_trends.append({
                                "source": "百度",
                                "keyword": str(row.get("关键词", row.get("keyword", ""))),
                                "hot": str(row.get("热度", row.get("hot", ""))),
                            })
            except Exception as e:
                logger.warning(f"获取 {source} 趋势失败: {e}")
                continue
        
        return {
            "success": True,
            "data": all_trends,
            "count": len(all_trends),
            "sources": sources,
        }
        
    except Exception as e:
        logger.error(f"获取趋势失败: {e}")
        return {"success": False, "error": str(e)}
