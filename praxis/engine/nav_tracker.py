"""日频净值追踪器

追踪组合每日净值，为计算最大回撤、波动率、夏普比率提供数据基础。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from praxis.core.ledger import FileLedger
from praxis.core.interfaces import DataProvider
from praxis.core.models.error import PraxisError


class DailyNav(BaseModel):
    """日频净值记录"""
    date: str                    # YYYY-MM-DD
    nav: float                   # 单位净值
    total_assets: float          # 总资产
    positions_value: float       # 持仓市值
    cash: float                  # 现金
    benchmark_nav: float | None = None  # 基准净值（可选）
    benchmark_code: str | None = None   # 基准代码（可选）


class NavTracker:
    """净值追踪器"""

    def __init__(
        self,
        nav_path: str | Path,
        ledger: FileLedger,
        data_provider: DataProvider,
        initial_capital: float = 70000,
    ):
        self._path = Path(nav_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ledger = ledger
        self._data = data_provider
        self._initial_capital = initial_capital

        # 内存索引
        self._records: list[DailyNav] = []
        self._load_records()

    def _load_records(self):
        """从文件加载记录"""
        if not self._path.exists():
            return

        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._records.append(DailyNav(**data))
                except (json.JSONDecodeError, Exception):
                    continue

    def record(self, nav: DailyNav) -> str:
        """记录当日净值（append-only）"""
        # 检查是否已记录
        for existing in self._records:
            if existing.date == nav.date:
                return f"日期 {nav.date} 已存在记录"

        # 追加记录
        line = nav.model_dump_json() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        self._records.append(nav)
        return f"已记录 {nav.date} 净值: {nav.nav:.4f}"

    async def snapshot(
        self,
        investor_id: str,
        portfolio_id: str,
        config_loader: any,
    ) -> DailyNav:
        """从 ledger + 行情计算当日净值快照"""
        # 加载配置
        investor = config_loader.load_investor(investor_id)
        portfolio = config_loader.load_portfolio(investor_id, portfolio_id)

        # 从 ledger 计算持仓
        from praxis.core.models.transaction import TransactionType
        positions_map: dict[str, dict] = {}
        for tx in self._ledger.get_all():
            ticker = tx.ticker
            if ticker not in positions_map:
                positions_map[ticker] = {"quantity": 0, "total_cost": 0}

            pos = positions_map[ticker]
            if tx.type in (TransactionType.BUY, TransactionType.SUBSCRIBE):
                pos["quantity"] += tx.quantity
                pos["total_cost"] += tx.quantity * tx.price + tx.fee
            elif tx.type in (TransactionType.SELL, TransactionType.REDEEM):
                pos["quantity"] -= tx.quantity
                pos["total_cost"] = max(0, pos["total_cost"] - tx.quantity * (pos["total_cost"] / max(pos["quantity"] + tx.quantity, 1)))

        # 获取行情
        tickers = [a.ticker for a in portfolio.assets if a.ticker]
        quotes = await self._data.get_realtime_quote(tickers)

        # 计算持仓市值
        positions_value = 0
        for ticker, pos_data in positions_map.items():
            if pos_data["quantity"] > 0:
                quote = quotes.get(ticker, {})
                price = quote.get("price", 0)

                # Fallback: 场外基金无行情时，尝试获取基金净值
                if price == 0:
                    try:
                        fund_data = await self._data.get_fund_nav(ticker)
                        if fund_data and fund_data.get("nav", 0) > 0:
                            price = fund_data["nav"]
                    except Exception:
                        pass

                positions_value += pos_data["quantity"] * price

        # 计算现金
        total_buy = sum(
            tx.quantity * tx.price + tx.fee
            for tx in self._ledger.get_all()
            if tx.type in (TransactionType.BUY, TransactionType.SUBSCRIBE)
        )
        total_sell = sum(
            tx.quantity * tx.price - tx.fee
            for tx in self._ledger.get_all()
            if tx.type in (TransactionType.SELL, TransactionType.REDEEM)
        )
        cash = investor.capital_cny - total_buy + total_sell
        total_assets = cash + positions_value

        # 计算净值
        nav = total_assets / investor.capital_cny if investor.capital_cny > 0 else 1.0

        return DailyNav(
            date=datetime.now().strftime("%Y-%m-%d"),
            nav=nav,
            total_assets=total_assets,
            positions_value=positions_value,
            cash=cash,
            benchmark_nav=None,
            benchmark_code=None,
        )

    def get_history(self, days: int = 60) -> list[DailyNav]:
        """获取历史净值"""
        return self._records[-days:] if days > 0 else self._records

    def get_latest(self) -> DailyNav | None:
        """获取最新净值"""
        return self._records[-1] if self._records else None

    def get_nav_series(self) -> list[float]:
        """获取净值序列（用于计算指标）"""
        return [r.nav for r in self._records]

    def count(self) -> int:
        """记录总数"""
        return len(self._records)
