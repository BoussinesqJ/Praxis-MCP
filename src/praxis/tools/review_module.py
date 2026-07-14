"""复盘 — review + cascade_review + market_weekly_review

v3.6:
- P0-1: _default_benchmark_index 复用 review_filler 中的实现
- P0-2: generate_market_weekly_review + _assemble_markdown
- P0-3: _build_risk_quality_section + _derive_holding_period_distribution
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from praxis.agents.base import Tool
from praxis.tools._schemas import (
    ReviewInput, CascadeReviewInput, MarketWeeklyReviewInput,
)

logger = logging.getLogger("praxis.review")


# ═══════════════════════════════════════════════════════════════
# 基础复盘工具
# ═══════════════════════════════════════════════════════════════


async def review(
    action: str, team: str | None = None, _deps: dict | None = None,
) -> dict:
    """决策复盘：fill/summary/calibration"""
    filler = _deps.get("review_filler") if _deps else None
    if filler is None:
        return {"success": False, "error": "ReviewFiller未注入"}
    if action == "fill":
        return await filler.fill_pending_reviews()
    elif action == "summary":
        return await filler.get_summary()
    elif action == "calibration":
        if not team:
            return {"success": False, "error": "需要 team 参数"}
        return await filler.get_confidence_calibration(team)
    return {"success": False, "error": f"未知 action: {action}"}


# ═══════════════════════════════════════════════════════════════
# 级联复盘体系 (Cascade Review)
# ═══════════════════════════════════════════════════════════════


def _get_evolution_engine(workspace: str = "."):
    """获取 EvolutionEngine 实例（如果可用）"""
    try:
        from praxis_sdk.meta.evolution import EvolutionEngine
        import os
        logs_dir = os.path.join(workspace, "outputs", "logs")
        return EvolutionEngine(logs_dir=logs_dir)
    except ImportError:
        return None


def _timestamp() -> str:
    return datetime.now().isoformat()


async def cascade_review(
    mode: str, investor: str = "demo", portfolio: str = "core",
    period: str = "", external_data_json: str = "",
    _deps: dict | None = None,
) -> dict:
    """级联复盘：monthly/quarterly/annual

    v3.6: 支持月度纪律代价复盘 + 季度/年度聚合。
    如果 EvolutionEngine 不可用，返回提示信息。
    """
    import re

    # P0: 外部数据路径
    if external_data_json and external_data_json.strip():
        return await _cascade_review_external(
            mode, external_data_json, investor, portfolio, period, _deps,
        )

    workspace = str(_deps.get("workspace", ".")) if _deps else "."

    if mode == "monthly":
        return await _generate_monthly_report(
            period, investor, portfolio, workspace, _deps,
        )
    elif mode == "quarterly":
        return await _generate_quarterly_report(
            period, investor, portfolio, workspace, _deps,
        )
    elif mode == "annual":
        return await _generate_annual_report(
            period, investor, portfolio, workspace, _deps,
        )
    else:
        return {
            "success": False,
            "error": f"未知 mode: {mode}，支持 monthly/quarterly/annual",
        }


async def _cascade_review_external(
    mode: str, external_data_json: str,
    investor: str, portfolio: str, period: str,
    _deps: dict | None,
) -> dict:
    """使用外部数据执行级联复盘

    Args:
        mode: 复盘模式
        external_data_json: ExternalDataPayload JSON 字符串
        investor: 投资者 ID
        portfolio: 组合 ID
        period: 时间范围
        _deps: 依赖注入

    Returns:
        级联复盘结果 dict
    """
    try:
        raw = json.loads(external_data_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}"}

    from praxis.core.schemas import ExternalDataPayload

    try:
        payload = ExternalDataPayload.model_validate(raw)
    except Exception as e:
        return {"success": False, "error": f"外部数据校验失败: {e}"}

    return {
        "success": True,
        "data": {
            "mode": mode,
            "investor": investor,
            "portfolio": portfolio,
            "period": payload.period or period,
            "external_data": {
                "sentinel": payload.sentinel,
                "portfolio": payload.portfolio,
                "quotes": payload.quotes,
                "klines": payload.klines,
                "valuation": payload.valuation,
                "performance": payload.performance,
            },
            "timestamp": _timestamp(),
            "source": "external",
        },
    }


async def _generate_monthly_report(
    period: str, investor: str, portfolio: str,
    workspace: str, _deps: dict | None,
) -> dict:
    """生成月度纪律代价复盘报告"""
    import re
    try:
        if not re.match(r"^\d{4}-\d{2}$", period):
            return {"success": False, "error": f"无效的 period 格式: {period}，需要 YYYY-MM"}

        engine = _get_evolution_engine(workspace)
        if engine is None:
            # 无 EvolutionEngine：只生成风险质量章节
            risk_quality_section = await _build_risk_quality_section(
                investor, portfolio, workspace, _deps,
            )
            discipline_report = (
                f"## 月度纪律代价报告 ({period})\n\n"
                f"> ℹ️ EvolutionEngine 不可用（praxis_sdk 未安装），"
                f"仅展示风险质量指标。\n"
            )
            full_report = discipline_report  # risk_quality_section 在 data dict 中独立返回
            return {
                "success": True,
                "data": {
                    "period": period,
                    "discipline_report": full_report,
                    "risk_quality_section": risk_quality_section,
                    "timestamp": _timestamp(),
                },
            }

        # EvolutionEngine 可用：完整报告
        discipline_report = engine.generate_monthly_report(period)
        risk_quality_section = await _build_risk_quality_section(
            investor, portfolio, workspace, _deps,
        )

        cost = engine.calculate_discipline_cost(period)
        evolution = engine.check_meta_evolution(period)

        full_report = discipline_report  # risk_quality_section 在 data dict 中独立返回

        return {
            "success": True,
            "data": {
                "period": period,
                "discipline_report": full_report,
                "risk_quality_section": risk_quality_section,
                "raw_stats": {
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
                },
                "timestamp": _timestamp(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _generate_quarterly_report(
    quarter: str, investor: str, portfolio: str,
    workspace: str, _deps: dict | None,
) -> dict:
    """生成季度复盘报告"""
    import re
    try:
        match = re.match(r"^(\d{4})-Q([1-4])$", quarter)
        if not match:
            return {"success": False, "error": f"无效的 quarter 格式: {quarter}，需要 YYYY-Qx"}

        year = int(match.group(1))
        q = int(match.group(2))
        months = [f"{year}-{(q-1)*3 + m:02d}" for m in range(1, 4)]

        engine = _get_evolution_engine(workspace)
        if engine is None:
            risk_quality_section = await _build_risk_quality_section(
                investor, portfolio, workspace, _deps,
            )
            return {
                "success": True,
                "data": {
                    "quarter": quarter,
                    "risk_quality_section": risk_quality_section,
                    "note": "EvolutionEngine 不可用，仅展示风险质量指标",
                    "timestamp": _timestamp(),
                },
            }

        monthly_stats = []
        total_interceptions = 0
        total_opportunity = 0.0
        total_risk = 0.0

        for month in months:
            cost = engine.calculate_discipline_cost(month)
            monthly_stats.append(cost)
            total_interceptions += cost.total_interceptions
            total_opportunity += cost.opportunity_cost_total
            total_risk += cost.risk_mitigated_total

        net_benefit = total_risk - total_opportunity
        ratio = total_risk / max(total_opportunity, 0.01)
        has_data = total_interceptions > 0

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
                "reason": (
                    f"季度拦截收益比 {ratio:.2f}，规则整体有效"
                    if ratio >= 1.0 else f"样本不足（{total_interceptions}次），继续观察"
                ),
                "suggested_changes": [],
            }
        else:
            evolution = {
                "should_evolve": False,
                "reason": "无拦截记录，数据积累中",
                "suggested_changes": [],
            }

        risk_quality_section = await _build_risk_quality_section(
            investor, portfolio, workspace, _deps,
        )

        return {
            "success": True,
            "data": {
                "quarter": quarter,
                "quarterly_summary": {
                    "quarter": quarter,
                    "months": months,
                    "total_interceptions": total_interceptions,
                    "opportunity_cost_total": round(total_opportunity, 3),
                    "risk_mitigated_total": round(total_risk, 3),
                    "net_benefit": round(net_benefit, 3),
                    "interception_ratio": round(ratio, 3),
                    "has_sufficient_data": total_interceptions >= 5,
                },
                "evolution": evolution,
                "risk_quality_section": risk_quality_section,
                "timestamp": _timestamp(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _generate_annual_report(
    year: str, investor: str, portfolio: str,
    workspace: str, _deps: dict | None,
) -> dict:
    """生成年度终极考核报告"""
    import re
    try:
        if not re.match(r"^\d{4}$", year):
            return {"success": False, "error": f"无效的 year 格式: {year}，需要 YYYY"}

        engine = _get_evolution_engine(workspace)
        if engine is None:
            risk_quality_section = await _build_risk_quality_section(
                investor, portfolio, workspace, _deps,
            )
            return {
                "success": True,
                "data": {
                    "year": year,
                    "risk_quality_section": risk_quality_section,
                    "note": "EvolutionEngine 不可用，仅展示风险质量指标",
                    "timestamp": _timestamp(),
                },
            }

        months = [f"{year}-{m:02d}" for m in range(1, 13)]
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

        rule_audit = _audit_rules(all_records)
        reshape_suggestions = _generate_reshape_suggestions(rule_audit)

        monthly_trend = [
            {"period": s["period"], "net_benefit": s["net_benefit"]}
            for s in monthly_stats if s["interceptions"] > 0
        ]

        risk_quality_section = await _build_risk_quality_section(
            investor, portfolio, workspace, _deps,
        )

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
                "risk_quality_section": risk_quality_section,
                "timestamp": _timestamp(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _audit_rules(records) -> dict:
    """审计每条规则的年度表现"""
    rule_stats: dict[str, dict] = {}
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

    for rule, stats in rule_stats.items():
        oc = stats["opportunity_cost"]
        rm = stats["risk_mitigated"]
        stats["ratio"] = round(rm / max(abs(oc), 0.01), 3)
        stats["opportunity_cost"] = round(oc, 3)
        stats["risk_mitigated"] = round(rm, 3)

    return rule_stats


def _generate_reshape_suggestions(rule_audit: dict) -> list:
    """生成铁律重塑建议"""
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


# ═══════════════════════════════════════════════════════════════
# P0-2: 市场环境周度复盘
# ═══════════════════════════════════════════════════════════════

_INDEX_TO_ETF: dict[str, str] = {
    "000300": "510310",  # 沪深300ETF
    "399006": "159915",  # 创业板ETF
    "000905": "510500",  # 中证500ETF
}


def _fallback_index_to_etf(index_code: str) -> str:
    """将指数代码映射为对应的 ETF 代理代码（用于降级路径查K线）"""
    return _INDEX_TO_ETF.get(index_code, index_code)


async def _generate_market_weekly_external(
    market_data_json: str,
    week_ending: str = "",
    index_code: str = "000300",
) -> dict:
    """使用外部市场数据生成周报

    Args:
        market_data_json: MarketDataPayload JSON 字符串
        week_ending: 周结束日期
        index_code: 基准指数代码

    Returns:
        周报结果 dict
    """
    if not market_data_json or not market_data_json.strip():
        return {"success": False, "error": "缺少外部市场数据"}

    try:
        raw = json.loads(market_data_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}"}

    from praxis.core.schemas import MarketDataPayload

    try:
        payload = MarketDataPayload.model_validate(raw)
    except Exception as e:
        return {"success": False, "error": f"市场数据校验失败: {e}"}

    actual_week_ending = payload.week_ending or week_ending
    actual_index_code = payload.index_code or index_code
    date_range = payload.date_range or {}

    report = _assemble_markdown(
        week_ending=actual_week_ending,
        index_code=actual_index_code,
        date_range=date_range,
        dimensions=payload.dimensions,
    )

    return {
        "success": True,
        "data": {
            "report": report,
            "dimensions": payload.dimensions,
            "week_ending": actual_week_ending,
            "date_range": date_range,
            "timestamp": _timestamp(),
            "source": "external",
        },
    }


async def generate_market_weekly_review(
    week_ending: str, index_code: str = "000300",
    transport: str | None = None, market_data_json: str = "",
    _deps: dict | None = None,
) -> dict:
    """生成市场环境周度复盘报告

    Args:
        week_ending: 周结束日期 YYYY-MM-DD
        index_code: 大盘基准指数（默认 000300 沪深300）
        transport: 市场数据采集传输（MCP server 注入；测试时可 mock）
        market_data_json: 外部市场数据（MarketDataPayload JSON）

    Returns:
        {"success": bool, "data": {"report": str, "dimensions": dict, "week_ending": str}}
    """
    # P0: 外部数据路径
    if market_data_json and market_data_json.strip():
        return await _generate_market_weekly_external(
            market_data_json, week_ending, index_code,
        )

    from praxis.engine.data.market_weekly import MarketWeeklyCollector

    # transport 参数：优先使用显式传入，其次从 _deps 查找
    actual_transport = transport
    if actual_transport is None and _deps:
        actual_transport = _deps.get("market_data_transport")

    if actual_transport is None:
        # 降级模式：无 MCP transport，创建本地 WestockTransport
        # trend 维度可用（通过 DataProvider K 线计算），
        # sector/fund_flow/sentiment/macro 返回结构化错误信息
        data_provider = _deps.get("data_provider") if _deps else None

        if data_provider is None:
            return {
                "success": False,
                "error": "transport 参数为必填项，且 _deps 中未找到 data_provider",
            }

        try:
            from praxis.engine.data.westock_transport import WestockTransport

            actual_transport = WestockTransport(data_provider=data_provider)
            collector = MarketWeeklyCollector(actual_transport)
            result = await collector.collect_all(week_ending, index_code)

            if not result["success"]:
                return {
                    "success": False,
                    "error": result.get("error", "所有数据源不可用"),
                    "data": {
                        "dimensions": result.get("dimensions", {}),
                        "week_ending": week_ending,
                        "mode": "degraded",
                    },
                }

            report = _assemble_markdown(
                week_ending=result["week_ending"],
                index_code=index_code,
                date_range=result["date_range"],
                dimensions=result["dimensions"],
            )

            return {
                "success": True,
                "data": {
                    "report": report,
                    "dimensions": result["dimensions"],
                    "week_ending": result["week_ending"],
                    "date_range": result["date_range"],
                    "timestamp": _timestamp(),
                    "mode": "degraded",
                },
            }
        except Exception as e:
            logger.error(
                "市场周报降级模式失败 week_ending=%s error=%s", week_ending, e
            )
            return {"success": False, "error": str(e)}

    try:
        collector = MarketWeeklyCollector(actual_transport)
        result = await collector.collect_all(week_ending, index_code)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "所有数据源不可用"),
                "data": {
                    "dimensions": result.get("dimensions", {}),
                    "week_ending": week_ending,
                },
            }

        report = _assemble_markdown(
            week_ending=result["week_ending"],
            index_code=index_code,
            date_range=result["date_range"],
            dimensions=result["dimensions"],
        )

        return {
            "success": True,
            "data": {
                "report": report,
                "dimensions": result["dimensions"],
                "week_ending": result["week_ending"],
                "date_range": result["date_range"],
                "timestamp": _timestamp(),
            },
        }
    except Exception as e:
        logger.error("市场周报生成失败 week_ending=%s error=%s", week_ending, e)
        return {"success": False, "error": str(e)}


def _assemble_markdown(
    week_ending: str,
    index_code: str,
    date_range: dict,
    dimensions: dict,
) -> str:
    """组装 5 节 Markdown 周报

    每节嵌入数据 + 一句话摘要。
    某维度失败 → 对应章节标注"数据获取失败: {error}"
    """
    start_date = date_range.get("start", "")
    end_date = date_range.get("end", "")

    lines = [
        f"## 市场环境周报 ({end_date})",
        f"",
        f"**基准指数**: {index_code} | **数据区间**: {start_date} ~ {end_date}",
        f"",
    ]

    # ── 一、大盘趋势 ──
    lines.append("### 一、大盘趋势")
    trend = dimensions.get("trend", {})
    if trend.get("error"):
        lines.append(f"> ⚠️ 数据获取失败: {trend['error']}")
    else:
        weekly_change = trend.get("weekly_change_pct")
        volume_trend = trend.get("volume_trend", "—")
        ma_positions = trend.get("ma_positions", {})
        if weekly_change is not None:
            lines.append(f"- **周涨跌幅**: {weekly_change:+.2f}%")
        else:
            lines.append(f"- **周涨跌幅**: —")
        lines.append(f"- **量能趋势**: {volume_trend}")
        if ma_positions:
            ma_str = " / ".join(f"{k}: {v}" for k, v in ma_positions.items())
            lines.append(f"- **均线位置**: {ma_str}")
        if weekly_change is not None:
            if weekly_change > 0:
                lines.append(f"> 📈 本周大盘上涨 {weekly_change:.2f}%，整体偏多。")
            else:
                lines.append(f"> 📉 本周大盘下跌 {abs(weekly_change):.2f}%，整体偏空。")
    lines.append(f"")

    # ── 二、题材轮动 ──
    lines.append("### 二、题材轮动")
    sector = dimensions.get("sector", {})
    if sector.get("error"):
        lines.append(f"> ⚠️ 数据获取失败: {sector['error']}")
    else:
        top_gainers = sector.get("top_gainers", [])
        top_losers = sector.get("top_losers", [])
        consecutive_hot = sector.get("consecutive_hot", [])

        if top_gainers:
            gainers_str = "、".join(
                f"{g.get('name', '?')}({g.get('change_pct', 0):+.1f}%)"
                for g in top_gainers[:5]
            )
            lines.append(f"- **涨幅 TOP5**: {gainers_str}")
        else:
            lines.append(f"- **涨幅 TOP5**: —")

        if top_losers:
            losers_str = "、".join(
                f"{l.get('name', '?')}({l.get('change_pct', 0):+.1f}%)"
                for l in top_losers[:5]
            )
            lines.append(f"- **跌幅 TOP5**: {losers_str}")
        else:
            lines.append(f"- **跌幅 TOP5**: —")

        if consecutive_hot:
            hot_str = "、".join(h.get("name", "?") for h in consecutive_hot[:3])
            lines.append(f"- **连续热点**: {hot_str}")

        if top_gainers:
            lines.append(f"> 🔥 本周题材集中在 {top_gainers[0].get('name', '热点板块')} 方向。")
    lines.append(f"")

    # ── 三、资金流向 ──
    lines.append("### 三、资金流向")
    fund_flow = dimensions.get("fund_flow", {})
    if fund_flow.get("error"):
        lines.append(f"> ⚠️ 数据获取失败: {fund_flow['error']}")
    else:
        main_force = fund_flow.get("main_force_net")
        north_bound = fund_flow.get("north_bound_net")
        etf_top5 = fund_flow.get("etf_inflow_top5", [])

        if main_force is not None:
            direction = "流入" if main_force > 0 else "流出"
            lines.append(f"- **主力周净额**: {main_force:+.2f}亿（{direction}）")
        else:
            lines.append(f"- **主力周净额**: —")

        if north_bound is not None:
            direction = "流入" if north_bound > 0 else "流出"
            lines.append(f"- **北向周净额**: {north_bound:+.2f}亿（{direction}）")
        else:
            lines.append(f"- **北向周净额**: —")

        if etf_top5:
            etf_str = "、".join(
                f"{e.get('name', '?')}({e.get('net_inflow', 0):+.1f}亿)"
                for e in etf_top5[:5]
            )
            lines.append(f"- **ETF 净流入 TOP5**: {etf_str}")

        if main_force is not None and main_force > 0:
            lines.append(f"> 💰 主力资金本周净流入，市场承接力较强。")
        elif main_force is not None:
            lines.append(f"> 💸 主力资金本周净流出，注意风险。")
    lines.append(f"")

    # ── 四、情绪温度 ──
    lines.append("### 四、情绪温度")
    sentiment = dimensions.get("sentiment", {})
    if sentiment.get("error"):
        lines.append(f"> ⚠️ 数据获取失败: {sentiment['error']}")
    else:
        limit_ratio = sentiment.get("avg_limit_up_down_ratio")
        avg_turnover = sentiment.get("avg_turnover")
        weekly_vol = sentiment.get("weekly_volatility")

        if limit_ratio is not None:
            lines.append(f"- **日均涨跌停比**: {limit_ratio:.2f}")
        else:
            lines.append(f"- **日均涨跌停比**: —")

        if avg_turnover is not None:
            lines.append(f"- **日均成交额**: {avg_turnover:.0f}亿")
        else:
            lines.append(f"- **日均成交额**: —")

        if weekly_vol is not None:
            lines.append(f"- **周波动率**: {weekly_vol:.2f}%")
        else:
            lines.append(f"- **周波动率**: —")

        if limit_ratio is not None and limit_ratio > 1.5:
            lines.append(f"> 🟢 市场情绪偏暖，涨停多于跌停。")
        elif limit_ratio is not None:
            lines.append(f"> 🔴 市场情绪偏冷，注意风险偏好变化。")
    lines.append(f"")

    # ── 五、宏观事件 ──
    lines.append("### 五、宏观事件")
    macro = dimensions.get("macro", {})
    if macro.get("error"):
        lines.append(f"> ⚠️ 数据获取失败: {macro['error']}")
    else:
        events = macro.get("events", [])
        if events:
            for evt in events[:5]:
                evt_date = evt.get("date", "?")
                evt_title = evt.get("title", evt.get("summary", "—"))
                lines.append(f"- **{evt_date}**: {evt_title}")
        else:
            lines.append(f"- 本周暂无重大宏观事件")
    lines.append(f"")

    lines.append(f"---")
    lines.append(f"*生成时间：{_timestamp()}*")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# P0-3: 风险质量维度
# ═══════════════════════════════════════════════════════════════


async def _build_risk_quality_section(
    investor: str, portfolio: str,
    workspace: str = ".", _deps: dict | None = None,
) -> str:
    """构建"风险与质量"Markdown 章节

    调用 performance 指标，从 Transaction 推导持仓周期分布。
    决策数 < 5 → 标注"数据积累中"。
    """
    from praxis.core.ledger import FileLedger
    from praxis.engine.performance import _derive_holding_period_distribution

    logger.info("构建风险质量章节 investor=%s portfolio=%s", investor, portfolio)

    lines = [
        f"### 二、风险与质量",
        f"",
    ]

    # 获取绩效指标
    perf_calc = _deps.get("performance_calculator") if _deps else None

    if perf_calc is None:
        lines.append(f"> ⚠️ 绩效计算器未注入")
        lines.append(f"")
        return "\n".join(lines)

    try:
        perf_result = perf_calc.calculate(investor, portfolio)
        logger.info("风险质量章节 performance 调用成功 investor=%s", investor)
    except Exception as e:
        logger.error("风险质量章节 performance 调用失败 investor=%s error=%s", investor, e)
        lines.append(f"> ⚠️ 绩效数据获取失败: {str(e)}")
        lines.append(f"")
        return "\n".join(lines)

    if not perf_result.get("success"):
        logger.warning("风险质量章节 performance 返回失败 investor=%s error=%s",
                       investor, perf_result.get("error"))
        lines.append(f"> ⚠️ 绩效数据获取失败: {perf_result.get('error', '未知错误')}")
        lines.append(f"")
        return "\n".join(lines)

    perf_data = perf_result.get("data", {})

    buy_count = 0
    sell_count = 0
    # 从交易记录统计买卖次数
    ledger = _deps.get("ledger") if _deps else None
    if ledger:
        txs = ledger.list(limit=1000)
        buy_count = sum(1 for t in txs if str(getattr(t, 'tx_type', '')) in ('buy', 'subscribe'))
        sell_count = sum(1 for t in txs if str(getattr(t, 'tx_type', '')) in ('sell', 'redeem'))
    total_decisions = buy_count + sell_count

    # N < 5 样本量保护
    if total_decisions < 5:
        lines.append(f"> ℹ️ 数据积累中（当前 {total_decisions} 笔交易，需要 ≥5 笔），以下指标仅供参考。")
        lines.append(f"")

    # 风险指标表格
    lines.append(f"| 指标 | 数值 | 说明 |")
    lines.append(f"|:---|:---|:---|")

    max_dd = perf_data.get("max_drawdown", 0)
    if total_decisions < 5:
        lines.append(f"| 最大回撤 | {max_dd:.2%} | 数据积累中（{total_decisions}笔交易） |")
    else:
        lines.append(f"| 最大回撤 | {max_dd:.2%} | — |")

    win_rate = perf_data.get("win_rate", 0)
    if total_decisions < 5:
        lines.append(f"| 胜率 | {win_rate:.1%} | 数据积累中（{total_decisions}笔交易） |")
    else:
        lines.append(f"| 胜率 | {win_rate:.1%} | — |")

    pl_ratio = perf_data.get("profit_loss_ratio", 0)
    if total_decisions < 5:
        lines.append(f"| 盈亏比 | {pl_ratio:.2f} | 数据积累中（{total_decisions}笔交易） |")
    else:
        lines.append(f"| 盈亏比 | {pl_ratio:.2f} | — |")

    sharpe = perf_data.get("sharpe_ratio", 0)
    if sharpe == 0 and total_decisions < 5:
        lines.append(f"| 夏普比率 | — | 暂无足够净值数据，数据积累中（{total_decisions}笔交易） |")
    elif sharpe == 0:
        lines.append(f"| 夏普比率 | — | 暂无足够净值数据 |")
    else:
        lines.append(f"| 夏普比率 | {sharpe:.2f} | — |")

    calmar = perf_data.get("calmar_ratio", 0)
    if calmar == 0 and max_dd == 0:
        lines.append(f"| 卡玛比率 | — | 回撤为零，无法计算 |")
    else:
        lines.append(f"| 卡玛比率 | {calmar:.2f} | — |")

    lines.append(f"")

    # 持仓周期分布
    lines.append(f"#### 持仓周期分布")
    lines.append(f"")

    try:
        ledger_obj = _deps.get("ledger") if _deps else None
        if ledger_obj:
            holding_dist = _derive_holding_period_distribution(ledger_obj)

            total_paired = holding_dist.get("total_paired", 0)
            unpaired = holding_dist.get("unpaired", 0)

            if total_paired == 0:
                lines.append(f"> ℹ️ 暂无卖出记录，持仓周期分布无法统计。")
            else:
                lines.append(f"| 持仓周期 | 次数 | 占比 |")
                lines.append(f"|:---|:---|:---|")
                for bucket, label in [
                    ("<3d", "<3天"), ("3-7d", "3-7天"),
                    ("7-20d", "7-20天"), (">20d", ">20天"),
                ]:
                    count = holding_dist.get(bucket, 0)
                    pct = (count / total_paired * 100) if total_paired > 0 else 0
                    lines.append(f"| {label} | {count} | {pct:.0f}% |")

                if unpaired > 0:
                    lines.append(f"")
                    lines.append(f"> ℹ️ {unpaired} 笔卖出未能配对到对应买入记录。")

                if total_decisions < 5:
                    lines.append(f"")
                    lines.append(f"> ℹ️ 数据积累中（当前 {total_paired} 笔配对，需要 ≥5 笔）。")
        else:
            lines.append(f"> ℹ️ 账本数据未注入，持仓周期分布无法统计。")
    except Exception as e:
        logger.warning("持仓周期分布推导失败: %s", e)
        lines.append(f"> ⚠️ 持仓周期分布推导失败: {str(e)}")

    lines.append(f"")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════════════════════════


def register(registry) -> None:
    """注册所有复盘相关工具"""
    registry.register(Tool(
        name="review",
        description="决策复盘：fill/summary/calibration",
        input_schema=ReviewInput,
        handler=review,
        agent_name="review",
        tier="core",
    ))
    registry.register(Tool(
        name="cascade_review",
        description="级联复盘：monthly/quarterly/annual",
        input_schema=CascadeReviewInput,
        handler=cascade_review,
        agent_name="review",
        tier="core",
    ))
    registry.register(Tool(
        name="generate_market_weekly_review",
        description="市场环境周度复盘：5维度（大盘趋势/题材轮动/资金流向/情绪温度/宏观事件）Markdown报告",
        input_schema=MarketWeeklyReviewInput,
        handler=generate_market_weekly_review,
        agent_name="review",
        tier="core",
    ))
