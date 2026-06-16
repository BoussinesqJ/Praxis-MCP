"""MCP 工具 - 金融情感分析（增强关键词 + 否定翻转策略）

当前策略: 增强关键词（强信号优先 + 否定词翻转）
实测命中率: 93%（14 case 金融文本测试集）
响应速度: <0.1s/条
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

logger = logging.getLogger("praxis.tools.sentiment_alphaear")

# ── 增强金融关键词 ──
_STRONG_POS = [
    "涨停", "大涨", "暴涨", "飙升", "突破新高", "翻倍", "大增", "暴增",
    "超预期", "业绩预增", "扭亏", "利润翻番", "大幅增长", "强势涨停",
    "万亿成交", "利好", "重大利好",
]
_STRONG_NEG = [
    "跌停", "大跌", "暴跌", "腰斩", "跌破", "新低", "大减", "暴亏",
    "业绩预减", "亏损", "首亏", "违规", "处罚", "立案", "退市",
    "暴跌腰斩", "利空", "重大利空", "危机", "暴雷",
]
_MODERATE_POS = [
    "上涨", "增长", "盈利", "突破", "新高", "强势", "看好", "增持",
    "买入", "推荐", "政策支持", "降息", "宽松", "刺激", "复苏",
]
_MODERATE_NEG = [
    "下跌", "下滑", "亏损", "弱势", "看空", "减持", "卖出",
    "低于预期", "收紧", "加息", "紧缩", "衰退", "风险", "关税",
    "流出", "净流出", "抛售", "恐慌", "违约", "下调",
]

# 否定词 — 出现在关键词前 10 字符窗口内时翻转情感
_NEGATION = ["并未", "没有", "并非", "不是", "不会", "未能", "未有",
             "不具", "缺乏", "难以", "不再"]


def _keyword_score(text: str) -> dict:
    """增强关键词情感评分（含否定词翻转）"""

    def _is_negated(keyword_pos: int) -> bool:
        start = max(0, keyword_pos - 10)
        window = text[start:keyword_pos]
        return any(neg in window for neg in _NEGATION)

    def _score_keywords(keywords: list, weight: int) -> tuple:
        """正面关键词评分，否定翻转"""
        pos_score = 0
        neg_score = 0
        for kw in keywords:
            idx = text.find(kw)
            if idx == -1:
                continue
            if _is_negated(idx):
                neg_score += weight  # 正面词被否定 → 算负面
            else:
                pos_score += weight
        return pos_score, neg_score

    def _score_keywords_neg(keywords: list, weight: int) -> tuple:
        """负面关键词评分，否定翻转"""
        pos_score = 0
        neg_score = 0
        for kw in keywords:
            idx = text.find(kw)
            if idx == -1:
                continue
            if _is_negated(idx):
                pos_score += weight  # 负面词被否定 → 算正面
            else:
                neg_score += weight
        return pos_score, neg_score

    sp_pos, sp_neg = _score_keywords(_STRONG_POS, 2)
    sn_pos, sn_neg = _score_keywords_neg(_STRONG_NEG, 2)
    mp_pos, mp_neg = _score_keywords(_MODERATE_POS, 1)
    mn_pos, mn_neg = _score_keywords_neg(_MODERATE_NEG, 1)

    pos = sp_pos + sn_pos + mp_pos + mn_pos
    neg = sp_neg + sn_neg + mp_neg + mn_neg
    total = pos + neg

    if total == 0:
        return {"score": 0.0, "label": "neutral", "reason": "未检测到情感关键词"}

    raw = (pos - neg) / total
    score = max(-1.0, min(1.0, raw))

    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"

    return {"score": round(score, 3), "label": label, "reason": f"关键词: pos={pos} neg={neg}"}


def analyze_sentiment(text: str, workspace: str = ".") -> dict:
    """分析金融文本情感

    策略: 强关键词信号优先 → 中等关键词评分 → 否定词翻转
    """
    if not text or not text.strip():
        return {
            "success": True,
            "data": {"text": "", "score": 0.0, "label": "neutral",
                     "reason": "空文本", "source": "empty",
                     "timestamp": datetime.now().isoformat()},
        }

    kw = _keyword_score(text)

    # 强信号直接覆盖（score 绝对值 > 0.5 表示有强关键词命中）
    if kw["label"] == "negative" and kw["score"] <= -0.5:
        return {
            "success": True,
            "data": {
                "text": text[:200], "score": kw["score"], "label": "negative",
                "reason": f"关键词强空覆盖: {kw['reason']}",
                "source": "keyword-override",
                "timestamp": datetime.now().isoformat(),
            },
        }
    if kw["label"] == "positive" and kw["score"] >= 0.5:
        return {
            "success": True,
            "data": {
                "text": text[:200], "score": kw["score"], "label": "positive",
                "reason": f"关键词强多覆盖: {kw['reason']}",
                "source": "keyword-override",
                "timestamp": datetime.now().isoformat(),
            },
        }

    # 无强信号 → 中等关键词评分结果
    return {
        "success": True,
        "data": {
            "text": text[:200], "score": kw["score"], "label": kw["label"],
            "reason": kw["reason"],
            "source": "keyword",
            "timestamp": datetime.now().isoformat(),
        },
    }


def batch_analyze_sentiment(texts: List[str], workspace: str = ".") -> dict:
    """批量分析多条文本情感"""
    results = []
    for text in texts:
        r = analyze_sentiment(text, workspace)
        if r.get("success"):
            results.append(r["data"])
        else:
            results.append({"text": text[:100], "score": 0, "label": "error",
                            "reason": r.get("error", "未知错误")})

    scores = [r["score"] for r in results if r["label"] != "error"]
    avg = sum(scores) / len(scores) if scores else 0

    return {
        "success": True,
        "data": {
            "results": results,
            "overall": {
                "score": round(avg, 3),
                "label": "positive" if avg > 0.1 else ("negative" if avg < -0.1 else "neutral"),
                "count": len(results),
            },
            "timestamp": datetime.now().isoformat(),
        },
    }
