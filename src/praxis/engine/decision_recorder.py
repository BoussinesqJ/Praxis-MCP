"""决策记录器 — JSONL append-only

核心职责:
1. 创建决策记录（关联交易前的思考过程）
2. 关联交易记录（决策→交易的映射）
3. 复盘回填（5d/20d/60d 后回填实际结果）
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.interfaces import DecisionRecorder
from praxis.core.models import DecisionRecord, DecisionStatus
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class FileDecisionRecorder(DecisionRecorder):
    """文件系统决策记录器"""

    def __init__(self, decisions_path: str | Path):
        self._path = Path(decisions_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()
        self._index: dict[str, DecisionRecord] = {}
        self._load_index()

    def _load_index(self):
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = DecisionRecord(**data)
                    self._index[record.decision_id] = record
                except Exception:
                    continue

    def create(self, record: DecisionRecord) -> str:
        """创建决策记录，返回 decision_id"""
        if not record.decision_id:
            record.decision_id = self._generate_id()
        record.created_at = datetime.now(timezone.utc).isoformat()
        record.updated_at = record.created_at

        self._append_record(record)
        self._index[record.decision_id] = record
        logger.info("decision_created", decision_id=record.decision_id,
                     ticker=record.ticker, action=record.action)
        return record.decision_id

    def get(self, decision_id: str) -> DecisionRecord | None:
        return self._index.get(decision_id)

    def get_executed(self, limit: int = 100) -> list[DecisionRecord]:
        """获取已执行的决策"""
        records = [r for r in self._index.values() if r.status == DecisionStatus.EXECUTED]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def list_pending(self, limit: int = 50) -> list[DecisionRecord]:
        """列出待审批的决策"""
        records = [r for r in self._index.values()
                   if r.status in (DecisionStatus.DRAFT, DecisionStatus.PENDING)]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def update_status(self, decision_id: str, status: str, **kwargs) -> bool:
        """更新决策状态"""
        record = self._index.get(decision_id)
        if record is None:
            return False

        try:
            record.status = DecisionStatus(status)
        except ValueError:
            return False

        record.updated_at = datetime.now(timezone.utc).isoformat()
        if "review_result" in kwargs:
            record.review_result = kwargs["review_result"]
        self._rewrite_file()
        return True

    def link_transaction(self, decision_id: str, tx_id: str) -> bool:
        """关联决策与交易"""
        record = self._index.get(decision_id)
        if record is None:
            return False
        record.tx_id = tx_id
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._rewrite_file()
        return True

    def update_review(self, decision_id: str, review_type: str, review_data: dict) -> bool:
        """回填复盘数据"""
        record = self._index.get(decision_id)
        if record is None:
            return False
        record.review_result = json.dumps({"type": review_type, **review_data}, ensure_ascii=False)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._rewrite_file()
        return True

    def list(self, status: str | None = None, limit: int = 100) -> list[DecisionRecord]:
        """列出决策（支持状态过滤）"""
        if status:
            try:
                ds = DecisionStatus(status)
                records = [r for r in self._index.values() if r.status == ds]
            except ValueError:
                records = []
        else:
            records = list(self._index.values())
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def _append_record(self, record: DecisionRecord):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump(), ensure_ascii=False, default=str) + "\n")

    def _rewrite_file(self):
        """重写全量文件（更新记录后）"""
        with open(self._path, "w", encoding="utf-8") as f:
            for record in self._index.values():
                f.write(json.dumps(record.model_dump(), ensure_ascii=False, default=str) + "\n")

    @staticmethod
    def _generate_id() -> str:
        return f"dec-{uuid.uuid4().hex[:12]}"

    def reload(self) -> int:
        """重新从磁盘加载全部决策记录到内存索引

        用于外部修改 JSONL 文件后刷新内存缓存（无需重启 MCP）。

        Returns:
            重载后索引中的记录数
        """
        self._index.clear()
        self._load_index()
        logger.debug("decision_recorder_reloaded", count=len(self._index))
        return len(self._index)
