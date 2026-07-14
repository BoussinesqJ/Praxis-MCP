"""配置加载器单元测试 — YamlConfigLoader + _check_config_id."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from praxis.engine.config_loader import YamlConfigLoader, _check_config_id
from praxis.core.exceptions import ConfigError
from praxis.core.models import (
    InvestorProfile, Portfolio, StrategyTemplate, AssetEntry, AssetType,
    SentinelEntry,
)


class TestCheckConfigId:
    """_check_config_id 安全校验."""

    def test_check_config_id_valid(self):
        """合法ID通过."""
        _check_config_id("investor_id", "test_investor")
        _check_config_id("strategy_name", "grid_value_v2")

    def test_check_config_id_path_traversal(self):
        """路径遍历拒绝 — 注意 _check_config_id 先检测非法字符."""
        with pytest.raises(ConfigError, match="非法字符"):
            _check_config_id("investor_id", "../../etc/passwd")

    def test_check_config_id_special_chars(self):
        """特殊字符拒绝."""
        with pytest.raises(ConfigError, match="非法字符"):
            _check_config_id("strategy_name", "evil/strategy")

    def test_check_config_id_empty(self):
        """空字符串拒绝."""
        with pytest.raises(ConfigError, match="不能为空"):
            _check_config_id("investor_id", "")


class TestLoadInvestor:
    """load_investor 测试."""

    def test_load_investor_basic(self, tmp_path):
        """基础加载 + id→investor_id 映射."""
        inv_dir = tmp_path / "config" / "investors" / "test_investor"
        inv_dir.mkdir(parents=True, exist_ok=True)
        profile_yaml = {
            "investor": {
                "id": "test_investor",
                "name": "测试投资者",
                "capital_cny": 100000.0,
                "risk_level": "C4",
            },
            "constraints": {"max_single_position_pct": 20.0},
        }
        with open(inv_dir / "profile.yaml", "w", encoding="utf-8") as f:
            yaml.dump(profile_yaml, f)

        loader = YamlConfigLoader(workspace=str(tmp_path))
        profile = loader.load_investor("test_investor")
        assert isinstance(profile, InvestorProfile)
        assert profile.investor_id == "test_investor"
        assert profile.name == "测试投资者"
        assert profile.capital_cny == 100000.0

    def test_file_not_found_config_error(self, tmp_path):
        """文件不存在 → ConfigError."""
        loader = YamlConfigLoader(workspace=str(tmp_path))
        with pytest.raises(ConfigError, match="配置文件不存在"):
            loader.load_investor("nonexistent")

    def test_yaml_parse_error(self, tmp_path):
        """YAML 解析错误 → ConfigError."""
        inv_dir = tmp_path / "config" / "investors" / "bad"
        inv_dir.mkdir(parents=True, exist_ok=True)
        (inv_dir / "profile.yaml").write_text(": invalid: yaml: :::", encoding="utf-8")

        loader = YamlConfigLoader(workspace=str(tmp_path))
        with pytest.raises(ConfigError, match="YAML 解析错误"):
            loader.load_investor("bad")


class TestLoadPortfolio:
    """load_portfolio 测试."""

    def test_load_portfolio_with_assets_sentinels(self, tmp_path):
        """加载含 assets + sentinels 的组合."""
        pf_dir = tmp_path / "config" / "investors" / "inv-test" / "portfolios" / "core"
        pf_dir.mkdir(parents=True)
        portfolio_yaml = {
            "portfolio": {
                "id": "core",
                "name": "核心组合",
            },
            "assets": [
                {"ticker": "600519", "name": "贵州茅台", "asset_type": "stock", "target_weight_pct": 50.0},
            ],
            "sentinels": {
                "macro": [
                    {"ticker": "510300", "name": "沪深300ETF", "role": "大盘基准"},
                ],
            },
        }
        with open(pf_dir / "portfolio.yaml", "w", encoding="utf-8") as f:
            yaml.dump(portfolio_yaml, f)

        loader = YamlConfigLoader(workspace=str(tmp_path))
        # 需要 investor 也存在
        inv_dir = tmp_path / "config" / "investors" / "inv-test"
        inv_dir.mkdir(parents=True, exist_ok=True)
        inv_data = {"investor": {"id": "inv-test", "name": "Test", "capital_cny": 100000}}
        with open(inv_dir / "profile.yaml", "w", encoding="utf-8") as f:
            yaml.dump(inv_data, f)

        portfolio = loader.load_portfolio("inv-test", "core")
        assert portfolio.portfolio_id == "core"
        assert len(portfolio.assets) >= 1
        assert len(portfolio.sentinels) >= 1


class TestOldSchemaNormalization:
    """旧 schema 归一化测试."""

    def test_old_schema_normalization(self, tmp_path):
        """旧 schema (name→strategy_name, rule→rule_id, ai_teams dict→list)."""
        strat_dir = tmp_path / "config" / "strategies"
        strat_dir.mkdir(parents=True)
        strategy_yaml = {
            "name": "grid_value_v1",
            "description": "网格价值策略",
            "rules": [
                {"rule": "risk.cash_floor", "params": {"min_pct": 5.0}},
            ],
            "ai_teams": {
                "reasonix": {"preferred_masters": ["gpt-4"]},
            },
            "suitable_for": "balanced",
            "evolution_dimensions": ["risk", "return"],
        }
        with open(strat_dir / "grid_value_v1.yaml", "w", encoding="utf-8") as f:
            yaml.dump(strategy_yaml, f)

        loader = YamlConfigLoader(workspace=str(tmp_path))
        strategy = loader.load_strategy("grid_value_v1")
        assert strategy.strategy_name == "grid_value_v1"
        assert len(strategy.rules) == 1
        assert strategy.rules[0].rule_id == "risk.cash_floor"


class TestLoadAssetDetail:
    """load_asset_detail 测试."""

    def test_load_asset_detail_from_file(self, tmp_path):
        """从独立文件加载标的详情."""
        asset_dir = tmp_path / "config" / "investors" / "inv-test" / "portfolios" / "core" / "assets"
        asset_dir.mkdir(parents=True)
        asset_yaml = {"ticker": "600519", "name": "贵州茅台", "grid_low": 1700, "grid_high": 2000}
        with open(asset_dir / "600519.yaml", "w", encoding="utf-8") as f:
            yaml.dump(asset_yaml, f)

        # 需要 investor 和 portfolio 也存在
        inv_dir = tmp_path / "config" / "investors" / "inv-test"
        inv_dir.mkdir(parents=True, exist_ok=True)
        inv_data = {"investor": {"id": "inv-test", "name": "Test", "capital_cny": 100000}}
        with open(inv_dir / "profile.yaml", "w", encoding="utf-8") as f:
            yaml.dump(inv_data, f)
        pf_dir = asset_dir.parent
        pf_dir.mkdir(parents=True, exist_ok=True)
        pf_data = {"portfolio": {"id": "core"}, "assets": [{"ticker": "600519", "name": "贵州茅台", "asset_type": "stock"}]}
        with open(pf_dir / "portfolio.yaml", "w", encoding="utf-8") as f:
            yaml.dump(pf_data, f)

        loader = YamlConfigLoader(workspace=str(tmp_path))
        detail = loader.load_asset_detail("inv-test", "core", "600519")
        assert detail["ticker"] == "600519"
        assert "grid_low" in detail


class TestListPortfolios:
    """list_portfolios 测试."""

    def test_list_portfolios(self, tmp_path):
        """列出投资者的所有组合."""
        pf_dir = tmp_path / "config" / "investors" / "inv-test" / "portfolios"
        (pf_dir / "core").mkdir(parents=True)
        (pf_dir / "aggressive").mkdir(parents=True)
        (pf_dir / "defensive").mkdir(parents=True)

        # 创建必需的 investor profile
        inv_dir = tmp_path / "config" / "investors" / "inv-test"
        inv_data = {"investor": {"id": "inv-test", "name": "Test", "capital_cny": 100000}}
        with open(inv_dir / "profile.yaml", "w", encoding="utf-8") as f:
            yaml.dump(inv_data, f)

        loader = YamlConfigLoader(workspace=str(tmp_path))
        portfolios = loader.list_portfolios("inv-test")
        assert len(portfolios) == 3
        assert "core" in portfolios
        assert "aggressive" in portfolios
        assert "defensive" in portfolios

    def test_list_portfolios_empty(self, tmp_path):
        """无组合目录返回空列表."""
        loader = YamlConfigLoader(workspace=str(tmp_path))
        portfolios = loader.list_portfolios("nonexistent")
        assert portfolios == []
