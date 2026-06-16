"""MCP 工具 - 自适应规则"""
from __future__ import annotations

from praxis.engine.adaptive_rules import AdaptiveRuleEngine


def learn_rules(workspace: str = ".") -> dict:
    """从历史数据中学习自适应规则

    分析交易记录和 NAV 历史，生成规则草案。
    所有规则经安全扫描后写入 teams/adaptive/learned_rules.json。
    """
    try:
        engine = AdaptiveRuleEngine(workspace)
        new_rules = engine.learn()
        all_rules = engine.load_rules()

        return {
            "success": True,
            "data": {
                "new_rules_count": len(new_rules),
                "total_rules_count": len(all_rules),
                "new_rules": [r.model_dump() for r in new_rules],
                "message": (
                    f"学习完成：新增 {len(new_rules)} 条规则，"
                    f"总计 {len(all_rules)} 条规则。"
                    + (" 新规则状态为 draft，需人工审批后激活。" if new_rules else " 无新规则。")
                ),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_learned_rules(workspace: str = ".") -> dict:
    """列出所有已学习的自适应规则"""
    try:
        engine = AdaptiveRuleEngine(workspace)
        rules = engine.load_rules()

        return {
            "success": True,
            "data": {
                "total": len(rules),
                "draft": [r.model_dump() for r in rules if r.status == "draft"],
                "active": [r.model_dump() for r in rules if r.status == "active"],
                "archived": [r.model_dump() for r in rules if r.status in ("retired", "rejected_by_scanner")],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def approve_rule(rule_id: str, workspace: str = ".") -> dict:
    """审批通过自适应规则（draft → active）"""
    try:
        engine = AdaptiveRuleEngine(workspace)
        return engine.update_rule_status(rule_id, "active")
    except Exception as e:
        return {"success": False, "error": str(e)}


def reject_rule(rule_id: str, workspace: str = ".") -> dict:
    """拒绝自适应规则（draft → rejected）"""
    try:
        engine = AdaptiveRuleEngine(workspace)
        return engine.update_rule_status(rule_id, "rejected_by_scanner")
    except Exception as e:
        return {"success": False, "error": str(e)}


def retire_rule(rule_id: str, workspace: str = ".") -> dict:
    """退休自适应规则（active → retired）"""
    try:
        engine = AdaptiveRuleEngine(workspace)
        return engine.update_rule_status(rule_id, "retired")
    except Exception as e:
        return {"success": False, "error": str(e)}
