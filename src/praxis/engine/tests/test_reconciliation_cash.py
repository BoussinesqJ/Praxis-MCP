"""Regression tests for ReconciliationEngine total-assets / cash computation.

These tests cover the recently fixed cash-balance logic:

* ``ReconciliationEngine._compute_cash_from_ledger`` — walks every *executed*
  transaction in the ledger and accumulates net cash flow against the investor's
  initial ``capital_cny``.
* The accounting identity used by ``reconcile`` / ``reconcile_with_quotes``::

      total_assets = cash_balance + total_positions_value
      cash          = CashState(total_cash=available_cash=cash_balance, frozen_cash=0)

All external dependencies (config_loader, data_provider, ledger) are replaced by
lightweight mock objects.  Real ``Transaction`` / ``TransactionType`` /
``TransactionStatus`` enums from ``praxis.core.models`` are reused to build ledger
entries so the production cash math is exercised against the real data shapes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from praxis.core.models import (
    AssetEntry,
    AssetType,
    InvestorProfile,
    Portfolio,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from praxis.engine.reconciliation import ReconciliationEngine

INVESTOR_ID = "inv-001"
PORTFOLIO_ID = "pf-001"


# ---------------------------------------------------------------------------
# Lightweight mocks
# ---------------------------------------------------------------------------


class FakeConfigLoader:
    """Minimal ConfigLoader stub returning a fixed InvestorProfile / Portfolio."""

    def __init__(self, capital_cny: float, portfolio: Portfolio) -> None:
        self._profile = InvestorProfile(
            investor_id=INVESTOR_ID,
            name="Test Investor",
            capital_cny=capital_cny,
        )
        self._portfolio = portfolio

    def load_investor(self, investor_id: str) -> InvestorProfile:
        return self._profile

    def load_portfolio(self, investor_id: str, portfolio_id: str) -> Portfolio:
        return self._portfolio


class FakeLedger:
    """Minimal Ledger stub returning a prebuilt list of Transaction objects."""

    def __init__(self, transactions) -> None:
        self._txs = list(transactions)

    def get_all(self):
        return self._txs


class FakeDataProvider:
    """Minimal DataProvider stub returning fixed quotes keyed by ticker."""

    def __init__(self, quotes: dict) -> None:
        self._quotes = quotes

    async def get_realtime_quote(self, tickers):
        return {t: self._quotes[t] for t in tickers if t in self._quotes}


# ---------------------------------------------------------------------------
# Factories / fixtures
# ---------------------------------------------------------------------------


def make_tx(
    ticker: str,
    tx_type: TransactionType,
    quantity: float,
    price: float,
    fee: float = 0.0,
    status: TransactionStatus = TransactionStatus.EXECUTED,
    created_at: str | None = None,
    portfolio_id: str = PORTFOLIO_ID,
    investor_id: str = INVESTOR_ID,
) -> Transaction:
    """Build a single Transaction with sane defaults."""
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    return Transaction(
        investor_id=investor_id,
        portfolio_id=portfolio_id,
        ticker=ticker,
        tx_type=tx_type,
        quantity=quantity,
        price=price,
        fee=fee,
        status=status,
        created_at=created_at,
    )


def core_transactions():
    """The 4-transaction scenario used by the core cash-flow / full-reconcile tests.

    capital_cny = 100000
      buy  A 100@10  fee 0  -> -1000      cash 99000
      sell A  50@12  fee 5  -> +(600-5)   cash 99595
      buy  B 200@5   fee 2  -> -(1000+2)  cash 98593
      redeem C 100@8 fee 3  -> +(800-3)   cash 99390
    """
    return [
        make_tx("A", TransactionType.BUY, 100, 10, fee=0.0, created_at="2024-01-01T09:00:00"),
        make_tx("A", TransactionType.SELL, 50, 12, fee=5.0, created_at="2024-01-02T09:00:00"),
        make_tx("B", TransactionType.BUY, 200, 5, fee=2.0, created_at="2024-01-03T09:00:00"),
        make_tx("C", TransactionType.REDEEM, 100, 8, fee=3.0, created_at="2024-01-04T09:00:00"),
    ]


def _empty_portfolio() -> Portfolio:
    """A portfolio with no assets (used for pure cash-flow unit tests)."""
    return Portfolio(portfolio_id=PORTFOLIO_ID, investor_id=INVESTOR_ID)


@pytest.fixture
def portfolio_two_assets() -> Portfolio:
    """Portfolio containing only A and B — C is intentionally excluded."""
    return Portfolio(
        portfolio_id=PORTFOLIO_ID,
        investor_id=INVESTOR_ID,
        name="Test Portfolio",
        assets=[
            AssetEntry(ticker="A", name="Stock A", asset_type=AssetType.STOCK, target_weight_pct=50.0),
            AssetEntry(ticker="B", name="Stock B", asset_type=AssetType.STOCK, target_weight_pct=50.0),
        ],
    )


# ---------------------------------------------------------------------------
# Case 1 — Core cash flow
# ---------------------------------------------------------------------------


def test_core_cash_flow_matches_hand_calc():
    """Core: 4 mixed transactions accumulate to a 99390.0 cash balance."""
    engine = ReconciliationEngine(
        FakeConfigLoader(100000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger(core_transactions()),
    )
    cash = engine._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID)
    # 100000 -1000 +595 -1002 +797 = 99390
    assert cash == pytest.approx(99390.0)


def test_core_cash_flow_order_independent():
    """Cash result must not depend on ledger ordering (sorted by created_at)."""
    txs = core_transactions()
    shuffled = list(reversed(txs))
    engine_a = ReconciliationEngine(
        FakeConfigLoader(100000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger(txs),
    )
    engine_b = ReconciliationEngine(
        FakeConfigLoader(100000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger(shuffled),
    )
    assert engine_a._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID) == pytest.approx(99390.0)
    assert engine_b._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID) == pytest.approx(99390.0)


# ---------------------------------------------------------------------------
# Case 2 — ledger is None
# ---------------------------------------------------------------------------


def test_ledger_none_returns_capital_without_crashing():
    """ledger=None must short-circuit and return capital_cny (no crash)."""
    engine = ReconciliationEngine(
        FakeConfigLoader(123456.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=None,
    )
    cash = engine._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID)
    assert cash == pytest.approx(123456.0)


# ---------------------------------------------------------------------------
# Case 3 — empty ledger
# ---------------------------------------------------------------------------


def test_empty_ledger_returns_capital():
    """An empty ledger (get_all() -> []) must return capital_cny unchanged."""
    engine = ReconciliationEngine(
        FakeConfigLoader(50000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger([]),
    )
    cash = engine._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID)
    assert cash == pytest.approx(50000.0)


# ---------------------------------------------------------------------------
# Case 4 — only buys, no sells
# ---------------------------------------------------------------------------


def test_only_buys_reduce_cash_below_capital():
    """With only buy/subscribe transactions, cash < capital and the reduction
    equals the sum of (price*qty + fee)."""
    txs = [
        make_tx("A", TransactionType.BUY, 100, 10, fee=0.0),
        make_tx("B", TransactionType.SUBSCRIBE, 50, 20, fee=10.0),
    ]
    engine = ReconciliationEngine(
        FakeConfigLoader(100000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger(txs),
    )
    cash = engine._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID)
    reduction = 100 * 10 + 0.0 + 50 * 20 + 10.0  # 1000 + 1010 = 2010
    assert cash < 100000.0
    assert 100000.0 - cash == pytest.approx(reduction)


# ---------------------------------------------------------------------------
# Case 5 — fee is accounted for
# ---------------------------------------------------------------------------


def test_fee_is_deducted_on_buy():
    """A single buy with a non-zero fee must reduce cash by price*qty + fee."""
    tx = make_tx("A", TransactionType.BUY, 100, 10, fee=30.0)
    engine = ReconciliationEngine(
        FakeConfigLoader(100000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger([tx]),
    )
    cash = engine._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID)
    # 100000 - (100*10 + 30) = 98970
    assert cash == pytest.approx(98970.0)
    assert 100000.0 - cash == pytest.approx(1000.0 + 30.0)


# ---------------------------------------------------------------------------
# Edge cases — filtering
# ---------------------------------------------------------------------------


def test_non_executed_transactions_are_ignored():
    """Only transactions with status.value == 'executed' affect the cash flow."""
    txs = [
        make_tx("A", TransactionType.BUY, 100, 10, fee=0.0, status=TransactionStatus.PENDING),
        make_tx("A", TransactionType.BUY, 100, 10, fee=0.0, status=TransactionStatus.EXECUTED),
        make_tx("A", TransactionType.BUY, 100, 10, fee=0.0, status=TransactionStatus.REVERSED),
    ]
    engine = ReconciliationEngine(
        FakeConfigLoader(100000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger(txs),
    )
    cash = engine._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID)
    # only the EXECUTED buy reduces cash by 1000
    assert cash == pytest.approx(99000.0)


def test_transactions_for_other_investor_are_ignored():
    """Transactions belonging to a different investor/portfolio are skipped."""
    txs = [
        make_tx("A", TransactionType.BUY, 100, 10, fee=0.0, investor_id="other-inv"),
        make_tx("A", TransactionType.BUY, 50, 10, fee=0.0),  # this investor
    ]
    engine = ReconciliationEngine(
        FakeConfigLoader(100000.0, _empty_portfolio()),
        FakeDataProvider({}),
        ledger=FakeLedger(txs),
    )
    cash = engine._compute_cash_from_ledger(INVESTOR_ID, PORTFOLIO_ID)
    # only the second buy (same investor) reduces cash by 500
    assert cash == pytest.approx(99500.0)


# ---------------------------------------------------------------------------
# Case 6 — full reconcile integration (accounting identity)
# ---------------------------------------------------------------------------


def test_full_reconcile_with_quotes_total_assets_identity(portfolio_two_assets):
    """reconcile_with_quotes: total_assets == cash + positions value == 101340.0."""
    ledger = FakeLedger(core_transactions())
    config = FakeConfigLoader(100000.0, portfolio_two_assets)
    engine = ReconciliationEngine(config, FakeDataProvider({}), ledger=ledger)

    quotes = {"A": 15.0, "B": 6.0}
    state = engine.reconcile_with_quotes(quotes, INVESTOR_ID, PORTFOLIO_ID)

    # accounting identity must hold
    assert state.total_assets == pytest.approx(state.cash.total_cash + state.total_market_value)
    # hand-computed ledger cash balance
    assert state.cash.total_cash == pytest.approx(99390.0)
    assert state.cash.available_cash == pytest.approx(99390.0)
    assert state.cash.frozen_cash == 0
    # positions: A 50*15=750, B 200*6=1200 -> 1950
    assert state.total_market_value == pytest.approx(1950.0)
    # total = 99390 + 1950
    assert state.total_assets == pytest.approx(101340.0)


def test_async_reconcile_accounting_identity(portfolio_two_assets):
    """async reconcile(): identity total_assets == cash + mv holds and cash equals
    the hand-computed ledger balance (99390.0)."""
    ledger = FakeLedger(core_transactions())
    config = FakeConfigLoader(100000.0, portfolio_two_assets)
    data = FakeDataProvider({"A": {"price": 15.0}, "B": {"price": 6.0}})
    engine = ReconciliationEngine(config, data, ledger=ledger)

    state = asyncio.run(engine.reconcile(INVESTOR_ID, PORTFOLIO_ID, dry_run=True))

    # accounting identity must hold
    assert state.total_assets == pytest.approx(state.cash.total_cash + state.total_market_value)
    # cash equals hand-computed ledger balance
    assert state.cash.total_cash == pytest.approx(99390.0)
    # positions value: A 50*15=750, B 200*6=1200 -> 1950
    assert state.total_market_value == pytest.approx(1950.0)
    assert state.total_assets == pytest.approx(101340.0)
