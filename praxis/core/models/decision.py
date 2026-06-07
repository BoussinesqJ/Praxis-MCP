"""决策记录模型"""
from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    """决策状态"""
    PENDING_APPROVAL = "pending_approval"  # 待审批
    APPROVED = "approved"                  # 已审批
    REJECTED = "rejected"                  # 已拒绝
    EXECUTED = "executed"                  # 已执行（关联到交易）
    REVIEWED_5D = "reviewed_5d"           # 5日复盘完成
    REVIEWED_20D = "reviewed_20d"         # 20日复盘完成
    REVIEWED_60D = "reviewed_60d"         # 60日复盘完成


class TeamSignal(BaseModel):
    """AI 团队信号"""
    recommendation: str  # buy/sell/hold
    confidence: float = Field(ge=0, le=1)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_warnings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    counter_arguments: list[str] = Field(default_factory=list)
    invalid_if: list[str] = Field(default_factory=list)


class ReviewSnapshot(BaseModel):
    """复盘快照"""
    reviewed_at: datetime | None = None
    actual_price: float | None = None
    actual_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    notes: str | None = None


class DecisionRecord(BaseModel):
    """决策记录（每次投资决策的上下文和后验结果）"""
    decision_id: str = Field(description="决策唯一ID，格式：dc-YYYYMMDD-NNN")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ticker: str
    action: str  # buy/sell/hold/redeem/subscribe
    quantity: float | None = None
    price_range: list[float] | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    reasoning: str = ""
    ai_team_signals: dict[str, TeamSignal] = Field(default_factory=dict)
    risk_constraints: list[str] = Field(default_factory=list)
    status: DecisionStatus = DecisionStatus.PENDING_APPROVAL
    approved_by: str | None = None
    approved_at: datetime | None = None
    execution_tx_id: str | None = None
    review_5d: ReviewSnapshot | None = None
    review_20d: ReviewSnapshot | None = None
    review_60d: ReviewSnapshot | None = None

    def to_jsonl(self) -> str:
        """序列化为 JSONL 行"""
        import json
        data = self.model_dump(mode="json")
        return json.dumps(data, ensure_ascii=False)
