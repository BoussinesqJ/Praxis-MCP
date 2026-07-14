"""交易工具 — trading (账本 CRUD + 审批 + 冲销)"""
from __future__ import annotations

import uuid

from praxis.agents.base import Tool
from praxis.tools._schemas import TradingInput
from praxis.core.models import Transaction, TransactionType, TransactionStatus
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


async def trading(
    action: str, ticker: str = "", trade_action: str = "",
    quantity: float = 0, price: float = 0, fee: float = 0,
    asset_type: str = "", tx_id: str = "", reason: str = "",
    decision_action: str = "", confidence: float = 0, reasoning: str = "",
    limit: int = 100, status: str = "", _deps: dict | None = None,
) -> dict:
    """交易管理入口"""
    ledger = _deps.get("ledger") if _deps else None
    if ledger is None:
        return {"success": False, "error": "Ledger 未注入"}

    if action == "ledger":
        txs = ledger.list(ticker=ticker or None, limit=limit)
        return {"success": True, "data": [tx.model_dump() for tx in txs]}

    elif action == "add":
        if not all([ticker, trade_action, quantity, price]):
            return {"success": False, "error": "缺少必填参数: ticker/trade_action/quantity/price"}

        tx_type_map = {"buy": TransactionType.BUY, "sell": TransactionType.SELL,
                       "subscribe": TransactionType.SUBSCRIBE, "redeem": TransactionType.REDEEM}
        tx = Transaction(
            tx_id=f"tx-{uuid.uuid4().hex[:12]}",
            ticker=ticker, tx_type=tx_type_map.get(trade_action, TransactionType.BUY),
            quantity=quantity, price=price, fee=fee,
            asset_type=asset_type or "stock",
            idempotency_key=f"{ticker}-{trade_action}-{quantity}-{price}",
            status=TransactionStatus.PENDING,
        )
        tx_id_created = ledger.append(tx)
        return {"success": True, "data": {"tx_id": tx_id_created, "status": "confirmed"}}

    elif action == "reverse":
        if not tx_id:
            return {"success": False, "error": "缺少 tx_id"}
        new_tx_id = ledger.reverse(tx_id, reason)
        return {"success": True, "data": {"tx_id": new_tx_id, "status": "reversed"}}

    elif action == "approve":
        if not tx_id:
            return {"success": False, "error": "缺少 tx_id"}
        ledger.approve(tx_id)
        return {"success": True, "data": {"tx_id": tx_id, "status": "approved"}}

    elif action == "reject":
        if not all([tx_id, reason]):
            return {"success": False, "error": "缺少 tx_id/reason"}
        ledger.reject(tx_id, reason)
        return {"success": True, "data": {"tx_id": tx_id, "status": "rejected"}}

    elif action == "decision":
        from praxis.engine.decision_recorder import FileDecisionRecorder
        from praxis.core.models import DecisionRecord, DecisionStatus
        from praxis.core.paths import get_decision_path

        recorder = _deps.get("decision_recorder")
        if recorder is None:
            return {"success": False, "error": "DecisionRecorder 未注入"}

        record = DecisionRecord(
            ticker=ticker, action=decision_action or "hold",
            confidence=confidence, reasoning=reasoning,
            status=DecisionStatus.PENDING,
        )
        dec_id = recorder.create(record)
        return {"success": True, "data": {"decision_id": dec_id, "status": "pending"}}

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(
        name="trading",
        description="交易管理：查询账本/添加交易/冲销/审批/拒绝/创建决策。",
        input_schema=TradingInput,
        handler=trading,
        agent_name="decision",
        tier="core",
        is_readonly=False,
    ))
