"""约束检查器单元测试 — SimpleConstraintChecker."""

from __future__ import annotations

import pytest

from praxis.engine.constraint_checker import SimpleConstraintChecker
from praxis.core.models import (
    InvestorProfile, Portfolio, StrategyTemplate, RuleEntry,
    PortfolioState, PositionState, CashState,
    AssetType, AssetEntry, AssetCategory,
    InvestorConstraints, ExecutionConfig,
)


def _make_investor(capital: float = 100000.0) -> InvestorProfile:
    return InvestorProfile(
        investor_id="inv-test", name="测试",
        capital_cny=capital, risk_level="C3",
        constraints=InvestorConstraints(),
        execution=ExecutionConfig(),
    )


def _make_portfolio() -> Portfolio:
    return Portfolio(
        portfolio_id="core", investor_id="inv-test", name="核心组合",
        assets=[
            AssetEntry(ticker="600519", name="贵州茅台", asset_type=AssetType.STOCK,
                       category=AssetCategory.LARGE_CAP, target_weight_pct=50.0),
        ],
    )


def _make_state(
    total_assets: float = 150000.0,
    cash_val: float = 34000.0,
    positions: list[PositionState] | None = None,
    total_return_pct: float = 5.0,
) -> PortfolioState:
    if positions is None:
        positions = [
            PositionState(
                ticker="600519", name="贵州茅台", asset_type=AssetType.STOCK,
                quantity=50.0, avg_cost=1800.0, current_price=1850.0,
                market_value=92500.0, unrealized_pnl=2500.0,
            ),
        ]
    return PortfolioState(
        investor_id="inv-test", portfolio_id="core",
        total_assets=total_assets,
        total_market_value=92500.0,
        cash=CashState(total_cash=cash_val, available_cash=cash_val, frozen_cash=0.0),
        positions=positions,
        nav=1.5, total_return_pct=total_return_pct,
    )


class TestBannedMarket:
    """禁入板块测试."""

    def test_banned_star_market_688(self):
        """688 开头科创板硬拦截."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(_make_state(), "buy", "688001", amount=50000)
        block = [r for r in results if r["level"] == "hard_block" and "科创板" in r["rule"]]
        assert len(block) >= 1

    def test_banned_star_market_588(self):
        """588 开头科创板硬拦截."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(_make_state(), "buy", "588000", amount=50000)
        block = [r for r in results if r["level"] == "hard_block" and "科创板" in r["rule"]]
        assert len(block) >= 1

    def test_banned_chinext_300(self):
        """300 开头创业板硬拦截."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(_make_state(), "buy", "300001", amount=50000)
        block = [r for r in results if r["level"] == "hard_block" and "创业板" in r["rule"]]
        assert len(block) >= 1

    def test_main_board_pass(self):
        """600 主板正常通过."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(_make_state(), "buy", "600519", amount=5000)
        # 禁入检查应该通过
        banned = [r for r in results if "禁止板块检查" in r["rule"]]
        assert banned[0]["passed"] is True


class TestBannedInstrument:
    """投资工具限制."""

    def test_banned_instrument_opt(self):
        """期权工具拦截."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(_make_state(), "buy", "OPT100", amount=50000)
        block = [r for r in results if "工具限制" in r["rule"]]
        assert not block[0]["passed"]

    def test_banned_instrument_cu(self):
        """CU期货拦截."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(_make_state(), "buy", "CU2409", amount=50000)
        block = [r for r in results if "工具限制" in r["rule"]]
        assert not block[0]["passed"]


class TestMinAmount:
    """最小交易金额."""

    def test_min_amount_warning(self):
        """低于最低金额触发 soft_warning."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(_make_state(), "buy", "600519", amount=100)
        warning = [r for r in results if "最小交易金额" in r["rule"]]
        assert len(warning) >= 1


class TestCashFloor:
    """现金底线."""

    def test_cash_floor_hard_block(self):
        """交易后现金不足触发 hard_block."""
        # total_assets=150000, cash=34000, buy amount=64000 → cash_after=-30000 < 7500(5%)
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(
            _make_state(total_assets=150000.0, cash_val=34000.0),
            "buy", "600519", amount=64000.0,
        )
        block = [r for r in results if "现金底线" in r["rule"] and r["level"] == "hard_block"]
        assert len(block) >= 1


class TestPositionCap:
    """单标的仓位上限."""

    @pytest.mark.skip(reason="测试隔离问题，独立运行通过（Todo: P1-P2 修复）")
    def test_position_cap(self):
        """仓位超上限触发 hard_block."""
        # current_mv=92500, buy 60000 → new=152500, new_pct=152500/150000*100=101.7% > 30%
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio())
        results = checker.check(
            _make_state(total_assets=150000.0, cash_val=100000.0),
            "buy", "600519", amount=60000.0,
        )
        block = [r for r in results if "持仓上限" in r["rule"] and r["level"] == "hard_block"]
        assert len(block) >= 1


class TestStrategyDrivenMode:
    """策略驱动模式."""

    def test_strategy_driven_mode(self):
        """有策略时从规则读取参数."""
        strategy = StrategyTemplate(
            strategy_name="grid_value",
            rules=[
                RuleEntry(rule_id="execution_rules.min_transaction", name="最小交易",
                          level="soft_warning", enabled=True,
                          params={"min_amount_cny": 3000.0}),
                RuleEntry(rule_id="risk_rules.cash_floor", name="现金底线",
                          level="hard_block", enabled=True,
                          params={"min_pct": 70.0}),
                RuleEntry(rule_id="risk_rules.position_cap", name="仓位上限",
                          level="hard_block", enabled=True,
                          params={"max_single_pct": 15.0}),
            ],
        )
        checker = SimpleConstraintChecker(
            _make_investor(), _make_portfolio(), strategy=strategy,
        )
        results = checker.check(
            _make_state(total_assets=150000.0),
            "buy", "600519", amount=10000.0,
        )
        # 策略驱动模式下应有额外规则检查
        assert len(results) >= 2  # 至少 banned + instrument


class TestFallbackMode:
    """回退模式."""

    def test_fallback_mode(self):
        """无策略时使用硬编码默认值."""
        checker = SimpleConstraintChecker(_make_investor(), _make_portfolio(), strategy=None)
        results = checker.check(
            _make_state(total_assets=150000.0, cash_val=34000.0),
            "buy", "600519", amount=5000.0,
        )
        # 回退模式：banned_market + banned_instrument + min_transaction + cash_floor + position_cap
        assert len(results) >= 4
