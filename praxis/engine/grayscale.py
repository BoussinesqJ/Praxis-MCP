"""策略风险灰度机制

GPT 要求：策略进化需要灰度验证，不能直接全量应用。
V1 实现：备份 + 审批 + 验证（基于回测数据）
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.backtest import SimpleBacktestEngine, BacktestConfig
from praxis.core.ledger import FileLedger
from praxis.core.models.error import PraxisError


class GrayscaleConfig(BaseModel):
    """灰度配置"""
    strategy_name: str
    change_description: str
    risk_level: str  # low/medium/high
    validation_days: int = 30
    require_backtest: bool = True
    require_approval: bool = True


class GrayscaleResult(BaseModel):
    """灰度验证结果"""
    strategy_name: str
    change_description: str
    risk_level: str
    backup_path: str
    backtest_result: dict | None = None
    validation_passed: bool = False
    approval_required: bool = True
    message: str


class StrategyGrayscale:
    """策略风险灰度管理器"""

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._config = YamlConfigLoader(workspace)
        self._ledger = FileLedger(workspace + "/data/ledger/transactions.jsonl")

    def prepare_grayscale(
        self,
        config: GrayscaleConfig,
    ) -> GrayscaleResult:
        """准备灰度验证

        流程：
        1. 备份当前策略
        2. 运行回测验证
        3. 返回验证结果
        """
        try:
            # 1. 备份当前策略
            backup_path = self._backup_strategy(config.strategy_name)

            # 2. 运行回测验证（如果需要）
            backtest_result = None
            if config.require_backtest:
                backtest_result = self._run_backtest_validation(config)

            # 3. 判断验证是否通过
            validation_passed = True
            if backtest_result and not backtest_result.get("success", False):
                validation_passed = False

            return GrayscaleResult(
                strategy_name=config.strategy_name,
                change_description=config.change_description,
                risk_level=config.risk_level,
                backup_path=str(backup_path),
                backtest_result=backtest_result,
                validation_passed=validation_passed,
                approval_required=config.require_approval,
                message=self._generate_message(config, validation_passed, backtest_result),
            )

        except Exception as e:
            return GrayscaleResult(
                strategy_name=config.strategy_name,
                change_description=config.change_description,
                risk_level=config.risk_level,
                backup_path="",
                validation_passed=False,
                approval_required=True,
                message=f"灰度验证失败: {str(e)}",
            )

    def _backup_strategy(self, strategy_name: str) -> Path:
        """备份策略文件"""
        strategy_path = self._workspace / "strategies" / f"{strategy_name}.yaml"
        if not strategy_path.exists():
            raise PraxisError(f"策略文件不存在: {strategy_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = strategy_path.with_suffix(f".{timestamp}.bak")
        shutil.copy2(strategy_path, backup_path)

        return backup_path

    def _run_backtest_validation(self, config: GrayscaleConfig) -> dict:
        """运行回测验证"""
        try:
            engine = SimpleBacktestEngine(self._ledger)

            # 计算回测期间
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - __import__('datetime').timedelta(days=config.validation_days)).strftime("%Y-%m-%d")

            backtest_config = BacktestConfig(
                strategy_name=config.strategy_name,
                start_date=start_date,
                end_date=end_date,
            )

            result = engine.run_backtest(backtest_config)

            return {
                "success": True,
                "total_return": result.total_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "win_rate": result.win_rate,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _generate_message(
        self,
        config: GrayscaleConfig,
        validation_passed: bool,
        backtest_result: dict | None,
    ) -> str:
        """生成验证消息"""
        lines = [
            f"策略: {config.strategy_name}",
            f"变更: {config.change_description}",
            f"风险等级: {config.risk_level}",
            f"",
        ]

        if config.require_backtest:
            if backtest_result and backtest_result.get("success"):
                lines.append("回测验证: ✅ 通过")
                lines.append(f"  总收益: {backtest_result['total_return']:.2%}")
                lines.append(f"  最大回撤: {backtest_result['max_drawdown']:.2%}")
                lines.append(f"  夏普比率: {backtest_result['sharpe_ratio']:.2f}")
                lines.append(f"  胜率: {backtest_result['win_rate']:.1%}")
            else:
                lines.append("回测验证: ❌ 失败")
                if backtest_result:
                    lines.append(f"  错误: {backtest_result.get('error', '未知')}")

        if config.require_approval:
            lines.append("")
            lines.append("⚠️ 需要人工审批后才能应用变更")

        return "\n".join(lines)

    def approve_grayscale(
        self,
        strategy_name: str,
        backup_path: str,
        new_content: str,
    ) -> dict:
        """审批通过后应用变更"""
        try:
            strategy_path = self._workspace / "strategies" / f"{strategy_name}.yaml"

            # 写入新内容
            strategy_path.write_text(new_content, encoding="utf-8")

            return {
                "success": True,
                "data": {
                    "message": f"策略 {strategy_name} 已更新",
                    "backup_path": backup_path,
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
