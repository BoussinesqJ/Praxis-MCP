"""哨兵雷达工具 — sentinel"""
from __future__ import annotations

import json

from praxis.agents.base import Tool
from praxis.tools._schemas import SentinelInput


async def scan_sentinel(workspace: str = ".", _deps: dict | None = None) -> dict:
    """哨兵扫描"""
    engine = _deps.get("sentinel_engine") if _deps else None
    if engine is None:
        return {"success": False, "error": "SentinelEngine 未注入"}
    return await engine.scan()


async def get_rule23_status(_deps: dict | None = None) -> dict:
    """Rule 23 状态"""
    engine = _deps.get("sentinel_engine") if _deps else None
    if engine is None:
        return {"success": False, "error": "SentinelEngine 未注入"}
    return engine.get_rule23_status()


async def get_sentinel_history(days: int = 10, _deps: dict | None = None) -> dict:
    """哨兵历史"""
    engine = _deps.get("sentinel_engine") if _deps else None
    if engine is None:
        return {"success": False, "error": "SentinelEngine 未注入"}
    history = engine.get_history(days)
    return {"success": True, "data": history}


async def _scan_external(klines_json: str, _deps: dict | None = None) -> dict:
    """使用外部K线数据执行哨兵扫描

    直接使用 WorkBuddy 传入的 KlinesPayload JSON，
    绕过内部 K 线采集，计算 MA10/MA20/MA30/MA60 并判定多空。

    Args:
        klines_json: KlinesPayload JSON 字符串
        _deps: 依赖注入字典

    Returns:
        哨兵扫描结果 dict（结构同 scan_sentinel()）
    """
    if not klines_json or not klines_json.strip():
        return {"success": False, "error": "缺少外部K线数据"}

    try:
        raw = json.loads(klines_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}"}

    from praxis.core.schemas import KlinesPayload

    try:
        payload = KlinesPayload.model_validate(raw)
    except Exception as e:
        return {"success": False, "error": f"K线数据校验失败: {e}"}

    # 复用 SentinelEngine 的计算逻辑
    engine = _deps.get("sentinel_engine") if _deps else None

    # Sentinel 定义：优先从 engine 借用（已从 config 读取），回退到硬编码
    if engine is not None and getattr(engine, "_sentinel_order", None):
        SENTINEL_DEFINITIONS = engine._sentinel_defs
        SENTINEL_ORDER = engine._sentinel_order
    else:
        SENTINEL_DEFINITIONS = {
            "510300": {"name": "沪深300ETF", "layer": "macro"},
            "159915": {"name": "创业板ETF", "layer": "macro"},
            "512000": {"name": "券商ETF", "layer": "macro"},
            "159928": {"name": "消费ETF", "layer": "macro"},
            "512100": {"name": "中证1000ETF", "layer": "execution"},
            "512480": {"name": "半导体ETF", "layer": "execution"},
            "516970": {"name": "基建ETF", "layer": "execution"},
            "515220": {"name": "煤炭ETF", "layer": "execution"},
        }
        SENTINEL_ORDER = ["510300", "159915", "512000", "159928", "512100", "512480", "516970", "515220"]
    POSITION_TIERS = [
        (0, "defense", 5.0),
        (1, "fortress", 8.0),
        (3, "caution", 10.0),
        (4, "balanced", 15.0),
        (6, "offensive", 20.0),
        (8, "aggressive", 30.0),
    ]

    def _compute_ma(closes: list, period: int) -> float:
        if len(closes) < period:
            return sum(closes) / len(closes) if closes else 0.0
        return sum(closes[-period:]) / period

    def _classify_vol(ratio: float) -> str:
        if ratio > 1.5:
            return "放量"
        elif ratio > 1.0:
            return "温和放量"
        elif ratio < 0.5:
            return "缩量"
        return "正常"

    sentinels: dict = {}
    bullish_count = 0

    for ticker in SENTINEL_ORDER:
        info = SENTINEL_DEFINITIONS.get(ticker, {})
        kline_dict = payload.etf_klines.get(ticker, {})

        if not kline_dict:
            sentinels[ticker] = {
                "name": info.get("name", ticker),
                "layer": info.get("layer", ""),
                "trend": "unknown",
                "error": "外部数据中未找到该ETF",
            }
            continue

        # 从外部数据字典中提取K线列表
        kline_items: list[dict] = []
        for key in sorted(kline_dict.keys()):
            item = kline_dict[key]
            if isinstance(item, dict):
                kline_items.append(item)

        if len(kline_items) < 20:
            sentinels[ticker] = {
                "name": info.get("name", ticker),
                "layer": info.get("layer", ""),
                "trend": "unknown",
                "error": "数据不足（<20条）",
            }
            continue

        closes = [float(k.get("close", 0)) for k in kline_items]
        volumes = [float(k.get("volume", 0)) for k in kline_items]
        last = kline_items[-1]

        ma10 = _compute_ma(closes, 10)
        ma20 = _compute_ma(closes, 20)
        ma30 = _compute_ma(closes, 30)
        ma60 = _compute_ma(closes, 60)

        # 量比：最近5日 vs 前20日
        if len(volumes) >= 25:
            recent_vol = sum(volumes[-5:]) / 5
            base_vol = sum(volumes[-25:-5]) / 20
            vol_ratio = recent_vol / max(base_vol, 1)
        else:
            vol_ratio = 1.0

        # 多空判定
        last_close = float(last.get("close", 0))
        if last_close > ma20 * 1.01:
            trend = "bullish"
        elif last_close < ma20 * 0.99:
            trend = "bearish"
        else:
            trend = "neutral"

        if trend == "bullish":
            bullish_count += 1

        prev_close = closes[-2] if len(closes) >= 2 else last_close
        sentinels[ticker] = {
            "name": info.get("name", ticker),
            "layer": info.get("layer", ""),
            "price": round(last_close, 3),
            "change_pct": round((last_close - prev_close) / prev_close * 100, 2) if prev_close != 0 else 0,
            "ma10": round(ma10, 3),
            "ma20": round(ma20, 3),
            "ma30": round(ma30, 3),
            "ma60": round(ma60, 3),
            "trend": trend,
            "vol_ratio": round(vol_ratio, 2),
            "vol_desc": _classify_vol(vol_ratio),
        }

    # 攻防判定
    state = "unknown"
    position_limit_pct = 10.0
    for threshold, state_name, limit_pct in POSITION_TIERS:
        if bullish_count <= threshold:
            state = state_name
            position_limit_pct = limit_pct
            break

    return {
        "success": True,
        "data": {
            "date": payload.schema_version,
            "bullish_count": bullish_count,
            "total": len(SENTINEL_ORDER),
            "state": state,
            "position_limit_pct": position_limit_pct,
            "sentinels": sentinels,
            "source": "external",
        },
    }


async def sentinel(action: str, days: int = 10, klines_json: str = "",
                   _deps: dict | None = None) -> dict:
    """哨兵雷达路由"""
    if action == "scan_external":
        return await _scan_external(klines_json, _deps)
    elif action == "scan":
        return await scan_sentinel(_deps=_deps)
    elif action == "rule23_status":
        return await get_rule23_status(_deps=_deps)
    elif action == "history":
        return await get_sentinel_history(days, _deps=_deps)
    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(
        name="sentinel",
        description="哨兵雷达：8个ETF扫描+MA20多空判定+Rule23情绪起爆器+攻防状态。",
        input_schema=SentinelInput,
        handler=sentinel,
        agent_name="risk",
        tier="core",
    ))
