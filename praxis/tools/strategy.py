"""MCP 工具 - 策略管理"""
from __future__ import annotations

from pathlib import Path

from praxis.engine.config_loader import YamlConfigLoader


def get_strategy(strategy_name: str, workspace: str = ".") -> dict:
    """获取策略详情（含规则+AI团队配置+进化维度）"""
    try:
        loader = YamlConfigLoader(workspace)
        strategy = loader.load_strategy(strategy_name)
        return {
            "success": True,
            "data": strategy.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_strategies(workspace: str = ".") -> dict:
    """列出所有策略模板"""
    try:
        strategies_dir = Path(workspace) / "strategies"
        if not strategies_dir.exists():
            return {"success": True, "data": {"strategies": []}}

        strategies = []
        for f in strategies_dir.glob("*.yaml"):
            strategies.append(f.stem)

        return {
            "success": True,
            "data": {"strategies": strategies},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_portfolio(
    investor: str,
    portfolio: str,
    field: str,
    value: str,
    workspace: str = ".",
) -> dict:
    """修改组合配置（需审批，GPT 架构底线）

    V1 实现：仅支持修改简单字段，复杂修改需人工审批
    """
    try:
        loader = YamlConfigLoader(workspace)
        # 读取当前配置
        p = loader.load_portfolio(investor, portfolio)

        # 检查字段是否可修改
        allowed_fields = ["version", "description"]
        if field not in allowed_fields:
            return {
                "success": False,
                "error": f"字段 {field} 不允许直接修改，需人工审批",
            }

        # 返回修改预览（不实际写入）
        return {
            "success": True,
            "data": {
                "status": "pending_approval",
                "field": field,
                "old_value": getattr(p, field, None),
                "new_value": value,
                "message": f"修改预览: {field} = {value}，需人工审批后写入",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
