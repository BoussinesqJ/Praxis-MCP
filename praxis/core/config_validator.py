"""PRAXIS YAML 配置验证器

验证 YAML 配置文件的结构和内容是否符合 Schema。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from praxis.core.models.investor import InvestorProfile
from praxis.core.models.portfolio import Portfolio
from praxis.core.models.strategy import StrategyTemplate
from praxis.core.models.error import ConfigError


class ConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate_investor_profile(data: dict[str, Any]) -> list[str]:
        """验证投资者画像配置"""
        errors = []
        try:
            InvestorProfile(**data)
        except ValidationError as e:
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(f"投资者画像字段错误 {field}: {error['msg']}")
        return errors

    @staticmethod
    def validate_portfolio(data: dict[str, Any]) -> list[str]:
        """验证投资组合配置"""
        errors = []
        try:
            Portfolio(**data)
        except ValidationError as e:
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(f"组合配置字段错误 {field}: {error['msg']}")
        return errors

    @staticmethod
    def validate_strategy(data: dict[str, Any]) -> list[str]:
        """验证策略模板配置"""
        errors = []
        try:
            StrategyTemplate(**data)
        except ValidationError as e:
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(f"策略模板字段错误 {field}: {error['msg']}")
        return errors

    @staticmethod
    def validate_yaml_file(file_path: Path, schema_type: str) -> list[str]:
        """验证 YAML 文件"""
        if not file_path.exists():
            return [f"文件不存在: {file_path}"]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"YAML 解析错误: {e}"]

        if data is None:
            return [f"文件为空: {file_path}"]

        # 处理嵌套结构
        if schema_type == "investor" and "investor" in data:
            # 合并 investor 和 constraints/execution/philosophy
            investor_data = data["investor"]
            if "constraints" in data:
                investor_data["constraints"] = data["constraints"]
            if "execution" in data:
                investor_data["execution"] = data["execution"]
            if "philosophy" in data:
                investor_data["philosophy"] = data["philosophy"]
            data = investor_data
        elif schema_type == "portfolio" and "portfolio" in data:
            # 合并 portfolio 和 assets/sentinels
            portfolio_data = data["portfolio"]
            if "assets" in data:
                portfolio_data["assets"] = data["assets"]
            if "sentinels" in data:
                portfolio_data["sentinels"] = data["sentinels"]
            data = portfolio_data

        validators = {
            "investor": ConfigValidator.validate_investor_profile,
            "portfolio": ConfigValidator.validate_portfolio,
            "strategy": ConfigValidator.validate_strategy,
        }

        validator = validators.get(schema_type)
        if not validator:
            return [f"不支持的 schema 类型: {schema_type}"]

        return validator(data)

    @staticmethod
    def validate_all_configs(workspace: str | Path) -> dict[str, list[str]]:
        """验证所有配置文件"""
        workspace = Path(workspace)
        results = {}

        # 验证投资者配置
        investors_dir = workspace / "investors"
        if investors_dir.exists():
            for investor_dir in investors_dir.iterdir():
                if investor_dir.is_dir():
                    profile_path = investor_dir / "profile.yaml"
                    if profile_path.exists():
                        errors = ConfigValidator.validate_yaml_file(profile_path, "investor")
                        results[str(profile_path)] = errors

                    # 验证组合配置
                    portfolios_dir = investor_dir / "portfolios"
                    if portfolios_dir.exists():
                        for portfolio_dir in portfolios_dir.iterdir():
                            if portfolio_dir.is_dir():
                                portfolio_path = portfolio_dir / "portfolio.yaml"
                                if portfolio_path.exists():
                                    errors = ConfigValidator.validate_yaml_file(portfolio_path, "portfolio")
                                    results[str(portfolio_path)] = errors

        # 验证策略配置
        strategies_dir = workspace / "strategies"
        if strategies_dir.exists():
            for strategy_file in strategies_dir.glob("*.yaml"):
                errors = ConfigValidator.validate_yaml_file(strategy_file, "strategy")
                results[str(strategy_file)] = errors

        return results

    @staticmethod
    def format_validation_report(results: dict[str, list[str]]) -> str:
        """格式化验证报告"""
        lines = ["=== 配置验证报告 ==="]

        total_errors = sum(len(errors) for errors in results.values())
        total_files = len(results)
        files_with_errors = sum(1 for errors in results.values() if errors)

        lines.append(f"文件总数: {total_files}")
        lines.append(f"有错误的文件: {files_with_errors}")
        lines.append(f"错误总数: {total_errors}")

        if total_errors == 0:
            lines.append("\n✅ 所有配置文件验证通过")
        else:
            lines.append("\n❌ 发现配置错误:")
            for file_path, errors in results.items():
                if errors:
                    lines.append(f"\n{file_path}:")
                    for error in errors:
                        lines.append(f"  - {error}")

        return "\n".join(lines)
