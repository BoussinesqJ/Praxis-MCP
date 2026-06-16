"""审计事件模型（append-only）"""
from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    """审计事件类型"""
    TOOL_CALL = "tool_call"              # MCP 工具调用
    TRANSACTION = "transaction"          # 交易记录变更
    DECISION = "decision"                # 决策记录变更
    RULE_CHANGE = "rule_change"          # 规则变更
    PROMPT_CHANGE = "prompt_change"      # Prompt 变更
    CONFIG_CHANGE = "config_change"      # 配置变更
    STATE_REBUILD = "state_rebuild"      # 状态重建
    RECONCILE = "reconcile"              # 对账操作
    EVOLUTION = "evolution"              # 进化操作


class AuditEvent(BaseModel):
    """审计事件（append-only）"""
    event_id: str = Field(description="事件唯一ID，格式：evt-YYYYMMDD-NNN")
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "system"  # "system" | "user" | "ai_agent"
    tool_name: str | None = None
    parameters: dict = Field(default_factory=dict)
    result_summary: str = ""
    success: bool = True
    error_message: str | None = None
    duration_ms: int | None = None
    idempotency_key: str | None = None

    def to_jsonl(self) -> str:
        """序列化为 JSONL 行"""
        import json
        data = self.model_dump(mode="json")
        return json.dumps(data, ensure_ascii=False)
