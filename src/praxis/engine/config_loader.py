"""配置加载器实现（YAML → Pydantic）"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from praxis.core.interfaces import ConfigLoader
from praxis.core.models import InvestorProfile, Portfolio, StrategyTemplate
from praxis.core.exceptions import ConfigError
from praxis.core.paths import get_paths

# 路径安全字符集：字母/数字/下划线/连字符/点（不允许路径分隔符和遍历字符）
import re
_SAFE_CONFIG_ID = re.compile(r'^[\w\-\.]+$')


def _check_config_id(name: str, value: str) -> None:
    """轻量配置 ID 路径安全校验（不要求业务前缀，仅防路径遍历）

    investor_id/portfolio_id/strategy_name 是配置目录名，不是业务 ID（tx-/dec-），
    不应使用 validate_id 的前缀校验。这里仅做路径安全检查。
    """
    if not value or not value.strip():
        raise ConfigError(f"{name} 不能为空")
    if not _SAFE_CONFIG_ID.match(value):
        raise ConfigError(f"{name} '{value}' 包含非法字符（仅允许字母/数字/下划线/连字符/点）")
    if '..' in value:
        raise ConfigError(f"{name} '{value}' 包含路径遍历字符 '..'")
    if value.startswith('.'):
        raise ConfigError(f"{name} '{value}' 不能以点开头")


class YamlConfigLoader(ConfigLoader):
    """YAML 配置加载器"""

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace or os.environ.get("PRAXIS_WORKSPACE", "."))
        paths = get_paths(str(self.workspace))
        self._investors_dir = paths["config"] / "investors"
        self._strategies_dir = paths["config"] / "strategies"

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
        _check_config_id("investor_id", investor_id)
        path = self._investors_dir / investor_id / "profile.yaml"
        data = self._load_yaml(path)
        investor_data = data.get("investor", data)
        # 映射 YAML 字段名 → Pydantic 字段名 (id → investor_id)
        if "id" in investor_data and "investor_id" not in investor_data:
            investor_data["investor_id"] = investor_data["id"]  # copy, not pop — model requires id field
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
        _check_config_id("investor_id", investor_id)
        _check_config_id("portfolio_id", portfolio_id)
        path = self._investors_dir / investor_id / "portfolios" / portfolio_id / "portfolio.yaml"
        data = self._load_yaml(path)
        portfolio_data = data.get("portfolio", data)
        # 映射 YAML 字段名 → Pydantic 字段名 (id → portfolio_id)
        if "id" in portfolio_data and "portfolio_id" not in portfolio_data:
            portfolio_data["portfolio_id"] = portfolio_data["id"]
        # 确保 investor_id 存在（YAML 可能省略，用参数补）
        if not portfolio_data.get("investor_id"):
            portfolio_data["investor_id"] = investor_id
        # 合并 assets, sentinels
        if "assets" in data:
            portfolio_data["assets"] = data["assets"]
        if "sentinels" in data:
            portfolio_data["sentinels"] = self._flatten_sentinels(data["sentinels"])
        return Portfolio(**portfolio_data)

    @staticmethod
    def _flatten_sentinels(sentinels_raw) -> list[dict]:
        """将哨兵配置从 dict(macro/execution 分组) 扁平化为 list

        YAML 格式:
            sentinels:
              macro:
                - ticker: "510300"
                  name: "沪深300ETF"
                  role: "大盘风向"
              execution:
                - ticker: "512480"
                  ...
        转为:
            [{"ticker": "510300", "name": "...", "layer": "macro"}, ...]
        """
        if isinstance(sentinels_raw, list):
            # 已经是扁平 list，补充 layer 默认值
            result = []
            for s in sentinels_raw:
                if isinstance(s, dict):
                    entry = dict(s)
                    entry.setdefault("layer", "macro")
                    result.append(entry)
            return result
        if isinstance(sentinels_raw, dict):
            result = []
            for layer, items in sentinels_raw.items():
                if not isinstance(items, list):
                    continue
                for s in items:
                    if isinstance(s, dict):
                        entry = dict(s)
                        entry["layer"] = layer
                        result.append(entry)
            return result
        return []

    def load_strategy(self, strategy_name: str) -> StrategyTemplate:
        """加载策略模板（含旧 schema 归一化）"""
        _check_config_id("strategy_name", strategy_name)
        path = self._strategies_dir / f"{strategy_name}.yaml"
        data = self._load_yaml(path)

        # ===== 旧 schema 归一化 =====
        # 1. name → strategy_name（旧 YAML 用 name，模型用 strategy_name）
        if "name" in data and "strategy_name" not in data:
            data["strategy_name"] = data.pop("name")

        # 2. rules: 旧格式 {rule, params} → RuleEntry {rule_id, name, params}
        if "rules" in data:
            normalized_rules = []
            for r in data["rules"]:
                if not isinstance(r, dict):
                    continue
                # rule → rule_id
                if "rule" in r and "rule_id" not in r:
                    r["rule_id"] = r.pop("rule")
                # 补默认 name（从 rule_id 推导）
                if "name" not in r:
                    r["name"] = r.get("rule_id", "unknown_rule")
                # 补默认 level 和 enabled
                r.setdefault("level", "hard_block")
                r.setdefault("enabled", True)
                r.setdefault("description", "")
                normalized_rules.append(r)
            data["rules"] = normalized_rules

        # 3. ai_teams: 旧格式 dict → list[AITeamConfig]
        if "ai_teams" in data and isinstance(data["ai_teams"], dict):
            teams_list = []
            for team_name, team_data in data["ai_teams"].items():
                entry: dict = {
                    "team_name": team_name,
                    "members": [],
                    "model_hint": "deep",
                    "enabled": True,
                }
                if isinstance(team_data, dict):
                    entry["members"] = team_data.get("preferred_masters", [])
                teams_list.append(entry)
            data["ai_teams"] = teams_list

        # 4. 移除模型中不存在的旧字段
        data.pop("suitable_for", None)
        data.pop("evolution_dimensions", None)

        return StrategyTemplate(**data)

    def load_asset_detail(self, investor_id: str, portfolio_id: str, ticker: str) -> dict:
        """加载单标的详情"""
        _check_config_id("investor_id", investor_id)
        _check_config_id("portfolio_id", portfolio_id)
        _check_config_id("ticker", ticker)
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
