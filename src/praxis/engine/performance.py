"""绩效计算器 — 增强版 12 项指标（v2: 基于 NAV 序列精确计算）"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from praxis.core.interfaces import PerformanceCalculator
from praxis.core.ledger import FileLedger
from praxis.core.models import Transaction, PerformanceMetrics
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class EnhancedPerformanceCalculator(PerformanceCalculator):
    """增强绩效计算器 — 12项指标

    v2 修复（0711）：
    - total_return 从 NAV 序列计算（latest_nav - 1.0），不再用 (sell-buy)/capital 的错误公式
    - max_drawdown 从 NAV 序列精确计算（峰值到谷值的最大跌幅）
    - volatility 从 NAV 日收益率标准差年化
    - annualized_return 根据时间跨度年化
    - sharpe_ratio = annualized_return / annualized_volatility
    - 无 NAV 历史时回退到旧逻辑（兼容）
    """

    def __init__(self, ledger: FileLedger, initial_capital: float = 70000,
                 provider=None, nav_tracker=None):
        self._ledger = ledger
        self._initial_capital = initial_capital
        self._provider = provider
        self._nav_tracker = nav_tracker

    def calculate(self, investor_id: str, portfolio_id: str,
                  start_date: str | None = None, end_date: str | None = None,
                  nav_series: list[float] | None = None,
                  benchmark_series: list[float] | None = None,
                  exclude_reversed: bool = False,
                  exclude_tags: list[str] | None = None,
                  include_tags: list[str] | None = None,
                  ticker: str | None = None) -> dict:
        """计算绩效指标"""
        txs = self._get_filtered_txs(exclude_reversed, exclude_tags, include_tags, ticker)

        if not txs:
            return {"success": False, "error": "无交易记录"}

        # 分类统计
        buy_txs = [t for t in txs if self._is_buy(t)]
        sell_txs = [t for t in txs if self._is_sell(t)]

        total_buy_amount = sum(self._tx_amount(t) for t in buy_txs)
        total_sell_amount = sum(self._tx_amount(t) for t in sell_txs)
        total_fee = sum(t.fee for t in txs if hasattr(t, 'fee'))

        # ── 从 NAV 序列计算精确指标 ──
        nav_records = self._load_nav_records()

        if nav_records and len(nav_records) >= 2:
            # 有 NAV 历史：精确计算
            navs = [r["nav"] for r in nav_records]
            total_assets_series = [r["total_assets"] for r in nav_records]

            # total_return = latest_nav - 1.0
            total_return = navs[-1] - 1.0

            # max_drawdown：峰值到谷值的最大跌幅
            peak = navs[0]
            max_dd = 0.0
            for nav in navs:
                if nav > peak:
                    peak = nav
                dd = (peak - nav) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd

            # volatility：日收益率标准差，年化
            daily_returns = []
            for i in range(1, len(navs)):
                if navs[i - 1] > 0:
                    daily_returns.append((navs[i] / navs[i - 1]) - 1)
            if daily_returns:
                avg_return = sum(daily_returns) / len(daily_returns)
                variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
                daily_vol = math.sqrt(variance)
                annualized_vol = daily_vol * math.sqrt(252)
            else:
                annualized_vol = 0.0

            # annualized_return：根据时间跨度年化
            annualized_return = self._calc_annualized_return(nav_records, total_return)

            # sharpe_ratio（无风险利率假设 0）
            sharpe_ratio = annualized_return / annualized_vol if annualized_vol > 0 else 0.0

            # calmar_ratio
            calmar_ratio = annualized_return / max_dd if max_dd > 0 else 0.0

            # benchmark_return
            benchmark_navs = [
                r.get("benchmark_nav") for r in nav_records
                if r.get("benchmark_nav") is not None
            ]
            if len(benchmark_navs) >= 2:
                benchmark_return = benchmark_navs[-1] / benchmark_navs[0] - 1
            else:
                benchmark_return = 0.0

            excess_return = total_return - benchmark_return

            logger.info(
                "performance_calc_nav_based",
                nav_count=len(nav_records),
                total_return=total_return,
                max_dd=max_dd,
                annualized_vol=annualized_vol,
            )
        else:
            # 无 NAV 历史：回退到旧逻辑（兼容）
            current_mv = self._initial_capital - total_buy_amount + total_sell_amount
            total_return = (current_mv - self._initial_capital) / self._initial_capital
            max_dd = 0.10
            annualized_vol = 0.0
            annualized_return = total_return
            sharpe_ratio = 0.0
            calmar_ratio = 0.0
            benchmark_return = 0
            excess_return = total_return

            logger.warning("performance_calc_fallback_no_nav", total_return=total_return)

        # 胜率
        win_count = sum(1 for t in sell_txs if self._is_profitable(t, buy_txs))
        total_count = len(sell_txs)
        win_rate = win_count / total_count if total_count > 0 else 0

        # 盈亏比
        avg_win = sum(self._tx_amount(t) for t in sell_txs if self._is_profitable(t, buy_txs)) / win_count if win_count > 0 else 0
        avg_loss = sum(self._tx_amount(t) for t in sell_txs if not self._is_profitable(t, buy_txs)) / (total_count - win_count) if (total_count - win_count) > 0 else 0
        profit_loss_ratio = avg_win / abs(avg_loss) if avg_loss != 0 else 0

        result = {
            "total_return": round(total_return, 4),
            "annualized_return": round(annualized_return, 4),
            "benchmark_return": round(benchmark_return, 4),
            "excess_return": round(excess_return, 4),
            "max_drawdown": round(max_dd, 4),
            "volatility": round(annualized_vol, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "calmar_ratio": round(calmar_ratio, 4),
            "win_rate": round(win_rate, 4),
            "profit_loss_ratio": round(profit_loss_ratio, 4),
            "turnover_rate": round((total_buy_amount + total_sell_amount) / (2 * self._initial_capital), 4),
            "total_fee": round(total_fee, 2),
        }

        return {"success": True, "data": result}

    def _load_nav_records(self) -> list[dict]:
        """从 nav_tracker 加载 NAV 历史记录"""
        if self._nav_tracker is None:
            return []
        try:
            result = self._nav_tracker.get_history(days=365)
            if result.get("success"):
                return result["data"]["records"]
        except Exception as e:
            logger.warning("nav_records_load_failed", error=str(e))
        return []

    @staticmethod
    def _calc_annualized_return(nav_records: list[dict], total_return: float) -> float:
        """根据 NAV 序列时间跨度计算年化收益"""
        try:
            first_date = nav_records[0]["date"]
            last_date = nav_records[-1]["date"]
            d1 = datetime.strptime(first_date, "%Y-%m-%d")
            d2 = datetime.strptime(last_date, "%Y-%m-%d")
            days = (d2 - d1).days
            if days > 0:
                return (1 + total_return) ** (365 / days) - 1
        except (ValueError, KeyError, OverflowError) as e:
            logger.warning("annualized_calc_failed", error=str(e))
        return total_return

    def compare_versions(self, version_a: str, version_b: str, metric: str = "sharpe_ratio") -> dict:
        """策略版本对比（stub）"""
        return {"success": True, "data": {
            "version_a": version_a, "version_b": version_b,
            "metric": metric, "improvement": 0.0,
        }}

    def _get_filtered_txs(self, exclude_reversed, exclude_tags, include_tags, ticker):
        txs = self._ledger.list(limit=1000)
        if exclude_reversed:
            txs = [t for t in txs if getattr(t, 'status', None) != 'reversed']
        if ticker:
            txs = [t for t in txs if getattr(t, 'ticker', '') == ticker]
        return txs

    @staticmethod
    def _is_buy(tx) -> bool:
        t = str(getattr(tx, 'tx_type', ''))
        return t in ('buy', 'subscribe')

    @staticmethod
    def _is_sell(tx) -> bool:
        t = str(getattr(tx, 'tx_type', ''))
        return t in ('sell', 'redeem')

    @staticmethod
    def _tx_amount(tx) -> float:
        qty = getattr(tx, 'quantity', 0)
        price = getattr(tx, 'price', 0)
        return qty * price

    def _is_profitable(self, sell_tx, buy_txs) -> bool:
        ticker = getattr(sell_tx, 'ticker', '')
        matched = [t for t in buy_txs if getattr(t, 'ticker', '') == ticker]
        if not matched:
            return sell_tx.price > 0
        avg_cost = sum(self._tx_amount(t) for t in matched) / sum(getattr(t, 'quantity', 1) for t in matched)
        return sell_tx.price > avg_cost


# ═══════════════════════════════════════════════════════════════
# P0-3: 持仓周期分布推导（独立函数，供 review_module 复用）
# ═══════════════════════════════════════════════════════════════


def _derive_holding_period_distribution(ledger: FileLedger) -> dict:
    """从交易账本推导持仓周期分布

    FIFO 配对逻辑：
    - 每笔 SELL/REDEEM 找同一 ticker 最近的 BUY/SUBSCRIBE
    - 按时间顺序，先买先配对卖出
    - 计算 (sell_date - buy_date).days
    - 分档：<3d / 3-7d / 7-20d / >20d

    Args:
        ledger: 交易账本（FileLedger 实例）

    Returns:
        {
            "<3d": int,
            "3-7d": int,
            "7-20d": int,
            ">20d": int,
            "total_paired": int,
            "unpaired": int,
        }
    """
    from datetime import datetime

    from praxis.core.models import TransactionType

    transactions = ledger.get_all()

    # 分离买单和卖单
    buys = [
        tx for tx in transactions
        if tx.tx_type in (TransactionType.BUY, TransactionType.SUBSCRIBE)
    ]
    sells = [
        tx for tx in transactions
        if tx.tx_type in (TransactionType.SELL, TransactionType.REDEEM)
    ]

    # 按 ticker 分组 + 时间排序
    buys_by_ticker: dict[str, list] = {}
    for tx in buys:
        buys_by_ticker.setdefault(tx.ticker, []).append(tx)
    for t_list in buys_by_ticker.values():
        t_list.sort(key=lambda x: x.created_at)

    sells.sort(key=lambda x: x.created_at)

    # 分档计数器
    buckets = {"<3d": 0, "3-7d": 0, "7-20d": 0, ">20d": 0}
    total_paired = 0
    unpaired = 0

    def _parse_dt(dt_val) -> datetime:
        """解析 created_at 为 naive datetime"""
        if isinstance(dt_val, datetime):
            return dt_val.replace(tzinfo=None)
        s = str(dt_val).replace("Z", "+00:00")
        return datetime.fromisoformat(s).replace(tzinfo=None)

    # FIFO 配对
    for sell_tx in sells:
        ticker_buys = buys_by_ticker.get(sell_tx.ticker, [])
        if not ticker_buys:
            unpaired += 1
            continue

        # 取最早的买单（FIFO：先买先配）
        buy_tx = ticker_buys.pop(0)

        buy_dt = _parse_dt(buy_tx.created_at)
        sell_dt = _parse_dt(sell_tx.created_at)

        days_held = (sell_dt - buy_dt).days

        # 分档
        if days_held < 3:
            buckets["<3d"] += 1
        elif days_held <= 7:
            buckets["3-7d"] += 1
        elif days_held <= 20:
            buckets["7-20d"] += 1
        else:
            buckets[">20d"] += 1

        total_paired += 1

    return {
        "<3d": buckets["<3d"],
        "3-7d": buckets["3-7d"],
        "7-20d": buckets["7-20d"],
        ">20d": buckets[">20d"],
        "total_paired": total_paired,
        "unpaired": unpaired,
    }


