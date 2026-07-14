"""复盘自动回填器 — 5d/20d/60d 决策复盘 + 信心度校准

v3.6: P0-1 基准超额收益对标 — 注入 BenchmarkProvider，增强 _calculate_review()
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.ledger import FileLedger
from praxis.core.interfaces import DataProvider, BenchmarkProvider
from praxis.core.models import DecisionRecord, DecisionStatus, SingleDecisionReview
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


def _default_benchmark_index(ticker: str) -> str:
    """根据 ticker 前缀推导默认基准指数

    映射规则：
    - 60xxxx / 00xxxx → "000300" (沪深300，主板)
    - 30xxxx → "399006" (创业板指)
    - 688xxx → "000905" (中证500，科创板)
    - 其他 → "000300" (默认沪深300)

    Args:
        ticker: 股票/基金代码

    Returns:
        基准指数代码
    """
    if not ticker:
        return "000300"
    ticker = str(ticker).strip()
    if len(ticker) < 5:
        return "000300"
    if ticker.startswith("688"):
        return "000905"
    if ticker.startswith("30"):
        return "399006"
    if ticker.startswith("60") or ticker.startswith("00"):
        return "000300"
    return "000300"


class ReviewFiller:
    """复盘自动回填器

    v3.6: 新增可选 benchmark_provider，用于计算基准超额收益 (alpha)。
    """

    def __init__(
        self,
        recorder: FileDecisionRecorder,
        ledger: FileLedger,
        data_provider: DataProvider,
        benchmark_provider: BenchmarkProvider | None = None,
    ):
        self._recorder = recorder
        self._ledger = ledger
        self._data = data_provider
        self._benchmark = benchmark_provider

    async def fill_pending_reviews(self) -> dict:
        """回填所有待复盘的决策（5d/20d/60d）

        v3.6: 为每个决策自动推导基准指数并传入 _calculate_review
        """
        decisions = self._recorder.get_executed()

        results = {
            "filled_5d": 0, "filled_20d": 0, "filled_60d": 0,
            "skipped": 0, "errors": [], "reviews": [],
        }

        for d in decisions:
            try:
                created_dt = self._parse_created_at(d)
                days_since = (datetime.now(timezone.utc) - created_dt).days

                # 推导基准指数
                benchmark_index_code = _default_benchmark_index(d.ticker)

                review_result: dict | None = None
                review_type: str = ""

                if days_since >= 60 and d.review_result is None:
                    review_result = await self._fill_review(d, "60d", benchmark_index_code)
                    results["filled_60d"] += 1
                    review_type = "60d"
                elif days_since >= 20 and d.review_result is None:
                    review_result = await self._fill_review(d, "20d", benchmark_index_code)
                    results["filled_20d"] += 1
                    review_type = "20d"
                elif days_since >= 5 and d.review_result is None:
                    review_result = await self._fill_review(d, "5d", benchmark_index_code)
                    results["filled_5d"] += 1
                    review_type = "5d"
                else:
                    results["skipped"] += 1

                # 收集复盘详情
                if review_result is not None and review_type:
                    alpha_pct: float | None = None
                    actual = review_result.get("actual_return_pct")
                    benchmark = review_result.get("benchmark_return_pct")
                    if actual is not None and benchmark is not None:
                        alpha_pct = round(actual - benchmark, 2)

                    results["reviews"].append({
                        "decision_id": d.decision_id,
                        "ticker": d.ticker,
                        "action": d.action,
                        "review_type": review_type,
                        "actual_return_pct": actual,
                        "benchmark_return_pct": benchmark,
                        "alpha_pct": alpha_pct,
                        "notes": review_result.get("notes", ""),
                    })
            except Exception as e:
                results["errors"].append({
                    "decision_id": d.decision_id, "error": str(e),
                })

        return {"success": True, "data": results}

    async def _fill_review(
        self, decision: DecisionRecord, review_type: str,
        benchmark_index_code: str = "000300",
    ) -> dict | None:
        """回填单条复盘 — 历史 K 线回测逻辑

        v3.6: 使用 K 线计算 N 日收益率 + 基准 alpha
        v3.7: 返回 review_data dict 供 fill_pending_reviews 收集详情
        """
        try:
            days_map = {"5d": 5, "20d": 20, "60d": 60}
            days = days_map.get(review_type, 5)

            # 计算执行价格
            exec_price = self._get_execution_price(decision)
            if exec_price is None:
                logger.warning(
                    "review_no_exec_price",
                    decision_id=decision.decision_id,
                    ticker=decision.ticker,
                )
                return None

            review_data = await self._calculate_review(
                decision, exec_price, days, benchmark_index_code,
            )
            if review_data:
                self._recorder.update_review(
                    decision.decision_id, review_type, review_data,
                )
                logger.info(
                    "review_filled",
                    decision_id=decision.decision_id,
                    review_type=review_type,
                    ticker=decision.ticker,
                    actual_return=review_data.get("actual_return_pct"),
                )
                return review_data
        except Exception as e:
            logger.error(
                "review_fill_failed",
                decision_id=decision.decision_id,
                error=str(e),
            )
        return None

    def _get_execution_price(self, decision: DecisionRecord) -> float | None:
        """从账本或决策记录获取执行价格"""
        # 从账本查找关联交易
        if decision.tx_id:
            tx = self._ledger.get(decision.tx_id)
            if tx:
                return tx.price

        # 回退：从决策记录的 reasoning 推断（弱回退）
        return None

    def _parse_created_at(self, decision: DecisionRecord) -> datetime:
        """解析 created_at 为 timezone-aware datetime"""
        raw = decision.created_at
        if isinstance(raw, datetime):
            if raw.tzinfo is None:
                return raw.replace(tzinfo=timezone.utc)
            return raw
        # ISO string
        s = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    async def _calculate_review(
        self,
        decision: DecisionRecord,
        exec_price: float,
        days: int,
        benchmark_index_code: str = "000300",
    ) -> dict | None:
        """计算复盘结果 — 历史 K 线回测 + 基准 alpha

        根据 decision.ticker 和执行价格，从历史 K 线中获取 N 个交易日后的价格计算收益。
        v3.6: 同步获取基准指数收益，计算 alpha（超额收益）。

        Args:
            decision: 决策记录
            exec_price: 执行价格
            days: 复盘天数（5/20/60）
            benchmark_index_code: 基准指数代码（默认 "000300"）

        Returns:
            复盘快照 dict，包含 actual_price, actual_return_pct, benchmark_return_pct, notes
        """
        try:
            # 获取足够多的历史 K 线
            lookback = days + 30
            klines = await self._data.get_history_kline(
                decision.ticker, period="day", count=lookback,
            )
            if not klines or len(klines) < days + 1:
                return {
                    "actual_price": None,
                    "actual_return_pct": None,
                    "benchmark_return_pct": None,
                    "notes": (
                        f"{days}日复盘：历史K线不足"
                        f"（{len(klines) if klines else 0}条），跳过"
                    ),
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                }

            # 标准化日期格式
            def _norm_date(d: str) -> str:
                d = d.replace("-", "")
                if len(d) == 8:
                    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                return d

            for kl in klines:
                kl["_date"] = _norm_date(str(kl.get("date", "")))

            klines.sort(key=lambda x: x["_date"])

            # 定位决策日期
            decision_dt = self._parse_created_at(decision)
            decision_date_str = decision_dt.strftime("%Y-%m-%d")
            start_idx = -1
            for i, kl in enumerate(klines):
                if kl["_date"] >= decision_date_str:
                    start_idx = i
                    break

            if start_idx < 0:
                return {
                    "actual_price": None,
                    "actual_return_pct": None,
                    "benchmark_return_pct": None,
                    "notes": (
                        f"{days}日复盘：无法定位决策日期 "
                        f"{decision_date_str} 在K线中的位置"
                    ),
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                }

            # 定位 N 个交易日后
            target_idx = start_idx + days
            if target_idx >= len(klines):
                return {
                    "actual_price": None,
                    "actual_return_pct": None,
                    "benchmark_return_pct": None,
                    "notes": (
                        f"{days}日复盘：数据不足，仅 "
                        f"{len(klines) - start_idx - 1} 个交易日"
                        f"（需要 {days} 个）"
                    ),
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                }

            target_kline = klines[target_idx]
            target_date = target_kline["_date"]
            target_price = float(target_kline.get("close", 0))

            if target_price <= 0:
                return None

            # 计算收益率
            actual_return_pct: float
            if decision.action in ("buy", "subscribe"):
                actual_return_pct = (target_price - exec_price) / exec_price
            elif decision.action in ("sell", "redeem"):
                actual_return_pct = (exec_price - target_price) / exec_price
            else:
                actual_return_pct = 0.0

            # ═══════════════════════════════════════════════════════
            # P0-1: 获取同期基准指数收益 + 计算 alpha
            # ═══════════════════════════════════════════════════════
            benchmark_return_pct: float | None = None
            notes_extra = ""

            if self._benchmark is not None:
                start_date = klines[start_idx]["_date"]
                t_bench_start = time.monotonic()
                try:
                    benchmark_klines = await self._benchmark.get_daily_kline(
                        benchmark_index_code, start_date, target_date,
                    )
                    t_bench = time.monotonic() - t_bench_start
                    logger.info(
                        "benchmark_fetch_success",
                        ticker=decision.ticker,
                        index=benchmark_index_code,
                        kline_count=len(benchmark_klines) if benchmark_klines else 0,
                        elapsed_ms=round(t_bench * 1000, 2),
                    )

                    if benchmark_klines and len(benchmark_klines) >= 2:
                        bm_start_price = float(benchmark_klines[0].get("open", 0))
                        bm_end_price = float(benchmark_klines[-1].get("close", 0))
                        if bm_start_price > 0:
                            benchmark_return_pct = (
                                (bm_end_price - bm_start_price) / bm_start_price
                            )
                        else:
                            logger.warning(
                                "benchmark_zero_open",
                                ticker=decision.ticker,
                                index=benchmark_index_code,
                            )
                    elif benchmark_klines and len(benchmark_klines) < 2:
                        logger.warning(
                            "benchmark_insufficient",
                            ticker=decision.ticker,
                            index=benchmark_index_code,
                            count=len(benchmark_klines),
                        )
                        notes_extra = "；基准K线数据不足"
                    else:
                        logger.warning(
                            "benchmark_no_coverage",
                            ticker=decision.ticker,
                            index=benchmark_index_code,
                            start=start_date,
                            end=target_date,
                        )
                        notes_extra = "；基准数据不覆盖此日期"
                except Exception as e:
                    t_bench = time.monotonic() - t_bench_start
                    logger.warning(
                        "benchmark_fetch_failed",
                        ticker=decision.ticker,
                        index=benchmark_index_code,
                        days=days,
                        elapsed_ms=round(t_bench * 1000, 2),
                        error=str(e),
                    )
                    notes_extra = "；基准数据缺失"

            # 计算 alpha
            alpha: float | None = None
            if benchmark_return_pct is not None:
                alpha = actual_return_pct - benchmark_return_pct

            # 生成 notes
            notes: str
            if alpha is not None:
                alpha_pct = round(alpha * 100, 2)
                if alpha > 0:
                    notes = (
                        f"{days}日复盘：执行价{exec_price}→"
                        f"{target_date}收盘价{target_price}，"
                        f"收益{actual_return_pct:.2%}，"
                        f"跑赢基准（α=+{alpha_pct:.2f}%）"
                    )
                else:
                    notes = (
                        f"{days}日复盘：执行价{exec_price}→"
                        f"{target_date}收盘价{target_price}，"
                        f"收益{actual_return_pct:.2%}，"
                        f"跑输基准（α={alpha_pct:.2f}%）"
                    )
                if actual_return_pct < 0 and alpha > 0:
                    notes += "（亏损但跑赢基准）"
            else:
                hit = actual_return_pct > 0
                notes = (
                    f"{days}日复盘：执行价{exec_price}→"
                    f"{target_date}收盘价{target_price}，"
                    f"收益{actual_return_pct:.2%}，"
                    f"{'正确' if hit else '错误'}"
                )
                if notes_extra:
                    notes += notes_extra

            return {
                "actual_price": target_price,
                "actual_return_pct": round(actual_return_pct * 100, 2),
                "benchmark_return_pct": (
                    round(benchmark_return_pct * 100, 2)
                    if benchmark_return_pct is not None else None
                ),
                "notes": notes,
                "filled_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(
                "review_calc_failed",
                decision_id=decision.decision_id,
                ticker=decision.ticker,
                days=days,
                error=str(e),
            )
            return {
                "actual_price": None,
                "actual_return_pct": None,
                "benchmark_return_pct": None,
                "notes": f"{days}日复盘失败：{str(e)}",
                "filled_at": datetime.now(timezone.utc).isoformat(),
            }

    async def get_summary(self) -> dict:
        """获取复盘汇总 — 含计数 + 已回填决策的收益统计与详情

        v3.7: 新增 avg_actual_return_5d / avg_alpha_5d / reviews 列表
        """
        decisions = self._recorder.get_executed()
        pending_5d = pending_20d = pending_60d = filled = 0
        reviews: list[dict] = []
        actual_returns: list[float] = []
        alphas: list[float] = []

        for d in decisions:
            created_dt = self._parse_created_at(d)
            days_since = (datetime.now(timezone.utc) - created_dt).days
            if d.review_result is not None:
                filled += 1
                # 解析已回填的 review_result JSON
                try:
                    rd = json.loads(d.review_result) if isinstance(d.review_result, str) else d.review_result
                except (json.JSONDecodeError, TypeError):
                    rd = {}

                actual = rd.get("actual_return_pct")
                benchmark = rd.get("benchmark_return_pct")

                # 计算 alpha
                alpha_pct: float | None = None
                if actual is not None and benchmark is not None:
                    alpha_pct = round(actual - benchmark, 2)

                reviews.append({
                    "decision_id": d.decision_id,
                    "ticker": d.ticker,
                    "action": d.action,
                    "review_type": rd.get("type", rd.get("review_type", "")),
                    "actual_return_pct": actual,
                    "benchmark_return_pct": benchmark,
                    "alpha_pct": alpha_pct,
                    "notes": rd.get("notes", ""),
                })

                if actual is not None:
                    actual_returns.append(actual)
                if alpha_pct is not None:
                    alphas.append(alpha_pct)
            elif days_since >= 60:
                pending_60d += 1
            elif days_since >= 20:
                pending_20d += 1
            elif days_since >= 5:
                pending_5d += 1

        avg_actual_return_5d = (
            round(sum(actual_returns) / len(actual_returns), 2)
            if actual_returns else None
        )
        avg_alpha_5d = (
            round(sum(alphas) / len(alphas), 2)
            if alphas else None
        )

        return {
            "success": True,
            "data": {
                "total_decisions": len(decisions),
                "pending_5d": pending_5d,
                "pending_20d": pending_20d,
                "pending_60d": pending_60d,
                "filled_count": filled,
                "avg_actual_return_5d": avg_actual_return_5d,
                "avg_alpha_5d": avg_alpha_5d,
                "reviews": reviews,
            },
        }

    async def get_confidence_calibration(self, team: str) -> dict:
        """计算团队信心度校准误差"""
        decisions = self._recorder.get_executed()
        errors: list[float] = []

        for d in decisions:
            if not d.review_result:
                continue
            signals = d.team_signals if hasattr(d, 'team_signals') else []
            for signal in signals:
                if hasattr(signal, 'team_name') and signal.team_name == team:
                    if d.review_result:
                        errors.append(abs(signal.confidence - 0.5))

        avg_error = sum(errors) / len(errors) if errors else 0

        return {
            "success": True,
            "data": {
                "team": team,
                "avg_calibration_error": round(avg_error, 4),
                "sample_size": len(errors),
            },
        }
