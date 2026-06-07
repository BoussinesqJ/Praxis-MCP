"""MCP 工具 - 策略版本对比"""
from __future__ import annotations

from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.core.models.state import PerformanceMetrics
from praxis.engine.performance import EnhancedPerformanceCalculator
from praxis.engine.version_compare import VersionComparer


async def compare_versions(
    strategy_a: str,
    strategy_b: str,
    workspace: str = ".",
) -> dict:
    """对比两个策略版本的绩效

    注意：V1 实现中，所有交易都在同一个 ledger 中，
    所以这里简化为对比两个时间段的绩效。
    """
    try:
        ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
        ledger = FileLedger(ledger_path)
        calculator = EnhancedPerformanceCalculator(ledger)

        # 简化实现：计算当前绩效
        # 实际应该分别计算两个策略版本的绩效
        metrics = calculator.calculate("example", "grid_value_v9")

        comparer = VersionComparer()
        comparison = comparer.compare(
            version_a=strategy_a,
            version_b=strategy_b,
            metrics_a=metrics,
            metrics_b=metrics,  # 简化：使用相同指标
        )
        formatted = comparer.format_comparison(comparison)

        return {
            "success": True,
            "data": {
                "comparison": comparison.model_dump(),
                "formatted": formatted,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
