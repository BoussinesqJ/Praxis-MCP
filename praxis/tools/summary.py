"""MCP 工具 - 组合概览（聚合视图）

一次调用返回总资产/持仓/配置比/策略合规等信息，
避免需要调用 4-5 个工具才能拼出完整视图。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from praxis.core.ledger import FileLedger, filter_active_transactions
from praxis.core.models.transaction import TransactionType
from praxis.core.state_builder import SimpleStateBuilder
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.data.provider import CachedDataProvider


async def get_portfolio_summary(
    investor: str,
    portfolio: str,
    workspace: str = ".",
) -> dict:
    """获取组合聚合概览

    一次返回：总资产、持仓明细、现金、配置比、交易统计、策略合规状态
    """
    try:
        loader = YamlConfigLoader(workspace)
        provider = CachedDataProvider()
        ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
        ledger = FileLedger(ledger_path)

        try:
            # 尝试加载配置（可选）
            try:
                investor_profile = loader.load_investor(investor)
                capital_cny = investor_profile.capital_cny
                risk_level = investor_profile.risk_level
                style = investor_profile.style
            except Exception:
                # 配置文件不存在，从 ledger 推断
                capital_cny = 0
                risk_level = "unknown"
                style = "unknown"

            try:
                portfolio_config = loader.load_portfolio(investor, portfolio)
                strategy_type = portfolio_config.strategy_type
                asset_count_config = len(portfolio_config.assets)
            except Exception:
                strategy_type = "unknown"
                asset_count_config = 0

            # 从 ledger 计算持仓
            positions_map: dict[str, dict] = {}
            total_buy = 0
            total_sell = 0
            total_fee = 0
            total_dividend = 0
            buy_count = 0
            sell_count = 0
            first_tx_time = None
            last_tx_time = None

            for tx in filter_active_transactions(ledger.get_all()):
                ticker = tx.ticker
                if ticker not in positions_map:
                    positions_map[ticker] = {
                        "quantity": 0.0,
                        "total_cost": 0.0,
                        "realized_pnl": 0.0,
                        "asset_type": tx.asset_type,
                    }

                pos = positions_map[ticker]
                if tx.type in (TransactionType.BUY, TransactionType.SUBSCRIBE):
                    pos["quantity"] += tx.quantity
                    pos["total_cost"] += tx.quantity * tx.price + tx.fee
                    total_buy += tx.quantity * tx.price + tx.fee
                    buy_count += 1
                elif tx.type in (TransactionType.SELL, TransactionType.REDEEM):
                    if pos["quantity"] > 0:
                        avg_cost = pos["total_cost"] / pos["quantity"]
                        pos["realized_pnl"] += tx.quantity * (tx.price - avg_cost) - tx.fee
                    pos["quantity"] -= tx.quantity
                    pos["total_cost"] = max(0, pos["total_cost"] - tx.quantity * (pos["total_cost"] / max(pos["quantity"] + tx.quantity, 1)))
                    total_sell += tx.quantity * tx.price - tx.fee
                    sell_count += 1
                elif tx.type == TransactionType.DIVIDEND:
                    total_dividend += tx.price

                total_fee += tx.fee
                if tx.asset_type and not pos["asset_type"]:
                    pos["asset_type"] = tx.asset_type

                if first_tx_time is None or tx.created_at < first_tx_time:
                    first_tx_time = tx.created_at
                if last_tx_time is None or tx.created_at > last_tx_time:
                    last_tx_time = tx.created_at

            # 获取行情
            tickers = [t for t, p in positions_map.items() if p["quantity"] > 0]
            market_data = await provider.get_realtime_quote(tickers) if tickers else {}

            # 构建持仓明细
            positions = []
            total_positions_value = 0
            allocation: dict[str, float] = {}

            for ticker, pos_data in positions_map.items():
                quantity = pos_data["quantity"]
                # 浮点精度保护：忽略极小持仓（< 0.0001）
                if quantity <= 0.0001:
                    continue

                total_cost = pos_data["total_cost"]
                avg_cost = total_cost / quantity if quantity > 0 else 0
                asset_type = pos_data.get("asset_type") or "unknown"

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
                pnl_pct = (current_price / avg_cost - 1) if avg_cost > 0 else 0

                positions.append({
                    "ticker": ticker,
                    "quantity": quantity,
                    "avg_cost": round(avg_cost, 4),
                    "current_price": round(current_price, 4),
                    "market_value": round(market_value, 2),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(pnl_pct, 4),
                    "realized_pnl": round(pos_data["realized_pnl"], 2),
                    "asset_type": asset_type,
                })
                total_positions_value += market_value

                # 资产配置分类
                alloc_key = asset_type if asset_type != "unknown" else "other"
                allocation[alloc_key] = allocation.get(alloc_key, 0) + market_value

            # 计算汇总
            cash_unknown = False
            if capital_cny > 0:
                available_cash = capital_cny - total_buy + total_sell + total_dividend
            else:
                # 无配置文件：无法准确计算现金，标记为未知
                available_cash = 0.0
                cash_unknown = True

            total_assets = available_cash + total_positions_value

            # 转换配置比为百分比
            allocation_pct = {}
            if total_assets > 0:
                for k, v in allocation.items():
                    allocation_pct[k] = round(v / total_assets * 100, 1)
                if not cash_unknown:
                    allocation_pct["cash"] = round(available_cash / total_assets * 100, 1)

            # 组合天数
            days_active = 0
            if first_tx_time and last_tx_time:
                days_active = (last_tx_time - first_tx_time).days

            return {
                "success": True,
                "data": {
                    "overview": {
                        "investor": investor,
                        "portfolio": portfolio,
                        "strategy_type": strategy_type,
                        "risk_level": risk_level,
                        "style": style,
                        "days_active": days_active,
                        "snapshot_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "assets": {
                        "total_assets": round(total_assets, 2),
                        "cash": round(available_cash, 2) if not cash_unknown else None,
                        "cash_unknown": cash_unknown,
                        "positions_value": round(total_positions_value, 2),
                        "cash_ratio": round(available_cash / total_assets * 100, 1) if total_assets > 0 and not cash_unknown else None,
                    },
                    "allocation": allocation_pct,
                    "positions": sorted(positions, key=lambda p: p["market_value"], reverse=True),
                    "trading_stats": {
                        "total_buy_cost": round(total_buy, 2),
                        "total_sell_revenue": round(total_sell, 2),
                        "total_fee": round(total_fee, 2),
                        "total_dividend": round(total_dividend, 2),
                        "buy_count": buy_count,
                        "sell_count": sell_count,
                        "net_invested": round(total_buy - total_sell - total_dividend, 2),
                    },
                    "strategy_compliance": {
                        "position_count": len(positions),
                        "config_asset_count": asset_count_config,
                        "has_config": asset_count_config > 0,
                    },
                },
            }
        finally:
            await provider.close()
    except Exception as e:
        return {"success": False, "error": str(e)}
