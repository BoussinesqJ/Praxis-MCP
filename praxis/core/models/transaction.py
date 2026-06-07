"""交易记录模型"""
from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """交易类型"""
    BUY = "buy"
    SELL = "sell"
    REDEEM = "redeem"       # 场外基金赎回
    SUBSCRIBE = "subscribe" # 场外基金申购
    DIVIDEND = "dividend"   # 分红
    CORRECTION = "correction"  # 冲销修正


class TransactionStatus(str, Enum):
    """交易状态"""
    PENDING = "pending"          # 待审批
    APPROVED = "approved"        # 已审批
    CONFIRMED = "confirmed"      # 已确认（写入账本）
    REJECTED = "rejected"        # 已拒绝
    CANCELLED = "cancelled"      # 已取消


class Transaction(BaseModel):
    """交易记录（append-only 账本条目）"""
    tx_id: str = Field(description="交易唯一ID，格式：tx-YYYYMMDD-NNN")
    type: TransactionType
    ticker: str
    quantity: float
    price: float
    fee: float = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: TransactionStatus = TransactionStatus.CONFIRMED
    decision_id: str | None = None
    idempotency_key: str | None = None
    target_tx_id: str | None = None  # 冲销修正时指向原交易
    reason: str | None = None        # 冲销原因
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)  # 标签：test/real/migration/opening 等
    asset_type: str | None = None  # 资产类型：stock/etf/offshore_fund

    def to_jsonl(self) -> str:
        """序列化为 JSONL 行"""
        import json
        data = self.model_dump(mode="json")
        # datetime 序列化为 ISO 格式
        if isinstance(data.get("created_at"), str):
            pass  # pydantic 已处理
        return json.dumps(data, ensure_ascii=False)
