"""E1.6 — 配置加载器测试"""
import pytest
from pathlib import Path

from praxis.engine.config_loader import YamlConfigLoader
from praxis.core.models.error import ConfigError


@pytest.fixture
def loader():
    return YamlConfigLoader("C:/Users/77271/Desktop/Portfolio vault")


class TestLoadInvestor:
    """加载投资者画像测试"""

    def test_load_example(self, loader):
        """加载示例投资者投资者画像"""
        investor = loader.load_investor("example")
        assert investor.name == "示例投资者"
        assert investor.id == "example"
        assert investor.capital_cny == 100000
        assert investor.risk_level == "C3"

    def test_load_investor_constraints(self, loader):
        """加载投资者约束"""
        investor = loader.load_investor("example")
        assert investor.constraints.etf_exemption is True
        assert len(investor.constraints.banned_markets) >= 1

    def test_load_investor_execution(self, loader):
        """加载执行配置"""
        investor = loader.load_investor("example")
        assert investor.execution.min_transaction_cny == 3000
        assert investor.execution.offshore_fund_window == "14:45-14:55"

    def test_load_nonexistent_investor(self, loader):
        """加载不存在的投资者"""
        with pytest.raises(ConfigError):
            loader.load_investor("nonexistent")


class TestLoadPortfolio:
    """加载投资组合测试"""

    def test_load_demo(self, loader):
        """加载示例组合"""
        portfolio = loader.load_portfolio("example", "demo")
        assert portfolio.strategy_type == "grid_value"
        assert portfolio.version == "v1.0"
        assert portfolio.description is not None

    def test_load_portfolio_assets(self, loader):
        """加载组合资产"""
        portfolio = loader.load_portfolio("example", "demo")
        assert len(portfolio.assets) == 3
        tickers = [a.ticker for a in portfolio.assets]
        assert "ETF_300" in tickers
        assert "ETF_500" in tickers
        assert "STOCK_A" in tickers
        # 验证新模型字段
        for asset in portfolio.assets:
            assert asset.grid is not None
            assert len(asset.grid) > 0

    def test_load_portfolio_sentinels(self, loader):
        """加载哨兵配置"""
        portfolio = loader.load_portfolio("example", "demo")
        assert len(portfolio.sentinels.macro_layer) == 1
        assert len(portfolio.sentinels.execution_layer) == 1
        assert portfolio.sentinels.execution_layer[0].blocks == "ETF_500"

    def test_load_nonexistent_portfolio(self, loader):
        """加载不存在的组合"""
        with pytest.raises(ConfigError):
            loader.load_portfolio("example", "nonexistent")


class TestLoadStrategy:
    """加载策略模板测试"""

    def test_load_grid_value(self, loader):
        """加载网格价值策略"""
        strategy = loader.load_strategy("grid_value")
        assert strategy.name == "网格价值策略"
        assert len(strategy.rules) > 0

    def test_load_strategy_rules(self, loader):
        """加载策略规则"""
        strategy = loader.load_strategy("grid_value")
        rule_names = [r.rule for r in strategy.rules]
        assert "time_rules.offshore_fund_window" in rule_names
        assert "risk_rules.cash_floor" in rule_names

    def test_load_strategy_ai_teams(self, loader):
        """加载 AI 团队配置"""
        strategy = loader.load_strategy("grid_value")
        assert len(strategy.ai_teams.asrg.emphasis) > 0
        assert len(strategy.ai_teams.masters.emphasis) > 0
        assert len(strategy.ai_teams.trading.emphasis) > 0

    def test_load_strategy_evolution_dimensions(self, loader):
        """加载进化维度"""
        strategy = loader.load_strategy("grid_value")
        assert len(strategy.evolution_dimensions) == 4
        dim_names = [d.name for d in strategy.evolution_dimensions]
        assert "grid_spacing" in dim_names
        assert "stop_loss_tightness" in dim_names

    def test_load_nonexistent_strategy(self, loader):
        """加载不存在的策略"""
        with pytest.raises(ConfigError):
            loader.load_strategy("nonexistent")


class TestListPortfolios:
    """列出组合测试"""

    def test_list_portfolios(self, loader):
        """列出投资者的所有组合"""
        portfolios = loader.list_portfolios("example")
        assert "demo" in portfolios
