"""状态重建器 — 从 ledger + 行情 + config 重建 PortfolioState

这是运行代码此前缺失的 StateBuilder 具体实现（core/interfaces.StateBuilder 仅有抽象类）。
reconcile 真实对账依赖它：当 ReconciliationEngine 注入 ledger + state_builder 且 dry_run=False 时，
reconcile 会调用 rebuild() 返回账本派生的真实组合状态，而非虚构的 capital*0.5。

设计要点：
- 现金 = 本金 - Σ(买入流出) + Σ(卖出流入)，买入流出 = price*qty + fee，卖出流入 = price*qty - fee。
- 持仓均价采用移动加权平均法（卖出按当前均价等比扣减成本基数）。
- 行情取价失败时（无网/标的无效）回退到 avg_cost，保证 reconcile 仍返回真实账本状态而非崩溃降级。
"""
from __future__ import annotations

from datetime import datetime, timezone

from praxis.core.interfaces import StateBuilder as StateBuilderABC, DataProvider, ConfigLoader, Ledger
from praxis.core.models import (
    PortfolioState, PositionState, CashState, TransactionType, AssetType,
)
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)

# 视为现金流出的交易类型
INFLOW_TYPES = {"sell", "redeem"}
OUTFLOW_TYPES = {"buy", "subscribe"}


class LedgerStateBuilder(StateBuilderABC):
    """基于 FileLedger 的账本状态重建器"""

    def __init__(self, data_provider: DataProvider, ledger: Ledger, config_loader: ConfigLoader):
        self._data = data_provider
        self._ledger = ledger
        self._config = config_loader

    async def rebuild(
        self,
        investor_id: str,
        portfolio_id: str,
        market_data: dict | None = None,
    ) -> PortfolioState:
        investor = self._config.load_investor(investor_id)
        # portfolio 仅用于潜在的资产维度扩展；真实持仓完全由 ledger 推导
        self._config.load_portfolio(investor_id, portfolio_id)

        txs = self._ledger.list(limit=100000)

        # 按时间排序：移动加权平均依赖买卖时序。FileLedger.list() 按 tx_id 字符串排序，
        # 会导致卖出排在对应买入之前而在持仓为 0 时被跳过，净持仓虚高。必须先按 created_at 排。
        def _ts(tx):
            c = getattr(tx, "created_at", "") or ""
            c = c.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(c)
            except Exception:
                return datetime.min

        txs = sorted(txs, key=_ts)

        # ticker -> {qty, cost, asset_type}
        positions: dict[str, dict] = {}
        buy_total = 0.0
        sell_total = 0.0

        for tx in txs:
            ttype = tx.tx_type.value if hasattr(tx.tx_type, "value") else str(tx.tx_type)
            qty = float(tx.quantity)
            price = float(tx.price)
            fee = float(tx.fee)
            if ttype in OUTFLOW_TYPES:
                p = positions.setdefault(
                    tx.ticker,
                    {"qty": 0.0, "cost": 0.0, "asset_type": tx.asset_type},
                )
                p["qty"] += qty
                p["cost"] += price * qty + fee
                p["asset_type"] = tx.asset_type
                buy_total += price * qty + fee
            elif ttype in INFLOW_TYPES:
                p = positions.get(tx.ticker)
                # 卖出按可用持仓钳制扣减（不允许负持仓）；现金汇总与顺序无关，照常计入
                if p is not None and p["qty"] > 1e-9:
                    avg = p["cost"] / p["qty"]
                    red = min(qty, p["qty"])
                    p["cost"] -= avg * red
                    p["qty"] -= red
                    if p["qty"] <= 1e-9:
                        p["qty"] = 0.0
                        p["cost"] = 0.0
                sell_total += price * qty - fee

        capital = float(investor.capital_cny)
        cash = capital - buy_total + sell_total

        # 取当前行情
        open_tickers = [k for k, v in positions.items() if v["qty"] > 1e-9]
        prices: dict[str, float] = {}
        if market_data:
            prices = {k: float(v) for k, v in market_data.items() if v is not None}
        else:
            try:
                quotes = await self._data.get_realtime_quote(open_tickers)
                for tk in open_tickers:
                    q = quotes.get(tk) or {}
                    px = q.get("price")
                    if px is not None and float(px) > 0:
                        prices[tk] = float(px)
            except Exception as e:  # 无网/数据源异常 → 回退到成本价
                logger.warning("state_builder_price_fallback", error=str(e))

        pos_states: list[PositionState] = []
        total_mv = 0.0
        for tk, p in positions.items():
            if p["qty"] <= 1e-9:
                continue
            avg = (p["cost"] / p["qty"]) if p["qty"] else 0.0
            cur = prices.get(tk, avg)
            mv = cur * p["qty"]
            upnl = (cur - avg) * p["qty"]
            total_mv += mv
            pos_states.append(PositionState(
                ticker=tk,
                name="",
                asset_type=p["asset_type"] if isinstance(p["asset_type"], AssetType) else AssetType.STOCK,
                quantity=round(p["qty"], 4),
                avg_cost=round(avg, 4),
                current_price=round(cur, 4),
                market_value=round(mv, 2),
                unrealized_pnl=round(upnl, 2),
                realized_pnl=0.0,
                weight_pct=0.0,
                today_change_pct=0.0,
            ))

        total_assets = cash + total_mv
        for ps in pos_states:
            ps.weight_pct = round(ps.market_value / total_assets * 100, 2) if total_assets else 0.0

        cash_state = CashState(
            total_cash=round(cash, 2),
            available_cash=round(cash, 2),
            frozen_cash=0.0,
        )

        return PortfolioState(
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            total_assets=round(total_assets, 2),
            total_market_value=round(total_mv, 2),
            cash=cash_state,
            positions=pos_states,
            nav=1.0,
            benchmark_nav=None,
            total_return_pct=0.0,
            snapshot_time=datetime.now(timezone.utc).isoformat(),
        )

    def validate(self, state: PortfolioState) -> list[str]:
        issues: list[str] = []
        calc = state.cash.total_cash + state.total_market_value
        if abs(calc - state.total_assets) > 1.0:
            issues.append(
                f"资产不平: total_assets={state.total_assets} vs cash+mv={round(calc, 2)}"
            )
        for ps in state.positions:
            if ps.quantity <= 0:
                issues.append(f"持仓数量异常: {ps.ticker} qty={ps.quantity}")
        return issues
