"""配置加载器实现（YAML → Pydantic）"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from praxis.core.interfaces import ConfigLoader
from praxis.core.models.investor import InvestorProfile
from praxis.core.models.portfolio import Portfolio
from praxis.core.models.strategy import StrategyTemplate
from praxis.core.models.error import ConfigError
from praxis.core.validation import validate_id


class YamlConfigLoader(ConfigLoader):
    """YAML 配置加载器"""

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace or os.environ.get("PRAXIS_WORKSPACE", "."))
        self._investors_dir = self.workspace / "investors"
        self._strategies_dir = self.workspace / "strategies"

    def _load_yaml(self, path: Path) -> dict:
        """加载 YAML 文件"""
        if not path.exists():
            raise ConfigError(f"配置文件不存在: {path}", path=str(path))
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data is None:
                raise ConfigError(f"配置文件为空: {path}", path=str(path))
            return data
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML 解析错误: {e}", path=str(path))

    def load_investor(self, investor_id: str) -> InvestorProfile:
        """加载投资者画像"""
        err = validate_id("investor_id", investor_id)
        if err:
            raise ConfigError(err)
        path = self._investors_dir / investor_id / "profile.yaml"
        data = self._load_yaml(path)
        investor_data = data.get("investor", data)
        # 合并 constraints, execution, philosophy
        if "constraints" in data:
            investor_data["constraints"] = data["constraints"]
        if "execution" in data:
            investor_data["execution"] = data["execution"]
        if "philosophy" in data:
            investor_data["philosophy"] = data["philosophy"]
        return InvestorProfile(**investor_data)

    def load_portfolio(self, investor_id: str, portfolio_id: str) -> Portfolio:
        """加载投资组合配置"""
        for name, val in [("investor_id", investor_id), ("portfolio_id", portfolio_id)]:
            err = validate_id(name, val)
            if err:
                raise ConfigError(err)
        path = self._investors_dir / investor_id / "portfolios" / portfolio_id / "portfolio.yaml"
        data = self._load_yaml(path)
        portfolio_data = data.get("portfolio", data)
        # 合并 assets, sentinels
        if "assets" in data:
            portfolio_data["assets"] = data["assets"]
        if "sentinels" in data:
            portfolio_data["sentinels"] = data["sentinels"]
        return Portfolio(**portfolio_data)

    def load_strategy(self, strategy_name: str) -> StrategyTemplate:
        """加载策略模板"""
        err = validate_id("strategy_name", strategy_name)
        if err:
            raise ConfigError(err)
        path = self._strategies_dir / f"{strategy_name}.yaml"
        data = self._load_yaml(path)
        return StrategyTemplate(**data)

    def load_asset_detail(self, investor_id: str, portfolio_id: str, ticker: str) -> dict:
        """加载单标的详情"""
        for name, val in [("investor_id", investor_id), ("portfolio_id", portfolio_id), ("ticker", ticker)]:
            err = validate_id(name, val)
            if err:
                raise ConfigError(err)
        # 尝试从独立文件加载
        asset_path = (
            self._investors_dir / investor_id
            / "portfolios" / portfolio_id / "assets" / f"{ticker}.yaml"
        )
        if asset_path.exists():
            return self._load_yaml(asset_path)
        # 回退：从 portfolio.yaml 中提取
        portfolio = self.load_portfolio(investor_id, portfolio_id)
        for asset in portfolio.assets:
            if asset.ticker == ticker:
                return asset.model_dump()
        raise ConfigError(f"标的 {ticker} 不存在", path=str(asset_path))

    def list_portfolios(self, investor_id: str) -> list[str]:
        """列出投资者的所有组合"""
        portfolios_dir = self._investors_dir / investor_id / "portfolios"
        if not portfolios_dir.exists():
            return []
        return [d.name for d in portfolios_dir.iterdir() if d.is_dir()]
