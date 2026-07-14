"""估值分位 — valuation"""
from __future__ import annotations
from praxis.agents.base import Tool
from praxis.tools._schemas import ValuationInput
from praxis.engine.valuation import (
    get_valuation_percentile,
    check_valuation_for_all_indices,
    get_index_pe_percentile,
)

async def valuation(action: str,
                    index_code: str = "000300",
                    index_codes: list[str] | None = None,
                    _deps: dict | None = None) -> dict:
    """指数估值分位：percentile | all | compare | level

    Args:
        action: 操作类型 — percentile | all | compare | level
        index_code: 单指数代码（percentile/level 时使用，默认 "000300"）
        index_codes: 多指数代码列表（compare 时使用，如 ["000300", "000905"]）
        _deps: 依赖注入（本工具不使用外部依赖，保留用于一致性）

    Returns:
        {"success": bool, "data": ..., "error": str|None}
    """
    if action == "percentile":
        return await get_valuation_percentile(index_code)

    elif action == "all":
        return await check_valuation_for_all_indices()

    elif action == "compare":
        if not index_codes:
            return {"success": False, "error": "compare 需要 index_codes 参数"}
        results = {}
        errors = []
        for code in index_codes:
            result = await get_index_pe_percentile(code)
            if result:
                results[code] = result
            else:
                errors.append(code)
        return {
            "success": len(errors) == 0,
            "data": {
                "indices": results,
                "errors": errors,
                "count": len(results),
            },
        }

    elif action == "level":
        result = await get_index_pe_percentile(index_code)
        if result is None:
            return {"success": False, "error": f"无法获取 {index_code} 的估值水平"}
        return {"success": True, "data": {"valuation_level": result.get("valuation_level", "fair")}}

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(name="valuation", description="指数估值分位：PE-TTM历史分位",
                           input_schema=ValuationInput, handler=valuation, agent_name="risk", tier="core"))
