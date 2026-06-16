"""决策记录器（GPT 架构底线：每次决策必须记录上下文）

核心职责：
1. 创建决策记录（关联交易前的思考过程）
2. 关联交易记录（决策→交易的映射）
3. 复盘回填（5d/20d/60d 后回填实际结果）
4. 统计 AI 团队建议命中率
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.interfaces import DecisionRecorder as DecisionRecorderInterface
from praxis.core.models.decision import DecisionRecord, DecisionStatus
from praxis.core.models.error import LedgerError


class FileDecisionRecorder(DecisionRecorderInterface):
    """文件系统决策记录器（append-only JSONL）"""

    def __init__(self, decisions_path: str | Path):
        self._path = Path(decisions_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()
        # 内存索引
        self._index: dict[str, DecisionRecord] = {}
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
                    record = DecisionRecord(**data)
                    self._index[record.decision_id] = record
                except (json.JSONDecodeError, Exception):
                    continue

    def create(self, record: DecisionRecord) -> str:
        """创建决策记录，返回 decision_id"""
        if not record.decision_id:
            record.decision_id = self._generate_decision_id()

        # 写入文件
        line = record.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        # 更新索引
        self._index[record.decision_id] = record
        return record.decision_id

    def _generate_decision_id(self) -> str:
        """生成决策 ID"""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        count = sum(1 for d in self._index.values() if today in d.decision_id)
        return f"dc-{today}-{count + 1:03d}"

    def get(self, decision_id: str) -> DecisionRecord | None:
        """获取决策记录"""
        return self._index.get(decision_id)

    def update_status(self, decision_id: str, status: str, **kwargs) -> bool:
        """更新决策状态"""
        record = self.get(decision_id)
        if not record:
            return False

        # 更新状态
        record.status = DecisionStatus(status)
        if "approved_by" in kwargs:
            record.approved_by = kwargs["approved_by"]
        if "approved_at" in kwargs:
            record.approved_at = kwargs["approved_at"]
        if "execution_tx_id" in kwargs:
            record.execution_tx_id = kwargs["execution_tx_id"]

        # 追加更新记录
        line = record.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        return True

    def list_pending(self, limit: int = 50) -> list[DecisionRecord]:
        """列出待审批的决策"""
        pending = [
            d for d in self._index.values()
            if d.status == DecisionStatus.PENDING_APPROVAL
        ]
        return pending[:limit]

    def link_transaction(self, decision_id: str, tx_id: str) -> bool:
        """关联决策与交易"""
        record = self.get(decision_id)
        if not record:
            return False

        record.execution_tx_id = tx_id
        record.status = DecisionStatus.EXECUTED

        # 追加更新记录
        line = record.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        return True

    def get_all(self) -> list[DecisionRecord]:
        """获取所有决策记录"""
        return list(self._index.values())

    def get_by_ticker(self, ticker: str) -> list[DecisionRecord]:
        """获取某标的的所有决策"""
        return [d for d in self._index.values() if d.ticker == ticker]

    def get_executed(self) -> list[DecisionRecord]:
        """获取所有已执行的决策"""
        return [
            d for d in self._index.values()
            if d.status in (DecisionStatus.EXECUTED, DecisionStatus.REVIEWED_5D,
                           DecisionStatus.REVIEWED_20D, DecisionStatus.REVIEWED_60D)
        ]

    def update_review(self, decision_id: str, review_type: str, review: dict) -> bool:
        """更新复盘记录"""
        record = self.get(decision_id)
        if not record:
            return False

        from praxis.core.models.decision import ReviewSnapshot
        snapshot = ReviewSnapshot(**review)

        if review_type == "5d":
            record.review_5d = snapshot
            record.status = DecisionStatus.REVIEWED_5D
        elif review_type == "20d":
            record.review_20d = snapshot
            record.status = DecisionStatus.REVIEWED_20D
        elif review_type == "60d":
            record.review_60d = snapshot
            record.status = DecisionStatus.REVIEWED_60D
        else:
            return False

        # 追加更新记录
        line = record.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        return True

    def count(self) -> int:
        """决策总数"""
        return len(self._index)
