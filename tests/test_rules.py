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
from praxis_sdk.core.rule_engine import PortfolioParser


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
        results = checker.check(state, "buy", "000001", amount=5000)
        cash_results = [r for r in results if r["rule"] == "risk_rules.cash_floor"]
        assert all(r["passed"] for r in cash_results)

    def test_cash_floor_block(self, checker):
        """现金不足应阻止"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=20000, cash_ratio=0.20),
        )
        results = checker.check(state, "buy", "000001", amount=5000)
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
        results = checker.check(state, "buy", "510050", amount=5000)
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
        results = checker.check(state, "buy", "000001", amount=5000)
        min_results = [r for r in results if r["rule"] == "execution_rules.min_transaction"]
        assert all(r["passed"] for r in min_results)

    def test_min_transaction_block(self, checker):
        """金额不足应阻止"""
        state = PortfolioState(
            investor_id="test",
            portfolio_id="test",
            cash=CashState(total_assets=100000, available_cash=50000, cash_ratio=0.50),
        )
        results = checker.check(state, "buy", "000001", amount=2000)
        min_results = [r for r in results if r["rule"] == "execution_rules.min_transaction"]
        assert any(not r["passed"] for r in min_results)


class TestPortfolioParser:
    """PortfolioParser — 按 agy spec 重构后的解析测试"""

    def test_full_parse_real_holdings_and_water_level(self, tmp_path):
        """
        模拟完整 project.md（持仓表 + FUNDS_DISTRIBUTION），验证：
        - 真实持仓正确解析（3 只标的，代码、数量、成本正确）
        - positions_value 来自"现有持仓市值"行
        - total_assets 来自"**合计**"行
        - cash = total_assets - positions_value
        - 没有 budget 字段
        """
        md_content = """# Praxis 个人投资管理计划

## ⚖️ Praxis 核心资产配置

### 持仓（防守姿态）

| 标的 | 数量 | 成本 | 现价 | 市值 | 盈亏 | 止损 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| 000001 平安银行 | 500股 | 12.00 | 12.50 | ¥6,250 | +4.17% | 11.40 (-5%) |
| 600000 浦发银行 | 300股 | 8.50 | 8.75 | ¥2,625 | +2.94% | 8.08 (-5%) |
| 510050 上证50ETF | 1000份 | 3.50 | 3.60 | ¥3,600 | +2.86% | 3.33 (-5%) |

### 观察池（不持仓）

| 标的 | 现价 | 观察买入位 | 积极买入位 | 备注 |
|:---|:---:|:---:|:---:|:---|
| 600000 浦发银行 | 10.50 | 9.80 | 10.20 | 观察中 |

---

<!-- FUNDS_DISTRIBUTION_START -->
| 项目 | 金额 | 占比 | 状态 |
|------|------|:----:|:----:|
| 现有持仓市值 | 12,475.00 | 17.6% | ✅ 测试 |
| 浦发银行动态网格 (600000) | 10,000.00 | 14.1% | 👁️ 测试 |
| 上证50 ETF 伏击预算 (510050) | 5,000.00 | 7.0% | 👀 测试 |
| 示例科技伏击预算 (000001) | 5,000.00 | 7.0% | 👀 测试 |
| 示例建仓预算 (000002) | 3,000.00 | 4.2% | 🎯 测试 |
| 纯闲置现金 (未分配储备) | 32,811.13 | 46.3% | 💵 测试 |
| **合计** | **71,000.00** | **100%** | 测试 |
<!-- FUNDS_DISTRIBUTION_END -->
"""
        md_file = tmp_path / "project.md"
        md_file.write_text(md_content, encoding="utf-8")

        parser = PortfolioParser(str(md_file))
        data = parser.parse()

        # --- 资金水位 ---
        assert data["positions_value"] == 12475.00, (
            f"positions_value 应为 12475.00，实际 {data['positions_value']}"
        )
        assert data["total_assets"] == 71000.00, (
            f"total_assets 应为 71000.00，实际 {data['total_assets']}"
        )
        expected_cash = 71000.00 - 12475.00
        assert data["cash"] == expected_cash, (
            f"cash 应为 {expected_cash}，实际 {data['cash']}"
        )
        assert abs(data["position_pct"] - 17.57) < 0.1, (
            f"position_pct 应约 17.6%，实际 {data['position_pct']}%"
        )

        # --- 没有 budget 字段 ---
        assert "budget" not in data, "不应再返回 budget 字段"

        # --- 真实持仓 ---
        assert len(data["positions"]) == 3, (
            f"应解析出 3 个持仓，实际 {len(data['positions'])}"
        )

        # 按 ticker 索引
        pos_by_ticker = {p.ticker: p for p in data["positions"]}

        # 000001 平安银行
        p = pos_by_ticker.get("000001")
        assert p is not None, "缺少 000001 平安银行"
        assert p.name == "平安银行"
        assert p.quantity == 500
        assert abs(p.avg_cost - 12.00) < 0.001
        assert abs(p.market_value - 6250) < 1

        # 600000 浦发银行
        p = pos_by_ticker.get("600000")
        assert p is not None, "缺少 600000 浦发银行"
        assert p.name == "浦发银行"
        assert p.quantity == 300
        assert abs(p.avg_cost - 8.50) < 0.001

        # 510050 上证50ETF
        p = pos_by_ticker.get("510050")
        assert p is not None, "缺少 510050 上证50ETF"
        assert p.name == "上证50ETF"
        assert p.quantity == 1000
        assert abs(p.avg_cost - 3.50) < 0.001
        # ETF 类型检测
        assert p.asset_type == "etf"

    def test_default_data_no_budget(self):
        """验证 _default_data 不再包含 budget 字段"""
        parser = PortfolioParser("/nonexistent/path.md")
        data = parser.parse()
        assert "budget" not in data
        assert data["total_assets"] == 70000
        assert data["positions_value"] == 7000
        assert data["cash"] == 63000
        assert data["position_pct"] == 10.0
