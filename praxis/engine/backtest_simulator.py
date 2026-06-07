"""基于规则和网格触发的历史日K线回测引擎"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any

from praxis.core.interfaces import DataProvider, ConfigLoader
from praxis.core.models.state import PortfolioState, PositionState, CashState
from praxis.core.models.transaction import Transaction, TransactionType, TransactionStatus
from praxis.engine.backtest import BacktestConfig, BacktestResult
from praxis.engine.execution.trading_calendar import TradingCalendar
from praxis.engine.constraint_checker import SimpleConstraintChecker


class RuleBasedBacktestEngine:
    """事件驱动型规则与网格回测模拟引擎"""

    def __init__(
        self,
        data_provider: DataProvider,
        config_loader: ConfigLoader,
        initial_capital: float = 70000.0,
    ):
        self._data = data_provider
        self._config = config_loader
        self._initial_capital = initial_capital

    async def run_backtest(
        self,
        investor_id: str,
        portfolio_id: str,
        start_date: str,
        end_date: str,
        benchmark: str = "000300",
    ) -> BacktestResult:
        """运行基于日K线和网格规则的历史回测"""
        # 1. 加载配置
        investor = self._config.load_investor(investor_id)
        portfolio = self._config.load_portfolio(investor_id, portfolio_id)
        checker = SimpleConstraintChecker(investor, portfolio)
        calendar = TradingCalendar()

        # 2. 收集日期范围内的所有交易日
        trading_days = []
        curr = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        while curr <= end_dt:
            if calendar.is_trading_day(curr):
                trading_days.append(curr.strftime("%Y-%m-%d"))
            curr += timedelta(days=1)

        if not trading_days:
            raise ValueError(f"指定时间区间 {start_date} ~ {end_date} 内没有交易日")

        # 3. 获取所有标的的日K线数据
        asset_klines: dict[str, dict[str, dict]] = {}
        for asset in portfolio.assets:
            if asset.ticker:
                # 获取充足的历史数据（例如 500 条）
                klines = await self._data.get_history_kline(asset.ticker, period="day", count=500)
                asset_klines[asset.ticker] = {}
                for k in klines:
                    k_date = k.get("date") or k.get("time") or k.get("nav_date")
                    if k_date:
                        if isinstance(k_date, datetime):
                            k_date_str = k_date.strftime("%Y-%m-%d")
                        else:
                            k_date_str = str(k_date).split(" ")[0].split("T")[0]
                        asset_klines[asset.ticker][k_date_str] = k

        # 4. 获取基准 K 线数据
        benchmark_klines: dict[str, dict] = {}
        try:
            b_klines = await self._data.get_history_kline(benchmark, period="day", count=500)
            for k in b_klines:
                k_date = k.get("date") or k.get("time") or k.get("nav_date")
                if k_date:
                    if isinstance(k_date, datetime):
                        k_date_str = k_date.strftime("%Y-%m-%d")
                    else:
                        k_date_str = str(k_date).split(" ")[0].split("T")[0]
                    benchmark_klines[k_date_str] = k
        except Exception:
            pass

        # 5. 初始化模拟持仓和现金
        sim_cash = self._initial_capital
        sim_positions = {asset.ticker: 0.0 for asset in portfolio.assets}
        sim_costs = {asset.ticker: 0.0 for asset in portfolio.assets}
        
        # 复制网格状态
        asset_grids = {}
        for asset in portfolio.assets:
            asset_grids[asset.ticker] = [level.model_copy() for level in asset.grid]

        daily_nav_series = []
        transactions: list[Transaction] = []
        win_count = 0
        loss_count = 0
        total_fee = 0.0

        last_known_prices = {asset.ticker: (asset.base_price or 0.0) for asset in portfolio.assets}

        # 6. 按交易日循环模拟
        for date_str in trading_days:
            day_prices = {}
            day_klines = {}
            for asset in portfolio.assets:
                ticker = asset.ticker
                kline = asset_klines.get(ticker, {}).get(date_str)
                if kline:
                    day_klines[ticker] = kline
                    # 兼容行情、净值、收盘价等多种字段
                    p = kline.get("close") or kline.get("price") or kline.get("nav") or last_known_prices[ticker]
                    day_prices[ticker] = float(p)
                    last_known_prices[ticker] = float(p)
                else:
                    day_prices[ticker] = last_known_prices[ticker]

            # 6.1 计算本日初持仓总市值及总资产
            total_pos_val = sum(sim_positions[ticker] * day_prices[ticker] for ticker in sim_positions)
            total_assets = sim_cash + total_pos_val

            # 6.2 构造 Mock PortfolioState 用作约束检查
            mock_positions = []
            for asset in portfolio.assets:
                ticker = asset.ticker
                qty = sim_positions[ticker]
                cost = sim_costs[ticker]
                avg_cost = cost / qty if qty > 0 else 0.0
                curr_price = day_prices[ticker]
                m_val = qty * curr_price
                mock_positions.append(
                    PositionState(
                        ticker=ticker,
                        name=asset.name,
                        type=asset.type,
                        category=asset.category,
                        quantity=qty,
                        avg_cost=avg_cost,
                        current_price=curr_price,
                        market_value=m_val,
                        unrealized_pnl=m_val - cost,
                        unrealized_pnl_pct=(curr_price / avg_cost - 1) if avg_cost > 0 else 0.0,
                        target_weight_pct=asset.target_weight_pct,
                        actual_weight_pct=(m_val / total_assets * 100) if total_assets > 0 else 0.0,
                    )
                )

            mock_cash = CashState(
                total_assets=total_assets,
                total_positions_value=total_pos_val,
                available_cash=sim_cash,
                cash_ratio=sim_cash / total_assets if total_assets > 0 else 1.0,
                frozen_amount=0,
            )

            mock_state = PortfolioState(
                investor_id=investor_id,
                portfolio_id=portfolio_id,
                snapshot_at=datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                positions=mock_positions,
                cash=mock_cash,
                grids=[],
                risk_metrics={},
                data_source="backtest_sim",
                is_stale=False,
            )

            # 6.3 检查止损触发 (优先检查)
            for asset in portfolio.assets:
                ticker = asset.ticker
                qty = sim_positions[ticker]
                if qty <= 0:
                    continue
                kline = day_klines.get(ticker)
                if not kline:
                    continue
                low_val = float(kline.get("low", day_prices[ticker]))

                sl = asset.stop_loss
                if sl:
                    sl_trigger = None
                    if sl.type in ("fixed", "fixed_price") and sl.trigger:
                        sl_trigger = sl.trigger
                    elif sl.type == "fixed_pct" and sl.trigger_pct is not None and asset.base_price:
                        sl_trigger = asset.base_price * (1 + sl.trigger_pct / 100.0)

                    if sl_trigger and low_val <= sl_trigger:
                        sell_price = min(sl_trigger, day_prices[ticker])
                        amount = qty * sell_price
                        fee = max(5.0, amount * 0.0003)
                        
                        sim_cash += amount - fee
                        total_fee += fee
                        
                        avg_cost = sim_costs[ticker] / qty
                        if sell_price > avg_cost:
                            win_count += 1
                        else:
                            loss_count += 1

                        sim_positions[ticker] = 0.0
                        sim_costs[ticker] = 0.0

                        transactions.append(
                            Transaction(
                                tx_id=f"tx-sl-{date_str}-{ticker}",
                                type=TransactionType.SELL,
                                ticker=ticker,
                                quantity=qty,
                                price=sell_price,
                                fee=fee,
                                created_at=datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                                status=TransactionStatus.CONFIRMED,
                                notes="止损卖出",
                                investor_id=investor_id,
                                portfolio_id=portfolio_id,
                            )
                        )

            # 6.4 检查止盈触发
            for asset in portfolio.assets:
                ticker = asset.ticker
                qty = sim_positions[ticker]
                if qty <= 0:
                    continue
                kline = day_klines.get(ticker)
                if not kline:
                    continue
                high_val = float(kline.get("high", day_prices[ticker]))

                for tp in asset.take_profit:
                    if high_val >= tp.trigger:
                        sell_price = max(tp.trigger, day_prices[ticker])
                        sell_qty = 0.0
                        if tp.sell_pct is not None:
                            sell_qty = qty * (tp.sell_pct / 100.0)
                        elif tp.action == "sell_100_shares":
                            sell_qty = min(100.0, qty)
                        elif tp.action == "liquidate":
                            sell_qty = qty

                        if sell_qty <= 0:
                            continue

                        amount = sell_qty * sell_price
                        fee = max(5.0, amount * 0.0003)

                        sim_cash += amount - fee
                        total_fee += fee

                        avg_cost = sim_costs[ticker] / qty
                        if sell_price > avg_cost:
                            win_count += 1
                        else:
                            loss_count += 1

                        sim_positions[ticker] -= sell_qty
                        sim_costs[ticker] = max(0.0, sim_costs[ticker] - sell_qty * avg_cost)

                        transactions.append(
                            Transaction(
                                tx_id=f"tx-tp-{date_str}-{ticker}",
                                type=TransactionType.SELL,
                                ticker=ticker,
                                quantity=sell_qty,
                                price=sell_price,
                                fee=fee,
                                created_at=datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                                status=TransactionStatus.CONFIRMED,
                                notes="止盈卖出",
                                investor_id=investor_id,
                                portfolio_id=portfolio_id,
                            )
                        )
                        break

            # 6.5 检查网格档位触发
            for asset in portfolio.assets:
                ticker = asset.ticker
                kline = day_klines.get(ticker)
                if not kline:
                    continue
                low_val = float(kline.get("low", day_prices[ticker]))
                high_val = float(kline.get("high", day_prices[ticker]))

                grids = asset_grids[ticker]
                for idx, level in enumerate(grids):
                    if level.status != "active":
                        continue

                    # 计算触发价
                    p_trigger = 0.0
                    if level.trigger is not None:
                        p_trigger = level.trigger
                    elif level.trigger_pct is not None and asset.base_price is not None:
                        p_trigger = asset.base_price * (1 + level.trigger_pct / 100.0)

                    if p_trigger <= 0:
                        continue

                    # 当日价格覆盖触发价，且 shares > 0 代表买入
                    if level.shares > 0 and low_val <= p_trigger <= high_val:
                        amount = level.shares * p_trigger
                        # 约束校验
                        checks = checker.check(mock_state, action="buy", ticker=ticker, amount=amount)
                        if all(c.get("passed", True) for c in checks):
                            fee = max(5.0, amount * 0.0003)
                            if sim_cash >= amount + fee:
                                sim_cash -= amount + fee
                                total_fee += fee

                                sim_positions[ticker] += level.shares
                                sim_costs[ticker] += amount + fee

                                level.status = "filled"
                                level.filled_at = date_str

                                transactions.append(
                                    Transaction(
                                        tx_id=f"tx-grid-{date_str}-{ticker}-{idx}",
                                        type=TransactionType.BUY,
                                        ticker=ticker,
                                        quantity=level.shares,
                                        price=p_trigger,
                                        fee=fee,
                                        created_at=datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                                        status=TransactionStatus.CONFIRMED,
                                        notes=f"网格买入: {level.label}",
                                        investor_id=investor_id,
                                        portfolio_id=portfolio_id,
                                    )
                                )

            # 6.6 结算记录本日 NAV
            day_pos_val = sum(sim_positions[ticker] * day_prices[ticker] for ticker in sim_positions)
            day_nav = sim_cash + day_pos_val
            daily_nav_series.append({"date": date_str, "nav": day_nav})

        # 7. 结算回测最终绩效
        final_value = sim_cash + sum(sim_positions[ticker] * last_known_prices[ticker] for ticker in sim_positions)
        total_return = (final_value - self._initial_capital) / self._initial_capital

        # 计算年化
        if len(trading_days) > 1:
            first_date = datetime.strptime(trading_days[0], "%Y-%m-%d")
            last_date = datetime.strptime(trading_days[-1], "%Y-%m-%d")
            days_held = (last_date - first_date).days
            annualized_return = (1 + total_return) ** (365 / max(1, days_held)) - 1
        else:
            annualized_return = 0.0

        # 最大回撤计算
        nav_values = [item["nav"] for item in daily_nav_series]
        max_drawdown = 0.0
        if nav_values:
            peak = nav_values[0]
            for nav in nav_values:
                peak = max(peak, nav)
                dd = (peak - nav) / peak
                max_drawdown = max(max_drawdown, dd)

        # 夏普比率计算
        sharpe_ratio = 0.0
        if len(nav_values) > 1:
            daily_returns = [
                (nav_values[i] - nav_values[i-1]) / nav_values[i-1]
                for i in range(1, len(nav_values))
            ]
            if daily_returns:
                mean_return = sum(daily_returns) / len(daily_returns)
                std_return = math.sqrt(sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns))
                if std_return > 0:
                    sharpe_ratio = (mean_return * 252 - 0.025) / (std_return * math.sqrt(252))

        # 计算基准收益
        benchmark_return = None
        excess_return = None
        if benchmark_klines:
            b_dates = sorted(benchmark_klines.keys())
            b_dates_in_range = [d for d in b_dates if trading_days[0] <= d <= trading_days[-1]]
            if len(b_dates_in_range) > 1:
                p_start = float(benchmark_klines[b_dates_in_range[0]]["close"])
                p_end = float(benchmark_klines[b_dates_in_range[-1]]["close"])
                if p_start > 0:
                    benchmark_return = (p_end - p_start) / p_start
                    excess_return = total_return - benchmark_return

        total_trades = win_count + loss_count
        win_rate = win_count / total_trades if total_trades > 0 else 0.0

        return BacktestResult(
            strategy_name=portfolio.strategy_type,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self._initial_capital,
            final_value=final_value,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            total_trades=total_trades,
            total_fee=total_fee,
            benchmark_return=benchmark_return,
            excess_return=excess_return,
        )
