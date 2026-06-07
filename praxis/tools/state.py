"""MCP 工具 - 状态查询"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.core.state_builder import SimpleStateBuilder
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.data.provider import CachedDataProvider


async def get_state(investor: str, portfolio: str, infer_from_ledger: bool = False, workspace: str = ".") -> dict:
    """从 ledger 重建组合状态

    Args:
        infer_from_ledger: 如果为 True，不依赖配置文件，纯从 ledger 推断持仓
    """
    loader = YamlConfigLoader(workspace)
    provider = CachedDataProvider()
    ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
    ledger = FileLedger(ledger_path)

    try:
        if infer_from_ledger:
            # 纯 ledger 推断模式：不需要配置文件
            state = await _rebuild_from_ledger(ledger, provider, investor, portfolio)
            issues = []
        else:
            builder = SimpleStateBuilder(ledger, loader, provider)
            state = await builder.rebuild(investor, portfolio)
            issues = builder.validate(state)

        lines = [
            f"=== 组合状态（从 Ledger 重建）===",
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
                    f"{pos.quantity:.0f}股 × ¥{pos.current_price:.2f} = ¥{pos.market_value:,.2f} "
                    f"({pos.unrealized_pnl_pct:+.1%}) "
                    f"[目标{pos.target_weight_pct:.0f}% 实际{pos.actual_weight_pct:.1f}%]"
                )
            elif pos.quantity > 0:
                lines.append(
                    f"  {pos.ticker} {pos.name}: "
                    f"{pos.quantity:.0f}股 (无行情数据) "
                    f"[目标{pos.target_weight_pct:.0f}%]"
                )

        if issues:
            lines.append(f"\n[状态验证问题]")
            for issue in issues:
                lines.append(f"  ⚠ {issue}")
        else:
            lines.append(f"\n[状态验证通过]")

        return {
            "success": True,
            "data": {
                "state": state.model_dump(mode="json"),
                "formatted": "\n".join(lines),
                "validation_issues": issues,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await provider.close()


async def _rebuild_from_ledger(
    ledger: FileLedger,
    provider: CachedDataProvider,
    investor_id: str,
    portfolio_id: str,
    capital_cny: float | None = None,
) -> PortfolioState:
    """纯从 ledger 推断持仓状态（不需要配置文件）

    Args:
        capital_cny: 初始资金（可选）。如果不传，现金相关指标标记为 unknown。
    """
    from praxis.core.models.transaction import TransactionType
    from praxis.core.models.state import PortfolioState, PositionState, CashState
    from praxis.core.models.asset import AssetType, AssetCategory

    # 从 ledger 计算持仓
    positions_map: dict[str, dict] = {}
    total_buy = 0
    total_sell = 0
    total_dividend = 0

    for tx in ledger.get_all():
        ticker = tx.ticker
        if ticker not in positions_map:
            positions_map[ticker] = {"quantity": 0.0, "total_cost": 0.0, "realized_pnl": 0.0}

        pos = positions_map[ticker]
        if tx.type in (TransactionType.BUY, TransactionType.SUBSCRIBE):
            pos["quantity"] += tx.quantity
            pos["total_cost"] += tx.quantity * tx.price + tx.fee
            total_buy += tx.quantity * tx.price + tx.fee
        elif tx.type in (TransactionType.SELL, TransactionType.REDEEM):
            if pos["quantity"] > 0:
                avg_cost = pos["total_cost"] / pos["quantity"]
                pos["realized_pnl"] += tx.quantity * (tx.price - avg_cost) - tx.fee
            pos["quantity"] -= tx.quantity
            pos["total_cost"] = max(0, pos["total_cost"] - tx.quantity * (pos["total_cost"] / max(pos["quantity"] + tx.quantity, 1)))
            total_sell += tx.quantity * tx.price - tx.fee
        elif tx.type == TransactionType.DIVIDEND:
            total_dividend += tx.price  # price 字段复用为分红金额

    # 获取行情
    tickers = [t for t, p in positions_map.items() if p["quantity"] > 0]
    market_data = await provider.get_realtime_quote(tickers) if tickers else {}

    # 构建持仓状态
    positions = []
    total_positions_value = 0

    for ticker, pos_data in positions_map.items():
        quantity = pos_data["quantity"]
        if quantity <= 0:
            continue

        total_cost = pos_data["total_cost"]
        avg_cost = total_cost / quantity

        quote = market_data.get(ticker, {})
        current_price = quote.get("price", 0)

        # Fallback: 场外基金无行情时，尝试获取基金净值
        if current_price == 0:
            try:
                fund_data = await provider.get_fund_nav(ticker)
                if fund_data and fund_data.get("nav", 0) > 0:
                    current_price = fund_data["nav"]
            except Exception:
                pass

        market_value = quantity * current_price
        unrealized_pnl = market_value - total_cost
        unrealized_pnl_pct = (current_price / avg_cost - 1) if avg_cost > 0 else 0

        positions.append(PositionState(
            ticker=ticker,
            name=ticker,  # 无配置文件，用 ticker 代替名称
            type=AssetType.UNKNOWN,
            category=AssetCategory.UNKNOWN,
            quantity=quantity,
            avg_cost=avg_cost,
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            target_weight_pct=0,
            actual_weight_pct=0,
        ))
        total_positions_value += market_value

    # 现金计算：需要初始资金才能准确计算
    if capital_cny and capital_cny > 0:
        available_cash = capital_cny - total_buy + total_sell + total_dividend
        total_assets = available_cash + total_positions_value
    else:
        # 无法准确计算：仅返回持仓市值，现金标记为不可用
        available_cash = 0.0
        total_assets = total_positions_value

    cash = CashState(
        total_assets=total_assets,
        total_positions_value=total_positions_value,
        available_cash=available_cash,
        cash_ratio=available_cash / total_assets if total_assets > 0 else 0.0,
        frozen_amount=0,
    )

    # 计算实际权重
    for pos in positions:
        pos.actual_weight_pct = (pos.market_value / total_assets * 100) if total_assets > 0 else 0

    return PortfolioState(
        investor_id=investor_id,
        portfolio_id=portfolio_id,
        snapshot_at=datetime.now(timezone.utc),
        positions=positions,
        cash=cash,
        grids=[],
        risk_metrics={},
        data_source="ledger_inferred" if not capital_cny else "ledger_inferred_with_capital",
        is_stale=not bool(capital_cny),  # 无初始资金时标记为 stale
    )
