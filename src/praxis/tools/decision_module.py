"""决策管理 — decision"""
from __future__ import annotations
import uuid
from praxis.agents.base import Tool
from praxis.tools._schemas import DecisionCreateInput
from praxis.core.models import DecisionRecord, DecisionStatus

async def decision(action: str,
                   ticker: str = "",
                   decision_action: str = "",
                   confidence: float = 0.0,
                   reasoning: str = "",
                   investor: str = "demo",
                   portfolio: str = "core",
                   decision_id: str = "",
                   status: str = "",
                   tx_id: str = "",
                   limit: int = 50,
                   _deps: dict | None = None) -> dict:
    """决策记录管理：create/get/list/update/link

    Args:
        action: 操作类型 — create | get | list | update | link
        ticker: 标的代码（create 时必填）
        decision_action: 决策动作（create: buy/sell/hold/watch）
        confidence: 置信度 0-1（create 时使用）
        reasoning: 决策理由（create 时使用）
        investor: 投资者 ID
        portfolio: 组合 ID
        decision_id: 决策 ID（get/update/link 时使用）
        status: 状态过滤（list/update 时使用）
        tx_id: 交易 ID（link 时使用）
        limit: 列表返回上限
        _deps: 依赖注入字典，需包含 'decision_recorder'

    Returns:
        {"success": bool, "data": ..., "error": str|None}
    """
    recorder = _deps.get("decision_recorder") if _deps else None
    if recorder is None:
        return {"success": False, "error": "DecisionRecorder未注入"}

    if action == "create":
        if not ticker or not decision_action:
            return {"success": False, "error": "create 需要 ticker 和 decision_action"}
        record = DecisionRecord(
            ticker=ticker,
            action=decision_action,
            confidence=confidence,
            reasoning=reasoning,
            decision_id=f"dec-{uuid.uuid4().hex[:12]}",
            status=DecisionStatus.PENDING,
            investor_id=investor,
            portfolio_id=portfolio,
        )
        dec_id = recorder.create(record)
        return {"success": True, "data": {"decision_id": dec_id, "status": "pending"}}

    elif action == "get":
        record = recorder.get(decision_id)
        if record is None:
            return {"success": False, "error": f"决策 {decision_id} 不存在"}
        return {"success": True, "data": record.model_dump()}

    elif action == "list":
        if status:
            records = recorder.list(status=status, limit=limit)
        else:
            records = recorder.list(limit=limit)
        return {
            "success": True,
            "data": {
                "decisions": [r.model_dump() for r in records],
                "count": len(records),
            },
        }

    elif action == "update":
        ok = recorder.update_status(decision_id, status)
        if not ok:
            return {"success": False, "error": f"更新决策 {decision_id} 状态失败"}
        return {"success": True, "data": {"decision_id": decision_id, "status": status}}

    elif action == "link":
        ok = recorder.link_transaction(decision_id, tx_id)
        if not ok:
            return {"success": False, "error": f"关联交易失败：决策 {decision_id} 不存在"}
        return {"success": True, "data": {"decision_id": decision_id, "tx_id": tx_id}}

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(name="decision", description="决策记录管理：创建投资决策",
                           input_schema=DecisionCreateInput, handler=decision, agent_name="decision",
                           tier="core", is_readonly=False))
