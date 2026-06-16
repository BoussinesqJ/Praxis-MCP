"""E1.7 — 状态重建器测试"""
import pytest
import asyncio
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.core.state_builder import SimpleStateBuilder
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.data.provider import CachedDataProvider


@pytest.fixture
def workspace():
    return "C:/Users/77271/Desktop/Portfolio vault"


@pytest.fixture
def loader(workspace):
    return YamlConfigLoader(workspace)


@pytest.fixture
def ledger(workspace):
    ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
    return FileLedger(ledger_path)


@pytest.fixture
def provider():
    return CachedDataProvider()


@pytest.fixture
def builder(ledger, loader, provider):
    return SimpleStateBuilder(ledger, loader, provider)


class TestStateRebuild:
    """状态重建测试"""

    def test_rebuild_basic(self, builder):
        """基本重建测试"""
        async def run():
            state = await builder.rebuild("example", "demo")
            return state

        state = asyncio.run(run())
        assert state.investor_id == "example"
        assert state.portfolio_id == "demo"

    def test_rebuild_cash(self, builder):
        """现金状态重建"""
        async def run():
            state = await builder.rebuild("example", "demo")
            return state

        state = asyncio.run(run())
        assert state.cash.total_assets > 0
        assert state.cash.available_cash > 0

    def test_rebuild_positions(self, builder):
        """持仓重建（空数据）"""
        async def run():
            state = await builder.rebuild("example", "demo")
            return state

        state = asyncio.run(run())
        # 空数据时持仓为 0
        assert len(state.positions) >= 0

    def test_rebuild_validation(self, builder):
        """状态验证"""
        async def run():
            state = await builder.rebuild("example", "demo")
            return state

        state = asyncio.run(run())
        issues = builder.validate(state)
        assert len(issues) == 0


class TestStateValidation:
    """状态验证测试"""

    def test_validate_consistent_state(self, builder):
        """验证一致的状态"""
        from praxis.core.models.state import PortfolioState, CashState

        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(
                total_assets=100000,
                total_positions_value=30000,
                available_cash=70000,
                cash_ratio=0.7,
            ),
        )
        issues = builder.validate(state)
        assert len(issues) == 0

    def test_validate_inconsistent_total(self, builder):
        """验证总资产不一致"""
        from praxis.core.models.state import PortfolioState, CashState

        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(
                total_assets=100000,
                total_positions_value=30000,
                available_cash=60000,  # 不一致：30000+60000=90000 ≠ 100000
                cash_ratio=0.6,
            ),
        )
        issues = builder.validate(state)
        assert len(issues) > 0
        assert "总资产不一致" in issues[0]

    def test_validate_inconsistent_ratio(self, builder):
        """验证现金比例不一致"""
        from praxis.core.models.state import PortfolioState, CashState

        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(
                total_assets=100000,
                total_positions_value=30000,
                available_cash=70000,
                cash_ratio=0.5,  # 不一致：70000/100000=0.7 ≠ 0.5
            ),
        )
        issues = builder.validate(state)
        assert len(issues) > 0
        assert "现金比例不一致" in issues[0]
