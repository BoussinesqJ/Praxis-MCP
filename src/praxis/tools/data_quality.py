"""数据质量工具 — 检查交易记录和行情数据的质量

对 data_quality 的 4 种调用（check/completeness/consistency/timeliness）。
"""
from __future__ import annotations

from praxis.agents.base import Tool
from praxis.engine.data_quality import DataQualityChecker
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


async def data_quality(
    action: str,
    _deps: dict | None = None,
) -> dict:
    """数据质量检查入口

    Args:
        action: "check" 运行全部 / "completeness" / "consistency" / "timeliness"
        _deps: 依赖注入 {"ledger": Ledger 实例, "data_provider": DataProvider 实例}

    Returns:
        {success: bool, data: dict, error: str | None}
    """
    ledger = _deps.get("ledger") if _deps else None
    data_provider = _deps.get("data_provider") if _deps else None

    if ledger is None:
        return {"success": False, "data": None, "error": "Ledger 未注入"}
    if data_provider is None:
        return {"success": False, "data": None, "error": "DataProvider 未注入"}

    checker = DataQualityChecker()

    try:
        if action == "check":
            result = checker.run_all_checks(ledger, data_provider)
            return {"success": True, "data": result, "error": None}

        elif action == "completeness":
            result = checker.check_completeness(ledger)
            return {"success": True, "data": result, "error": None}

        elif action == "consistency":
            result = checker.check_consistency(ledger, data_provider)
            return {"success": True, "data": result, "error": None}

        elif action == "timeliness":
            result = checker.check_timeliness(data_provider)
            return {"success": True, "data": result, "error": None}

        return {"success": False, "data": None, "error": f"未知 action: {action}"}

    except Exception as e:
        logger.error(f"数据质量检查失败 action={action}: {e}")
        return {"success": False, "data": None, "error": str(e)}


def register(registry):
    registry.register(Tool(
        name="data_quality",
        description="数据质量检查：完整性(字段/重复)/一致性(账本vs持仓)/时效性(数据过期检查)。action: check|completeness|consistency|timeliness",
        input_schema=type("DataQualityInput", (), {}),
        handler=data_quality,
        agent_name="admin",
        tier="advanced",
        is_readonly=True,
    ))
