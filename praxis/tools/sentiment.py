"""MCP 工具 - 金融情感分析（基于 AlphaEar）

集成 AlphaEar 的 FinBERT 情感分析能力。
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("praxis.tools.sentiment")


def _get_sentiment_tools():
    """延迟加载 AlphaEar 情感分析工具"""
    import sys
    from pathlib import Path

    alphaear_path = Path.home() / "Desktop" / "Praxis management" / ".agent" / "skills" / "AF" / "skills" / "alphaear-sentiment" / "scripts"
    if alphaear_path.exists() and str(alphaear_path.parent) not in sys.path:
        sys.path.insert(0, str(alphaear_path.parent))

    try:
        from scripts.sentiment_tools import SentimentTools
        from scripts.database_manager import DatabaseManager
        db = DatabaseManager()
        return SentimentTools(db)
    except ImportError as e:
        logger.warning(f"AlphaEar 情感分析工具导入失败: {e}")
        return None


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
        sentiment_tools = _get_sentiment_tools()
        if not sentiment_tools:
            return {"success": False, "error": "AlphaEar 情感分析工具未安装，请检查 skills 目录"}

        result = sentiment_tools.analyze_sentiment(text)

        return {
            "success": True,
            "data": {
                "text": text[:200],  # 截断过长文本
                "score": result.get("score", 0),
                "label": result.get("label", "neutral"),
                "reason": result.get("reason", ""),
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def batch_analyze_sentiment(
    texts: list[str],
    workspace: str = ".",
) -> dict:
    """批量分析多条金融文本情感

    Args:
        texts: 要分析的文本列表
        workspace: 工作目录

    Returns:
        每条文本的情感分析结果
    """
    try:
        sentiment_tools = _get_sentiment_tools()
        if not sentiment_tools:
            return {"success": False, "error": "AlphaEar 情感分析工具未安装"}

        results = []
        for text in texts:
            try:
                result = sentiment_tools.analyze_sentiment(text)
                results.append({
                    "text": text[:100],
                    "score": result.get("score", 0),
                    "label": result.get("label", "neutral"),
                    "reason": result.get("reason", ""),
                })
            except Exception as e:
                results.append({
                    "text": text[:100],
                    "score": 0,
                    "label": "error",
                    "reason": str(e),
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
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
