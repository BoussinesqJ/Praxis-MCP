"""回测引擎 — 基于账本数据的绩效分析

提供 BacktestConfig/BacktestResult 模型和 run_backtest 核心函数。
从原版 SimpleBacktestEngine + tools/backtest.py 合并迁移。
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from praxis.core.models import TransactionType


class BacktestConfig(BaseModel):
    """回测配置"""
    strategy_name: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    initial_capital: float = 70000.0
    benchmark: str = "000300"


class BacktestResult(BaseModel):
    """回测结果"""
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    annualized_return: float
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    trade_count: int = 0
    total_fee: float = 0.0
    benchmark_return: float | None = None
    excess_return: float | None = None


def run_backtest(
    config: BacktestConfig,
    ledger,
    benchmark_provider: Any | None = None,
) -> BacktestResult:
    """运行回测分析

    基于账本中的交易记录计算绩效指标。

    Args:
        config: 回测配置
        ledger: 账本实例（需 get_all() 或 list() 方法返回交易列表）
        benchmark_provider: 可选，基准数据提供者

    Returns:
        BacktestResult: 回测分析结果
    """
    # 获取全部交易
    transactions = _get_transactions(ledger)

    # 按日期范围过滤
    transactions = _filter_by_date(transactions, config.start_date, config.end_date)

    # 计算基本指标
    total_buy_cost = sum(
        tx.quantity * tx.price + getattr(tx, 'fee', 0)
        for tx in transactions
        if _is_buy_type(tx.tx_type)
    )
    total_sell_revenue = sum(
        tx.quantity * tx.price - getattr(tx, 'fee', 0)
        for tx in transactions
        if _is_sell_type(tx.tx_type)
    )
    total_fee = sum(getattr(tx, 'fee', 0) for tx in transactions)
    total_dividend = sum(
        getattr(tx, 'price', 0)
        for tx in transactions
        if _is_dividend(tx.tx_type)
    )

    realized_pnl = total_sell_revenue - total_buy_cost + total_dividend
    final_value = config.initial_capital + realized_pnl
    total_return = realized_pnl / config.initial_capital if config.initial_capital > 0 else 0.0

    # 年化收益率
    annualized_return = _calc_annualized(transactions, total_return)

    # 胜率 & 交易次数
    win_rate, trade_count = _calc_win_rate(transactions)

    return BacktestResult(
        strategy_name=config.strategy_name,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
        final_value=round(final_value, 2),
        total_return=round(total_return, 4),
        annualized_return=round(annualized_return, 4),
        max_drawdown=0.0,
        sharpe_ratio=0.0,
        calmar_ratio=0.0,
        win_rate=round(win_rate, 4),
        trade_count=trade_count,
        total_fee=round(total_fee, 2),
        benchmark_return=None,
        excess_return=None,
    )


def _calculate_period_returns(ledger, start: str, end: str) -> list[dict]:
    """按时间段筛选交易并计算期间收益"""
    transactions = _get_transactions(ledger)
    filtered = _filter_by_date(transactions, start, end)

    return [
        {
            "ticker": tx.ticker,
            "type": str(tx.tx_type),
            "quantity": tx.quantity,
            "price": tx.price,
            "fee": getattr(tx, 'fee', 0),
            "date": _tx_date(tx),
        }
        for tx in filtered
    ]


def _calculate_metrics(nav_series: list[float], config: BacktestConfig | None = None) -> dict:
    """从净值序列计算绩效指标（Sharpe/Calmar/MDD）"""
    if not nav_series or len(nav_series) < 2:
        return {"sharpe_ratio": 0.0, "calmar_ratio": 0.0, "max_drawdown": 0.0}

    # 日收益率
    daily_returns = [
        (nav_series[i] - nav_series[i - 1]) / nav_series[i - 1]
        for i in range(1, len(nav_series))
    ]

    if not daily_returns:
        return {"sharpe_ratio": 0.0, "calmar_ratio": 0.0, "max_drawdown": 0.0}

    # 最大回撤
    peak = nav_series[0]
    max_dd = 0.0
    for nav in nav_series:
        peak = max(peak, nav)
        dd = (peak - nav) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    # 夏普比率
    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    std_return = math.sqrt(variance)
    if std_return > 0:
        sharpe = (mean_return * 252 - 0.025) / (std_return * math.sqrt(252))
    else:
        sharpe = 0.0

    # 卡玛比率
    calmar = (mean_return * 252) / max_dd if max_dd > 0 else 0.0

    return {
        "sharpe_ratio": round(sharpe, 4),
        "calmar_ratio": round(calmar, 4),
        "max_drawdown": round(max_dd, 4),
    }


# ── 辅助函数 ──

def _get_transactions(ledger) -> list:
    """从账本获取交易列表"""
    if hasattr(ledger, 'get_all'):
        return ledger.get_all()
    return ledger.list(limit=10000)


def _filter_by_date(transactions: list, start: str, end: str) -> list:
    """按日期范围过滤交易"""
    return [
        tx for tx in transactions
        if start <= _tx_date(tx) <= end
    ]


def _tx_date(tx) -> str:
    """获取交易日期字符串"""
    dt = getattr(tx, 'created_at', '')
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    if isinstance(dt, str):
        return dt[:10]
    return str(dt)[:10]


def _is_buy_type(tx_type) -> bool:
    t = str(tx_type)
    return t in ('buy', 'subscribe')


def _is_sell_type(tx_type) -> bool:
    t = str(tx_type)
    return t in ('sell', 'redeem')


def _is_dividend(tx_type) -> bool:
    return str(tx_type) == 'dividend'


def _calc_annualized(transactions: list, total_return: float) -> float:
    """计算年化收益率"""
    if not transactions:
        return 0.0
    dates = set()
    for tx in transactions:
        d = _parse_date(tx)
        if d:
            dates.add(d)
    if len(dates) < 2:
        return total_return
    first_date = min(dates)
    last_date = max(dates)
    diff = last_date - first_date
    days = diff.days
    if days <= 0:
        return total_return
    return (1 + total_return) ** (365.0 / days) - 1


def _parse_date(tx):
    """解析交易日期为 date 对象"""
    dt = getattr(tx, 'created_at', None)
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.date()
    try:
        return datetime.fromisoformat(str(dt).replace('Z', '+00:00')).date()
    except (ValueError, TypeError):
        return None


def _calc_win_rate(transactions: list) -> tuple[float, int]:
    """计算胜率和总交易次数"""
    win_count = 0
    loss_count = 0

    buys_by_ticker: dict = {}
    for tx in transactions:
        if _is_buy_type(tx.tx_type):
            buys_by_ticker.setdefault(tx.ticker, []).append(tx)

    for tx in transactions:
        if _is_sell_type(tx.tx_type):
            buys = buys_by_ticker.get(tx.ticker, [])
            if buys:
                total_cost = sum(b.quantity * b.price for b in buys)
                total_qty = sum(b.quantity for b in buys)
                avg_cost = total_cost / total_qty if total_qty > 0 else 0.0
                if tx.price > avg_cost:
                    win_count += 1
                else:
                    loss_count += 1

    total_trades = win_count + loss_count
    win_rate = win_count / total_trades if total_trades > 0 else 0.0
    return win_rate, total_trades
