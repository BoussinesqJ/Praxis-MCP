"""MCP 工具 - 财经新闻聚合（基于妙想 API）

使用妙想 API 获取财经新闻，作为主数据源。
通过 API + Key 获取数据，最准确。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger("praxis.tools.news")

# 妙想 API 配置
MX_API_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"


def _get_mx_api_key():
    """获取妙想 API Key"""
    return os.getenv("MX_APIKEY")


def _query_mx(query: str) -> dict:
    """调用妙想 API 查询数据"""
    api_key = _get_mx_api_key()
    if not api_key:
        raise Exception("MX_APIKEY 未设置")

    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
    }
    data = {"toolQuery": query}

    resp = requests.post(MX_API_URL, headers=headers, json=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_finance_news(
    sources: list[str] | None = None,
    count: int = 10,
    workspace: str = ".",
) -> dict:
    """获取财经新闻（使用妙想 API）

    Args:
        sources: 新闻源列表（暂不使用，妙想 API 统一返回）
        count: 获取的新闻数量
        workspace: 工作目录

    Returns:
        新闻列表
    """
    try:
        # 使用妙想 API 查询财经新闻
        query = "今日财经新闻 重大消息 政策 公司公告"
        data = _query_mx(query)
        
        # 解析返回数据
        news_list = []
        tables = (
            data.get("data", {})
            .get("data", {})
            .get("searchDataResultDTO", {})
            .get("dataTableDTOList", [])
        )
        
        for table in tables:
            table_data = table.get("table", {})
            entity_name = table.get("entityName", "")
            
            # 解析新闻数据
            if isinstance(table_data, dict):
                for key, value in table_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        for item in value:
                            if isinstance(item, str) and len(item) > 10:
                                news_list.append({
                                    "source": "妙想",
                                    "title": item[:100],
                                    "content": item,
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                })
        
        # 如果没有解析到新闻（dataTableDTOList 为空），返回提示
        if not news_list:
            return {"success": False, "error": "妙想 API 暂不支持新闻查询"}
        
        return {
            "success": True,
            "data": news_list[:count],
            "count": len(news_list[:count]),
            "source": "mx",
        }
        
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        return {"success": False, "error": str(e)}


def get_unified_trends_report(
    sources: list[str] | None = None,
    workspace: str = ".",
) -> dict:
    """获取热点趋势报告（使用妙想 API）

    Args:
        sources: 数据源列表（暂不使用）
        workspace: 工作目录

    Returns:
        热点趋势报告
    """
    try:
        # 使用妙想 API 查询热点趋势
        query = "今日热点 市场情绪 板块轮动 资金流向"
        data = _query_mx(query)
        
        # 解析返回数据
        trends = []
        tables = (
            data.get("data", {})
            .get("data", {})
            .get("searchDataResultDTO", {})
            .get("dataTableDTOList", [])
        )
        
        for table in tables:
            table_data = table.get("table", {})
            entity_name = table.get("entityName", "")
            
            # 解析趋势数据
            if isinstance(table_data, dict):
                for key, value in table_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        for item in value:
                            if isinstance(item, str) and len(item) > 5:
                                trends.append({
                                    "source": "妙想",
                                    "keyword": item[:50],
                                    "hot": "高",
                                })
        
        return {
            "success": True,
            "data": trends,
            "count": len(trends),
            "source": "mx",
        }
        
    except Exception as e:
        logger.error(f"获取趋势失败: {e}")
        return {"success": False, "error": str(e)}
