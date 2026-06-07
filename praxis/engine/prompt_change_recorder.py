"""Prompt 变更记录器（append-only）"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.models.prompt_change import PromptChange, PromptChangeStatus
from praxis.core.models.error import PraxisError


class PromptChangeRecorder:
    """Prompt 变更记录器"""

    def __init__(self, changes_path: str | Path):
        self._path = Path(changes_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()

        # 内存索引
        self._index: dict[str, PromptChange] = {}
        self._load_index()

    def _load_index(self):
        """从文件加载索引"""
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    change = PromptChange(**data)
                    self._index[change.change_id] = change
                except (json.JSONDecodeError, Exception):
                    continue

    def record(self, change: PromptChange) -> str:
        """记录变更（append-only）"""
        if not change.change_id:
            change.change_id = self._generate_change_id()

        # 追加记录
        line = change.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        self._index[change.change_id] = change
        return change.change_id

    def _generate_change_id(self) -> str:
        """生成变更 ID"""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        count = sum(1 for c in self._index.values() if today in c.change_id)
        return f"pc-{today}-{count + 1:03d}"

    def get(self, change_id: str) -> PromptChange | None:
        """获取变更记录"""
        return self._index.get(change_id)

    def list_pending(self) -> list[PromptChange]:
        """列出待审批的变更"""
        return [
            c for c in self._index.values()
            if c.status == PromptChangeStatus.PENDING
        ]

    def approve(self, change_id: str, approved_by: str) -> bool:
        """审批变更"""
        change = self.get(change_id)
        if not change:
            return False

        change.status = PromptChangeStatus.APPROVED
        change.approved_by = approved_by

        # 追加更新记录
        line = change.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        return True

    def reject(self, change_id: str, reason: str) -> bool:
        """拒绝变更"""
        change = self.get(change_id)
        if not change:
            return False

        change.status = PromptChangeStatus.REJECTED

        # 追加更新记录
        line = change.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        return True

    def count(self) -> int:
        """变更总数"""
        return len(self._index)
