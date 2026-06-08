"""E1.5 — 约束检查器测试"""
import pytest

from praxis.engine.constraint_checker import SimpleConstraintChecker
from praxis.core.models.investor import InvestorProfile, InvestorConstraints, ExecutionConfig
from praxis.core.models.portfolio import Portfolio, AssetEntry
from praxis.core.models.asset import AssetType, AssetCategory
from praxis.core.models.state import PortfolioState, CashState
from praxis.core.models.strategy import StrategyTemplate, RuleEntry


@pytest.fixture
def investor():
    return InvestorProfile(
        name="测试投资者",
        id="test",
        capital_cny=70000,
        risk_level="C3-C4",
        style="balanced",
        constraints=InvestorConstraints(
            banned_instruments=["leverage", "options", "short"],
            etf_exemption=True,
        ),
        execution=ExecutionConfig(
            min_transaction_cny=3000,
        ),
    )


@pytest.fixture
def portfolio():
    return Portfolio(
        strategy_type="grid_value",
        strategy_template="grid_value",
        created_at="2026-05-18",
        version="v9.0",
        assets=[
            AssetEntry(
                ticker="600995",
                name="南网储能",
                type=AssetType.STOCK,
                category=AssetCategory.POWER_INFRA,
                target_weight_pct=12,
            ),
        ],
    )


@pytest.fixture
def strategy():
    """策略模板（包含禁入板块规则）"""
    return StrategyTemplate(
        name="grid_value",
        description="测试策略",
        rules=[
            RuleEntry(
                rule="access_rules.blacklist_market",
                params={"markets": ["star_market", "chinext"], "etf_exempt": True},
            ),
            RuleEntry(
                rule="access_rules.blacklist_instrument",
                params={"instruments": ["leverage", "options", "short"]},
            ),
            RuleEntry(
                rule="execution_rules.min_transaction",
                params={"min_amount_cny": 3000},
            ),
            RuleEntry(
                rule="risk_rules.cash_floor",
                params={"min_pct": 40},
            ),
            RuleEntry(
                rule="risk_rules.position_cap",
                params={"max_single_pct": 15},
            ),
        ],
    )


@pytest.fixture
def state():
    return PortfolioState(
        investor_id="test",
        portfolio_id="test",
        cash=CashState(
            total_assets=70000,
            available_cash=65000,
            cash_ratio=0.93,
        ),
    )


@pytest.fixture
def checker(investor, portfolio, strategy):
    return SimpleConstraintChecker(investor, portfolio, strategy=strategy)


class TestBannedMarket:
    """禁入板块测试"""

    def test_star_market_blocked(self, checker, state):
        """科创板股票被阻止"""
        results = checker.check(state, "buy", "688001", amount=3000)
        market_check = next(r for r in results if r["rule"] == "access_rules.blacklist_market")
        assert market_check["passed"] is False
        assert market_check["level"] == "hard_block"

    def test_chinext_blocked(self, checker, state):
        """创业板股票被阻止"""
        results = checker.check(state, "buy", "300001", amount=3000)
        market_check = next(r for r in results if r["rule"] == "access_rules.blacklist_market")
        assert market_check["passed"] is False

    def test_normal_stock_allowed(self, checker, state):
        """正常股票允许"""
        results = checker.check(state, "buy", "600995", amount=3000)
        market_check = next(r for r in results if r["rule"] == "access_rules.blacklist_market")
        assert market_check["passed"] is True

    def test_etf_exemption(self, checker, state):
        """ETF 豁免板块禁令"""
        results = checker.check(state, "buy", "589850", amount=3000)
        market_check = next(r for r in results if r["rule"] == "access_rules.blacklist_market")
        assert market_check["passed"] is True


class TestMinTransaction:
    """最小交易金额测试"""

    def test_below_minimum(self, checker, state):
        """低于最小金额"""
        results = checker.check(state, "buy", "600995", amount=2000)
        min_check = next(r for r in results if r["rule"] == "execution_rules.min_transaction")
        assert min_check["passed"] is False
        assert min_check["level"] == "hard_block"

    def test_at_minimum(self, checker, state):
        """等于最小金额"""
        results = checker.check(state, "buy", "600995", amount=3000)
        min_check = next(r for r in results if r["rule"] == "execution_rules.min_transaction")
        assert min_check["passed"] is True

    def test_above_minimum(self, checker, state):
        """高于最小金额"""
        results = checker.check(state, "buy", "600995", amount=5000)
        min_check = next(r for r in results if r["rule"] == "execution_rules.min_transaction")
        assert min_check["passed"] is True

    def test_sell_no_minimum(self, checker, state):
        """卖出不检查最小金额"""
        results = checker.check(state, "sell", "600995", amount=0)
        # 卖出不应该检查最小金额
        min_checks = [r for r in results if r["rule"] == "execution_rules.min_transaction"]
        assert len(min_checks) == 0


class TestCashFloor:
    """现金底线测试"""

    def test_cash_floor_pass(self, checker, state):
        """现金充足"""
        results = checker.check(state, "buy", "600995", amount=3000)
        cash_check = next(r for r in results if r["rule"] == "risk_rules.cash_floor")
        assert cash_check["passed"] is True

    def test_cash_floor_fail(self, checker):
        """现金不足"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(
                total_assets=70000,
                available_cash=20000,
                cash_ratio=0.29,
            ),
        )
        results = checker.check(state, "buy", "600995", amount=5000)
        cash_check = next(r for r in results if r["rule"] == "risk_rules.cash_floor")
        assert cash_check["passed"] is False
        assert cash_check["level"] == "hard_block"
