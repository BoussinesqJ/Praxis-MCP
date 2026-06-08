"""复盘自动回填器

GPT 要求：5d/20d/60d 后自动回填实际结果，计算 AI 信心度校准误差。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.ledger import FileLedger
from praxis.core.interfaces import DataProvider
from praxis.core.models.decision import DecisionRecord, DecisionStatus, ReviewSnapshot
from praxis.core.models.transaction import TransactionType


class ReviewSummary(BaseModel):
    """复盘汇总"""
    total_decisions: int
    pending_5d: int
    pending_20d: int
    pending_60d: int
    filled_count: int


class ReviewFiller:
    """复盘自动回填器"""

    def __init__(
        self,
        recorder: FileDecisionRecorder,
        ledger: FileLedger,
        data_provider: DataProvider,
    ):
        self._recorder = recorder
        self._ledger = ledger
        self._data = data_provider

    async def fill_pending_reviews(self) -> list[dict]:
        """回填所有待复盘的决策"""
        results = []
        decisions = self._recorder.get_executed()

        for d in decisions:
            # 获取执行价格
            exec_price = self._get_execution_price(d)
            if exec_price is None:
                continue

            # 检查是否需要 5 日复盘
            if d.review_5d is None and self._days_since(d.timestamp) >= 5:
                review = await self._calculate_review(d, exec_price, days=5)
                if review:
                    self._recorder.update_review(d.decision_id, "5d", review)
                    results.append({"decision_id": d.decision_id, "type": "5d"})

            # 检查是否需要 20 日复盘
            if d.review_20d is None and self._days_since(d.timestamp) >= 20:
                review = await self._calculate_review(d, exec_price, days=20)
                if review:
                    self._recorder.update_review(d.decision_id, "20d", review)
                    results.append({"decision_id": d.decision_id, "type": "20d"})

            # 检查是否需要 60 日复盘
            if d.review_60d is None and self._days_since(d.timestamp) >= 60:
                review = await self._calculate_review(d, exec_price, days=60)
                if review:
                    self._recorder.update_review(d.decision_id, "60d", review)
                    results.append({"decision_id": d.decision_id, "type": "60d"})

        return results

    def _get_execution_price(self, decision: DecisionRecord) -> float | None:
        """从账本获取执行价格"""
        if not decision.execution_tx_id:
            # 尝试从 decision 本身获取
            if decision.price_range:
                return sum(decision.price_range) / len(decision.price_range)
            return None

        tx = self._ledger.get(decision.execution_tx_id)
        if tx:
            return tx.price

        # 回退到 price_range
        if decision.price_range:
            return sum(decision.price_range) / len(decision.price_range)
        return None

    def _days_since(self, timestamp: datetime) -> int:
        """计算距离现在的天数"""
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return (now - timestamp).days

    async def _calculate_review(
        self, decision: DecisionRecord, exec_price: float, days: int
    ) -> dict | None:
        """计算复盘结果

        根据决策的 ticker 和执行价格，计算 N 日后的收益
        """
        try:
            # 获取当前行情
            quotes = await self._data.get_realtime_quote([decision.ticker])
            if not quotes or decision.ticker not in quotes:
                return None

            current_price = quotes[decision.ticker].get("price", 0)
            if current_price <= 0:
                return None

            # 计算收益率
            if decision.action in ("buy", "subscribe"):
                actual_return_pct = (current_price - exec_price) / exec_price
            elif decision.action in ("sell", "redeem"):
                actual_return_pct = (exec_price - current_price) / exec_price
            else:
                actual_return_pct = 0

            # 计算是否正确
            hit = actual_return_pct > 0

            return {
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "actual_price": current_price,
                "actual_return_pct": round(actual_return_pct * 100, 2),
                "benchmark_return_pct": None,  # TODO: 接入基准数据
                "notes": f"{days}日复盘：执行价{exec_price}→现价{current_price}，收益{actual_return_pct:.2%}，{'正确' if hit else '错误'}",
            }
        except Exception as e:
            return {
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "actual_price": None,
                "actual_return_pct": None,
                "benchmark_return_pct": None,
                "notes": f"{days}日复盘失败：{str(e)}",
            }

    def calculate_confidence_calibration(self, team: str) -> dict:
        """计算信心度校准误差

        校准误差 = 平均信心度 - 实际命中率
        误差越小，信心度越准确
        """
        decisions = self._recorder.get_executed()
        team_decisions = [
            d for d in decisions
            if team in d.ai_team_signals and d.review_5d is not None
        ]

        if not team_decisions:
            return {
                "team": team,
                "total_decisions": 0,
                "avg_confidence": 0,
                "hit_rate": 0,
                "calibration_error": 0,
                "message": "无复盘数据",
            }

        avg_confidence = sum(
            d.ai_team_signals[team].confidence
            for d in team_decisions
        ) / len(team_decisions)

        hits = sum(
            1 for d in team_decisions
            if d.review_5d.actual_return_pct is not None
            and d.review_5d.actual_return_pct > 0
        )
        hit_rate = hits / len(team_decisions)

        calibration_error = avg_confidence - hit_rate

        return {
            "team": team,
            "total_decisions": len(team_decisions),
            "avg_confidence": round(avg_confidence, 3),
            "hit_rate": round(hit_rate, 3),
            "calibration_error": round(calibration_error, 3),
            "message": f"信心度校准误差: {calibration_error:.3f} ({'偏乐观' if calibration_error > 0 else '偏悲观' if calibration_error < 0 else '准确'})",
        }

    def get_summary(self) -> ReviewSummary:
        """获取复盘汇总"""
        decisions = self._recorder.get_executed()

        pending_5d = sum(1 for d in decisions if d.review_5d is None)
        pending_20d = sum(1 for d in decisions if d.review_20d is None)
        pending_60d = sum(1 for d in decisions if d.review_60d is None)
        filled_count = sum(
            1 for d in decisions
            if d.review_5d is not None or d.review_20d is not None or d.review_60d is not None
        )

        return ReviewSummary(
            total_decisions=len(decisions),
            pending_5d=pending_5d,
            pending_20d=pending_20d,
            pending_60d=pending_60d,
            filled_count=filled_count,
        )
