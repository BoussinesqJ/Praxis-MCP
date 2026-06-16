"""MCP 工具 - 金融情感分析（基于关键词）

使用关键词匹配进行简单的情感分析，替代 AlphaEar。
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("praxis.tools.sentiment")

# 正面关键词
POSITIVE_KEYWORDS = [
    "利好", "上涨", "增长", "盈利", "超预期", "突破", "新高", "涨停",
    "大增", "暴增", "翻倍", "强势", "看好", "增持", "买入", "推荐",
    "业绩好", "利润增", "收入增", "订单增", "签约", "中标", "获批",
    "政策支持", "补贴", "减税", "降息", "宽松", "刺激", "复苏",
]

# 负面关键词
NEGATIVE_KEYWORDS = [
    "利空", "下跌", "亏损", "下滑", "低于预期", "跌破", "新低", "跌停",
    "大减", "暴跌", "腰斩", "弱势", "看空", "减持", "卖出", "回避",
    "业绩差", "利润降", "收入降", "订单减", "违约", "违规", "处罚",
    "政策收紧", "加税", "加息", "紧缩", "衰退", "危机", "风险",
]


def analyze_sentiment(
    text: str,
    workspace: str = ".",
) -> dict:
    """分析金融文本情感

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
        
        # 统计正面和负面关键词
        positive_count = 0
        negative_count = 0
        
        for keyword in POSITIVE_KEYWORDS:
            if keyword in text:
                positive_count += 1
        
        for keyword in NEGATIVE_KEYWORDS:
            if keyword in text:
                negative_count += 1
        
        # 计算情感分数
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            label = "neutral"
            reason = "未检测到明显情感关键词"
        else:
            score = (positive_count - negative_count) / total
            if score > 0.3:
                label = "positive"
                reason = f"检测到 {positive_count} 个正面关键词，{negative_count} 个负面关键词"
            elif score < -0.3:
                label = "negative"
                reason = f"检测到 {positive_count} 个正面关键词，{negative_count} 个负面关键词"
            else:
                label = "neutral"
                reason = f"检测到 {positive_count} 个正面关键词，{negative_count} 个负面关键词，情感倾向不明显"
        
        return {
            "success": True,
            "data": {
                "score": round(score, 2),
                "label": label,
                "reason": reason,
                "positive_count": positive_count,
                "negative_count": negative_count,
            }
        }
        
    except Exception as e:
        logger.error(f"情感分析失败: {e}")
        return {"success": False, "error": str(e)}


def batch_analyze_sentiment(
    texts: list[str],
    workspace: str = ".",
) -> dict:
    """批量分析金融文本情感

    Args:
        texts: 要分析的金融文本列表
        workspace: 工作目录

    Returns:
        情感分析结果列表
    """
    try:
        results = []
        for text in texts:
            result = analyze_sentiment(text, workspace)
            results.append(result.get("data", {}))
        
        return {
            "success": True,
            "data": results,
            "count": len(results),
        }
        
    except Exception as e:
        logger.error(f"批量情感分析失败: {e}")
        return {"success": False, "error": str(e)}
