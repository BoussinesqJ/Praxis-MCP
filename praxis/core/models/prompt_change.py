"""Prompt 变更记录模型"""
from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PromptChangeStatus(str, Enum):
    """Prompt 变更状态"""
    PENDING = "pending"          # 待审批
    APPROVED = "approved"        # 已审批
    REJECTED = "rejected"        # 已拒绝


class PromptChange(BaseModel):
    """Prompt 变更记录"""
    change_id: str = Field(description="变更唯一ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    file_path: str               # 变更的文件
    old_hash: str                # 旧版本 hash
    new_hash: str                # 新版本 hash
    diff: str                    # 变更差异
    reason: str                  # 变更原因
    status: PromptChangeStatus = PromptChangeStatus.PENDING
    approved_by: str | None = None
    scanner_result: dict = Field(default_factory=dict)  # 安全扫描结果

    def to_jsonl(self) -> str:
        """序列化为 JSONL 行"""
        import json
        data = self.model_dump(mode="json")
        return json.dumps(data, ensure_ascii=False)
