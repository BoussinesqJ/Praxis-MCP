"""MCP 工具 - 决策记录"""
from __future__ import annotations

from pathlib import Path

from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.models.decision import DecisionRecord, DecisionStatus, TeamSignal


def _get_recorder(workspace: str = ".") -> FileDecisionRecorder:
    """获取决策记录器实例"""
    decisions_path = Path(workspace) / "data" / "decisions" / "decision_records.jsonl"
    return FileDecisionRecorder(decisions_path)


def get_decision_record(decision_id: str, workspace: str = ".") -> dict:
    """获取决策记录"""
    try:
        recorder = _get_recorder(workspace)
        record = recorder.get(decision_id)
        if not record:
            return {"success": False, "error": f"决策 {decision_id} 不存在"}
        return {
            "success": True,
            "data": record.model_dump(mode="json"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_decisions(status: str | None = None, limit: int = 50, workspace: str = ".") -> dict:
    """列出决策记录"""
    try:
        recorder = _get_recorder(workspace)
        if status:
            records = [
                d for d in recorder.get_all()
                if d.status.value == status
            ]
        else:
            records = recorder.get_all()
        return {
            "success": True,
            "data": {
                "total": recorder.count(),
                "decisions": [r.model_dump(mode="json") for r in records[:limit]],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_decision(
    ticker: str,
    action: str,
    confidence: float,
    reasoning: str,
    quantity: float | None = None,
    price_range: list[float] | None = None,
    workspace: str = ".",
) -> dict:
    """创建决策记录"""
    try:
        recorder = _get_recorder(workspace)
        record = DecisionRecord(
            decision_id="",  # 由 recorder 生成
            ticker=ticker,
            action=action,
            quantity=quantity,
            price_range=price_range,
            confidence=confidence,
            reasoning=reasoning,
            status=DecisionStatus.PENDING_APPROVAL,
        )
        decision_id = recorder.create(record)
        return {
            "success": True,
            "data": {
                "decision_id": decision_id,
                "status": "pending_approval",
                "message": f"决策已创建: {action} {ticker}，信心={confidence}",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
