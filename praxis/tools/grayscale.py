"""MCP 工具 - 策略风险灰度"""
from __future__ import annotations

from pathlib import Path

from praxis.engine.grayscale import StrategyGrayscale, GrayscaleConfig


def prepare_grayscale(
    strategy_name: str,
    change_description: str,
    risk_level: str = "medium",
    validation_days: int = 30,
    workspace: str = ".",
) -> dict:
    """准备策略灰度验证"""
    try:
        engine = StrategyGrayscale(workspace)
        config = GrayscaleConfig(
            strategy_name=strategy_name,
            change_description=change_description,
            risk_level=risk_level,
            validation_days=validation_days,
        )
        result = engine.prepare_grayscale(config)
        return {
            "success": True,
            "data": result.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def approve_grayscale(
    strategy_name: str,
    backup_path: str,
    new_content: str,
    workspace: str = ".",
) -> dict:
    """审批通过后应用策略变更"""
    try:
        engine = StrategyGrayscale(workspace)
        result = engine.approve_grayscale(strategy_name, backup_path, new_content)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
