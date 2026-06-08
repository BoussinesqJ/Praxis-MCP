"""账本绩效分析引擎

注意：此模块分析已有交易记录的绩效统计，不是历史模拟回测。
基于账本数据的事后分析，不模拟交易执行。

后续版本将实现真正的模拟回测（基于历史价格数据模拟交易执行）。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType
from praxis.engine.performance import EnhancedPerformanceCalculator


class BacktestConfig(BaseModel):
    """回测配置"""
    strategy_name: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    initial_capital: float = 70000
    benchmark: str = "000300"  # 沪深300


class BacktestResult(BaseModel):
    """回测结果"""
    mode: str = "ledger_analysis"  # ledger_analysis | simulation
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fee: float
    benchmark_return: float | None = None
    excess_return: float | None = None


class SimpleBacktestEngine:
    """账本绩效分析引擎

    基于已有交易记录计算绩效统计（非历史模拟回测）。
    后续版本将实现真正的模拟回测。
    """

    def __init__(self, ledger: FileLedger, initial_capital: float = 70000):
        self._ledger = ledger
        self._initial_capital = initial_capital

    def run_backtest(
        self,
        config: BacktestConfig,
        nav_series: list[dict] | None = None,
        benchmark_series: list[dict] | None = None,
    ) -> BacktestResult:
        """运行回测

        Args:
            config: 回测配置
            nav_series: 历史净值数据 [{date, nav}, ...]
            benchmark_series: 基准数据 [{date, close}, ...]

        Returns:
            BacktestResult: 回测结果
        """
        # 获取交易记录
        transactions = self._ledger.get_all()

        # 计算基本指标
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
            tx.price
            for tx in transactions
            if tx.type == TransactionType.DIVIDEND
        )

        # 计算已实现盈亏
        realized_pnl = total_sell_revenue - total_buy_cost + total_dividend
        final_value = self._initial_capital + realized_pnl

        # 计算收益率
        total_return = realized_pnl / self._initial_capital

        # 计算年化收益率
        if transactions:
            first_date = min(tx.created_at for tx in transactions)
            last_date = max(tx.created_at for tx in transactions)
            days_held = (last_date - first_date).days
            if days_held > 0:
                annualized_return = (1 + total_return) ** (365 / days_held) - 1
            else:
                annualized_return = total_return
        else:
            annualized_return = 0

        # 计算胜率
        win_count = 0
        loss_count = 0
        for tx in transactions:
            if tx.type in (TransactionType.SELL, TransactionType.REDEEM):
                buy_txs = [
                    t for t in transactions
                    if t.ticker == tx.ticker
                    and t.type in (TransactionType.BUY, TransactionType.SUBSCRIBE)
                ]
                if buy_txs:
                    avg_buy_price = sum(t.quantity * t.price for t in buy_txs) / sum(t.quantity for t in buy_txs)
                    if tx.price > avg_buy_price:
                        win_count += 1
                    else:
                        loss_count += 1

        total_trades = win_count + loss_count
        win_rate = win_count / total_trades if total_trades > 0 else 0

        # 计算最大回撤（如果有净值序列）
        max_drawdown = 0
        if nav_series and len(nav_series) > 1:
            nav_values = [item["nav"] for item in nav_series]
            max_drawdown = self._calculate_max_drawdown(nav_values)

        # 计算夏普比率（简化）
        sharpe_ratio = 0
        if nav_series and len(nav_series) > 1:
            nav_values = [item["nav"] for item in nav_series]
            daily_returns = [
                (nav_values[i] - nav_values[i-1]) / nav_values[i-1]
                for i in range(1, len(nav_values))
            ]
            if daily_returns:
                import math
                mean_return = sum(daily_returns) / len(daily_returns)
                std_return = math.sqrt(sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns))
                if std_return > 0:
                    sharpe_ratio = (mean_return * 252 - 0.025) / (std_return * math.sqrt(252))

        # 计算基准收益
        benchmark_return = None
        excess_return = None
        if benchmark_series and len(benchmark_series) > 1:
            benchmark_return = (benchmark_series[-1]["close"] - benchmark_series[0]["close"]) / benchmark_series[0]["close"]
            excess_return = total_return - benchmark_return

        return BacktestResult(
            strategy_name=config.strategy_name,
            start_date=config.start_date,
            end_date=config.end_date,
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

    def _calculate_max_drawdown(self, nav_series: list[float]) -> float:
        """计算最大回撤"""
        if not nav_series:
            return 0

        peak = nav_series[0]
        max_dd = 0

        for nav in nav_series:
            peak = max(peak, nav)
            dd = (peak - nav) / peak
            max_dd = max(max_dd, dd)

        return max_dd

    def format_result(self, result: BacktestResult) -> str:
        """格式化回测结果"""
        mode_label = "账本绩效分析" if result.mode == "ledger_analysis" else "模拟回测"
        lines = [
            f"=== {mode_label}结果 ===",
            f"模式: {mode_label}（基于已有交易记录，非历史模拟）",
            f"策略: {result.strategy_name}",
            f"回测期间: {result.start_date} ~ {result.end_date}",
            f"",
            f"--- 收益指标 ---",
            f"初始资金: ¥{result.initial_capital:,.2f}",
            f"最终价值: ¥{result.final_value:,.2f}",
            f"总收益率: {result.total_return:.2%}",
            f"年化收益率: {result.annualized_return:.2%}",
        ]

        if result.benchmark_return is not None:
            lines.append(f"基准收益: {result.benchmark_return:.2%}")
            if result.excess_return is not None:
                lines.append(f"超额收益: {result.excess_return:.2%} {'✅ 跑赢基准' if result.excess_return > 0 else '❌ 跑输基准'}")

        lines.extend([
            f"",
            f"--- 风险指标 ---",
            f"最大回撤: {result.max_drawdown:.2%}",
            f"夏普比率: {result.sharpe_ratio:.2f}",
            f"",
            f"--- 交易统计 ---",
            f"总交易次数: {result.total_trades}",
            f"胜率: {result.win_rate:.1%}",
            f"总手续费: ¥{result.total_fee:,.2f}",
        ])

        return "\n".join(lines)
