"""MCP 工具 - 金融情感分析（AlphaEar 纯 Python 引擎）

优先级链: AlphaEar (关键词+否定翻转) → 妙想 API → 关键词匹配
纯本地推理，无网络依赖，无 C-level 库，<0.1s/条。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("praxis.tools.sentiment")


def _try_alphaear(text: str) -> Optional[dict]:
    """尝试 AlphaEar 纯 Python 分析（第一优先级）"""
    try:
        from praxis.tools.sentiment_alphaear import analyze_sentiment
        result = analyze_sentiment(text)
        if result.get("success"):
            logger.info("✅ 使用 AlphaEar 情感分析")
            return result
        logger.warning(f"AlphaEar 分析失败: {result.get('error')}")
    except ImportError as e:
        logger.warning(f"AlphaEar 模块导入失败: {e}")
    except Exception as e:
        logger.warning(f"AlphaEar 异常: {e}")
    return None


def _try_mx(text: str, workspace: str) -> Optional[dict]:
    """尝试妙想 API 分析（第二优先级）"""
    try:
        import os
        if not os.getenv("MX_APIKEY"):
            logger.warning("MX_APIKEY 未设置，跳过妙想")
            return None
        from praxis.tools.sentiment_mx import analyze_sentiment
        result = analyze_sentiment(text, workspace)
        if result.get("success"):
            logger.info("✅ 使用妙想 API 情感分析")
            return {
                "success": True,
                "data": {
                    "text": text[:200],
                    "score": result.get("data", {}).get("score", 0),
                    "label": result.get("data", {}).get("label", "neutral"),
                    "reason": result.get("data", {}).get("reason", ""),
                    "source": "mx",
                    "timestamp": datetime.now().isoformat(),
                },
            }
        logger.warning(f"妙想分析失败: {result.get('error')}")
    except ImportError as e:
        logger.warning(f"妙想情感模块导入失败: {e}")
    except Exception as e:
        logger.warning(f"妙想情感异常: {e}")
    return None


def _try_keyword(text: str, workspace: str) -> dict:
    """关键词匹配分析（最终降级）"""
    try:
        from praxis.tools.sentiment_keyword import analyze_sentiment
        result = analyze_sentiment(text, workspace)
        logger.info("使用关键词情感分析（降级）")
        return {
            "success": True,
            "data": {
                "text": text[:200],
                "score": result.get("data", {}).get("score", 0),
                "label": result.get("data", {}).get("label", "neutral"),
                "reason": result.get("data", {}).get("reason", ""),
                "source": "keyword",
                "timestamp": datetime.now().isoformat(),
            },
        }
    except ImportError:
        logger.error("关键词情感分析工具也无法导入")
        return {"success": False, "error": "所有情感分析工具都不可用"}


def analyze_sentiment(
    text: str,
    workspace: str = ".",
) -> dict:
    """分析金融文本情感（优先级链自动降级）

    优先级链: AlphaEar (纯 Python) → 妙想 API → 关键词匹配

    Args:
        text: 金融文本（新闻标题、公告、研报摘要等）
        workspace: 工作目录

    Returns:
        标准化情感分析结果: score (-1.0~1.0), label, reason
    """
    if not text or not text.strip():
        return {
            "success": True,
            "data": {
                "text": "",
                "score": 0.0,
                "label": "neutral",
                "reason": "空文本",
                "timestamp": datetime.now().isoformat(),
            },
        }

    # 优先级链: AlphaEar → MX → keyword
    result = _try_alphaear(text)
    if result is not None:
        return result

    result = _try_mx(text, workspace)
    if result is not None:
        return result

    return _try_keyword(text, workspace)


def batch_analyze_sentiment(
    texts: List[str],
    workspace: str = ".",
) -> dict:
    """批量分析多条金融文本情感

    Args:
        texts: 文本列表
        workspace: 工作目录

    Returns:
        标准化批量结果
    """
    try:
        # 优先尝试 AlphaEar 批处理
        try:
            from praxis.tools.sentiment_alphaear import batch_analyze_sentiment as alphaear_batch
            result = alphaear_batch(texts, workspace)
            if result.get("success"):
                logger.info(f"✅ AlphaEar 批量分析 {len(texts)} 条")
                return result
        except Exception as e:
            logger.warning(f"AlphaEar 批量分析失败: {e}")

        # 逐条降级
        results = []
        for text in texts:
            result = analyze_sentiment(text, workspace)
            if result.get("success"):
                results.append(result.get("data", {}))
            else:
                results.append({
                    "text": text[:100],
                    "score": 0,
                    "label": "error",
                    "reason": result.get("error", "未知错误"),
                })

        scores = [r.get("score", 0) for r in results if r.get("label") != "error"]
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
                    "error_count": sum(1 for r in results if r.get("label") == "error"),
                },
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
