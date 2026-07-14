"""绩效计算 — performance"""
from __future__ import annotations
from praxis.agents.base import Tool
from praxis.tools._schemas import PerformanceInput

async def performance(action: str = "calculate",
                      investor: str = "",
                      portfolio: str = "",
                      exclude_reversed: bool = False,
                      exclude_tags: list[str] | None = None,
                      include_tags: list[str] | None = None,
                      ticker: str | None = None,
                      version_a: str = "",
                      version_b: str = "",
                      metric: str = "sharpe_ratio",
                      _deps: dict | None = None) -> dict:
    """绩效计算：calculate | compare

    Args:
        action: 操作类型 — calculate（默认） | compare
        investor: 投资者 ID（calculate 时使用）
        portfolio: 组合 ID（calculate 时使用）
        exclude_reversed: 排除已冲销交易
        exclude_tags: 排除含指定标签的交易
        include_tags: 仅包含含指定标签的交易
        ticker: 按标的过滤
        version_a: 基准版本标签（compare 时使用）
        version_b: 对比版本标签（compare 时使用）
        metric: 对比指标（compare 时使用，默认 "sharpe_ratio"）
        _deps: 依赖注入字典，需包含 'performance_calculator'

    Returns:
        {"success": bool, "data": ..., "error": str|None}
    """
    calc = _deps.get("performance_calculator") if _deps else None
    if calc is None:
        return {"success": False, "error": "PerformanceCalculator未注入"}

    if action == "calculate":
        return calc.calculate(
            investor, portfolio,
            exclude_reversed=exclude_reversed,
            exclude_tags=exclude_tags,
            include_tags=include_tags,
            ticker=ticker,
        )

    elif action == "compare":
        if not version_a or not version_b:
            return {"success": False, "error": "compare 需要 version_a 和 version_b"}
        return calc.compare_versions(version_a, version_b, metric=metric)

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(name="performance", description="绩效计算：累计收益/年化/夏普/回撤/胜率等",
                           input_schema=PerformanceInput, handler=performance, agent_name="admin", tier="core"))
