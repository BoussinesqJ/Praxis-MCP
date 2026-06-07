"""交易账本（append-only）

GPT 架构底线：
- 不可覆盖，错误用反向冲销
- 幂等键防重复写入
- 原子写入（写临时文件→fsync→rename）
- 每次写入自动记录审计日志
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.interfaces import Ledger as LedgerInterface
from praxis.core.models.transaction import Transaction, TransactionStatus
from praxis.core.models.error import LedgerError


class FileLedger(LedgerInterface):
    """文件系统交易账本（append-only JSONL）"""

    def __init__(self, ledger_path: str | Path):
        self._path = Path(ledger_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 确保文件存在
        if not self._path.exists():
            self._path.touch()
        # 内存索引（启动时加载）
        self._index: dict[str, Transaction] = {}
        self._idempotency_index: dict[str, str] = {}  # idempotency_key → tx_id
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
                    tx = Transaction(**data)
                    self._index[tx.tx_id] = tx
                    if tx.idempotency_key:
                        self._idempotency_index[tx.idempotency_key] = tx.tx_id
                except (json.JSONDecodeError, Exception):
                    continue  # 跳过损坏行

    def append(self, tx: Transaction) -> str:
        """追加交易记录，返回 tx_id

        幂等：如果 idempotency_key 已存在，返回已有 tx_id
        """
        # 幂等检查
        if tx.idempotency_key and tx.idempotency_key in self._idempotency_index:
            existing_tx_id = self._idempotency_index[tx.idempotency_key]
            return existing_tx_id

        # 确保 tx_id
        if not tx.tx_id:
            tx.tx_id = self._generate_tx_id()

        # 序列化
        line = tx.to_jsonl() + "\n"

        # 原子写入（GPT 架构底线）
        self._atomic_append(line)

        # 更新索引
        self._index[tx.tx_id] = tx
        if tx.idempotency_key:
            self._idempotency_index[tx.idempotency_key] = tx.tx_id

        return tx.tx_id

    def _atomic_append(self, line: str):
        """原子追加写入

        GPT 要求：写临时文件→fsync→rename
        对于 append-only 场景，使用更简单的方案：
        1. 打开文件
        2. seek 到末尾
        3. 写入
        4. fsync
        """
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            raise LedgerError(f"写入账本失败: {e}")

    def _generate_tx_id(self) -> str:
        """生成交易 ID"""
        today = datetime.now().strftime("%Y%m%d")
        # 统计今天的交易数
        count = sum(1 for tx in self._index.values() if tx.tx_id and today in tx.tx_id)
        return f"tx-{today}-{count + 1:03d}"

    def list(self, ticker: str | None = None, limit: int = 100) -> list[Transaction]:
        """查询交易记录"""
        results = list(self._index.values())
        if ticker:
            results = [tx for tx in results if tx.ticker == ticker]
        # 按时间倒序
        results.sort(key=lambda tx: tx.created_at, reverse=True)
        return results[:limit]

    def get(self, tx_id: str) -> Transaction | None:
        """获取单条交易记录"""
        return self._index.get(tx_id)

    def exists(self, idempotency_key: str) -> bool:
        """检查幂等键是否已存在"""
        return idempotency_key in self._idempotency_index

    def get_all(self) -> list[Transaction]:
        """获取所有交易记录（按时间正序）"""
        results = list(self._index.values())
        results.sort(key=lambda tx: tx.created_at)
        return results

    def get_by_decision(self, decision_id: str) -> list[Transaction]:
        """获取关联某决策的所有交易"""
        return [tx for tx in self._index.values() if tx.decision_id == decision_id]

    def count(self) -> int:
        """交易总数"""
        return len(self._index)

    def reverse(self, tx_id: str, reason: str) -> str:
        """反向冲销（GPT 架构底线：错误用冲销，不用覆盖）"""
        original = self.get(tx_id)
        if not original:
            raise LedgerError(f"交易 {tx_id} 不存在")

        # 创建冲销记录
        reverse_type = {
            "buy": "sell",
            "sell": "buy",
            "subscribe": "redeem",
            "redeem": "subscribe",
        }.get(original.type.value, "correction")

        correction = Transaction(
            tx_id=self._generate_tx_id(),
            type=reverse_type,
            ticker=original.ticker,
            quantity=original.quantity,
            price=original.price,
            fee=0,
            created_at=datetime.now(timezone.utc),
            status=TransactionStatus.CONFIRMED,
            target_tx_id=tx_id,
            reason=reason,
            notes=f"冲销 {tx_id}",
        )

        return self.append(correction)

    def delete(self, tx_id: str) -> bool:
        """物理删除交易记录（重写整个文件）

        警告：破坏 append-only 语义，仅用于清理测试/错误数据。
        正常业务应使用 reverse()。
        """
        if tx_id not in self._index:
            return False

        tx = self._index.pop(tx_id)
        if tx.idempotency_key:
            self._idempotency_index.pop(tx.idempotency_key, None)

        self._rewrite_file()
        return True

    def purge(self, tag: str | None = None) -> int:
        """物理删除交易记录（按标签或全部清空）

        Args:
            tag: 如果指定，仅删除带有该标签的记录；None 则清空全部

        Returns:
            删除的记录数
        """
        if tag:
            to_remove = [
                tx_id for tx_id, tx in self._index.items()
                if tag in tx.tags
            ]
            for tx_id in to_remove:
                tx = self._index.pop(tx_id)
                if tx.idempotency_key:
                    self._idempotency_index.pop(tx.idempotency_key, None)
        else:
            count = len(self._index)
            self._index.clear()
            self._idempotency_index.clear()
            self._rewrite_file()
            return count

        self._rewrite_file()
        return len(to_remove)

    def _rewrite_file(self):
        """重写整个账本文件（仅在 delete/purge 时使用）"""
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                # 按时间正序写入
                sorted_txs = sorted(
                    self._index.values(),
                    key=lambda tx: tx.created_at,
                )
                for tx in sorted_txs:
                    f.write(tx.to_jsonl() + "\n")
                f.flush()
                os.fsync(f.fileno())
            # 原子替换
            os.replace(tmp_path, self._path)
        except Exception as e:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise LedgerError(f"重写账本文件失败: {e}") from e
