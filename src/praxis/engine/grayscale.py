"""策略风险灰度机制

GPT 要求：策略进化需要灰度验证，不能直接全量应用。
V1 实现：备份 + 审批 + 验证（基于回测数据）

从原版 engine/grayscale.py + tools/grayscale.py 合并迁移。
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from praxis.core.exceptions import ConfigError


class GrayscaleConfig(BaseModel):
    """灰度配置"""
    strategy_name: str
    change_description: str
    risk_level: str = "medium"  # low / medium / high
    validation_days: int = 30
    require_backtest: bool = True
    require_approval: bool = True


class GrayscaleResult(BaseModel):
    """灰度验证结果"""
    strategy_name: str
    change_description: str
    risk_level: str
    backup_path: str = ""
    backtest_result: dict | None = None
    validation_passed: bool = False
    approval_required: bool = True
    message: str = ""


class GrayscaleEngine:
    """策略灰度验证引擎

    验证流程：
    1. 备份当前策略 YAML
    2. (可选) 运行回测
    3. 对比回测结果
    4. 返回验证结论
    """

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._config_dir = self._workspace / "config" / "strategies"

    def run_validation(
        self,
        config: GrayscaleConfig,
        ledger=None,
        benchmark_provider=None,
    ) -> GrayscaleResult:
        """运行灰度验证

        Args:
            config: 灰度配置
            ledger: 账本实例（require_backtest=True 时必需）
            benchmark_provider: 基准数据提供者

        Returns:
            GrayscaleResult: 验证结果
        """
        try:
            # 1. 备份当前策略
            backup_path = self._backup_strategy(config.strategy_name)

            # 2. 运行回测验证
            backtest_result = None
            if config.require_backtest:
                backtest_result = self._run_backtest_validation(config, ledger)

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
                message=_generate_message(config, validation_passed, backtest_result),
            )
        except Exception as e:
            return GrayscaleResult(
                strategy_name=config.strategy_name,
                change_description=config.change_description,
                risk_level=config.risk_level,
                backup_path="",
                validation_passed=False,
                approval_required=True,
                message=f"灰度验证失败: {e}",
            )

    def _backup_strategy(self, strategy_name: str) -> Path:
        """备份策略文件"""
        strategy_path = self._config_dir / f"{strategy_name}.yaml"
        if not strategy_path.exists():
            raise ConfigError(f"策略文件不存在: {strategy_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = strategy_path.with_suffix(f".{timestamp}.bak")
        shutil.copy2(strategy_path, backup_path)
        return backup_path

    def _run_backtest_validation(self, config: GrayscaleConfig, ledger) -> dict:
        """运行回测验证"""
        try:
            from praxis.engine.backtest import BacktestConfig, run_backtest

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=config.validation_days)).strftime("%Y-%m-%d")

            bt_config = BacktestConfig(
                strategy_name=config.strategy_name,
                start_date=start_date,
                end_date=end_date,
            )

            result = run_backtest(bt_config, ledger)
            return {
                "success": True,
                "total_return": result.total_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "win_rate": result.win_rate,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


def _generate_message(
    config: GrayscaleConfig,
    validation_passed: bool,
    backtest_result: dict | None,
) -> str:
    """生成验证消息"""
    lines = [
        f"策略: {config.strategy_name}",
        f"变更: {config.change_description}",
        f"风险等级: {config.risk_level}",
    ]

    if config.require_backtest:
        if backtest_result and backtest_result.get("success"):
            lines.append("回测验证: 通过")
        else:
            lines.append("回测验证: 失败")
            if backtest_result:
                lines.append(f"  错误: {backtest_result.get('error', '未知')}")

    if config.require_approval:
        lines.append("需要人工审批后才能应用变更")

    return "\n".join(lines)
