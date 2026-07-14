"""MCP 工具 — 策略版本对比

支持两个版本 strategy YAML 的差异对比：
- rules: 新增/删除/参数变更
- ai_teams: 新增/删除
- 元数据: suitable_for/evolution_dimensions/version/description 变更
"""
from __future__ import annotations

import yaml
from pathlib import Path

from praxis.agents.base import Tool


async def version_compare(
    action: str = "diff",
    strategy_name: str = "",
    version_a: str = "",
    version_b: str = "",
    _deps: dict | None = None,
) -> dict:
    """策略版本对比

    Args:
        action: 操作类型 — diff
        strategy_name: 策略名称
        version_a: 版本 A 标识（不含 .yaml）
        version_b: 版本 B 标识（不含 .yaml）
        _deps: 依赖注入字典，需包含 'workspace'

    Returns:
        {"success": bool, "data": {"additions": [...], "deletions": [...], "modifications": [...]}, ...}
    """
    if action != "diff":
        return {"success": False, "error": f"未知 action: {action}"}

    if not strategy_name or not version_a or not version_b:
        return {"success": False, "error": "diff 需要 strategy_name, version_a, version_b 参数"}

    ws = _deps.get("workspace", ".") if _deps else "."
    versions_dir = Path(ws) / "config" / "strategies" / "versions" / strategy_name

    path_a = versions_dir / f"{version_a}.yaml"
    path_b = versions_dir / f"{version_b}.yaml"

    if not path_a.exists():
        return {"success": False, "error": f"版本 A 不存在: {path_a}"}
    if not path_b.exists():
        return {"success": False, "error": f"版本 B 不存在: {path_b}"}

    try:
        with open(path_a, "r", encoding="utf-8") as f:
            data_a = yaml.safe_load(f) or {}
        with open(path_b, "r", encoding="utf-8") as f:
            data_b = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        return {"success": False, "error": f"YAML 解析错误: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    additions: list[dict] = []
    deletions: list[dict] = []
    modifications: list[dict] = []

    # ===== 1. rules 对比 =====
    rules_a = {r["rule_id"] if isinstance(r, dict) else r: r
               for r in data_a.get("rules", [])}
    rules_b = {r["rule_id"] if isinstance(r, dict) else r: r
               for r in data_b.get("rules", [])}

    for rid in rules_b:
        if rid not in rules_a:
            additions.append({"section": "rules", "item": rid,
                            "detail": rules_b[rid] if isinstance(rules_b[rid], dict) else {}})
        elif isinstance(rules_a[rid], dict) and isinstance(rules_b[rid], dict):
            # 检查参数变更
            params_a = rules_a[rid].get("params", {})
            params_b = rules_b[rid].get("params", {})
            if params_a != params_b:
                modifications.append({
                    "section": "rules", "item": rid, "field": "params",
                    "old": params_a, "new": params_b,
                })
            # 检查其他字段变更
            for key in ["level", "enabled", "description", "name"]:
                if rules_a[rid].get(key) != rules_b[rid].get(key):
                    modifications.append({
                        "section": "rules", "item": rid, "field": key,
                        "old": rules_a[rid].get(key), "new": rules_b[rid].get(key),
                    })

    for rid in rules_a:
        if rid not in rules_b:
            deletions.append({"section": "rules", "item": rid,
                            "detail": rules_a[rid] if isinstance(rules_a[rid], dict) else {}})

    # ===== 2. ai_teams 对比 =====
    teams_a = _index_by_key(data_a.get("ai_teams", []), "team_name")
    teams_b = _index_by_key(data_b.get("ai_teams", []), "team_name")

    for tn in teams_b:
        if tn not in teams_a:
            additions.append({"section": "ai_teams", "item": tn, "detail": teams_b[tn]})

    for tn in teams_a:
        if tn not in teams_b:
            deletions.append({"section": "ai_teams", "item": tn, "detail": teams_a[tn]})

    # ===== 3. 元数据对比 =====
    meta_fields = ["version", "description", "suitable_for", "evolution_dimensions"]
    for field in meta_fields:
        val_a = data_a.get(field)
        val_b = data_b.get(field)
        if val_a != val_b:
            if val_b is not None and val_a is None:
                additions.append({"section": "metadata", "item": field, "detail": val_b})
            elif val_b is None and val_a is not None:
                deletions.append({"section": "metadata", "item": field, "detail": val_a})
            else:
                modifications.append({
                    "section": "metadata", "item": field,
                    "old": val_a, "new": val_b,
                })

    return {
        "success": True,
        "data": {
            "strategy_name": strategy_name,
            "version_a": version_a,
            "version_b": version_b,
            "additions": additions,
            "deletions": deletions,
            "modifications": modifications,
            "summary": (
                f"对比 {version_a} → {version_b}: "
                f"+{len(additions)} 新增, "
                f"-{len(deletions)} 删除, "
                f"~{len(modifications)} 变更"
            ),
        },
    }


def _index_by_key(items, key):
    """将列表按指定字段索引为字典"""
    if isinstance(items, list):
        return {item.get(key, item): item for item in items if isinstance(item, dict)}
    if isinstance(items, dict):
        return items
    return {}


def register(registry):
    registry.register(
        Tool(
            name="version_compare",
            description="策略版本对比：对比两个版本 strategy YAML 的 rules/ai_teams/元数据差异",
            handler=version_compare,
            agent_name="admin",
            tier="core",
        )
    )
