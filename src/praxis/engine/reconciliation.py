"""对账引擎（R1: dry-run only，不写入任何文件）"""
from __future__ import annotations

from datetime import datetime, timezone

from praxis.core.interfaces import DataProvider, ConfigLoader
from praxis.core.models import PortfolioState, PositionState, CashState, Portfolio, InvestorProfile
from praxis.core.exceptions import DataError


class ReconciliationEngine:
    """对账引擎

    R1 阶段：只读计算，不写入 state.yaml
    R2 阶段：支持 write 模式，写入 ledger
    """

    def __init__(self, config_loader: ConfigLoader, data_provider: DataProvider, ledger=None, state_builder=None):
        self._config = config_loader
        self._data = data_provider
        self._ledger = ledger
        self._state_builder = state_builder

    async def reconcile(
        self,
        investor_id: str,
        portfolio_id: str,
        nav: float | None = None,
        dry_run: bool = True,
    ) -> PortfolioState:
        """对账计算

        Args:
            investor_id: 投资者ID
            portfolio_id: 组合ID
            nav: 场外基金净值（可选，用于更新）
            dry_run: 是否只读模式

        Returns:
            PortfolioState: 计算后的组合状态
        """
        # 如果有 state_builder，使用它从 ledger 重建
        if self._state_builder and not dry_run:
            market_data = None
            if nav:
                # 如果提供了净值，先获取行情再覆盖
                investor = self._config.load_investor(investor_id)
                portfolio = self._config.load_portfolio(investor_id, portfolio_id)
                tickers = [a.ticker for a in portfolio.assets if a.ticker]
                market_data = await self._data.get_realtime_quote(tickers)
            return await self._state_builder.rebuild(investor_id, portfolio_id, market_data)

        # R1 阶段：dry-run 简化计算
        investor = self._config.load_investor(investor_id)
        portfolio = self._config.load_portfolio(investor_id, portfolio_id)

        tickers = [a.ticker for a in portfolio.assets if a.ticker]
        quotes = await self._data.get_realtime_quote(tickers)

        # 从 ledger 累加交易记录计算持仓
        positions_acc = self._compute_positions_from_ledger(investor_id, portfolio_id)

        positions = []
        total_positions_value = 0

        for asset in portfolio.assets:
            if not asset.ticker:
                continue
            quote = quotes.get(asset.ticker, {})
            current_price = quote.get("price", 0)
            if nav and asset.asset_type == "offshore_fund":
                current_price = nav

            acc = positions_acc.get(asset.ticker, {"quantity": 0.0, "avg_cost": 0.0, "realized_pnl": 0.0})
            quantity = acc["quantity"]
            avg_cost = acc["avg_cost"]
            market_value = quantity * current_price
            unrealized_pnl = (current_price - avg_cost) * quantity if quantity > 0 else 0
            total_positions_value += market_value

            position = PositionState(
                ticker=asset.ticker,
                name=asset.name,
                asset_type=asset.asset_type,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=acc["realized_pnl"],
                weight_pct=asset.target_weight_pct,
                today_change_pct=float(quote.get("change_percent", 0)),
            )
            positions.append(position)

        cash_balance = self._compute_cash_from_ledger(investor_id, portfolio_id)
        total_assets = cash_balance + total_positions_value
        cash = CashState(
            total_cash=cash_balance,
            available_cash=cash_balance,
            frozen_cash=0,
        )

        state = PortfolioState(
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            total_assets=total_assets,
            total_market_value=total_positions_value,
            cash=cash,
            positions=positions,
            nav=1.0,
        )

        return state

    def _compute_positions_from_ledger(self, investor_id: str, portfolio_id: str) -> dict[str, dict]:
        """从 ledger 累加交易记录，计算每个 ticker 的持仓

        使用移动加权平均法计算 avg_cost，卖出时实现盈亏。

        Args:
            investor_id: 投资者 ID
            portfolio_id: 组合 ID

        Returns:
            {ticker: {"quantity": float, "avg_cost": float, "realized_pnl": float}}
        """
        if self._ledger is None:
            return {}

        all_txs = self._ledger.get_all()
        txs = [
            tx for tx in all_txs
            if tx.investor_id == investor_id
            and tx.portfolio_id == portfolio_id
            and tx.status.value == "executed"
        ]
        txs.sort(key=lambda tx: tx.created_at)

        acc: dict[str, dict] = {}
        for tx in txs:
            ticker = tx.ticker
            if ticker not in acc:
                acc[ticker] = {"quantity": 0.0, "avg_cost": 0.0, "realized_pnl": 0.0}
            entry = acc[ticker]
            qty = tx.quantity
            price = tx.price
            fee = tx.fee

            if tx.tx_type.value in ("buy", "subscribe"):
                old_qty = entry["quantity"]
                old_cost = entry["avg_cost"]
                new_qty = old_qty + qty
                if new_qty > 0:
                    fee_val = fee if fee else 0.0  # 防御 fee 为 None/0
                    entry["avg_cost"] = (old_qty * old_cost + qty * price + fee_val) / new_qty
                entry["quantity"] = new_qty
            elif tx.tx_type.value in ("sell", "redeem"):
                old_qty = entry["quantity"]
                if old_qty > 0:
                    realized = (price - entry["avg_cost"]) * qty - fee
                    entry["realized_pnl"] += realized
                entry["quantity"] = old_qty - qty

        return acc

    def _compute_cash_from_ledger(self, investor_id: str, portfolio_id: str) -> float:
        """从 ledger 累加所有 executed 交易，计算账户现金余额

        会计恒等式：账户现金余额 = 初始本金(capital_cny) + 全账本净现金流
        遍历**所有** executed 交易记录（不限于 portfolio.assets 列表里的标的），
        按现金流口径累加：
            - buy / subscribe 类型：cash -= quantity * price + fee
            - sell / redeem 类型：cash += quantity * price - fee

        Args:
            investor_id: 投资者 ID
            portfolio_id: 组合 ID

        Returns:
            float: 账户现金余额（初始值为 capital_cny）
        """
        investor = self._config.load_investor(investor_id)
        capital = investor.capital_cny

        # 防御性处理：ledger 不可用时退化为原行为（仅返回本金），不崩溃
        if self._ledger is None:
            return capital

        all_txs = self._ledger.get_all()
        txs = [
            tx for tx in all_txs
            if tx.investor_id == investor_id
            and tx.portfolio_id == portfolio_id
            and tx.status.value == "executed"
        ]
        txs.sort(key=lambda tx: tx.created_at)

        cash_balance: float = capital
        for tx in txs:
            qty = tx.quantity
            price = tx.price
            fee = tx.fee
            if tx.tx_type.value in ("buy", "subscribe"):
                cash_balance -= qty * price + fee
            elif tx.tx_type.value in ("sell", "redeem"):
                cash_balance += qty * price - fee

        return cash_balance

    def format_state(self, state: PortfolioState) -> str:
        """格式化状态为可读文本"""
        total_assets = state.total_assets
        total_mv = state.total_market_value
        total_cash = state.cash.total_cash if state.cash else 0
        cash_ratio = (total_cash / total_assets) if total_assets > 0 else 0
        lines = [
            f"=== 组合状态快照 ===",
            f"投资者: {state.investor_id}",
            f"组合: {state.portfolio_id}",
            f"快照时间: {state.snapshot_time}",
            f"",
            f"--- 资产总览 ---",
            f"总资产: ¥{total_assets:,.2f}",
            f"持仓市值: ¥{total_mv:,.2f}",
            f"可用现金: ¥{state.cash.available_cash:,.2f}" if state.cash else "可用现金: ¥0.00",
            f"现金比例: {cash_ratio:.1%}",
            f"",
            f"--- 持仓明细 ---",
        ]

        for pos in state.positions:
            if pos.market_value > 0:
                pnl_pct = (pos.unrealized_pnl / pos.market_value) if pos.market_value > 0 else 0
                lines.append(
                    f"  {pos.ticker} {pos.name}: "
                    f"{pos.quantity}股 × ¥{pos.current_price:.2f} = ¥{pos.market_value:,.2f} "
                    f"({pnl_pct:+.1%})"
                )
            else:
                lines.append(f"  {pos.ticker} {pos.name}: 无持仓 (当前价: ¥{pos.current_price:.2f})")

        return "\n".join(lines)

    def reconcile_with_quotes(
        self,
        quotes: dict[str, float],
        investor_id: str,
        portfolio_id: str,
    ) -> PortfolioState:
        """使用外部传入的行情数据对账（数据解耦）

        跳过 DataProvider，直接使用传入的 quotes 构建 PortfolioState，
        执行对账计算（成本 vs 市价、盈亏）。

        Args:
            quotes: ticker → price 映射，由 WorkBuddy 外部采集后传入
            investor_id: 投资者 ID
            portfolio_id: 组合 ID

        Returns:
            PortfolioState: 计算后的组合状态（data_source="external"）
        """
        investor = self._config.load_investor(investor_id)
        portfolio = self._config.load_portfolio(investor_id, portfolio_id)

        # 从 ledger 累加交易记录计算持仓
        positions_acc = self._compute_positions_from_ledger(investor_id, portfolio_id)

        positions: list[PositionState] = []
        total_positions_value: float = 0.0

        for asset in portfolio.assets:
            if not asset.ticker:
                continue
            current_price: float = quotes.get(asset.ticker, 0.0)

            acc = positions_acc.get(asset.ticker, {"quantity": 0.0, "avg_cost": 0.0, "realized_pnl": 0.0})
            quantity = acc["quantity"]
            avg_cost = acc["avg_cost"]
            market_value = quantity * current_price
            unrealized_pnl = (current_price - avg_cost) * quantity if quantity > 0 else 0
            total_positions_value += market_value

            position = PositionState(
                ticker=asset.ticker,
                name=asset.name,
                asset_type=asset.asset_type,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=acc["realized_pnl"],
                weight_pct=asset.target_weight_pct,
                today_change_pct=0,
            )
            positions.append(position)

        cash_balance = self._compute_cash_from_ledger(investor_id, portfolio_id)
        total_assets: float = cash_balance + total_positions_value
        cash = CashState(
            total_cash=cash_balance,
            available_cash=cash_balance,
            frozen_cash=0,
        )

        state = PortfolioState(
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            total_assets=total_assets,
            total_market_value=total_positions_value,
            cash=cash,
            positions=positions,
            nav=1.0,
        )

        return state
