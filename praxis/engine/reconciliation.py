"""对账引擎（R1: dry-run only，不写入任何文件）"""
from __future__ import annotations

from datetime import datetime, timezone

from praxis.core.interfaces import DataProvider, ConfigLoader
from praxis.core.models.state import PortfolioState, PositionState, CashState
from praxis.core.models.portfolio import Portfolio
from praxis.core.models.investor import InvestorProfile
from praxis.core.models.error import ReconcileError


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

        positions = []
        total_positions_value = 0

        for asset in portfolio.assets:
            if not asset.ticker:
                continue
            quote = quotes.get(asset.ticker, {})
            current_price = quote.get("price", 0)
            if nav and asset.type == "offshore_fund":
                current_price = nav

            position = PositionState(
                ticker=asset.ticker,
                name=asset.name,
                type=asset.type,
                category=asset.category,
                quantity=0,
                avg_cost=0,
                current_price=current_price,
                market_value=0,
                unrealized_pnl=0,
                unrealized_pnl_pct=0,
                target_weight_pct=asset.target_weight_pct,
                actual_weight_pct=0,
            )
            positions.append(position)

        total_assets = investor.capital_cny
        cash = CashState(
            total_assets=total_assets,
            total_positions_value=total_positions_value,
            available_cash=total_assets - total_positions_value,
            cash_ratio=1.0 if total_positions_value == 0 else (total_assets - total_positions_value) / total_assets,
            frozen_amount=0,
        )

        state = PortfolioState(
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            snapshot_at=datetime.now(timezone.utc),
            positions=positions,
            cash=cash,
            grids=[],
            risk_metrics={},
            data_source="computed",
            is_stale=False,
        )

        return state

    def format_state(self, state: PortfolioState) -> str:
        """格式化状态为可读文本"""
        lines = [
            f"=== 组合状态快照 ===",
            f"投资者: {state.investor_id}",
            f"组合: {state.portfolio_id}",
            f"快照时间: {state.snapshot_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"--- 资产总览 ---",
            f"总资产: ¥{state.cash.total_assets:,.2f}",
            f"持仓市值: ¥{state.cash.total_positions_value:,.2f}",
            f"可用现金: ¥{state.cash.available_cash:,.2f}",
            f"现金比例: {state.cash.cash_ratio:.1%}",
            f"",
            f"--- 持仓明细 ---",
        ]

        for pos in state.positions:
            if pos.market_value > 0:
                lines.append(
                    f"  {pos.ticker} {pos.name}: "
                    f"{pos.quantity}股 × ¥{pos.current_price:.2f} = ¥{pos.market_value:,.2f} "
                    f"({pos.unrealized_pnl_pct:+.1%})"
                )
            else:
                lines.append(f"  {pos.ticker} {pos.name}: 无持仓 (当前价: ¥{pos.current_price:.2f})")

        if state.data_source == "computed":
            lines.append(f"\n[数据来源: 实时计算]")
        if state.is_stale:
            lines.append(f"[警告: 数据可能过期]")

        return "\n".join(lines)
