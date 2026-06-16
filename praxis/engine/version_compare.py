"""策略版本对比

对比不同策略版本的绩效，回答"v8 vs v9 哪个好"。
"""
from __future__ import annotations

from pydantic import BaseModel

from praxis.core.models.state import PerformanceMetrics


class VersionComparison(BaseModel):
    """策略版本对比"""
    version_a: str
    version_b: str
    metrics_a: PerformanceMetrics
    metrics_b: PerformanceMetrics
    winner: str                   # a/b/tie
    improvement: dict             # 各指标改善幅度


class VersionComparer:
    """策略版本对比器"""

    def compare(
        self,
        version_a: str,
        version_b: str,
        metrics_a: PerformanceMetrics,
        metrics_b: PerformanceMetrics,
    ) -> VersionComparison:
        """对比两个版本"""
        # 计算改善幅度
        improvement = {
            "total_return": metrics_b.total_return - metrics_a.total_return,
            "annualized_return": metrics_b.annualized_return - metrics_a.annualized_return,
            "max_drawdown": metrics_b.max_drawdown - metrics_a.max_drawdown,
            "sharpe_ratio": metrics_b.sharpe_ratio - metrics_a.sharpe_ratio,
            "calmar_ratio": metrics_b.calmar_ratio - metrics_a.calmar_ratio,
            "win_rate": metrics_b.win_rate - metrics_a.win_rate,
            "profit_loss_ratio": metrics_b.profit_loss_ratio - metrics_a.profit_loss_ratio,
        }

        # 判断胜负
        score_a = self._calculate_score(metrics_a)
        score_b = self._calculate_score(metrics_b)

        if score_a > score_b:
            winner = version_a
        elif score_b > score_a:
            winner = version_b
        else:
            winner = "tie"

        return VersionComparison(
            version_a=version_a,
            version_b=version_b,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            winner=winner,
            improvement=improvement,
        )

    def _calculate_score(self, metrics: PerformanceMetrics) -> float:
        """计算综合评分

        评分公式：夏普比率 * 0.4 + 收益率 * 0.3 - 回撤 * 0.2 + 胜率 * 0.1
        """
        return (
            metrics.sharpe_ratio * 0.4
            + metrics.annualized_return * 0.3
            - metrics.max_drawdown * 0.2
            + metrics.win_rate * 0.1
        )

    def format_comparison(self, comparison: VersionComparison) -> str:
        """格式化对比结果"""
        lines = [
            "=== 策略版本对比 ===",
            f"版本 A: {comparison.version_a}",
            f"版本 B: {comparison.version_b}",
            "",
            "--- 指标对比 ---",
            f"{'指标':<20} {'版本A':>10} {'版本B':>10} {'改善':>10}",
            "-" * 50,
        ]

        metrics = [
            ("总收益率", "total_return"),
            ("年化收益率", "annualized_return"),
            ("最大回撤", "max_drawdown"),
            ("夏普比率", "sharpe_ratio"),
            ("卡玛比率", "calmar_ratio"),
            ("胜率", "win_rate"),
            ("盈亏比", "profit_loss_ratio"),
        ]

        for name, key in metrics:
            val_a = getattr(comparison.metrics_a, key)
            val_b = getattr(comparison.metrics_b, key)
            imp = comparison.improvement.get(key, 0)

            # 格式化
            if key in ("total_return", "annualized_return", "max_drawdown", "win_rate"):
                fmt = lambda x: f"{x:.2%}"
            else:
                fmt = lambda x: f"{x:.2f}"

            lines.append(f"{name:<20} {fmt(val_a):>10} {fmt(val_b):>10} {fmt(imp):>10}")

        lines.append("")
        lines.append(f"综合评分: {self._calculate_score(comparison.metrics_a):.2f} vs {self._calculate_score(comparison.metrics_b):.2f}")
        lines.append(f"优胜版本: {comparison.winner}")

        return "\n".join(lines)
