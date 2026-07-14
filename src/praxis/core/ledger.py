"""交易账本（append-only JSONL）

设计原则（GPT 架构底线）：
- 不可覆盖：所有记录一旦写入不可修改，错误用冲销（reverse）修正
- 幂等键防重复写入
- 原子写入（写临时文件→fsync→rename）
- 每次写入自动记录审计日志

适配 PRAXIS Agent 新的 Pydantic v2 Transaction 模型。
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.interfaces import Ledger
from praxis.core.models import (
    Transaction,
    TransactionType,
    TransactionStatus,
    AssetType,
)
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class LedgerError(Exception):
    """账本操作异常"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class FileLedger(Ledger):
    """文件系统交易账本（append-only JSONL）

    特性：
    - 原子追加写入（flock + fsync）
    - 内存索引加速查询
    - 幂等键防重复
    - 冲销（reverse）代替物理删除

    Usage:
        ledger = FileLedger("workspace/ledger/transactions.jsonl")
        tx_id = ledger.append(tx)
        txs = ledger.list(ticker="000001", limit=50)
    """

    def __init__(self, ledger_path: str | Path):
        """初始化账本

        Args:
            ledger_path: JSONL 文件路径
        """
        self._path = Path(ledger_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # 确保文件存在
        if not self._path.exists():
            self._path.touch()

        # 内存索引（启动时加载）
        self._index: dict[str, Transaction] = {}
        self._idempotency_index: dict[str, str] = {}  # idempotency_key → tx_id
        self._load_index()

        logger.info(
            "ledger_initialized",
            path=str(self._path),
            tx_count=len(self._index),
        )

    # ── 内部方法 ───────────────────────────────────────────────

    def _load_index(self) -> None:
        """从 JSONL 文件加载内存索引"""
        count = 0
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
                    count += 1
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning("ledger_corrupt_line", error=str(e))
                    continue

        if count > 0:
            logger.debug("ledger_index_loaded", count=count)

    def _atomic_append(self, line: str) -> None:
        """原子追加写入

        策略：
        1. 打开文件（追加模式）
        2. seek 到末尾
        3. 写入 + flush
        4. fsync 确保持久化

        对于 append-only 场景，不需要写入临时文件再 rename，
        因为追加操作本身不会破坏已有数据。
        """
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            raise LedgerError(f"写入账本失败: {e}") from e

    def _generate_tx_id(self) -> str:
        """生成交易 ID

        格式: tx-YYYYMMDD-NNN
        """
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"tx-{today}-"
        count = sum(1 for tx_id in self._index if tx_id.startswith(prefix))
        return f"{prefix}{count + 1:03d}"

    def _rewrite_file(self) -> None:
        """重写整个账本文件（仅在 delete/purge 时使用）

        使用原子写入策略：
        1. 写入临时文件
        2. fsync
        3. os.replace（原子重命名）

        警告：破坏 append-only 语义，仅用于清理测试/错误数据。
        """
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                # 按创建时间正序写入
                sorted_txs = sorted(
                    self._index.values(),
                    key=lambda tx: tx.created_at,
                )
                for tx in sorted_txs:
                    f.write(self._serialize(tx) + "\n")
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

    @staticmethod
    def _serialize(tx: Transaction) -> str:
        """序列化交易记录为 JSON 字符串

        适配 Pydantic v2 Transaction model。
        """
        data = tx.model_dump(mode="json")
        return json.dumps(data, ensure_ascii=False)

    # ── Ledger 接口实现 ────────────────────────────────────────

    def append(self, tx: Transaction) -> str:
        """追加交易记录，返回 tx_id

        规则：
        1. 幂等：如果 idempotency_key 已存在，返回已有 tx_id
        2. 唯一性：如果 tx_id 已存在，拒绝重复写入
        3. 自动生成 tx_id（如果为空）

        Args:
            tx: 交易记录

        Returns:
            交易的 tx_id

        Raises:
            LedgerError: 重复写入时抛出
        """
        # 幂等检查
        if tx.idempotency_key and tx.idempotency_key in self._idempotency_index:
            existing_tx_id = self._idempotency_index[tx.idempotency_key]
            logger.debug(
                "ledger_idempotent_skip",
                idempotency_key=tx.idempotency_key,
                existing_tx_id=existing_tx_id,
            )
            return existing_tx_id

        # tx_id 唯一性校验
        if tx.tx_id and tx.tx_id in self._index:
            raise LedgerError(f"交易 {tx.tx_id} 已存在，拒绝重复写入")

        # 自动生成 tx_id
        if not tx.tx_id:
            tx.tx_id = self._generate_tx_id()

        # 序列化
        line = self._serialize(tx) + "\n"

        # 原子写入
        self._atomic_append(line)

        # 更新索引
        self._index[tx.tx_id] = tx
        if tx.idempotency_key:
            self._idempotency_index[tx.idempotency_key] = tx.tx_id

        logger.info(
            "ledger_append",
            tx_id=tx.tx_id,
            ticker=tx.ticker,
            tx_type=tx.tx_type.value,
            quantity=tx.quantity,
        )

        return tx.tx_id

    def list(
        self, ticker: str | None = None, limit: int = 100
    ) -> list[Transaction]:
        """查询交易记录

        Args:
            ticker: 按标的代码过滤（可选）
            limit: 最大返回数量

        Returns:
            交易记录列表（按创建时间倒序）
        """
        results = list(self._index.values())

        if ticker:
            results = [tx for tx in results if tx.ticker == ticker]

        # 按创建时间倒序
        results.sort(key=lambda tx: tx.created_at, reverse=True)
        return results[:limit]

    def get(self, tx_id: str) -> Transaction | None:
        """获取单条交易记录

        Args:
            tx_id: 交易 ID

        Returns:
            交易记录，不存在则返回 None
        """
        return self._index.get(tx_id)

    def exists(self, idempotency_key: str) -> bool:
        """检查幂等键是否已存在

        Args:
            idempotency_key: 幂等键

        Returns:
            True 如果已存在
        """
        return idempotency_key in self._idempotency_index

    def delete(self, tx_id: str) -> bool:
        """物理删除单条交易记录

        警告：破坏 append-only 语义，仅用于清理测试/错误数据。
        正常业务应使用 reverse()。

        Args:
            tx_id: 要删除的交易 ID

        Returns:
            True 如果成功删除，False 如果不存在
        """
        if tx_id not in self._index:
            return False

        tx = self._index.pop(tx_id)
        if tx.idempotency_key:
            self._idempotency_index.pop(tx.idempotency_key, None)

        self._rewrite_file()

        logger.warning("ledger_delete", tx_id=tx_id, ticker=tx.ticker)
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
            logger.warning("ledger_purge_all", count=count)
            return count

        self._rewrite_file()

        logger.warning("ledger_purge_tag", tag=tag, count=len(to_remove))
        return len(to_remove)

    # ── 扩展方法 ───────────────────────────────────────────────

    def reverse(self, tx_id: str, reason: str) -> str:
        """反向冲销（GPT 架构底线：错误用冲销，不用覆盖）

        创建一条与原交易相反的冲销记录：
        - BUY → SELL 冲销
        - SELL → BUY 冲销
        - SUBSCRIBE → REDEEM 冲销
        - REDEEM → SUBSCRIBE 冲销

        防护规则：
        1. 不能冲销不存在的交易
        2. 不能冲销冲销记录本身
        3. 不能重复冲销已被冲销的交易
        4. 分红交易不能冲销（无对手方）

        Args:
            tx_id: 要冲销的原始交易 ID
            reason: 冲销原因

        Returns:
            冲销记录的 tx_id

        Raises:
            LedgerError: 冲销条件不满足时抛出
        """
        original = self.get(tx_id)
        if not original:
            raise LedgerError(f"交易 {tx_id} 不存在，无法冲销")

        # 防护：不能冲销已经是冲销的记录
        if original.tx_type == TransactionType.REVERSE:
            raise LedgerError(f"交易 {tx_id} 已经是冲销记录，不能再次冲销")

        # 防护：检查是否已被其他记录冲销
        for other in self._index.values():
            if (
                other.tx_type == TransactionType.REVERSE
                and other.reason
                and tx_id in other.reason
            ):
                raise LedgerError(
                    f"交易 {tx_id} 已被 {other.tx_id} 冲销，不能重复冲销"
                )

        # 防护：分红无 quantity 可逆
        if original.tx_type == TransactionType.DIVIDEND:
            raise LedgerError(
                f"分红交易 {tx_id} 不能冲销（无对手方），请用反向分红记录处理"
            )

        # 确定冲销类型
        reverse_type_map = {
            TransactionType.BUY: TransactionType.SELL,
            TransactionType.SELL: TransactionType.BUY,
            TransactionType.SUBSCRIBE: TransactionType.REDEEM,
            TransactionType.REDEEM: TransactionType.SUBSCRIBE,
        }
        reverse_type = reverse_type_map.get(
            original.tx_type, TransactionType.REVERSE
        )

        # 创建冲销记录
        now = datetime.now(timezone.utc).isoformat()
        correction = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=reverse_type,
            ticker=original.ticker,
            quantity=original.quantity,
            price=original.price,
            fee=0.0,
            asset_type=original.asset_type,
            status=TransactionStatus.EXECUTED,
            idempotency_key="",
            tags=original.tags + ["reversal"],
            decision_id="",
            reason=f"冲销 {tx_id}: {reason}",
            created_at=now,
            updated_at=now,
            investor_id=original.investor_id,
            portfolio_id=original.portfolio_id,
        )

        result_id = self.append(correction)
        logger.info(
            "ledger_reverse",
            original_tx_id=tx_id,
            reverse_tx_id=result_id,
            reason=reason,
        )
        return result_id

    def approve(self, tx_id: str) -> bool:
        """审批通过交易

        将交易状态从 PENDING 更新为 APPROVED。

        Args:
            tx_id: 交易 ID

        Returns:
            True 如果成功，False 如果交易不存在
        """
        tx = self._index.get(tx_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.PENDING:
            logger.warning(
                "ledger_approve_skip",
                tx_id=tx_id,
                current_status=tx.status.value,
            )
            return False

        tx.status = TransactionStatus.APPROVED
        tx.updated_at = datetime.now(timezone.utc).isoformat()
        self._rewrite_file()

        logger.info("ledger_approve", tx_id=tx_id)
        return True

    def reject(self, tx_id: str, reason: str) -> bool:
        """拒绝交易

        将交易状态从 PENDING 更新为 REJECTED。

        Args:
            tx_id: 交易 ID
            reason: 拒绝原因

        Returns:
            True 如果成功，False 如果交易不存在
        """
        tx = self._index.get(tx_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.PENDING:
            logger.warning(
                "ledger_reject_skip",
                tx_id=tx_id,
                current_status=tx.status.value,
            )
            return False

        tx.status = TransactionStatus.REJECTED
        tx.reason = reason
        tx.updated_at = datetime.now(timezone.utc).isoformat()
        self._rewrite_file()

        logger.info("ledger_reject", tx_id=tx_id, reason=reason)
        return True

    # ── 数据重载 ───────────────────────────────────────────────

    def reload(self) -> int:
        """重新从磁盘加载全部交易记录到内存索引

        用于外部修改 JSONL 文件后刷新内存缓存（无需重启 MCP）。

        Returns:
            重载后索引中的记录数
        """
        self._index.clear()
        self._idempotency_index.clear()
        self._load_index()
        logger.debug("ledger_reloaded", count=len(self._index))
        return len(self._index)

    # ── 查询扩展 ───────────────────────────────────────────────

    def get_all(self) -> list[Transaction]:
        """获取所有交易记录（按创建时间正序）

        Returns:
            全部交易记录列表
        """
        results = list(self._index.values())
        results.sort(key=lambda tx: tx.created_at)
        return results

    def get_by_decision(self, decision_id: str) -> list[Transaction]:
        """获取关联某决策的所有交易

        Args:
            decision_id: 决策 ID

        Returns:
            关联的交易记录列表
        """
        return [
            tx for tx in self._index.values()
            if tx.decision_id == decision_id
        ]

    def count(self) -> int:
        """交易总数"""
        return len(self._index)

    def get_by_status(
        self, status: TransactionStatus, limit: int = 100
    ) -> list[Transaction]:
        """按状态查询交易

        Args:
            status: 交易状态
            limit: 最大返回数量

        Returns:
            匹配的交易记录列表
        """
        results = [
            tx for tx in self._index.values()
            if tx.status == status
        ]
        results.sort(key=lambda tx: tx.created_at, reverse=True)
        return results[:limit]
