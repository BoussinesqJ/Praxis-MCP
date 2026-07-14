"""状态重建器单元测试 — LedgerStateBuilder rebuild + validate."""

from __future__ import annotations

import pytest

from praxis.engine.state_builder import LedgerStateBuilder
from praxis.engine.tests.conftest import FakeDataProvider, FakeConfigLoader, FakeLedger
from praxis.core.models import (
    Transaction, TransactionType, TransactionStatus, AssetType,
    PortfolioState, PositionState, CashState,
    AssetEntry, AssetCategory,
)


def _make_tx(
    ticker: str, tx_type: TransactionType, quantity: float, price: float,
    fee: float = 0.0, created_at: str = "2024-06-01T10:00:00",
) -> Transaction:
    return Transaction(
        investor_id="inv-test", portfolio_id="core",
        ticker=ticker, tx_type=tx_type,
        quantity=quantity, price=price, fee=fee,
        asset_type=AssetType.STOCK,
        status=TransactionStatus.EXECUTED,
        created_at=created_at,
    )


class TestPureCash:
    """纯现金状态."""

    @pytest.mark.asyncio
    async def test_pure_cash(self):
        """无任何交易时状态为纯现金."""
        config = FakeConfigLoader()
        ledger = FakeLedger([])
        data = FakeDataProvider()
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)

        state = await builder.rebuild("inv-test", "core")
        assert isinstance(state, PortfolioState)
        assert state.total_assets == 100000.0
        assert state.cash.total_cash == 100000.0
        assert state.total_market_value == 0.0
        assert len(state.positions) == 0


class TestSingleBuy:
    """单次买入."""

    @pytest.mark.asyncio
    async def test_single_buy_unrealized_pnl(self):
        """单次买入 + unrealized_pnl 计算."""
        config = FakeConfigLoader()
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 50.0, 1800.0, fee=5.0),
        ])
        data = FakeDataProvider(quotes={
            "600519": {"price": 1850.0},
        })
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)

        state = await builder.rebuild("inv-test", "core")
        assert len(state.positions) == 1
        pos = state.positions[0]
        assert pos.ticker == "600519"
        assert pos.quantity == 50.0
        # avg_cost = (1800*50 + 5) / 50 = 1800.1
        assert pos.avg_cost == pytest.approx(1800.1, rel=1e-4)
        assert pos.current_price == 1850.0
        assert pos.unrealized_pnl > 0


class TestBuySellMovingAvg:
    """买卖移动加权."""

    @pytest.mark.asyncio
    async def test_buy_sell_moving_average(self):
        """买卖移动加权平均 — 卖出减少成本基数."""
        config = FakeConfigLoader()
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 100.0, 1800.0, fee=10.0, created_at="2024-06-01T10:00:00"),
            _make_tx("600519", TransactionType.SELL, 30.0, 1900.0, fee=5.0, created_at="2024-06-02T10:00:00"),
        ])
        data = FakeDataProvider(quotes={"600519": {"price": 1850.0}})
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)

        state = await builder.rebuild("inv-test", "core")
        assert len(state.positions) == 1
        pos = state.positions[0]
        assert pos.ticker == "600519"
        assert pos.quantity == 70.0
        # avg = (1800*100+10)/100 = 1800.1, sell 30 at avg → cost=(1800.1)*70
        assert pos.avg_cost == pytest.approx(1800.1, rel=1e-4)


class TestCostWithFee:
    """含 fee 成本."""

    @pytest.mark.asyncio
    async def test_cost_with_fee(self):
        """买入手续费计入成本."""
        config = FakeConfigLoader()
        # buy 50@1800 fee=30 → cost=1800*50+30=90030, avg=90030/50=1800.6
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 50.0, 1800.0, fee=30.0),
        ])
        data = FakeDataProvider(quotes={"600519": {"price": 1800.0}})
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)

        state = await builder.rebuild("inv-test", "core")
        pos = state.positions[0]
        assert pos.avg_cost == pytest.approx(1800.6, rel=1e-4)


class TestPriceFallback:
    """行情缺失回退."""

    @pytest.mark.asyncio
    async def test_price_fallback(self):
        """行情缺失时回退到 avg_cost."""
        config = FakeConfigLoader()
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 50.0, 1800.0),
        ])
        data = FakeDataProvider(quotes={})  # 无行情
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)

        state = await builder.rebuild("inv-test", "core")
        pos = state.positions[0]
        assert pos.current_price == pos.avg_cost
        assert pos.unrealized_pnl == 0.0


class TestValidate:
    """validate 验证."""

    def test_validate_asset_balance(self):
        """资产平衡检测."""
        state = PortfolioState(
            investor_id="inv-test", portfolio_id="core",
            total_assets=100000.0, total_market_value=50000.0,
            cash=CashState(total_cash=49000.0, available_cash=49000.0, frozen_cash=0.0),
            positions=[], nav=1.0,
        )
        config = FakeConfigLoader()
        ledger = FakeLedger([])
        data = FakeDataProvider()
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)
        issues = builder.validate(state)
        # cash(49000) + mv(50000) = 99000 != total_assets(100000): 差值 1000 > 1.0
        assert len(issues) >= 1
        assert "不平" in issues[0]

    def test_validate_position_anomaly(self):
        """持仓数量异常检测."""
        state = PortfolioState(
            investor_id="inv-test", portfolio_id="core",
            total_assets=100000.0, total_market_value=0.0,
            cash=CashState(total_cash=100000.0, available_cash=100000.0, frozen_cash=0.0),
            positions=[
                PositionState(
                    ticker="600519", name="贵州茅台", asset_type=AssetType.STOCK,
                    quantity=0.0, avg_cost=1800.0, current_price=1850.0,
                    market_value=0.0, unrealized_pnl=0.0,
                ),
            ],
            nav=1.0,
        )
        config = FakeConfigLoader()
        ledger = FakeLedger([])
        data = FakeDataProvider()
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)
        issues = builder.validate(state)
        assert len(issues) >= 1
        assert any("异常" in i for i in issues)


class TestMultiTicker:
    """多 ticker."""

    @pytest.mark.asyncio
    async def test_multi_ticker_weights(self):
        """多 ticker + 权重计算."""
        config = FakeConfigLoader()
        ledger = FakeLedger([
            _make_tx("600519", TransactionType.BUY, 50.0, 1800.0, created_at="2024-06-01T10:00:00"),
            _make_tx("159915", TransactionType.BUY, 10000.0, 2.30, created_at="2024-06-02T10:00:00"),
        ])
        data = FakeDataProvider(quotes={
            "600519": {"price": 1850.0},
            "159915": {"price": 2.35},
        })
        builder = LedgerStateBuilder(data_provider=data, ledger=ledger, config_loader=config)

        state = await builder.rebuild("inv-test", "core")
        assert len(state.positions) == 2
        for pos in state.positions:
            assert pos.weight_pct > 0
        total_weight = sum(p.weight_pct for p in state.positions)
        assert 0 < total_weight <= 200  # positions exist and have weights
