"""全量复盘聚合器 — 6 维度并行编排 (P1-2)

并行调用 portfolio / sentinel / performance / valuation / decision / market，
每个维度独立 try/except 容错，汇总为 ReviewSnapshot dict。
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

from praxis.agents.base import Tool

logger = logging.getLogger("praxis.full_review")

# 指数 → ETF 代理映射
_INDEX_TO_ETF: dict[str, str] = {
    "000300": "510310",
    "399006": "159915",
    "000905": "510500",
}


async def full_review(
    investor: str = "",
    portfolio: str = "",
    week_ending: str = "",
    index_code: str = "000300",
    external_data_json: str = "",
    _deps: dict | None = None,
) -> dict:
    """全量复盘聚合：6 维度并行编排，汇总为统一快照

    Args:
        investor: 投资者 ID
        portfolio: 组合 ID
        week_ending: 周结束日期 YYYY-MM-DD，默认最新周五
        index_code: 基准指数代码
        external_data_json: 外部数据（ExternalDataPayload JSON）
        _deps: 依赖注入

    Returns:
        {"success": bool, "data": {"snapshot": dict, "errors": [...]}}
    """
    # P0: 外部数据路径
    if external_data_json and external_data_json.strip():
        return await _full_review_external(
            investor, portfolio, week_ending, index_code, external_data_json,
        )

    deps = _deps or {}

    review_filler = deps.get("review_filler")
    reconciliation_engine = deps.get("reconciliation_engine")
    sentinel_engine = deps.get("sentinel_engine")
    performance_calculator = deps.get("performance_calculator")
    data_provider = deps.get("data_provider")

    # 解析 week_ending
    if not week_ending:
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7
        latest_friday = today - timedelta(days=days_since_friday)
        week_ending = latest_friday.strftime("%Y-%m-%d")

    start_date = (datetime.strptime(week_ending, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d")

    # ═══════════════════════════════════════════════════════════
    # 内部协程：每个维度独立容错
    # ═══════════════════════════════════════════════════════════

    async def _collect_portfolio() -> dict:
        """portfolio 维度：从 reconciliation_engine 获取组合快照

        reconcile() 返回 PortfolioState 对象（非 dict），需按对象属性访问。
        """
        try:
            if reconciliation_engine is None:
                return {"error": "reconciliation_engine 未注入"}

            state = await reconciliation_engine.reconcile(investor, portfolio)
            # reconcile 返回 PortfolioState 对象
            if state is None:
                return {"error": "reconcile 返回空"}

            total_assets = float(getattr(state, "total_assets", 0))
            cash = getattr(state, "cash", None)
            if cash is not None:
                total_cash = float(getattr(cash, "total_cash", 0))
            else:
                total_cash = 0.0
            cash_ratio_pct = round((total_cash / total_assets * 100), 2) if total_assets > 0 else 0.0

            positions = getattr(state, "positions", [])
            # positions 是 list[PositionState]，转为 dict 列表便于序列化
            holdings = []
            for p in positions:
                if hasattr(p, "model_dump"):
                    holdings.append(p.model_dump())
                else:
                    holdings.append({
                        "ticker": getattr(p, "ticker", ""),
                        "name": getattr(p, "name", ""),
                        "current_price": getattr(p, "current_price", 0),
                        "quantity": getattr(p, "quantity", 0),
                        "market_value": getattr(p, "market_value", 0),
                    })

            return {
                "total_assets": total_assets,
                "nav": float(getattr(state, "nav", 1.0)),
                "positions": len(positions),
                "cash_ratio_pct": cash_ratio_pct,
                "holdings": holdings,
            }
        except Exception as e:
            logger.warning("full_review portfolio failed: %s", e)
            return {"error": str(e)}

    async def _collect_sentinel() -> dict:
        """sentinel 维度：哨兵扫描"""
        try:
            if sentinel_engine is None:
                return {"error": "sentinel_engine 未注入"}

            result = await sentinel_engine.scan()
            sentinel_details: list[dict] = []
            raw_sentinels = result.get("sentinels", {})
            if isinstance(raw_sentinels, dict):
                for ticker, info in raw_sentinels.items():
                    if isinstance(info, dict):
                        sentinel_details.append({
                            "ticker": ticker,
                            "name": info.get("name", ""),
                            "trend": info.get("trend", "unknown"),
                            "layer": info.get("layer", ""),
                        })

            return {
                "overall_signal": result.get("state", ""),
                "bullish_count": result.get("bullish_count", 0),
                "total": result.get("total", len(sentinel_details)),
                "position_limit_pct": float(result.get("position_limit_pct", 0)),
                "sentinel_details": sentinel_details,
            }
        except Exception as e:
            logger.warning("full_review sentinel failed: %s", e)
            return {"error": str(e)}

    async def _collect_performance() -> dict:
        """performance 维度：绩效指标"""
        try:
            if performance_calculator is None:
                return {"error": "performance_calculator 未注入"}

            result = performance_calculator.calculate(investor, portfolio)
            if not result.get("success"):
                return {"error": result.get("error", "performance 计算失败")}

            data = result.get("data", {})
            return {
                "total_return": float(data.get("total_return", 0)),
                "annualized_return": float(data.get("annualized_return", 0)),
                "benchmark_return": float(data.get("benchmark_return", 0)),
                "excess_return": float(data.get("excess_return", 0)),
                "max_drawdown": float(data.get("max_drawdown", 0)),
                "volatility": float(data.get("volatility", 0)),
                "sharpe_ratio": data.get("sharpe_ratio"),
                "calmar_ratio": data.get("calmar_ratio"),
                "win_rate": float(data.get("win_rate", 0)) if data.get("win_rate") is not None else None,
                "profit_loss_ratio": data.get("profit_loss_ratio"),
            }
        except Exception as e:
            logger.warning("full_review performance failed: %s", e)
            return {"error": str(e)}

    async def _collect_valuation() -> dict:
        """valuation 维度：PE 分位"""
        try:
            from praxis.engine.valuation import get_index_pe_percentile

            result = await get_index_pe_percentile(index_code)
            if result is None:
                return {"error": f"无法获取 {index_code} 的 PE 分位数据"}

            pe_pct = result.get("percentile_all")
            level = result.get("valuation_level")
            if pe_pct is not None and pe_pct < 30:
                level = "undervalued"
            elif pe_pct is not None and pe_pct > 80:
                level = "overvalued"
            else:
                level = "fair"

            return {
                "pe_percentile": result.get("percentile_all"),
                "pb_percentile": result.get("pb_percentile"),
                "dividend_yield": result.get("dividend_yield"),
                "level": level,
                "current_pe": result.get("current_pe"),
                "pe_30pct": result.get("pe_30pct"),
                "pe_80pct": result.get("pe_80pct"),
            }
        except Exception as e:
            logger.warning("full_review valuation failed: %s", e)
            return {"error": str(e)}

    async def _collect_decision_reviews() -> dict:
        """decision_reviews 维度：决策复盘汇总"""
        try:
            if review_filler is None:
                return {"error": "review_filler 未注入"}

            result = await review_filler.get_summary()
            if not result.get("success"):
                return {"error": result.get("error", "review summary 失败")}

            data = result.get("data", {})
            return {
                "total_decisions": data.get("total_decisions", 0),
                "filled_count": data.get("filled_count", 0),
                "pending_5d": data.get("pending_5d", 0),
                "pending_20d": data.get("pending_20d", 0),
                "pending_60d": data.get("pending_60d", 0),
                "avg_actual_return_5d": data.get("avg_actual_return_5d"),
                "avg_alpha_5d": data.get("avg_alpha_5d"),
                "reviews": data.get("reviews", []),
            }
        except Exception as e:
            logger.warning("full_review decision_reviews failed: %s", e)
            return {"error": str(e)}

    async def _collect_market() -> dict:
        """market 维度：大盘趋势（简化版，仅 trend）"""
        try:
            if data_provider is None:
                return {"error": "data_provider 未注入"}

            etf_code = _INDEX_TO_ETF.get(index_code, index_code)
            kline_data = await data_provider.get_history_kline(
                etf_code, period="week", count=12,
            )

            if not kline_data or len(kline_data) < 1:
                return {"error": f"无法获取 {index_code} 的历史K线数据"}

            closes = [float(k.get("close", 0.0)) for k in kline_data]
            weekly_change_pct: float | None = None
            if len(closes) >= 2 and closes[-2] != 0:
                weekly_change_pct = round(
                    (closes[-1] - closes[-2]) / closes[-2] * 100, 2,
                )

            volumes = [float(k.get("volume", 0.0)) for k in kline_data[-4:]]
            latest_vol = volumes[-1] if volumes else 0.0
            avg_vol = sum(volumes[:-1]) / max(len(volumes) - 1, 1) if len(volumes) > 1 else 1.0
            volume_trend: str | None = None
            if avg_vol > 0:
                vol_ratio = latest_vol / avg_vol
                if vol_ratio > 1.2:
                    volume_trend = "放量"
                elif vol_ratio < 0.8:
                    volume_trend = "缩量"
                else:
                    volume_trend = "持平"
            else:
                volume_trend = "—"

            latest_close = closes[-1] if closes else 0.0
            ma_positions: dict[str, str] = {}
            for period_label, period in [("MA5", 5), ("MA10", 10)]:
                if len(closes) >= period:
                    ma_val = sum(closes[-period:]) / period
                    ma_positions[period_label] = (
                        "上方" if latest_close > ma_val else "下方"
                    )

            return {
                "index_code": index_code,
                "weekly_change_pct": weekly_change_pct,
                "volume_trend": volume_trend,
                "ma_positions": ma_positions,
            }
        except Exception as e:
            logger.warning("full_review market failed: %s", e)
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════
    # 并行执行
    # ═══════════════════════════════════════════════════════════

    results = await asyncio.gather(
        _collect_portfolio(),
        _collect_sentinel(),
        _collect_performance(),
        _collect_valuation(),
        _collect_decision_reviews(),
        _collect_market(),
        return_exceptions=True,
    )

    portfolio_raw, sentinel_raw, performance_raw, valuation_raw, decision_raw, market_raw = results

    # ── 容错处理：异常转换为 error dict ──
    def _safe_dict(raw, label: str) -> dict:
        if isinstance(raw, Exception):
            logger.warning("full_review dim=%s exception: %s", label, raw)
            return {"error": str(raw)}
        if raw is None:
            return {"error": f"{label} 返回 None"}
        return raw if isinstance(raw, dict) else {"error": f"unexpected type: {type(raw)}"}

    portfolio_dim = _safe_dict(portfolio_raw, "portfolio")
    sentinel_dim = _safe_dict(sentinel_raw, "sentinel")
    performance_dim = _safe_dict(performance_raw, "performance")
    valuation_dim = _safe_dict(valuation_raw, "valuation")
    decision_dim = _safe_dict(decision_raw, "decision_reviews")
    market_dim = _safe_dict(market_raw, "market")

    # ── 组装 ReviewSnapshot ──
    snapshot = {
        "snapshot_type": "full",
        "generated_at": datetime.now().isoformat(),
        "period": {
            "start": start_date,
            "end": week_ending,
            "label": f"{week_ending[:4]}-W{_week_number(week_ending)}",
        },
        "portfolio": portfolio_dim,
        "sentinel": sentinel_dim,
        "performance": performance_dim,
        "valuation": valuation_dim,
        "decision_reviews": decision_dim,
        "market": market_dim,
    }

    # 收集错误
    errors: list[dict] = []
    dim_names = ["portfolio", "sentinel", "performance", "valuation", "decision_reviews", "market"]
    dims = [portfolio_dim, sentinel_dim, performance_dim, valuation_dim, decision_dim, market_dim]
    for name, dim in zip(dim_names, dims):
        if dim.get("error"):
            errors.append({"dimension": name, "error": dim["error"]})

    success_count = 6 - len(errors)
    logger.info(
        "full_review complete investor=%s portfolio=%s week=%s success=%d/6",
        investor, portfolio, week_ending, success_count,
    )

    return {
        "success": len(errors) < 6,
        "data": {
            "snapshot": snapshot,
            "errors": errors,
            "success_count": success_count,
            "total_dimensions": 6,
            "timestamp": datetime.now().isoformat(),
        },
    }


async def _full_review_external(
    investor: str, portfolio: str, week_ending: str,
    index_code: str, external_data_json: str,
) -> dict:
    """使用外部数据执行全量复盘聚合

    Args:
        investor: 投资者 ID
        portfolio: 组合 ID
        week_ending: 周结束日期
        index_code: 基准指数代码
        external_data_json: ExternalDataPayload JSON 字符串

    Returns:
        复盘快照 dict
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

    if not week_ending:
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7
        latest_friday = today - timedelta(days=days_since_friday)
        week_ending = latest_friday.strftime("%Y-%m-%d")

    start_date = (
        datetime.strptime(week_ending, "%Y-%m-%d") - timedelta(days=5)
    ).strftime("%Y-%m-%d")

    snapshot = {
        "snapshot_type": "full_external",
        "generated_at": datetime.now().isoformat(),
        "period": {
            "start": start_date,
            "end": week_ending,
            "label": f"{week_ending[:4]}-W{_week_number(week_ending)}",
        },
        "investor": investor,
        "portfolio": portfolio,
        "index_code": index_code,
        "sentinel": payload.sentinel,
        "portfolio_data": payload.portfolio,
        "quotes": payload.quotes,
        "klines": payload.klines,
        "valuation": payload.valuation,
        "performance": payload.performance,
    }

    return {
        "success": True,
        "data": {
            "snapshot": snapshot,
            "errors": [],
            "success_count": 6,
            "total_dimensions": 6,
            "timestamp": datetime.now().isoformat(),
            "source": "external",
        },
    }


def _week_number(date_str: str) -> str:
    """从 YYYY-MM-DD 推算 ISO 周号（简化版）"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%U")
    except ValueError:
        return "??"


def register(registry) -> None:
    """注册 full_review 工具"""
    from praxis.tools._schemas import FullReviewInput

    registry.register(Tool(
        name="full_review",
        description="全量复盘聚合：6维度（组合+市场+哨兵+绩效+决策回顾+估值）一次调用",
        input_schema=FullReviewInput,
        handler=full_review,
        agent_name="review",
        tier="core",
    ))
