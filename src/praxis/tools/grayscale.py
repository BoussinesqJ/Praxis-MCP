"""MCP 工具 — 策略风险灰度

从原版 tools/grayscale.py 迁移，适配重构版接口。
"""
from __future__ import annotations

from praxis.engine.grayscale import GrayscaleEngine, GrayscaleConfig


VALID_RISK_LEVELS = ("low", "medium", "high")


async def grayscale(
    action: str,
    strategy_name: str = "",
    change_description: str = "",
    risk_level: str = "medium",
    validation_days: int = 30,
    _deps: dict | None = None,
) -> dict:
    """策略灰度验证工具

    Args:
        action: "validate" | "status"
        strategy_name: 策略名称
        change_description: 变更描述
        risk_level: 风险等级 (low/medium/high)
        validation_days: 验证天数
        _deps: 依赖注入 {workspace, ledger, benchmark_provider}

    Returns:
        {success, data, error}
    """
    deps = _deps or {}
    workspace = deps.get("workspace", ".")

    if action == "validate":
        if not strategy_name:
            return {"success": False, "error": "strategy_name 不能为空"}

        if risk_level not in VALID_RISK_LEVELS:
            return {
                "success": False,
                "error": f"无效 risk_level: {risk_level}，支持 {'/'.join(VALID_RISK_LEVELS)}",
            }

        ledger = deps.get("ledger")
        benchmark_provider = deps.get("benchmark_provider")

        engine = GrayscaleEngine(str(workspace))
        config = GrayscaleConfig(
            strategy_name=strategy_name,
            change_description=change_description,
            risk_level=risk_level,
            validation_days=validation_days,
            require_backtest=risk_level != "low",
            require_approval=risk_level != "low",
        )

        result = engine.run_validation(
            config,
            ledger=ledger,
            benchmark_provider=benchmark_provider,
        )
        return {
            "success": True,
            "data": result.model_dump(),
        }

    elif action == "status":
        if not strategy_name:
            return {"success": False, "error": "strategy_name 不能为空"}

        engine = GrayscaleEngine(str(workspace))
        strategy_path = engine._config_dir / f"{strategy_name}.yaml"
        backup_files = list(engine._config_dir.glob(f"{strategy_name}.*.bak"))

        return {
            "success": True,
            "data": {
                "strategy_name": strategy_name,
                "strategy_exists": strategy_path.exists(),
                "backup_count": len(backup_files),
                "backups": [
                    str(b.name)
                    for b in sorted(
                        backup_files,
                        key=lambda x: x.stat().st_mtime,
                        reverse=True,
                    )
                ],
            },
        }

    else:
        return {
            "success": False,
            "error": f"未知 action: {action}，支持 validate | status",
        }
