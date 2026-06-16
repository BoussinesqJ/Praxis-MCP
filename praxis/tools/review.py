"""MCP 工具 - 复盘管理"""
from __future__ import annotations

import asyncio
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.engine.data.provider import CachedDataProvider
from praxis.engine.review_filler import ReviewFiller


def _get_filler(workspace: str = ".") -> ReviewFiller:
    """获取复盘填充器实例"""
    decisions_path = Path(workspace) / "data" / "decisions" / "decision_records.jsonl"
    ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
    recorder = FileDecisionRecorder(decisions_path)
    ledger = FileLedger(ledger_path)
    provider = CachedDataProvider()
    return ReviewFiller(recorder, ledger, provider)


async def fill_reviews(workspace: str = ".") -> dict:
    """自动回填待复盘的决策"""
    filler = _get_filler(workspace)
    try:
        results = await filler.fill_pending_reviews()
        summary = filler.get_summary()
        return {
            "success": True,
            "data": {
                "filled": results,
                "summary": {
                    "total_decisions": summary.total_decisions,
                    "pending_5d": summary.pending_5d,
                    "pending_20d": summary.pending_20d,
                    "pending_60d": summary.pending_60d,
                    "filled_count": summary.filled_count,
                },
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_review_summary(workspace: str = ".") -> dict:
    """获取复盘汇总"""
    try:
        filler = _get_filler(workspace)
        summary = filler.get_summary()
        return {
            "success": True,
            "data": {
                "total_decisions": summary.total_decisions,
                "pending_5d": summary.pending_5d,
                "pending_20d": summary.pending_20d,
                "pending_60d": summary.pending_60d,
                "filled_count": summary.filled_count,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_confidence_calibration(team: str, workspace: str = ".") -> dict:
    """获取指定团队的信心度校准"""
    try:
        filler = _get_filler(workspace)
        result = filler.calculate_confidence_calibration(team)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# 级联复盘体系 (Cascade Review)
# ═══════════════════════════════════════════════════════════════

def _get_evolution_engine(workspace: str = "."):
    """获取 EvolutionEngine 实例"""
    import os
    from praxis_sdk.meta.evolution import EvolutionEngine
    logs_dir = os.path.join(workspace, "outputs", "logs")
    return EvolutionEngine(logs_dir=logs_dir)


def generate_monthly_report(
    period: str,
    investor: str = "demo",
    portfolio: str = "core",
    workspace: str = ".",
) -> dict:
    """生成月度纪律代价复盘报告

    Args:
        period: 月份标识 (YYYY-MM)，如 "2026-06"
        investor: 投资者 ID
        portfolio: 组合 ID
        workspace: 工作目录

    Returns:
        Markdown 报告 + 原始 JSON 统计数据
    """
    import re
    try:
        if not re.match(r"^\d{4}-\d{2}$", period):
            return {"success": False, "error": f"无效的 period 格式: {period}，需要 YYYY-MM"}

        engine = _get_evolution_engine(workspace)

        # 纪律代价报告（Markdown）
        discipline_report = engine.generate_monthly_report(period)

        # 原始统计数据（JSON，供 AI 二次分析）
        cost = engine.calculate_discipline_cost(period)
        evolution = engine.check_meta_evolution(period)

        raw_stats = {
            "period": period,
            "total_interceptions": cost.total_interceptions,
            "opportunity_cost_total": round(cost.opportunity_cost_total, 3),
            "risk_mitigated_total": round(cost.risk_mitigated_total, 3),
            "net_benefit": round(cost.net_benefit, 3),
            "interception_ratio": round(cost.interception_ratio, 3),
            "meta_evolution_suggestion": cost.meta_evolution_suggestion,
            "should_evolve": evolution.should_evolve,
            "evolution_reason": evolution.reason,
            "suggested_changes": evolution.suggested_changes,
        }

        return {
            "success": True,
            "data": {
                "period": period,
                "discipline_report": discipline_report,
                "raw_stats": raw_stats,
                "timestamp": _timestamp(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_quarterly_report(
    quarter: str,
    investor: str = "demo",
    portfolio: str = "core",
    workspace: str = ".",
) -> dict:
    """生成季度复盘报告（聚合 3 个月纪律代价 + 进化评估）

    Args:
        quarter: 季度标识 (YYYY-Qx)，如 "2026-Q2"
        investor: 投资者 ID
        portfolio: 组合 ID
        workspace: 工作目录

    Returns:
        3 个月汇总 + 季度进化评估 + 参数修改建议
    """
    import re
    try:
        match = re.match(r"^(\d{4})-Q([1-4])$", quarter)
        if not match:
            return {"success": False, "error": f"无效的 quarter 格式: {quarter}，需要 YYYY-Qx (如 2026-Q2)"}

        year = int(match.group(1))
        q = int(match.group(2))
        months = [f"{year}-{(q-1)*3 + m:02d}" for m in range(1, 4)]

        engine = _get_evolution_engine(workspace)

        # 聚合 3 个月数据
        monthly_reports = []
        monthly_stats = []
        total_interceptions = 0
        total_opportunity = 0.0
        total_risk = 0.0

        for month in months:
            records = engine.load_records(month)
            cost = engine.calculate_discipline_cost(month)
            report_md = engine.generate_monthly_report(month)

            monthly_reports.append({
                "period": month,
                "report": report_md,
                "stats": {
                    "total_interceptions": cost.total_interceptions,
                    "opportunity_cost_total": round(cost.opportunity_cost_total, 3),
                    "risk_mitigated_total": round(cost.risk_mitigated_total, 3),
                    "net_benefit": round(cost.net_benefit, 3),
                },
            })
            monthly_stats.append(cost)
            total_interceptions += cost.total_interceptions
            total_opportunity += cost.opportunity_cost_total
            total_risk += cost.risk_mitigated_total

        # 季度汇总
        net_benefit = total_risk - total_opportunity
        ratio = total_risk / max(total_opportunity, 0.01)
        has_data = total_interceptions > 0

        quarterly_summary = {
            "quarter": quarter,
            "months": months,
            "total_interceptions": total_interceptions,
            "opportunity_cost_total": round(total_opportunity, 3),
            "risk_mitigated_total": round(total_risk, 3),
            "net_benefit": round(net_benefit, 3),
            "interception_ratio": round(ratio, 3),
            "has_sufficient_data": total_interceptions >= 5,
        }

        # 季度级进化评估（阈值比月度更宽松）
        if has_data and ratio < 1.0 and total_interceptions >= 10:
            evolution = {
                "should_evolve": True,
                "reason": f"季度拦截收益比 {ratio:.2f} < 1.0，累计 {total_interceptions} 次拦截",
                "suggested_changes": [
                    "考虑拓宽规则阈值",
                    "需要人工审核并确认是否执行元进化",
                ],
            }
        elif has_data:
            evolution = {
                "should_evolve": False,
                "reason": f"季度拦截收益比 {ratio:.2f}，规则整体有效" if ratio >= 1.0 else f"样本不足（{total_interceptions}次），继续观察",
                "suggested_changes": [],
            }
        else:
            evolution = {
                "should_evolve": False,
                "reason": "无拦截记录，数据积累中",
                "suggested_changes": [],
            }

        return {
            "success": True,
            "data": {
                "quarter": quarter,
                "monthly_reports": monthly_reports,
                "quarterly_summary": quarterly_summary,
                "evolution": evolution,
                "timestamp": _timestamp(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_annual_report(
    year: str,
    investor: str = "demo",
    portfolio: str = "core",
    workspace: str = ".",
) -> dict:
    """生成年度终极考核报告（12 个月聚合 + 铁律审计 + 重塑建议）

    Args:
        year: 年份 (YYYY)，如 "2026"
        investor: 投资者 ID
        portfolio: 组合 ID
        workspace: 工作目录

    Returns:
        年度汇总 + 铁律执行审计 + 重塑建议
    """
    import re
    try:
        if not re.match(r"^\d{4}$", year):
            return {"success": False, "error": f"无效的 year 格式: {year}，需要 YYYY"}

        engine = _get_evolution_engine(workspace)
        months = [f"{year}-{m:02d}" for m in range(1, 13)]

        # 聚合 12 个月
        monthly_stats = []
        total_interceptions = 0
        total_opportunity = 0.0
        total_risk = 0.0
        all_records = []

        for month in months:
            cost = engine.calculate_discipline_cost(month)
            monthly_stats.append({
                "period": month,
                "interceptions": cost.total_interceptions,
                "opportunity_cost": round(cost.opportunity_cost_total, 3),
                "risk_mitigated": round(cost.risk_mitigated_total, 3),
                "net_benefit": round(cost.net_benefit, 3),
            })
            total_interceptions += cost.total_interceptions
            total_opportunity += cost.opportunity_cost_total
            total_risk += cost.risk_mitigated_total
            all_records.extend(cost.records)

        net_benefit = total_risk - total_opportunity
        ratio = total_risk / max(total_opportunity, 0.01)

        # 铁律审计
        rule_audit = _audit_rules(all_records)

        # 重塑建议（Rule 1 + Rule 7 白名单）
        reshape_suggestions = _generate_reshape_suggestions(rule_audit)

        # 月度趋势
        monthly_trend = [
            {"period": s["period"], "net_benefit": s["net_benefit"]}
            for s in monthly_stats if s["interceptions"] > 0
        ]

        return {
            "success": True,
            "data": {
                "year": year,
                "annual_summary": {
                    "total_interceptions": total_interceptions,
                    "opportunity_cost_total": round(total_opportunity, 3),
                    "risk_mitigated_total": round(total_risk, 3),
                    "net_benefit": round(net_benefit, 3),
                    "interception_ratio": round(ratio, 3),
                    "has_sufficient_data": total_interceptions >= 12,
                },
                "monthly_breakdown": monthly_stats,
                "monthly_trend": monthly_trend,
                "rule_audit": rule_audit,
                "reshape_suggestions": reshape_suggestions,
                "timestamp": _timestamp(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _audit_rules(records) -> dict:
    """审计每条规则的年度表现"""
    rule_stats = {}
    for r in records:
        rule = r.rule
        if rule not in rule_stats:
            rule_stats[rule] = {
                "interceptions": 0,
                "opportunity_cost": 0.0,
                "risk_mitigated": 0.0,
            }
        rule_stats[rule]["interceptions"] += 1
        rule_stats[rule]["opportunity_cost"] += r.opportunity_cost_pct or 0
        rule_stats[rule]["risk_mitigated"] += r.risk_mitigated_pct or 0

    # 计算每条规则的拦截收益比
    for rule, stats in rule_stats.items():
        oc = stats["opportunity_cost"]
        rm = stats["risk_mitigated"]
        stats["ratio"] = round(rm / max(abs(oc), 0.01), 3)
        stats["opportunity_cost"] = round(oc, 3)
        stats["risk_mitigated"] = round(rm, 3)

    return rule_stats


def _generate_reshape_suggestions(rule_audit: dict) -> list:
    """生成铁律重塑建议

    安全白名单: Rule 1（ETF网格买入绝对豁免）和 Rule 7（价格到位即可买）
    永不建议废除或收紧。对账操作永不作为冗余剔除。
    """
    WHITELIST = {"Rule 1", "Rule 7"}
    suggestions = []

    for rule, stats in rule_audit.items():
        ratio = stats.get("ratio", 0)
        if rule in WHITELIST:
            suggestions.append(f"🔒 {rule}: 白名单豁免（ratio={ratio}），保持现状")
            continue
        if ratio < 0.5:
            suggestions.append(f"⚠️ {rule}: 拦截收益比仅 {ratio}，建议放宽阈值或废除")
        elif ratio > 5.0:
            suggestions.append(f"🔒 {rule}: 拦截收益比 {ratio}，规则极其有效，建议保持")
        elif ratio >= 1.0:
            suggestions.append(f"✅ {rule}: 拦截收益比 {ratio}，规则有效")
        else:
            suggestions.append(f"🔍 {rule}: 拦截收益比 {ratio}，建议观察")

    return suggestions


def _timestamp() -> str:
    from datetime import datetime
    return datetime.now().isoformat()
