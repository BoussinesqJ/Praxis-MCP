"""净值追踪器 — 日频净值记录 + 快照 + 历史"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.core.interfaces import DataProvider
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class NavTracker:
    """日频净值追踪器"""

    def __init__(self, nav_path: str | Path, ledger: FileLedger,
                 data_provider: DataProvider, initial_capital: float = 70000):
        self._path = Path(nav_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ledger = ledger
        self._data = data_provider
        self._initial_capital = initial_capital
        self._records: list[dict] = []
        self._load_records()

    def _load_records(self):
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    self._records.append(json.loads(line.strip()))
                except (json.JSONDecodeError, Exception):
                    continue

    def record(self, nav: float, total_assets: float, positions_value: float,
               cash: float, benchmark_nav: float | None = None,
               benchmark_code: str | None = None) -> dict:
        """记录当日净值"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 去重：今天已记录则跳过
        for r in self._records:
            if r.get("date") == today:
                return {"success": False, "error": f"今日 {today} 已记录净值"}

        record_data = {
            "date": today,
            "nav": round(nav, 4),
            "total_assets": round(total_assets, 2),
            "positions_value": round(positions_value, 2),
            "cash": round(cash, 2),
            "benchmark_nav": round(benchmark_nav, 4) if benchmark_nav else None,
            "benchmark_code": benchmark_code,
        }

        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record_data, ensure_ascii=False) + "\n")

        self._records.append(record_data)
        logger.info("nav_recorded", date=today, nav=nav, total_assets=total_assets)
        return {"success": True, "data": record_data}

    async def snapshot(self, investor_id: str, portfolio_id: str) -> dict:
        """获取净值快照（含当日行情估值）"""
        if not self._records:
            return {"success": False, "error": "无净值记录"}

        latest = self._records[-1]

        # 尝试获取当日行情
        try:
            txs = self._ledger.list(limit=100)
            tickers = list(set(tx.ticker for tx in txs if hasattr(tx, 'ticker')))
            if tickers:
                quotes = await self._data.get_realtime_quote(tickers)
                positions_value = sum(
                    quotes.get(t, {}).get("price", 0) * sum(
                        tx.quantity for tx in txs
                        if hasattr(tx, 'ticker') and tx.ticker == t and
                        hasattr(tx, 'tx_type') and str(tx.tx_type) in ('buy', 'subscribe')
                    )
                    for t in tickers
                )
                latest["positions_value"] = round(positions_value, 2)
                latest["total_assets"] = round(positions_value + latest["cash"], 2)
                latest["nav"] = round(latest["total_assets"] / self._initial_capital, 4)
        except Exception as e:
            logger.warning("nav_snapshot_quote_failed", error=str(e))

        return {"success": True, "data": latest}

    def get_history(self, days: int = 30) -> dict:
        """获取净值历史"""
        history = self._records[-days:] if len(self._records) > days else self._records
        return {"success": True, "data": {"records": history, "count": len(history)}}
