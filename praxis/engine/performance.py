"""绩效指标计算（增强版）

核心指标：
- 收益指标：总收益率、年化收益率、基准收益率、超额收益
- 风险指标：最大回撤、波动率、下行波动率
- 风险调整收益：夏普比率、卡玛比率、索提诺比率、信息比率
- 交易指标：胜率、盈亏比、换手率、总费用
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.interfaces import PerformanceCalculator as PerformanceCalculatorInterface
from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType
from praxis.core.models.decision import DecisionRecord
from praxis.core.models.state import PerformanceMetrics


class EnhancedPerformanceCalculator(PerformanceCalculatorInterface):
    """增强绩效计算器"""

    def __init__(self, ledger: FileLedger, initial_capital: float = 70000):
        self._ledger = ledger
        self._initial_capital = initial_capital

    def calculate(
        self,
        investor_id: str,
        portfolio_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        nav_series: list[float] | None = None,
        benchmark_series: list[float] | None = None,
        exclude_reversed: bool = False,
        exclude_tags: list[str] | None = None,
        include_tags: list[str] | None = None,
        ticker: str | None = None,
    ) -> PerformanceMetrics:
        """计算绩效指标

        Args:
            exclude_reversed: 排除已冲销的交易对
            exclude_tags: 排除带有这些标签的交易
            include_tags: 仅计算带有这些标签的交易（优先于 exclude_tags）
            ticker: 仅计算指定标的的绩效
        """
        transactions = self._ledger.get_all()

        # 过滤：按标的
        if ticker:
            transactions = [tx for tx in transactions if tx.ticker == ticker]

        # 过滤：按标签
        if include_tags:
            tag_set = set(include_tags)
            transactions = [tx for tx in transactions if tag_set.intersection(tx.tags)]
        elif exclude_tags:
            tag_set = set(exclude_tags)
            transactions = [tx for tx in transactions if not tag_set.intersection(tx.tags)]

        # 过滤：排除已冲销的交易对
        if exclude_reversed:
            # target_tx_id 是冲销记录的可靠信号
            # 任何有 target_tx_id 的记录都是冲销记录，指向被冲销的原始交易
            reversed_ids = {tx.target_tx_id for tx in transactions if tx.target_tx_id}
            # 排除：被冲销的原始记录 + 冲销记录本身
            transactions = [
                tx for tx in transactions
                if tx.tx_id not in reversed_ids and not tx.target_tx_id
            ]

        # 1. 计算基本收益指标
        total_buy_cost = sum(
            tx.quantity * tx.price + tx.fee
            for tx in transactions
            if tx.type in (TransactionType.BUY, TransactionType.SUBSCRIBE)
        )
        total_sell_revenue = sum(
            tx.quantity * tx.price - tx.fee
            for tx in transactions
            if tx.type in (TransactionType.SELL, TransactionType.REDEEM)
        )
        total_fee = sum(tx.fee for tx in transactions)
        total_dividend = sum(
            tx.price  # price 字段复用为分红金额
            for tx in transactions
            if tx.type == TransactionType.DIVIDEND
        )

        realized_pnl = total_sell_revenue - total_buy_cost + total_dividend
        total_return = realized_pnl / self._initial_capital if self._initial_capital > 0 else 0

        # 2. 计算交易统计
        buy_count = sum(1 for tx in transactions if tx.type in (TransactionType.BUY, TransactionType.SUBSCRIBE))
        sell_count = sum(1 for tx in transactions if tx.type in (TransactionType.SELL, TransactionType.REDEEM))

        # 3. 计算胜率与盈亏比
        win_count = 0
        loss_count = 0
        win_pnls = []
        loss_pnls = []
        for tx in transactions:
            if tx.type in (TransactionType.SELL, TransactionType.REDEEM):
                # 仅筛选在当前卖出交易之前发生的买入交易，防范后视偏差 (look-ahead bias)
                buy_txs = [
                    t for t in transactions
                    if t.ticker == tx.ticker
                    and t.type in (TransactionType.BUY, TransactionType.SUBSCRIBE)
                    and t.created_at < tx.created_at
                ]
                if buy_txs:
                    avg_buy_price = sum(t.quantity * t.price for t in buy_txs) / sum(t.quantity for t in buy_txs)
                    trade_pnl = tx.quantity * (tx.price - avg_buy_price) - tx.fee
                    if trade_pnl > 0:
                        win_count += 1
                        win_pnls.append(trade_pnl)
                    else:
                        loss_count += 1
                        loss_pnls.append(abs(trade_pnl))

        total_trades = win_count + loss_count
        win_rate = win_count / total_trades if total_trades > 0 else 0

        # 4. 计算盈亏比 (平均盈利 / 平均亏损)
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 5. 计算换手率
        turnover_rate = total_buy_cost / self._initial_capital if self._initial_capital > 0 else 0

        # 6. 计算年化收益率
        annualized_return = total_return
        if transactions:
            first_date = min(tx.created_at for tx in transactions)
            last_date = max(tx.created_at for tx in transactions)
            days_held = (last_date - first_date).days
            if days_held > 0:
                annualized_return = (1 + total_return) ** (365 / days_held) - 1

        # 7. 计算风险指标（如果有净值序列）
        max_drawdown = 0
        max_drawdown_duration = 0
        volatility = 0
        downside_volatility = 0
        sharpe_ratio = 0
        calmar_ratio = 0
        sortino_ratio = 0
        information_ratio = 0
        benchmark_return = 0
        excess_return = total_return

        if nav_series and len(nav_series) > 1:
            # 最大回撤
            max_drawdown, max_drawdown_duration = self._calculate_max_drawdown(nav_series)

            # 计算日收益率
            daily_returns = [
                (nav_series[i] - nav_series[i-1]) / nav_series[i-1]
                for i in range(1, len(nav_series))
            ]

            # 年化波动率
            if daily_returns:
                volatility = self._calculate_volatility(daily_returns)

                # 下行波动率
                downside_volatility = self._calculate_downside_volatility(daily_returns)

                # 夏普比率（无风险利率 = 2.5%）
                risk_free_rate = 0.025
                if volatility > 0:
                    sharpe_ratio = (annualized_return - risk_free_rate) / volatility

                # 卡玛比率
                if max_drawdown > 0:
                    calmar_ratio = annualized_return / max_drawdown

                # 索提诺比率
                if downside_volatility > 0:
                    sortino_ratio = (annualized_return - risk_free_rate) / downside_volatility

        # 8. 计算基准收益和超额收益
        if benchmark_series and len(benchmark_series) > 1:
            benchmark_return = (benchmark_series[-1] - benchmark_series[0]) / benchmark_series[0]
            excess_return = total_return - benchmark_return

            # 信息比率
            if nav_series and len(nav_series) > 1:
                tracking_error = self._calculate_tracking_error(nav_series, benchmark_series)
                if tracking_error > 0:
                    information_ratio = excess_return / tracking_error

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            benchmark_return=benchmark_return,
            excess_return=excess_return,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_drawdown_duration,
            volatility=volatility,
            downside_volatility=downside_volatility,
            sharpe_ratio=sharpe_ratio,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio,
            information_ratio=information_ratio,
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            turnover_rate=turnover_rate,
            total_fee=total_fee,
            buy_count=buy_count,
            sell_count=sell_count,
            realized_pnl=realized_pnl,
            total_dividend=total_dividend,
        )

    def _calculate_max_drawdown(self, nav_series: list[float]) -> tuple[float, int]:
        """计算最大回撤和持续天数"""
        peak = nav_series[0]
        max_dd = 0
        max_dd_duration = 0
        current_dd_duration = 0

        for nav in nav_series:
            peak = max(peak, nav)
            dd = (peak - nav) / peak
            if dd > 0:
                current_dd_duration += 1
                if dd > max_dd:
                    max_dd = dd
                    max_dd_duration = current_dd_duration
            else:
                current_dd_duration = 0

        return max_dd, max_dd_duration

    def _calculate_volatility(self, daily_returns: list[float]) -> float:
        """计算年化波动率"""
        if not daily_returns:
            return 0
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = math.sqrt(variance)
        return std_dev * math.sqrt(252)

    def _calculate_downside_volatility(self, daily_returns: list[float]) -> float:
        """计算下行波动率"""
        if not daily_returns:
            return 0
        negative_returns = [r for r in daily_returns if r < 0]
        if not negative_returns:
            return 0
        mean = sum(negative_returns) / len(negative_returns)
        variance = sum((r - mean) ** 2 for r in negative_returns) / len(negative_returns)
        std_dev = math.sqrt(variance)
        return std_dev * math.sqrt(252)

    def _calculate_tracking_error(
        self, nav_series: list[float], benchmark_series: list[float]
    ) -> float:
        """计算跟踪误差"""
        if len(nav_series) != len(benchmark_series):
            return 0

        nav_returns = [
            (nav_series[i] - nav_series[i-1]) / nav_series[i-1]
            for i in range(1, len(nav_series))
        ]
        benchmark_returns = [
            (benchmark_series[i] - benchmark_series[i-1]) / benchmark_series[i-1]
            for i in range(1, len(benchmark_series))
        ]

        if not nav_returns or not benchmark_returns:
            return 0

        excess_returns = [n - b for n, b in zip(nav_returns, benchmark_returns)]
        mean = sum(excess_returns) / len(excess_returns)
        variance = sum((r - mean) ** 2 for r in excess_returns) / len(excess_returns)
        return math.sqrt(variance) * math.sqrt(252)

    def compare_versions(
        self, version_a: str, version_b: str, metric: str = "sharpe_ratio"
    ) -> dict:
        """策略版本对比（需要历史数据）"""
        return {
            "version_a": version_a,
            "version_b": version_b,
            "metric": metric,
            "result": "需要历史数据支持",
        }
