"""Engine 层测试专用 fixtures 和 Fake 类.

为 Engine 层 10 个测试模块提供：
- 8 个 Fake 类（模拟外部依赖）
- 8 个 fixture（共享测试数据）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from praxis.core.interfaces import DataProvider, ConfigLoader, Ledger, BenchmarkProvider, DecisionRecorder, PerformanceCalculator
from praxis.core.models import (
    AssetType, AssetCategory, AssetEntry,
    InvestorProfile, InvestorConstraints, ExecutionConfig,
    Portfolio, SentinelEntry,
    StrategyTemplate, RuleEntry,
    PortfolioState, PositionState, CashState,
    DecisionRecord, DecisionStatus,
    Transaction, TransactionType, TransactionStatus,
    TeamSignal,
)
from praxis.core.exceptions import ConfigError


# ═══════════════════════════════════════════════════════════════════
# Fake 类
# ═══════════════════════════════════════════════════════════════════

class FakeDataProvider(DataProvider):
    """内存数据源 — 实现 DataProvider 接口."""

    def __init__(self, quotes=None, klines=None, fund_nav=None):
        self._quotes = quotes or {}
        self._klines = klines or {}
        self._fund_nav = fund_nav or {}

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        return {t: self._quotes.get(t, {}) for t in tickers}

    async def get_history_kline(self, ticker: str, period: str = "day", count: int = 60) -> list[dict]:
        return self._klines.get(ticker, [])[:count]

    async def get_fund_nav(self, ticker: str) -> dict:
        return self._fund_nav.get(ticker, {})


class FakeConfigLoader(ConfigLoader):
    """内存配置加载器 — 实现 ConfigLoader 接口."""

    def __init__(
        self,
        investor: InvestorProfile | None = None,
        portfolios: dict[str, Portfolio] | None = None,
        strategies: dict[str, StrategyTemplate] | None = None,
        asset_details: dict[str, dict] | None = None,
    ):
        self._investor = investor or _default_investor()
        self._portfolios = portfolios or {}
        self._strategies = strategies or {}
        self._asset_details = asset_details or {}

    def load_investor(self, investor_id: str) -> InvestorProfile:
        return self._investor

    def load_portfolio(self, investor_id: str, portfolio_id: str) -> Portfolio:
        key = f"{investor_id}/{portfolio_id}"
        if key in self._portfolios:
            return self._portfolios[key]
        return self._portfolios.get(portfolio_id,
            _default_portfolio(portfolio_id, investor_id))

    def load_strategy(self, strategy_name: str) -> StrategyTemplate:
        if strategy_name in self._strategies:
            return self._strategies[strategy_name]
        return _default_strategy(strategy_name)

    def load_asset_detail(self, investor_id: str, portfolio_id: str, ticker: str) -> dict:
        key = f"{investor_id}/{portfolio_id}/{ticker}"
        if key in self._asset_details:
            return self._asset_details[key]
        return {"ticker": ticker, "name": ticker, "target_weight_pct": 10.0}

    def list_portfolios(self, investor_id: str) -> list[str]:
        result = []
        for key in self._portfolios:
            if key.startswith(f"{investor_id}/"):
                result.append(key.split("/", 1)[1])
        return result if result else ["core"]


class FakeLedger(Ledger):
    """内存交易账本 — 实现 Ledger 接口，额外提供 get_all/get_by_status."""

    def __init__(self, transactions: list[Transaction] | None = None):
        self._txs: dict[str, Transaction] = {}
        self._idempotency: dict[str, str] = {}
        self._next_id = 1
        if transactions:
            for tx in transactions:
                self.append(tx)

    def append(self, tx: Transaction) -> str:
        if tx.idempotency_key and tx.idempotency_key in self._idempotency:
            return self._idempotency[tx.idempotency_key]
        tx_id = tx.tx_id or f"tx-{self._next_id:06d}"
        self._next_id += 1
        tx.tx_id = tx_id
        self._txs[tx_id] = tx
        if tx.idempotency_key:
            self._idempotency[tx.idempotency_key] = tx_id
        return tx_id

    def list(self, ticker: str | None = None, limit: int = 100) -> list[Transaction]:
        result = list(self._txs.values())
        if ticker:
            result = [tx for tx in result if tx.ticker == ticker]
        return result[:limit]

    def get(self, tx_id: str) -> Transaction | None:
        return self._txs.get(tx_id)

    def exists(self, idempotency_key: str) -> bool:
        return idempotency_key in self._idempotency

    def delete(self, tx_id: str) -> bool:
        if tx_id in self._txs:
            del self._txs[tx_id]
            return True
        return False

    def purge(self, tag: str | None = None) -> int:
        if tag is None:
            count = len(self._txs)
            self._txs.clear()
            self._idempotency.clear()
            return count
        to_delete = [
            tx_id for tx_id, tx in self._txs.items()
            if tag in (getattr(tx, 'tags', []) or [])
        ]
        for tx_id in to_delete:
            del self._txs[tx_id]
        return len(to_delete)

    def get_all(self) -> list[Transaction]:
        """引擎层扩展 — 返回全部交易."""
        return list(self._txs.values())

    def get_by_status(self, status: str) -> list[Transaction]:
        """引擎层扩展 — 按状态过滤."""
        return [tx for tx in self._txs.values()
                if str(getattr(tx, 'status', '')) == status]

    def reverse(self, tx_id: str) -> bool:
        """标记冲销."""
        tx = self._txs.get(tx_id)
        if tx is None:
            return False
        tx.status = TransactionStatus.REVERSED
        return True


class FakeBenchmarkProvider(BenchmarkProvider):
    """内存基准数据源 — 实现 BenchmarkProvider 接口."""

    def __init__(self, klines: dict[str, list[dict]] | None = None):
        self._klines = klines or {}

    async def get_daily_kline(
        self, index_code: str, start_date: str, end_date: str,
    ) -> list[dict]:
        all_kl = self._klines.get(index_code, [])
        return [k for k in all_kl if start_date <= k.get("date", "") <= end_date]

    async def get_latest_price(self, index_code: str) -> dict:
        kl = self._klines.get(index_code, [])
        if kl:
            last = kl[-1]
            return {
                "price": last.get("close", 0),
                "change": 0,
                "change_pct": 0,
                "date": last.get("date", ""),
            }
        return {"price": 0, "change": 0, "change_pct": 0, "date": ""}

    def get_supported_indices(self) -> list[dict]:
        return [
            {"code": "000300", "name": "沪深300", "description": "沪深300指数"},
            {"code": "000905", "name": "中证500", "description": "中证500指数"},
            {"code": "399006", "name": "创业板指", "description": "创业板指数"},
        ]


class FakeNavTracker:
    """内存净值追踪器 — Duck typing 匹配 NavTracker API."""

    def __init__(self, records: list[dict] | None = None, ledger=None, data_provider=None):
        self._records: list[dict] = list(records or [])
        self._ledger = ledger
        self._data = data_provider
        self._initial_capital = 70000.0

    def record(
        self, nav: float, total_assets: float, positions_value: float,
        cash: float, benchmark_nav: float | None = None,
        benchmark_code: str | None = None,
    ) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for r in self._records:
            if r.get("date") == today:
                return {"success": False, "error": f"今日 {today} 已记录净值"}
        entry = {
            "date": today, "nav": round(nav, 4),
            "total_assets": round(total_assets, 2),
            "positions_value": round(positions_value, 2),
            "cash": round(cash, 2),
            "benchmark_nav": round(benchmark_nav, 4) if benchmark_nav else None,
            "benchmark_code": benchmark_code,
        }
        self._records.append(entry)
        return {"success": True, "data": entry}

    async def snapshot(self, investor_id: str, portfolio_id: str) -> dict:
        if not self._records:
            return {"success": False, "error": "无净值记录"}
        return {"success": True, "data": dict(self._records[-1])}

    def get_history(self, days: int = 30) -> dict:
        history = self._records[-days:] if len(self._records) > days else self._records
        return {"success": True, "data": {"records": history, "count": len(history)}}


class FakeDecisionRecorder(DecisionRecorder):
    """内存决策记录器 — 实现 DecisionRecorder + 引擎扩展方法."""

    def __init__(self, decisions: list[DecisionRecord] | None = None):
        self._index: dict[str, DecisionRecord] = {}
        self._counter = 1
        if decisions:
            for d in decisions:
                self.create(d)

    def create(self, record: DecisionRecord) -> str:
        if not record.decision_id:
            record.decision_id = f"dec-fake-{self._counter:06d}"
            self._counter += 1
        self._index[record.decision_id] = record
        return record.decision_id

    def get(self, decision_id: str) -> DecisionRecord | None:
        return self._index.get(decision_id)

    def update_status(self, decision_id: str, status: str, **kwargs) -> bool:
        record = self._index.get(decision_id)
        if record is None:
            return False
        try:
            record.status = DecisionStatus(status)
        except ValueError:
            return False
        record.updated_at = datetime.now(timezone.utc).isoformat()
        if "review_result" in kwargs:
            record.review_result = kwargs["review_result"]
        return True

    def list_pending(self, limit: int = 50) -> list[DecisionRecord]:
        records = [r for r in self._index.values()
                   if r.status in (DecisionStatus.DRAFT, DecisionStatus.PENDING)]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def link_transaction(self, decision_id: str, tx_id: str) -> bool:
        record = self._index.get(decision_id)
        if record is None:
            return False
        record.tx_id = tx_id
        record.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    # ── 引擎层扩展 ──

    def get_executed(self, limit: int = 100) -> list[DecisionRecord]:
        records = [r for r in self._index.values()
                   if r.status == DecisionStatus.EXECUTED]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def update_review(self, decision_id: str, review_type: str, review_data: dict) -> bool:
        record = self._index.get(decision_id)
        if record is None:
            return False
        import json
        record.review_result = json.dumps({"type": review_type, **review_data}, ensure_ascii=False)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def list(self, status: str | None = None, limit: int = 100) -> list[DecisionRecord]:
        if status:
            try:
                ds = DecisionStatus(status)
                records = [r for r in self._index.values() if r.status == ds]
            except ValueError:
                records = []
        else:
            records = list(self._index.values())
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]


class FakeSentinelEngine:
    """内存哨兵引擎 — Duck typing 匹配 SentinelEngine API."""

    def __init__(self, scan_result: dict | None = None):
        self._scan_result = scan_result or {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "bullish_count": 4, "total": 8,
            "state": "适度试探期", "position_limit_pct": 20.0,
            "rule23_triggered": False, "rule23_consecutive_days": 0,
            "sentinels": {},
        }
        self._history: list[dict] = [dict(self._scan_result)]

    async def scan(self) -> dict:
        entry = dict(self._scan_result)
        self._history.append(entry)
        return entry

    def get_rule23_status(self) -> dict:
        if not self._history:
            return {"triggered": False, "consecutive_days": 0,
                    "bullish_count": 0, "message": "无历史数据"}
        last = self._history[-1]
        return {
            "triggered": last.get("rule23_triggered", False),
            "consecutive_days": last.get("rule23_consecutive_days", 0),
            "bullish_count": last.get("bullish_count", 0),
            "state": last.get("state", "unknown"),
            "date": last.get("date", ""),
        }

    def get_history(self, days: int = 10) -> list[dict]:
        return self._history[-days:]


class FakePerformanceCalculator(PerformanceCalculator):
    """内存绩效计算器 — 实现 PerformanceCalculator 接口."""

    def __init__(self, result: dict | None = None):
        self._result = result or {
            "total_return": 0.05, "annualized_return": 0.12,
            "benchmark_return": 0.03, "excess_return": 0.02,
            "max_drawdown": 0.08, "volatility": 0.15,
            "sharpe_ratio": 0.8, "calmar_ratio": 1.5,
            "win_rate": 0.6, "profit_loss_ratio": 1.8,
            "turnover_rate": 0.3, "total_fee": 50.0,
        }

    def calculate(
        self, investor_id: str, portfolio_id: str,
        start_date: str | None = None, end_date: str | None = None,
        **kwargs,
    ) -> dict:
        return {"success": True, "data": dict(self._result)}

    def compare_versions(
        self, version_a: str, version_b: str, metric: str = "sharpe_ratio",
    ) -> dict:
        return {
            "success": True, "data": {
                "version_a": version_a, "version_b": version_b,
                "metric": metric, "improvement": 0.05,
            },
        }


# ═══════════════════════════════════════════════════════════════════
# 默认工厂函数
# ═══════════════════════════════════════════════════════════════════

def _default_investor(capital: float = 100000.0) -> InvestorProfile:
    return InvestorProfile(
        investor_id="inv-test",
        name="测试投资者",
        capital_cny=capital,
        risk_level="C3",
        constraints=InvestorConstraints(),
        execution=ExecutionConfig(),
    )


def _default_portfolio(portfolio_id: str = "core", investor_id: str = "inv-test") -> Portfolio:
    return Portfolio(
        portfolio_id=portfolio_id,
        investor_id=investor_id,
        name="测试组合",
        assets=[
            AssetEntry(ticker="600519", name="贵州茅台", asset_type=AssetType.STOCK, 
                       category=AssetCategory.LARGE_CAP, target_weight_pct=50.0),
            AssetEntry(ticker="159915", name="创业板ETF", asset_type=AssetType.ETF,
                       category=AssetCategory.BROAD_MARKET, target_weight_pct=50.0),
        ],
    )


def _default_strategy(name: str = "grid_value") -> StrategyTemplate:
    return StrategyTemplate(
        strategy_name=name,
        version="1.0.0",
        description="测试策略",
        rules=[
            RuleEntry(rule_id="execution_rules.min_transaction", name="最小交易金额",
                      level="soft_warning", enabled=True,
                      params={"min_amount_cny": 3000.0}),
            RuleEntry(rule_id="risk_rules.cash_floor", name="现金底线",
                      level="hard_block", enabled=True,
                      params={"min_pct": 70.0}),
            RuleEntry(rule_id="risk_rules.position_cap", name="仓位上限",
                      level="hard_block", enabled=True,
                      params={"max_single_pct": 15.0}),
            RuleEntry(rule_id="risk_rules.stop_loss", name="止损",
                      level="hard_block", enabled=True,
                      params={"default_pct": -10.0}),
            RuleEntry(rule_id="risk_rules.max_drawdown", name="最大回撤",
                      level="hard_block", enabled=True,
                      params={"pct": 20.0}),
            RuleEntry(rule_id="time_rules.offshore_fund_window", name="交易窗口",
                      level="advisory", enabled=True,
                      params={"start": "14:45", "end": "14:55"}),
        ],
    )


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def fake_data_provider() -> FakeDataProvider:
    """含预设行情的 FakeDataProvider.

    返回:
        FakeDataProvider: 含 600519(1850)/159915(2.35) 行情 + 60条K线
    """
    quotes = {
        "600519": {"price": 1850.0, "change": 15.0, "change_pct": 0.82, "volume": 5000000, "name": "贵州茅台"},
        "159915": {"price": 2.35, "change": -0.02, "change_pct": -0.85, "volume": 1e8, "name": "创业板ETF"},
        "000001": {"price": 12.5, "change": 0.3, "change_pct": 2.46, "volume": 8000000, "name": "平安银行"},
    }

    # 生成 60 条模拟日K线
    klines_600519 = []
    for i in range(60):
        base = 1800.0 + i * 1.2
        klines_600519.append({
            "date": f"2024-{(i//20)+1:02d}-{(i%20)+1:02d}",
            "open": base, "high": base + 10, "low": base - 8,
            "close": base + 5, "volume": 5000000,
        })

    klines_159915 = []
    for i in range(60):
        base = 2.20 + i * 0.003
        klines_159915.append({
            "date": f"2024-{(i//20)+1:02d}-{(i%20)+1:02d}",
            "open": base, "high": base + 0.05, "low": base - 0.03,
            "close": base + 0.02, "volume": 1e8,
        })

    return FakeDataProvider(
        quotes=quotes,
        klines={"600519": klines_600519, "159915": klines_159915},
    )


@pytest.fixture
def fake_config_loader() -> FakeConfigLoader:
    """含默认 investor(capital=100000) + portfolio + strategy 的 FakeConfigLoader.

    返回:
        FakeConfigLoader: 预配置的测试配置加载器
    """
    investor = _default_investor(100000.0)
    portfolio = Portfolio(
        portfolio_id="core",
        investor_id="inv-test",
        name="核心组合",
        assets=[
            AssetEntry(ticker="600519", name="贵州茅台", asset_type=AssetType.STOCK,
                       category=AssetCategory.LARGE_CAP, target_weight_pct=50.0),
            AssetEntry(ticker="159915", name="创业板ETF", asset_type=AssetType.ETF,
                       category=AssetCategory.BROAD_MARKET, target_weight_pct=50.0),
        ],
        sentinels=[
            SentinelEntry(ticker="510300", name="沪深300ETF", layer="macro", role="大盘基准"),
            SentinelEntry(ticker="159915", name="创业板ETF", layer="macro", role="成长风向标"),
        ],
    )
    strategy = _default_strategy("grid_value")
    return FakeConfigLoader(
        investor=investor,
        portfolios={"inv-test/core": portfolio},
        strategies={"grid_value": strategy},
    )


@pytest.fixture
def fake_ledger() -> FakeLedger:
    """空内存账本.

    返回:
        FakeLedger: 无交易记录的空账本
    """
    return FakeLedger()


@pytest.fixture
def fake_benchmark_provider() -> FakeBenchmarkProvider:
    """含预设 K 线的 FakeBenchmarkProvider.

    返回:
        FakeBenchmarkProvider: 含 000300/000905/399006 日K线数据
    """
    klines_000300 = []
    for i in range(30):
        base = 3500.0 + i * 10.0
        klines_000300.append({
            "date": f"2024-{(i//15)+6:02d}-{(i%15)+1:02d}",
            "open": round(base, 2), "high": round(base + 20, 2),
            "low": round(base - 15, 2), "close": round(base + 8, 2),
            "volume": 1e9,
        })
    return FakeBenchmarkProvider(klines={"000300": klines_000300})


@pytest.fixture
def fake_nav_tracker() -> FakeNavTracker:
    """含 30 条日频 NAV 记录的 FakeNavTracker.

    返回:
        FakeNavTracker: 从 1.000 逐步增长到 ~1.05 的净值序列
    """
    records = []
    for i in range(30):
        nav_val = 1.0 + i * 0.0017
        ta = 70000.0 + i * 120.0
        pv = 35000.0 + i * 60.0
        cash_val = ta - pv
        records.append({
            "date": f"2024-{(i//15)+6:02d}-{(i%15)+1:02d}",
            "nav": round(nav_val, 4),
            "total_assets": round(ta, 2),
            "positions_value": round(pv, 2),
            "cash": round(cash_val, 2),
            "benchmark_nav": round(1.0 + i * 0.001, 4),
            "benchmark_code": "000300",
        })
    return FakeNavTracker(records=records)


@pytest.fixture
def fake_decision_recorder() -> FakeDecisionRecorder:
    """空 FakeDecisionRecorder.

    返回:
        FakeDecisionRecorder: 无决策记录的空记录器
    """
    return FakeDecisionRecorder()


@pytest.fixture
def fake_review_filler_deps(
    fake_decision_recorder: FakeDecisionRecorder,
    fake_ledger: FakeLedger,
    fake_data_provider: FakeDataProvider,
    fake_benchmark_provider: FakeBenchmarkProvider,
) -> dict:
    """ReviewFiller 所需的依赖字典.

    返回:
        dict: {recorder, ledger, data_provider, benchmark_provider}
    """
    return {
        "recorder": fake_decision_recorder,
        "ledger": fake_ledger,
        "data_provider": fake_data_provider,
        "benchmark_provider": fake_benchmark_provider,
    }


@pytest.fixture
def sample_state() -> PortfolioState:
    """含 2 个持仓的 PortfolioState.

    返回:
        PortfolioState: 600519(1850*50) + 159915(2.35*10000) 的状态
    """
    pos1 = PositionState(
        ticker="600519", name="贵州茅台", asset_type=AssetType.STOCK,
        quantity=50.0, avg_cost=1800.0, current_price=1850.0,
        market_value=92500.0, unrealized_pnl=2500.0,
        realized_pnl=0.0, weight_pct=61.67, today_change_pct=0.82,
    )
    pos2 = PositionState(
        ticker="159915", name="创业板ETF", asset_type=AssetType.ETF,
        quantity=10000.0, avg_cost=2.30, current_price=2.35,
        market_value=23500.0, unrealized_pnl=500.0,
        realized_pnl=0.0, weight_pct=15.67, today_change_pct=-0.85,
    )
    return PortfolioState(
        investor_id="inv-test",
        portfolio_id="core",
        total_assets=150000.0,
        total_market_value=116000.0,
        cash=CashState(total_cash=34000.0, available_cash=34000.0, frozen_cash=0.0),
        positions=[pos1, pos2],
        nav=1.5,
        total_return_pct=5.0,
    )
