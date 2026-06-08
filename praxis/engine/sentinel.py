"""哨兵雷达引擎 (Sentinel Radar Engine)

双层全景哨兵矩阵：8个哨兵ETF的MA20多空趋势追踪、连续天数计数、
Rule 23 情绪起爆器验证、Rule 26 攻防仓位阶梯判定。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger("praxis.engine.sentinel")

SENTINEL_DEFINITIONS = {
    "510300": {"name": "沪深300ETF华泰柏瑞", "layer": "macro", "role": "大盘价值基准", "covers": ["all"]},
    "159915": {"name": "创业板ETF易方达", "layer": "macro", "role": "成长风险偏好", "covers": ["all"]},
    "512000": {"name": "券商ETF华宝", "layer": "macro", "role": "市场情绪温度计", "covers": ["all"]},
    "159601": {"name": "A50ETF华夏", "layer": "macro", "role": "港股科技联动", "covers": ["all"]},
    "512480": {"name": "半导体ETF国联安", "layer": "execution", "role": "科技板块哨兵", "covers": ["589850"]},
    "515050": {"name": "通信ETF华夏", "layer": "execution", "role": "通信板块哨兵", "covers": ["600522"]},
    "515220": {"name": "煤炭ETF国泰", "layer": "execution", "role": "煤炭板块哨兵", "covers": ["601699", "601898"]},
    "511220": {"name": "城投债ETF海富通", "layer": "execution", "role": "防守/避险哨兵", "covers": ["defense"]},
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
    """获取历史K线（新浪财经API为主，腾讯K线为备用）"""
    sina_code = _tencent_ticker(ticker)  # sh510300 格式
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_code}&scale=240&ma=no&datalen={count}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                result = []
                for item in data:
                    result.append({
                        "date": item["day"],
                        "open": float(item["open"]),
                        "close": float(item["close"]),
                        "high": float(item["high"]),
                        "low": float(item["low"]),
                        "volume": float(item["volume"]),
                    })
                return result[-count:] if len(result) > count else result
        except Exception as e:
            logger.warning(f"新浪K线请求失败 {ticker}: {e}")

    # 备用：腾讯K线
    tencent_code = _tencent_ticker(ticker)
    url = f"https://web.ifzq.gtimg.cn/appnew/tech/history?code={tencent_code}&type=day"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            if data.get("code") == 0 and "data" in data:
                klines = data["data"].get("kline", [])
                result = []
                for item in klines:
                    if len(item) >= 6:
                        result.append({
                            "date": item[0], "open": float(item[1]), "close": float(item[2]),
                            "high": float(item[3]), "low": float(item[4]), "volume": float(item[5]),
                        })
                return result[-count:] if len(result) > count else result
        except Exception as e:
            logger.warning(f"腾讯K线备用也失败 {ticker}: {e}")

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
    else:
        return f"量平 ({vol_ratio:.2f})"


class SentinelEngine:
    POSITION_TIERS = [
        (2, "绝对防守期", 10.0),
        (4, "适度试探期", 20.0),
        (6, "积极配置期", 30.0),
        (8, "全面进攻期", 50.0),
    ]

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._history_path = self._workspace / "data" / "sentinel_history.jsonl"
        self._history_path.parent.mkdir(parents=True, exist_ok=True)

    async def scan(self) -> SentinelSnapshot:
        today = date.today().isoformat()
        snapshot = SentinelSnapshot(date=today)
        for ticker in SENTINEL_ORDER:
            defn = SENTINEL_DEFINITIONS[ticker]
            state = SentinelState(
                ticker=ticker, name=defn["name"],
                layer=defn["layer"], role=defn["role"],
            )
            klines = await _fetch_kline(ticker, count=70)
            if not klines:
                logger.warning(f"哨兵 {ticker} K线数据为空")
                snapshot.sentinels[ticker] = asdict(state)
                continue
            closes = [k["close"] for k in klines]
            volumes = [k["volume"] for k in klines]
            state.price = closes[-1]
            state.change_pct = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0.0
            state.ma10 = _compute_ma(closes, 10)
            state.ma20 = _compute_ma(closes, 20)
            state.ma30 = _compute_ma(closes, 30)
            state.ma60 = _compute_ma(closes, 60)
            state.trend = "📈 多头" if state.price >= state.ma20 else "📉 空头"
            state.vol_ratio = _compute_vol_ratio(volumes)
            state.vol_desc = _classify_vol(state.vol_ratio)
            snapshot.sentinels[ticker] = asdict(state)
            if "多头" in state.trend:
                snapshot.bullish_count += 1
        for max_bull, state_name, limit in self.POSITION_TIERS:
            if snapshot.bullish_count <= max_bull:
                snapshot.state = state_name
                snapshot.position_limit_pct = limit
                break
        consecutive = self._count_consecutive_le2(snapshot.bullish_count)
        snapshot.rule23_consecutive_days = consecutive
        snapshot.rule23_triggered = consecutive >= 5
        self._save_snapshot(snapshot)
        return snapshot

    def _count_consecutive_le2(self, current_bullish: int) -> int:
        history = self._load_history()
        if not history:
            return 1 if current_bullish <= 2 else 0
        count = 1 if current_bullish <= 2 else 0
        for record in reversed(history):
            if record.get("bullish_count", 8) <= 2:
                count += 1
            else:
                break
        return count

    def _load_history(self) -> list[dict]:
        records = []
        if not self._history_path.exists():
            return records
        with open(self._history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def _save_snapshot(self, snapshot: SentinelSnapshot) -> None:
        history = self._load_history()
        history = [r for r in history if r.get("date") != snapshot.date]
        record = {
            "date": snapshot.date,
            "bullish_count": snapshot.bullish_count,
            "total": snapshot.total,
            "state": snapshot.state,
            "position_limit_pct": snapshot.position_limit_pct,
            "rule23_triggered": snapshot.rule23_triggered,
            "rule23_consecutive_days": snapshot.rule23_consecutive_days,
            "sentinels": {},
        }
        for ticker, sd in snapshot.sentinels.items():
            record["sentinels"][ticker] = {
                "name": sd["name"], "price": sd["price"],
                "change_pct": sd["change_pct"], "trend": sd["trend"],
                "ma20": sd["ma20"], "vol_desc": sd["vol_desc"],
            }
        history.append(record)
        with open(self._history_path, "w", encoding="utf-8") as f:
            for r in history:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logger.info(f"哨兵快照已保存: {snapshot.date}, 多头 {snapshot.bullish_count}/8, {snapshot.state}")

    def get_rule23_status(self) -> dict:
        history = self._load_history()
        if not history:
            return {"consecutive_days": 0, "triggered": False, "history": []}
        # 直接使用最新快照中已计算好的连续天数（scan 时已算好）
        latest = history[-1]
        consecutive = latest.get("rule23_consecutive_days", 0)
        # 如果最新快照不是今天，从历史末尾重新计数
        if latest.get("date") != date.today().isoformat():
            consecutive = 0
            for record in reversed(history):
                if record.get("bullish_count", 8) <= 2:
                    consecutive += 1
                else:
                    break
        recent = history[-5:] if len(history) >= 5 else history
        return {
            "consecutive_days": consecutive,
            "triggered": consecutive >= 5,
            "latest": history[-1] if history else None,
            "recent_history": [
                {"date": r["date"], "bullish": r["bullish_count"], "state": r["state"]}
                for r in recent
            ],
        }

    def get_history(self, days: int = 10) -> list[dict]:
        history = self._load_history()
        return history[-days:]
