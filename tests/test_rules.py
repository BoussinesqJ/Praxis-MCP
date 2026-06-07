"""E3.1 — 规则测试用例"""
import pytest

from praxis.core.models.rule import (
    RuleLevel, RuleDefinition, PREDEFINED_RULES
)
from praxis.engine.constraint_checker import SimpleConstraintChecker
from praxis.core.models.investor import InvestorProfile, InvestorConstraints, ExecutionConfig
from praxis.core.models.portfolio import Portfolio, AssetEntry
from praxis.core.models.asset import AssetType, AssetCategory
from praxis.core.models.state import PortfolioState, CashState


class TestRuleSchema:
    """规则 Schema 测试"""

    def test_rule_definition(self):
        """规则定义测试"""
        rule = RuleDefinition(
            rule_id="test.rule",
            name="测试规则",
            description="测试用规则",
            level=RuleLevel.HARD_BLOCK,
        )
        assert rule.rule_id == "test.rule"
        assert rule.level == RuleLevel.HARD_BLOCK
        assert rule.default_enabled is True

    def test_predefined_rules_count(self):
        """预定义规则数量"""
        assert len(PREDEFINED_RULES) >= 5

    def test_predefined_rule_cash_floor(self):
        """现金底线规则"""
        rule = PREDEFINED_RULES["risk.cash_floor"]
        assert rule.level == RuleLevel.HARD_BLOCK
        assert rule.params["min_cash_ratio"] == 0.40
        assert len(rule.test_cases) >= 2

    def test_predefined_rule_position_cap(self):
        """持仓上限规则"""
        rule = PREDEFINED_RULES["risk.position_cap"]
        assert rule.level == RuleLevel.HARD_BLOCK
        assert rule.params["max_single_pct"] == 0.15

    def test_predefined_rule_banned_market(self):
        """禁入板块规则"""
        rule = PREDEFINED_RULES["access.banned_market"]
        assert rule.level == RuleLevel.HARD_INVARIANT
        assert rule.can_disable is False
        assert "star_market" in rule.params["banned_markets"]


class TestRuleLevels:
    """规则级别测试"""

    def test_hard_invariant(self):
        """硬不变量"""
        assert RuleLevel.HARD_INVARIANT == "hard_invariant"

    def test_hard_block(self):
        """硬阻止"""
        assert RuleLevel.HARD_BLOCK == "hard_block"

    def test_soft_warning(self):
        """软警告"""
        assert RuleLevel.SOFT_WARNING == "soft_warning"

    def test_advisory(self):
        """建议"""
        assert RuleLevel.ADVISORY == "advisory"


class TestCashFloorRule:
    """现金底线规则测试"""

    @pytest.fixture
    def checker(self):
        investor = InvestorProfile(
            name="测试",
            id="test",
            capital_cny=100000,
            risk_level="C3",
            style="balanced",
            constraints=InvestorConstraints(etf_exemption=True),
            execution=ExecutionConfig(min_transaction_cny=3000),
        )
        portfolio = Portfolio(
            strategy_type="grid_value",
            strategy_template="grid_value",
            created_at="2026-01-01",
            version="v1",
        )
        return SimpleConstraintChecker(investor, portfolio)

    def test_cash_floor_pass(self, checker):
        """现金充足应通过"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=50000, cash_ratio=0.50),
        )
        results = checker.check(state, "buy", "600995", amount=5000)
        cash_results = [r for r in results if r["rule"] == "risk_rules.cash_floor"]
        assert all(r["passed"] for r in cash_results)

    def test_cash_floor_block(self, checker):
        """现金不足应阻止"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=20000, cash_ratio=0.20),
        )
        results = checker.check(state, "buy", "600995", amount=5000)
        cash_results = [r for r in results if r["rule"] == "risk_rules.cash_floor"]
        assert any(not r["passed"] for r in cash_results)


class TestBannedMarketRule:
    """禁入板块规则测试"""

    @pytest.fixture
    def checker(self):
        investor = InvestorProfile(
            name="测试",
            id="test",
            capital_cny=100000,
            risk_level="C3",
            style="balanced",
            constraints=InvestorConstraints(
                banned_markets=[
                    {"id": "star_market", "desc": "科创板"},
                    {"id": "chinext", "desc": "创业板"},
                ],
                etf_exemption=True,
            ),
        )
        portfolio = Portfolio(
            strategy_type="grid_value",
            strategy_template="grid_value",
            created_at="2026-01-01",
            version="v1",
        )
        return SimpleConstraintChecker(investor, portfolio)

    def test_star_market_stock_blocked(self, checker):
        """科创板股票应阻止"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=50000, cash_ratio=0.50),
        )
        results = checker.check(state, "buy", "688001", amount=5000)
        market_results = [r for r in results if r["rule"] == "access_rules.blacklist_market"]
        assert any(not r["passed"] for r in market_results)

    def test_star_market_etf_pass(self, checker):
        """科创板ETF应通过"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=50000, cash_ratio=0.50),
        )
        results = checker.check(state, "buy", "589850", amount=5000)
        market_results = [r for r in results if r["rule"] == "access_rules.blacklist_market"]
        assert all(r["passed"] for r in market_results)


class TestMinTransactionRule:
    """最小交易金额规则测试"""

    @pytest.fixture
    def checker(self):
        investor = InvestorProfile(
            name="测试",
            id="test",
            capital_cny=100000,
            risk_level="C3",
            style="balanced",
            execution=ExecutionConfig(min_transaction_cny=3000),
        )
        portfolio = Portfolio(
            strategy_type="grid_value",
            strategy_template="grid_value",
            created_at="2026-01-01",
            version="v1",
        )
        return SimpleConstraintChecker(investor, portfolio)

    def test_min_transaction_pass(self, checker):
        """金额充足应通过"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=50000, cash_ratio=0.50),
        )
        results = checker.check(state, "buy", "600995", amount=5000)
        min_results = [r for r in results if r["rule"] == "execution_rules.min_transaction"]
        assert all(r["passed"] for r in min_results)

    def test_min_transaction_block(self, checker):
        """金额不足应阻止"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=50000, cash_ratio=0.50),
        )
        results = checker.check(state, "buy", "600995", amount=2000)
        min_results = [r for r in results if r["rule"] == "execution_rules.min_transaction"]
        assert any(not r["passed"] for r in min_results)
