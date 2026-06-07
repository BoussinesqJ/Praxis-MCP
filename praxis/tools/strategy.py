"""MCP 工具 - 策略管理"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import yaml

from praxis.engine.config_loader import YamlConfigLoader
from praxis.core.database import Database


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

        # 保存变更提案到 SQLite
        db = Database(Path(workspace) / "data" / "praxis_system.db")
        proposal_id = f"port-update-{investor}-{portfolio}-{field}"
        old_val = getattr(p, field, None)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO portfolio_proposals (proposal_id, investor, portfolio, field, new_value, old_value, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (proposal_id, investor, portfolio, field, value, old_val, timestamp)
            )

        return {
            "success": True,
            "data": {
                "proposal_id": proposal_id,
                "status": "pending_approval",
                "field": field,
                "old_value": old_val,
                "new_value": value,
                "message": f"修改提案 {proposal_id} 已生成，修改预览: {field} = {value}，请调用 approve_portfolio_update_tool 完成配置更新写入。",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def approve_portfolio_update(
    investor: str,
    portfolio: str,
    field: str,
    value: str,
    workspace: str = ".",
) -> dict:
    """审批并通过组合配置修改"""
    try:
        db = Database(Path(workspace) / "data" / "praxis_system.db")
        proposal_id = f"port-update-{investor}-{portfolio}-{field}"
        
        proposal = None
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT investor, portfolio, field, new_value, old_value, timestamp FROM portfolio_proposals WHERE proposal_id = ?",
                (proposal_id,)
            )
            row = cursor.fetchone()
            if row:
                proposal = {
                    "investor": row["investor"],
                    "portfolio": row["portfolio"],
                    "field": row["field"],
                    "new_value": row["new_value"],
                    "old_value": row["old_value"],
                    "timestamp": row["timestamp"],
                }
            
        if not proposal:
            return {"success": False, "error": f"未找到对应的待审批提案: {proposal_id}"}
            
        if proposal["new_value"] != value:
            return {
                "success": False,
                "error": f"审批内容不匹配: 提案值为 '{proposal['new_value']}', 审批传入值为 '{value}'"
            }
            
        # 实际执行写入 YAML
        portfolio_yaml_path = (
            Path(workspace) / "investors" / investor / "portfolios" / portfolio / "portfolio.yaml"
        )
        if not portfolio_yaml_path.exists():
            return {"success": False, "error": f"投资组合配置文件不存在: {portfolio_yaml_path}"}
            
        with open(portfolio_yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        if "portfolio" in data and isinstance(data["portfolio"], dict):
            data["portfolio"][field] = value
        else:
            data[field] = value
            
        with open(portfolio_yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            
        # 从挂起提案中删除该条记录
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM portfolio_proposals WHERE proposal_id = ?", (proposal_id,))
            
        return {
            "success": True,
            "data": {
                "message": f"提案 {proposal_id} 已批准，组合 {portfolio} 的字段 {field} 已成功更新为 {value}",
                "investor": investor,
                "portfolio": portfolio,
                "field": field,
                "value": value,
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
