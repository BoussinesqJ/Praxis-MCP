"""情感分析 — sentiment (关键词匹配+否定翻转)"""
from __future__ import annotations
from praxis.agents.base import Tool
from praxis.tools._schemas import SentimentInput

POSITIVE = {"涨", "增长", "利好", "突破", "强劲", "盈利", "反弹", "创新高", "涨停", "超预期"}
NEGATIVE = {"跌", "下跌", "利空", "破位", "亏损", "暴跌", "减持", "退市", "跌停", "低于预期"}
NEGATORS = {"不", "没有", "未", "非", "无"}

def _analyze(text: str) -> dict:
    pos = sum(1 for w in POSITIVE if w in text)
    neg = sum(1 for w in NEGATIVE if w in text)
    for negator in NEGATORS:
        for w in list(POSITIVE):
            if f"{negator}{w}" in text:
                pos -= 1; neg += 1
        for w in list(NEGATIVE):
            if f"{negator}{w}" in text:
                neg -= 1; pos += 1
    total = pos + neg
    score = (pos - neg) / max(total, 1)
    label = "positive" if score > 0.2 else ("negative" if score < -0.2 else "neutral")
    return {"score": round(score, 3), "label": label, "positive_count": pos, "negative_count": neg}

async def sentiment(action: str, text: str | None = None, texts: list[str] | None = None,
                    _deps: dict | None = None) -> dict:
    if action == "analyze" and text:
        return {"success": True, "data": _analyze(text)}
    elif action == "batch" and texts:
        return {"success": True, "data": [_analyze(t) for t in texts]}
    return {"success": False, "error": "需要 text(texts) 参数"}

def register(registry):
    registry.register(Tool(name="sentiment", description="金融文本情感分析：关键词匹配+否定翻转",
                           input_schema=SentimentInput, handler=sentiment, agent_name="market", tier="core"))
