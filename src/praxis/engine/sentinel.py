"""哨兵雷达引擎 — 8 ETF 多空趋势追踪 + Rule23 情绪起爆器

双层全景哨兵矩阵：
  大局风格层: 510300(沪深300), 159915(创业板), 512000(券商), 159601(恒生科技)
  执行持仓层: 512480(半导体), 515050(通信), 515220(煤炭), 511220(国债)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import httpx

from praxis.core.logging_config import get_logger

logger = get_logger(__name__)

SENTINEL_DEFINITIONS = {
    "510300": {"name": "沪深300ETF", "layer": "macro", "role": "大盘价值基准"},
    "159915": {"name": "创业板ETF", "layer": "macro", "role": "成长风险偏好"},
    "512000": {"name": "券商ETF", "layer": "macro", "role": "市场情绪温度计"},
    "159601": {"name": "恒生科技ETF", "layer": "macro", "role": "港股科技风向标"},
    "512480": {"name": "半导体ETF", "layer": "execution", "role": "硬科技弹性基准"},
    "515050": {"name": "通信ETF", "layer": "execution", "role": "通信行业哨兵"},
    "515220": {"name": "煤炭ETF", "layer": "execution", "role": "防御与红利基准"},
    "511220": {"name": "国债ETF", "layer": "execution", "role": "避险资产基准"},
}
SENTINEL_ORDER = ["510300", "159915", "512000", "159601", "512480", "515050", "515220", "511220"]

_TENCENT_PREFIX = {"5": "sh", "0": "sz", "1": "sz", "6": "sh"}


def _tencent_ticker(ticker: str) -> str:
    return f"{_TENCENT_PREFIX.get(ticker[0], 'sh')}{ticker}"


@dataclass
class SentinelState:
    ticker: str
    name: str
    layer: str
    role: str
    price: float = 0.0
    change_pct: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma30: float = 0.0
    ma60: float = 0.0
    trend: str = "unknown"
    vol_ratio: float = 1.0
    vol_desc: str = "N/A"


@dataclass
class SentinelSnapshot:
    date: str
    bullish_count: int = 0
    total: int = 8
    state: str = "unknown"
    position_limit_pct: float = 10.0
    sentinels: dict = field(default_factory=dict)
    rule23_triggered: bool = False
    rule23_consecutive_days: int = 0


async def _fetch_kline(ticker: str, count: int = 70) -> list[dict]:
    """获取历史K线（新浪 → 腾讯降级）"""
    sina_code = _tencent_ticker(ticker)
    url = (f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={sina_code}&scale=240&ma=no&datalen={count}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                result = [{"date": d["day"], "open": float(d["open"]), "close": float(d["close"]),
                           "high": float(d["high"]), "low": float(d["low"]),
                           "volume": float(d["volume"])} for d in data]
                return result[-count:] if len(result) > count else result
        except Exception as e:
            logger.warning(f"sentinel_kline_sina_failed", ticker=ticker, error=str(e))

    # 腾讯备用
    tencent_code = _tencent_ticker(ticker)
    url = f"https://web.ifzq.gtimg.cn/appnew/tech/history?code={tencent_code}&type=day"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            if data.get("code") == 0 and "data" in data:
                klines = data["data"].get("kline", [])
                result = [{"date": k[0], "open": float(k[1]), "close": float(k[2]),
                           "high": float(k[3]), "low": float(k[4]), "volume": float(k[5])}
                          for k in klines if len(k) >= 6]
                return result[-count:] if len(result) > count else result
        except Exception as e:
            logger.warning(f"sentinel_kline_tencent_failed", ticker=ticker, error=str(e))

    return []


def _compute_ma(closes: list[float], period: int) -> float:
    if len(closes) >= period:
        return sum(closes[-period:]) / period
    return sum(closes) / len(closes) if closes else 0.0


def _compute_vol_ratio(volumes: list[float]) -> float:
    if len(volumes) < 6:
        return 1.0
    avg_5d = sum(volumes[-6:-1]) / 5.0
    return volumes[-1] / avg_5d if avg_5d > 0 else 1.0


def _classify_vol(vol_ratio: float) -> str:
    if vol_ratio > 1.5:
        return f"异常放量 ({vol_ratio:.2f})"
    elif vol_ratio < 0.6:
        return f"静默缩量 ({vol_ratio:.2f})"
    return f"量平 ({vol_ratio:.2f})"


class SentinelEngine:
    """哨兵雷达引擎

    Rule 23: 情绪起爆器 — 连续2日 bullish_count≥4 触发
    Rule 26: 攻防仓位阶梯 — bullish_count 0-2防御/3-5试探/6-8进攻
    """

    POSITION_TIERS = [
        (2, "绝对防守期", 10.0),
        (4, "适度试探期", 20.0),
        (6, "积极配置期", 30.0),
        (8, "全面进攻期", 50.0),
    ]

    def __init__(self, workspace: str = ".", config_loader=None,
                 investor_id: str = "", portfolio_id: str = ""):
        self._workspace = Path(workspace)
        self._history_path = self._workspace / "data" / "sentinel_history.jsonl"
        self._history_path.parent.mkdir(parents=True, exist_ok=True)

        # 哨兵清单：优先从 config 读取，回退到模块级硬编码
        self._sentinel_defs: dict = dict(SENTINEL_DEFINITIONS)
        self._sentinel_order: list[str] = list(SENTINEL_ORDER)
        if config_loader is not None:
            try:
                portfolio = config_loader.load_portfolio(investor_id, portfolio_id)
                if portfolio.sentinels:
                    defs = {}
                    order = []
                    for s in portfolio.sentinels:
                        defs[s.ticker] = {
                            "name": s.name,
                            "layer": s.layer,
                            "role": s.role,
                        }
                        order.append(s.ticker)
                    if order:
                        self._sentinel_defs = defs
                        self._sentinel_order = order
                        logger.info("sentinel_loaded_from_config",
                                    count=len(order), investor=investor_id)
            except Exception as e:
                logger.warning("sentinel_config_load_failed",
                               error=str(e), investor=investor_id)

    async def scan(self) -> dict:
        """执行哨兵扫描"""
        snapshot = SentinelSnapshot(date=date.today().isoformat(),
                                    total=len(self._sentinel_order))

        for ticker in self._sentinel_order:
            info = self._sentinel_defs.get(ticker, {})
            klines = await _fetch_kline(ticker, count=70)

            if not klines or len(klines) < 20:
                logger.warning(f"sentinel_insufficient_data", ticker=ticker)
                snapshot.sentinels[ticker] = {"name": info.get("name", ticker),
                                               "layer": info.get("layer", ""),
                                               "trend": "unknown", "error": "数据不足"}
                continue

            closes = [k["close"] for k in klines]
            volumes = [k["volume"] for k in klines]
            last = klines[-1]

            ma10 = _compute_ma(closes, 10)
            ma20 = _compute_ma(closes, 20)
            ma30 = _compute_ma(closes, 30)
            ma60 = _compute_ma(closes, 60)
            vol_ratio = _compute_vol_ratio(volumes)

            # 多空判定：价格在 MA20 上方为多头
            if last["close"] > ma20 * 1.01:
                trend = "bullish"
            elif last["close"] < ma20 * 0.99:
                trend = "bearish"
            else:
                trend = "neutral"

            if trend == "bullish":
                snapshot.bullish_count += 1

            snapshot.sentinels[ticker] = {
                "name": info.get("name", ticker),
                "layer": info.get("layer", ""),
                "price": round(last["close"], 3),
                "change_pct": round((last["close"] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 else 0,
                "ma10": round(ma10, 3), "ma20": round(ma20, 3),
                "ma30": round(ma30, 3), "ma60": round(ma60, 3),
                "trend": trend, "vol_ratio": round(vol_ratio, 2),
                "vol_desc": _classify_vol(vol_ratio),
            }

        # 攻防判定
        for threshold, state_name, limit_pct in self.POSITION_TIERS:
            if snapshot.bullish_count <= threshold:
                snapshot.state = state_name
                snapshot.position_limit_pct = limit_pct
                break

        # Rule 23 情绪起爆器
        previous = self._load_previous_snapshot()
        if previous and previous.get("bullish_count", 0) >= 4 and snapshot.bullish_count >= 4:
            snapshot.rule23_triggered = True
            snapshot.rule23_consecutive_days = previous.get("rule23_consecutive_days", 0) + 1
        elif snapshot.bullish_count >= 4:
            snapshot.rule23_triggered = True
            snapshot.rule23_consecutive_days = 1

        self._save_snapshot(snapshot)
        return self._snapshot_to_dict(snapshot)

    def get_rule23_status(self) -> dict:
        """获取 Rule 23 状态"""
        snapshot = self._load_previous_snapshot()
        if snapshot is None:
            return {"triggered": False, "consecutive_days": 0, "bullish_count": 0,
                    "message": "无历史数据，请先执行 scan"}
        return {
            "triggered": snapshot.get("rule23_triggered", False),
            "consecutive_days": snapshot.get("rule23_consecutive_days", 0),
            "bullish_count": snapshot.get("bullish_count", 0),
            "state": snapshot.get("state", "unknown"),
            "date": snapshot.get("date", ""),
        }

    def get_history(self, days: int = 10) -> list[dict]:
        """获取哨兵历史"""
        history = []
        if not self._history_path.exists():
            return history
        with open(self._history_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    history.append(json.loads(line.strip()))
                except (json.JSONDecodeError, Exception):
                    continue
        return history[-days:]

    def _load_previous_snapshot(self) -> Optional[dict]:
        """加载上一次扫描结果"""
        if not self._history_path.exists():
            return None
        history = self.get_history(1)
        return history[0] if history else None

    def _save_snapshot(self, snapshot: SentinelSnapshot) -> None:
        """持久化哨兵快照"""
        data = self._snapshot_to_dict(snapshot)
        with open(self._history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    @staticmethod
    def _snapshot_to_dict(snapshot: SentinelSnapshot) -> dict:
        return {
            "date": snapshot.date,
            "bullish_count": snapshot.bullish_count,
            "total": snapshot.total,
            "state": snapshot.state,
            "position_limit_pct": snapshot.position_limit_pct,
            "rule23_triggered": snapshot.rule23_triggered,
            "rule23_consecutive_days": snapshot.rule23_consecutive_days,
            "sentinels": snapshot.sentinels,
        }
