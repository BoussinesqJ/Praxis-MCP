"""Regression tests for the buy-side ``avg_cost`` fee fix in ReconciliationEngine.

This suite locks down the defect fix made in
``ReconciliationEngine._compute_positions_from_ledger`` (buy branch, ~L150-157):

    Before:  avg_cost = (old_qty * old_cost + qty * price) / new_qty   # fee dropped
    After:   fee_val  = fee if fee else 0.0
             avg_cost = (old_qty * old_cost + qty * price + fee_val) / new_qty

The buy fee is now folded into the moving-average cost basis, while the sell
branch is *unchanged* (sell fee still flows into realized_pnl).  The cash
ledger (``_compute_cash_from_ledger``) was already charging the buy fee, so
this fix makes the cost basis consistent with the cash basis.

These tests also cover the defensive ``fee if fee else 0.0`` guard that must
not raise when ``fee`` is ``None`` or ``0``.

All external dependencies (config_loader, data_provider, ledger) are replaced
by lightweight mock objects.  Real ``Transaction`` / ``TransactionType`` /
``TransactionStatus`` enums from ``praxis.core.models`` are reused to build
ledger entries so the production math is exercised against the real data
shapes.  The production ``Transaction`` model rejects ``fee=None`` (``fee:
float`` with ``ge=0``), so a duck-typed object is used only for the explicit
``fee=None`` case to exercise the defensive branch.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from praxis.core.models import (
    AssetEntry,
    AssetType,
    Portfolio,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from praxis.engine.reconciliation import ReconciliationEngine

INVESTOR_ID = "inv-cost-001"
PORTFOLIO_ID = "pf-cost-001"


# ---------------------------------------------------------------------------
# Lightweight mocks
# ---------------------------------------------------------------------------


class FakeConfigLoader:
    """Minimal ConfigLoader stub returning a fixed InvestorProfile / Portfolio."""

    def __init__(self, capital_cny: float, portfolio: Portfolio) -> None:
        from praxis.core.models import InvestorProfile

        self._profile = InvestorProfile(
            investor_id=INVESTOR_ID,
            name="Test Investor",
            capital_cny=capital_cny,
        )
        self._portfolio = portfolio

    def load_investor(self, investor_id: str):
        return self._profile

    def load_portfolio(self, investor_id: str, portfolio_id: str) -> Portfolio:
        return self._portfolio


class FakeLedger:
    """Minimal Ledger stub returning a prebuilt list of transaction objects."""

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


class NoneFeeTx:
    """Duck-typed transaction whose ``fee`` is explicitly ``None``.

    Used only for the defensive ``fee=None`` branch, because the production
    ``Transaction`` Pydantic model (``fee: float``, ``ge=0``) rejects ``None``.
    Exposes the same attribute surface the engine reads:
    ``tx_type.value``, ``status.value``, ``ticker``, ``quantity``, ``price``,
    ``fee``, ``created_at``, ``investor_id``, ``portfolio_id``.
    """

    def __init__(
        self,
        ticker: str,
        tx_type: TransactionType,
        quantity: float,
        price: float,
        fee,
        status: TransactionStatus = TransactionStatus.EXECUTED,
        created_at: str | None = None,
        investor_id: str = INVESTOR_ID,
        portfolio_id: str = PORTFOLIO_ID,
    ) -> None:
        self.tx_type = tx_type
        self.status = status
        self.ticker = ticker
        self.quantity = quantity
        self.price = price
        self.fee = fee
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.investor_id = investor_id
        self.portfolio_id = portfolio_id


# ---------------------------------------------------------------------------
# Factories
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
    """Build a single real Transaction with sane defaults."""
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


def _portfolio_with(ticker: str = "A", name: str = "Stock A") -> Portfolio:
    """A portfolio containing a single asset (default ticker A)."""
    return Portfolio(
        portfolio_id=PORTFOLIO_ID,
        investor_id=INVESTOR_ID,
        name="Cost Fee Portfolio",
        assets=[
            AssetEntry(
                ticker=ticker,
                name=name,
                asset_type=AssetType.STOCK,
                target_weight_pct=100.0,
            )
        ],
    )


def _engine(capital_cny: float, transactions, portfolio: Portfolio | None = None):
    """Build a ReconciliationEngine wired to in-memory mocks."""
    portfolio = portfolio or _portfolio_with()
    return ReconciliationEngine(
        FakeConfigLoader(capital_cny, portfolio),
        FakeDataProvider({}),
        ledger=FakeLedger(transactions),
    )


# ---------------------------------------------------------------------------
# Case 1 — open position with fee (CORE regression for the fix)
# ---------------------------------------------------------------------------


def test_open_position_includes_buy_fee_in_avg_cost():
    """Open a position: buy A 100@54.00 fee=3.00 -> avg_cost == 54.03."""
    tx = make_tx("A", TransactionType.BUY, 100, 54.00, fee=3.00,
                 created_at="2024-01-01T09:00:00")
    engine = _engine(100000.0, [tx])
    acc = engine._compute_positions_from_ledger(INVESTOR_ID, PORTFOLIO_ID)

    assert "A" in acc
    assert acc["A"]["quantity"] == pytest.approx(100.0)
    # hand-calc: (0 + 100*54.00 + 3.00) / 100 = 54.03  (NOT 54.00)
    assert acc["A"]["avg_cost"] == pytest.approx(54.03)
    # the bug would yield 54.00 — guard explicitly against regression
    assert acc["A"]["avg_cost"] != pytest.approx(54.00)


# ---------------------------------------------------------------------------
# Case 2 — add to position with fee (moving-average basis)
# ---------------------------------------------------------------------------


def test_add_position_includes_buy_fee_in_avg_cost():
    """Add to a position; the second buy's fee must be averaged in.

    buy A 100@50.00 fee=0   -> avg_cost 50.00
    buy A 100@60.00 fee=10  -> avg_cost (100*50 + 100*60 + 10)/200 = 55.05
    """
    txs = [
        make_tx("A", TransactionType.BUY, 100, 50.00, fee=0.0,
                created_at="2024-01-01T09:00:00"),
        make_tx("A", TransactionType.BUY, 100, 60.00, fee=10.00,
                created_at="2024-01-02T09:00:00"),
    ]
    engine = _engine(100000.0, txs)
    acc = engine._compute_positions_from_ledger(INVESTOR_ID, PORTFOLIO_ID)

    assert acc["A"]["quantity"] == pytest.approx(200.0)
    assert acc["A"]["avg_cost"] == pytest.approx(55.05)


# ---------------------------------------------------------------------------
# Case 3 — fee is None must not raise; treated as 0
# ---------------------------------------------------------------------------


def test_open_position_fee_none_does_not_raise_and_yields_cost_without_fee():
    """buy A 100@54.00 fee=None -> avg_cost == 54.00 (fee_val degrades to 0).

    The production Transaction model rejects ``fee=None``, so a duck-typed
    transaction is used.  Must not raise TypeError and must ignore the None fee.
    """
    tx = NoneFeeTx("A", TransactionType.BUY, 100, 54.00, fee=None,
                   created_at="2024-01-01T09:00:00")
    engine = _engine(100000.0, [tx])
    # must not raise
    acc = engine._compute_positions_from_ledger(INVESTOR_ID, PORTFOLIO_ID)

    assert "A" in acc
    assert acc["A"]["avg_cost"] == pytest.approx(54.00)


# ---------------------------------------------------------------------------
# Case 4 — fee is 0 must not raise and yields pure price basis
# ---------------------------------------------------------------------------


def test_open_position_fee_zero_does_not_raise_and_yields_cost_without_fee():
    """buy A 100@54.00 fee=0.0 -> avg_cost == 54.00, no crash."""
    tx = make_tx("A", TransactionType.BUY, 100, 54.00, fee=0.0,
                 created_at="2024-01-01T09:00:00")
    engine = _engine(100000.0, [tx])
    acc = engine._compute_positions_from_ledger(INVESTOR_ID, PORTFOLIO_ID)

    assert acc["A"]["avg_cost"] == pytest.approx(54.00)


# ---------------------------------------------------------------------------
# Case 5 — sell fee still flows into realized_pnl (must NOT be broken by fix)
# ---------------------------------------------------------------------------


def test_sell_fee_still_charged_in_realized_pnl():
    """Sell fee must reduce realized pnl (regression: ensure fix didn't amputate it).

    buy A 100@50.00 fee=0   -> avg_cost 50.00
    sell A 100@60.00 fee=10 -> realized = (60-50)*100 - 10 = 990.00
    """
    txs = [
        make_tx("A", TransactionType.BUY, 100, 50.00, fee=0.0,
                created_at="2024-01-01T09:00:00"),
        make_tx("A", TransactionType.SELL, 100, 60.00, fee=10.00,
                created_at="2024-01-02T09:00:00"),
    ]
    engine = _engine(100000.0, txs)
    acc = engine._compute_positions_from_ledger(INVESTOR_ID, PORTFOLIO_ID)

    assert acc["A"]["quantity"] == pytest.approx(0.0)
    assert acc["A"]["realized_pnl"] == pytest.approx(990.00)


# ---------------------------------------------------------------------------
# Case 6 — full async reconcile: fee in avg_cost AND accounting identity holds
# ---------------------------------------------------------------------------


def test_full_reconcile_buy_fee_in_avg_cost_and_accounting_identity():
    """Async reconcile: A's avg_cost carries the buy fee and the accounting
    identity total_assets == cash + market_value holds.

    Scenario: capital 100000, buy A 100@54.00 fee=3.00, current price 55.05.
      avg_cost A        = (0 + 100*54 + 3)/100 = 54.03
      cash_balance      = 100000 - (100*54 + 3) = 94597
      market_value A    = 100 * 55.05 = 5505
      total_assets      = 94597 + 5505 = 100102
    """
    tx = make_tx("A", TransactionType.BUY, 100, 54.00, fee=3.00,
                 created_at="2024-01-01T09:00:00")
    portfolio = _portfolio_with("A", "Stock A")
    config = FakeConfigLoader(100000.0, portfolio)
    data = FakeDataProvider({"A": {"price": 55.05, "change_percent": 0.0}})
    engine = ReconciliationEngine(config, data, ledger=FakeLedger([tx]))

    state = asyncio.run(engine.reconcile(INVESTOR_ID, PORTFOLIO_ID, dry_run=True))

    # accounting identity MUST hold (cash basis already includes the fee)
    assert state.total_assets == pytest.approx(
        state.cash.total_cash + state.total_market_value
    )

    # A's avg_cost carries the buy fee
    a_pos = next(p for p in state.positions if p.ticker == "A")
    assert a_pos.quantity == pytest.approx(100.0)
    assert a_pos.avg_cost == pytest.approx(54.03)
    assert a_pos.avg_cost != pytest.approx(54.00)  # regression guard for the fix

    # cash basis is consistent with the cost basis (both charge the buy fee)
    assert state.cash.total_cash == pytest.approx(94597.0)
    assert state.cash.available_cash == pytest.approx(94597.0)
    assert state.total_market_value == pytest.approx(5505.0)
    assert state.total_assets == pytest.approx(100102.0)
