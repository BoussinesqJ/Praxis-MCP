"""MCP 工具 - 金融情感分析（基于妙想 API）

使用妙想 API 进行情感分析，作为主数据源。
通过 API + Key 获取数据，最准确。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger("praxis.tools.sentiment")

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


def analyze_sentiment(
    text: str,
    workspace: str = ".",
) -> dict:
    """分析金融文本情感（使用妙想 API）

    Args:
        text: 要分析的金融文本（新闻标题、公告、研报摘要等）
        workspace: 工作目录

    Returns:
        情感分析结果：score (-1.0~1.0), label (positive/negative/neutral), reason
    """
    try:
        if not text:
            return {
                "success": True,
                "data": {
                    "score": 0.0,
                    "label": "neutral",
                    "reason": "空文本",
                }
            }
        
        # 使用妙想 API 分析情感
        query = f"分析以下文本的情感倾向（看多/看空/中性）：{text}"
        data = _query_mx(query)
        
        # 解析返回数据
        tables = (
            data.get("data", {})
            .get("data", {})
            .get("searchDataResultDTO", {})
            .get("dataTableDTOList", [])
        )
        
        # 默认值
        score = 0.0
        label = "neutral"
        reason = "妙想 API 分析结果：中性"
        positive_count = 0
        negative_count = 0
        
        # 解析情感分析结果
        for table in tables:
            table_data = table.get("table", {})
            entity_name = table.get("entityName", "")
            
            if isinstance(table_data, dict):
                # 检查表格数据中的正面/负面指标
                for key, value in table_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        result_text = str(value[0])
                        
                        # 检查正面指标
                        if key == "100000000001395":  # 业绩预告类型
                            if "预增" in result_text or "预盈" in result_text or "扭亏" in result_text or "大幅上升" in result_text:
                                positive_count += 2
                                reason = f"妙想 API：{entity_name} 业绩预增"
                            elif "预减" in result_text or "预亏" in result_text or "大幅下降" in result_text or "首亏" in result_text:
                                negative_count += 2
                                reason = f"妙想 API：{entity_name} 业绩预减"
                            elif "续盈" in result_text or "略增" in result_text:
                                positive_count += 1
                                reason = f"妙想 API：{entity_name} 业绩续盈"
                            elif "续亏" in result_text or "略减" in result_text:
                                negative_count += 1
                                reason = f"妙想 API：{entity_name} 业绩续亏"
                        
                        # 检查其他正面/负面指标
                        if "增长" in result_text or "超预期" in result_text or "利好" in result_text:
                            positive_count += 1
                        if "下降" in result_text or "低于预期" in result_text or "利空" in result_text:
                            negative_count += 1
        
        # 计算情感分数
        if positive_count > negative_count:
            score = min(0.9, 0.5 + (positive_count - negative_count) * 0.1)
            label = "positive"
        elif negative_count > positive_count:
            score = max(-0.9, -0.5 - (negative_count - positive_count) * 0.1)
            label = "negative"
        else:
            score = 0.0
            label = "neutral"
        
        return {
            "success": True,
            "data": {
                "score": round(score, 2),
                "label": label,
                "reason": reason,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "source": "mx",
                "timestamp": datetime.now().isoformat(),
            },
        }
        
    except Exception as e:
        logger.error(f"情感分析失败: {e}")
        return {"success": False, "error": str(e)}


def batch_analyze_sentiment(
    texts: list[str],
    workspace: str = ".",
) -> dict:
    """批量分析金融文本情感（使用妙想 API）

    Args:
        texts: 要分析的文本列表
        workspace: 工作目录

    Returns:
        情感分析结果列表
    """
    try:
        results = []
        for text in texts:
            result = analyze_sentiment(text, workspace)
            if result.get("success"):
                results.append(result.get("data", {}))
            else:
                results.append({
                    "score": 0.0,
                    "label": "error",
                    "reason": result.get("error", "未知错误"),
                })
        
        # 计算整体情感
        scores = [r["score"] for r in results if r["label"] != "error"]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        if avg_score > 0.1:
            overall_label = "positive"
        elif avg_score < -0.1:
            overall_label = "negative"
        else:
            overall_label = "neutral"
        
        return {
            "success": True,
            "data": {
                "results": results,
                "overall": {
                    "score": round(avg_score, 3),
                    "label": overall_label,
                    "count": len(results),
                    "error_count": sum(1 for r in results if r["label"] == "error"),
                },
                "source": "mx",
                "timestamp": datetime.now().isoformat(),
            },
        }
        
    except Exception as e:
        logger.error(f"批量情感分析失败: {e}")
        return {"success": False, "error": str(e)}
