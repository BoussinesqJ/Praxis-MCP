"""状态重建器（GPT 架构底线：state = rebuild(transactions + market_data + config)）

核心原则：transactions 才是账本事实源，state 只是计算出来的缓存。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from praxis.core.interfaces import StateBuilder as StateBuilderInterface
from praxis.core.interfaces import DataProvider
from praxis.core.models.state import PortfolioState, PositionState, CashState, GridState
from praxis.core.models.transaction import Transaction, TransactionType
from praxis.core.models.portfolio import Portfolio
from praxis.core.models.investor import InvestorProfile
from praxis.core.models.asset import AssetType
from praxis.core.ledger import FileLedger
from praxis.engine.config_loader import YamlConfigLoader


class SimpleStateBuilder(StateBuilderInterface):
    """简单状态重建器"""

    def __init__(
        self,
        ledger: FileLedger,
        config_loader: YamlConfigLoader,
        data_provider: DataProvider,
    ):
        self._ledger = ledger
        self._config = config_loader
        self._data = data_provider

    async def rebuild(
        self,
        investor_id: str,
        portfolio_id: str,
        market_data: dict | None = None,
    ) -> PortfolioState:
        """从 ledger + 行情 + config 重建状态"""
        # 1. 加载配置
        investor = self._config.load_investor(investor_id)
        portfolio = self._config.load_portfolio(investor_id, portfolio_id)

        # 2. 从 ledger 计算持仓
        positions_map: dict[str, dict] = {}
        for tx in self._ledger.get_all():
            ticker = tx.ticker
            if ticker not in positions_map:
                positions_map[ticker] = {
                    "quantity": 0.0,
                    "total_cost": 0.0,
                    "realized_pnl": 0.0,
                }

            pos = positions_map[ticker]
            if tx.type in (TransactionType.BUY, TransactionType.SUBSCRIBE):
                pos["quantity"] += tx.quantity
                pos["total_cost"] += tx.quantity * tx.price + tx.fee
            elif tx.type in (TransactionType.SELL, TransactionType.REDEEM):
                if pos["quantity"] > 0:
                    avg_cost = pos["total_cost"] / pos["quantity"]
                    pos["realized_pnl"] += tx.quantity * (tx.price - avg_cost) - tx.fee
                pos["quantity"] -= tx.quantity
                pos["total_cost"] = max(0, pos["total_cost"] - tx.quantity * (pos["total_cost"] / max(pos["quantity"] + tx.quantity, 1)))
            elif tx.type == TransactionType.DIVIDEND:
                pos["realized_pnl"] += tx.price  # price 字段复用为分红金额

        # 3. 获取行情
        if market_data is None:
            tickers = [a.ticker for a in portfolio.assets if a.ticker]
            market_data = await self._data.get_realtime_quote(tickers)

        # 4. 构建 PositionState
        positions = []
        total_positions_value = 0

        for asset in portfolio.assets:
            ticker = asset.ticker
            pos_data = positions_map.get(ticker, {"quantity": 0, "total_cost": 0, "realized_pnl": 0})
            quantity = pos_data["quantity"]
            total_cost = pos_data["total_cost"]
            avg_cost = total_cost / quantity if quantity > 0 else 0

            quote = market_data.get(ticker, {})
            current_price = quote.get("price", 0)
            market_value = quantity * current_price
            unrealized_pnl = market_value - total_cost if quantity > 0 else 0
            unrealized_pnl_pct = (current_price / avg_cost - 1) if avg_cost > 0 else 0

            positions.append(PositionState(
                ticker=ticker,
                name=asset.name,
                type=asset.type,
                category=asset.category,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
                target_weight_pct=asset.target_weight_pct,
                actual_weight_pct=0,  # 后面计算
            ))
            total_positions_value += market_value

        # 5. 计算现金（简化：初始资金 - 买入总额 + 卖出总额）
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
        total_dividend = sum(
            tx.price
            for tx in self._ledger.get_all()
            if tx.type == TransactionType.DIVIDEND
        )
        available_cash = investor.capital_cny - total_buy + total_sell + total_dividend
        total_assets = available_cash + total_positions_value

        cash = CashState(
            total_assets=total_assets,
            total_positions_value=total_positions_value,
            available_cash=available_cash,
            cash_ratio=available_cash / total_assets if total_assets > 0 else 1.0,
            frozen_amount=0,
        )

        # 6. 计算实际权重
        for pos in positions:
            pos.actual_weight_pct = (pos.market_value / total_assets * 100) if total_assets > 0 else 0

        # 7. 构建网格状态
        grids = []
        for asset in portfolio.assets:
            if hasattr(asset, 'grid') and asset.grid:
                triggers = [g.model_dump() for g in asset.grid] if isinstance(asset.grid, list) else []
                grids.append(GridState(
                    ticker=asset.ticker,
                    triggers=triggers,
                    stop_loss=asset.stop_loss.model_dump() if asset.stop_loss else None,
                    take_profit=[tp.model_dump() for tp in asset.take_profit] if asset.take_profit else [],
                    moving_stop=asset.moving_stop.model_dump() if asset.moving_stop else None,
                ))

        return PortfolioState(
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            snapshot_at=datetime.now(timezone.utc),
            positions=positions,
            cash=cash,
            grids=grids,
            risk_metrics={},
            data_source="computed",
            is_stale=False,
        )

    def validate(self, state: PortfolioState) -> list[str]:
        """验证状态一致性"""
        issues = []

        # 检查总资产 = 现金 + 持仓市值
        expected_total = state.cash.available_cash + state.cash.total_positions_value
        if abs(state.cash.total_assets - expected_total) > 0.01:
            issues.append(
                f"总资产不一致: {state.cash.total_assets} ≠ {expected_total}"
            )

        # 检查现金比例
        if state.cash.total_assets > 0:
            expected_ratio = state.cash.available_cash / state.cash.total_assets
            if abs(state.cash.cash_ratio - expected_ratio) > 0.001:
                issues.append(
                    f"现金比例不一致: {state.cash.cash_ratio} ≠ {expected_ratio}"
                )

        # 检查持仓数量非负
        for pos in state.positions:
            if pos.quantity < 0:
                issues.append(f"标的 {pos.ticker} 持仓数量为负: {pos.quantity}")

        return issues
