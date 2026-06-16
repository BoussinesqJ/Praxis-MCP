"""MCP 工具 - 进化引擎"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from praxis.engine.evolution import EvolutionEngine


def evaluate_evolution(
    strategy_name: str,
    investor: str,
    portfolio: str,
    workspace: str = ".",
) -> dict:
    """评估进化维度"""
    try:
        engine = EvolutionEngine(workspace)
        result = engine.evaluate(strategy_name, investor, portfolio)
        if result["success"]:
            result["data"]["formatted"] = engine.format_evaluation(result)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def evolve_strategy(
    strategy_name: str,
    investor: str,
    portfolio: str,
    workspace: str = ".",
) -> dict:
    """进化策略（需审批，GPT 架构底线）

    流程：
    1. 评估进化维度
    2. 生成进化建议
    3. 备份策略文件
    4. 返回修改预览（需人工审批后写入）
    """
    try:
        engine = EvolutionEngine(workspace)

        # 1. 评估
        evaluation = engine.evaluate(strategy_name, investor, portfolio)
        if not evaluation["success"]:
            return evaluation

        # 添加格式化输出
        evaluation["data"]["formatted"] = engine.format_evaluation(evaluation)

        # 2. 备份
        backup_path = engine.backup_strategy(strategy_name)

        # 3. 返回修改预览
        return {
            "success": True,
            "data": {
                "status": "pending_approval",
                "evaluation": evaluation["data"],
                "backup_path": backup_path,
                "message": "进化评估完成，策略文件已备份。需人工审批后执行修改。",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def auto_evolve(
    strategy_name: str,
    investor: str,
    portfolio: str,
    workspace: str = ".",
) -> dict:
    """一键自进化：评估 → 建议 → 备份 → 待审批

    事件驱动触发：每笔交易后 / 每日 NAV 记录后 / 哨兵状态变更时。
    结果自动落盘到 deliverables/evolution/。
    """
    try:
        engine = EvolutionEngine(workspace)

        # 1. 评估
        evaluation = engine.evaluate(strategy_name, investor, portfolio)
        if not evaluation["success"]:
            return evaluation

        evaluation["data"]["formatted"] = engine.format_evaluation(evaluation)

        # 2. 检查是否有需要进化的维度
        dimensions = evaluation["data"].get("dimensions", [])
        critical_dims = [d for d in dimensions if d.get("status") == "critical"]
        warning_dims = [d for d in dimensions if d.get("status") == "warning"]

        if not critical_dims and not warning_dims:
            return {
                "success": True,
                "data": {
                    "status": "no_action_needed",
                    "evaluation": evaluation["data"],
                    "message": "所有进化维度均在健康范围内，无需调整。",
                },
            }

        # 3. 备份
        backup_path = engine.backup_strategy(strategy_name)

        # 4. 生成进化建议
        suggestions = []
        for dim in critical_dims:
            suggestions.append({
                "dimension": dim["name"],
                "priority": "critical",
                "description": dim.get("desc", ""),
                "metric_value": dim.get("value", 0),
                "threshold": dim.get("threshold") or dim.get("range"),
            })
        for dim in warning_dims:
            suggestions.append({
                "dimension": dim["name"],
                "priority": "warning",
                "description": dim.get("desc", ""),
                "metric_value": dim.get("value", 0),
                "threshold": dim.get("threshold") or dim.get("range"),
            })

        # 5. 落盘
        deliverables_dir = Path(workspace) / "deliverables" / "evolution"
        deliverables_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = deliverables_dir / f"evolve_{strategy_name}_{timestamp}.md"

        report_lines = [
            f"# 进化评估报告: {strategy_name}",
            f"> 时间: {datetime.now().isoformat()}",
            f"> 投资者: {investor}",
            f"> 组合: {portfolio}",
            "",
            "## 评估结果",
            evaluation["data"].get("formatted", ""),
            "",
            "## 进化建议",
        ]
        for s in suggestions:
            report_lines.append(f"- **{s['priority'].upper()}** {s['dimension']}: {s['description']} (当前值={s['metric_value']}, 阈值={s['threshold']})")
        report_lines.extend([
            "",
            "## 状态",
            "pending_approval",
        ])

        report_path.write_text("\n".join(report_lines), encoding="utf-8")

        # 6. 自动归档到进化记忆（断点衔接）
        try:
            from praxis.tools.memory import record_evolution_memory
            record_evolution_memory(
                trigger_event="auto_evolve",
                strategy_name=strategy_name,
                evaluation_summary=f"临界: {len(critical_dims)}, 警告: {len(warning_dims)}",
                dimensions=dimensions,
                suggestions=suggestions,
                workspace=workspace,
            )
        except Exception:
            pass  # 记忆归档失败不影响进化结果

        # 7. 自动触发规则学习（断点衔接）
        try:
            from praxis.tools.adaptive import learn_rules
            learn_rules(workspace)
        except Exception:
            pass  # 规则学习失败不影响进化结果

        return {
            "success": True,
            "data": {
                "status": "pending_approval",
                "evaluation": evaluation["data"],
                "suggestions": suggestions,
                "backup_path": str(backup_path),
                "report_path": str(report_path),
                "critical_count": len(critical_dims),
                "warning_count": len(warning_dims),
                "message": f"发现 {len(critical_dims)} 个临界维度 + {len(warning_dims)} 个警告维度。策略已备份，报告已落盘。需人工审批后执行修改。",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
