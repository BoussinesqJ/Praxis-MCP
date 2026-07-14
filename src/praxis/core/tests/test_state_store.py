"""tests for core/state_store.py — SQLiteStateStore + SQLiteLedger + SQLiteDecisionRecorder.

⚠️ SQLite 使用 :memory: 模式无文件残留。
"""

from __future__ import annotations

import pytest

from praxis.core.state_store import (
    SQLiteStateStore,
    SQLiteLedger,
    SQLiteDecisionRecorder,
)
from praxis.core.models import (
    Transaction,
    TransactionType,
    TransactionStatus,
    AssetType,
    DecisionRecord,
    DecisionStatus,
)
from praxis.core.ledger import FileLedger


# ── 辅助 ──────────────────────────────────────────────────────────


def _make_tx(**kwargs) -> Transaction:
    defaults = dict(
        ticker="000001",
        tx_type=TransactionType.BUY,
        quantity=100.0,
        price=10.0,
        investor_id="inv-test",
        portfolio_id="port-test",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def _make_decision(**kwargs) -> DecisionRecord:
    defaults = dict(
        ticker="000001",
        action="buy",
        confidence=0.8,
        reasoning="测试决策",
    )
    defaults.update(kwargs)
    return DecisionRecord(**defaults)


# ── 场景1：SQLiteStateStore save/load/delete/list_keys ─────────


class TestSQLiteStateStoreBasic:
    """SQLiteStateStore 基础 KV 操作。"""

    def test_save_and_load(self, sqlite_store: SQLiteStateStore):
        """save 后 load 返回原 dict。"""
        sqlite_store.save("test1", {"a": 1, "b": "hello"})
        result = sqlite_store.load("test1")
        assert result == {"a": 1, "b": "hello"}

    def test_load_nonexistent(self, sqlite_store: SQLiteStateStore):
        """不存在的 key 返回 None。"""
        assert sqlite_store.load("nonexistent") is None

    def test_save_overwrites(self, sqlite_store: SQLiteStateStore):
        """重复 save 覆盖旧值。"""
        sqlite_store.save("key1", {"v": 1})
        sqlite_store.save("key1", {"v": 2})
        assert sqlite_store.load("key1") == {"v": 2}

    def test_delete(self, sqlite_store: SQLiteStateStore):
        """delete 后 load 返回 None。"""
        sqlite_store.save("to_delete", {"x": 1})
        sqlite_store.delete("to_delete")
        assert sqlite_store.load("to_delete") is None

    def test_list_keys(self, sqlite_store: SQLiteStateStore):
        """list_keys 按前缀过滤。"""
        sqlite_store.save("test_a", {"v": 1})
        sqlite_store.save("test_b", {"v": 2})
        sqlite_store.save("other_c", {"v": 3})

        keys = sqlite_store.list_keys("test")
        assert set(keys) == {"test_a", "test_b"}

    def test_list_keys_all(self, sqlite_store: SQLiteStateStore):
        """list_keys("") 返回全部。"""
        sqlite_store.save("k1", {})
        sqlite_store.save("k2", {})
        assert len(sqlite_store.list_keys("")) == 2


# ── 场景2：SQLiteLedger append 基础 ────────────────────────────


class TestSQLiteLedgerAppend:
    """SQLiteLedger append 基础。"""

    def test_append_returns_tx_id(self, sqlite_ledger: SQLiteLedger):
        """append 返回 tx-* 格式 ID。"""
        tx = _make_tx()
        result = sqlite_ledger.append(tx)
        assert result.startswith("tx-")

    def test_append_persists(self, sqlite_ledger: SQLiteLedger):
        """append 后 get 可获取。"""
        tx = _make_tx()
        tx_id = sqlite_ledger.append(tx)
        retrieved = sqlite_ledger.get(tx_id)
        assert retrieved is not None
        assert retrieved.ticker == "000001"
        assert retrieved.quantity == 100.0

    def test_wal_mode(self, sqlite_ledger: SQLiteLedger):
        """WAL 模式生效（通过 append 不报错间接验证）。"""
        tx_id = sqlite_ledger.append(_make_tx())
        assert tx_id.startswith("tx-")

    def test_table_auto_created(self, sqlite_ledger: SQLiteLedger):
        """表自动创建。"""
        sqlite_ledger.append(_make_tx())
        # 如果能 append 不报错，说明表已存在


# ── 场景3：SQLiteLedger list/get/exists/delete/purge ──────────


class TestSQLiteLedgerCRUD:
    """SQLiteLedger CRUD 操作。"""

    def test_list_all(self, sqlite_ledger: SQLiteLedger):
        """list() 返回全部记录。"""
        sqlite_ledger.append(_make_tx(ticker="000001"))
        sqlite_ledger.append(_make_tx(ticker="600519"))
        results = sqlite_ledger.list()
        assert len(results) == 2

    def test_list_ticker_filter(self, sqlite_ledger: SQLiteLedger):
        """list(ticker='...') 过滤。"""
        sqlite_ledger.append(_make_tx(ticker="000001"))
        sqlite_ledger.append(_make_tx(ticker="600519"))
        results = sqlite_ledger.list(ticker="000001")
        assert len(results) == 1
        assert results[0].ticker == "000001"

    def test_list_limit(self, sqlite_ledger: SQLiteLedger):
        """list(limit=N) 限制。"""
        for i in range(5):
            sqlite_ledger.append(_make_tx(ticker=f"00000{i+1}"))
        results = sqlite_ledger.list(limit=2)
        assert len(results) == 2

    def test_get(self, sqlite_ledger: SQLiteLedger):
        """get 返回正确记录。"""
        tx_id = sqlite_ledger.append(_make_tx())
        tx = sqlite_ledger.get(tx_id)
        assert tx.tx_id == tx_id
        assert tx.ticker == "000001"

    def test_exists(self, sqlite_ledger: SQLiteLedger):
        """exists 幂等键检查。"""
        sqlite_ledger.append(_make_tx(idempotency_key="ikey-sqlite"))
        assert sqlite_ledger.exists("ikey-sqlite") is True
        assert sqlite_ledger.exists("ikey-nonexistent") is False

    def test_delete(self, sqlite_ledger: SQLiteLedger):
        """delete 后 get 返回 None。"""
        tx_id = sqlite_ledger.append(_make_tx())
        sqlite_ledger.delete(tx_id)
        assert sqlite_ledger.get(tx_id) is None

    def test_purge(self, sqlite_ledger: SQLiteLedger):
        """purge 全清。"""
        for _ in range(3):
            sqlite_ledger.append(_make_tx())
        count = sqlite_ledger.purge()
        assert count == 3
        assert len(sqlite_ledger.list()) == 0


# ── 场景4：SQLiteLedger reverse/approve/reject ────────────────


class TestSQLiteLedgerStateChange:
    """SQLiteLedger 状态变更操作。"""

    def test_reverse_generates_tx_rev_id(self, sqlite_ledger: SQLiteLedger):
        """reverse 生成 tx-rev-* ID。"""
        tx_id = sqlite_ledger.append(_make_tx())
        rev_id = sqlite_ledger.reverse(tx_id, "纠错")
        assert rev_id.startswith("tx-rev-")

    def test_reverse_updates_original_status(self, sqlite_ledger: SQLiteLedger):
        """reverse 将原始交易状态设为 reversed。"""
        tx_id = sqlite_ledger.append(_make_tx())
        sqlite_ledger.reverse(tx_id, "纠错")
        tx = sqlite_ledger.get(tx_id)
        assert tx.status == TransactionStatus.REVERSED

    def test_approve(self, sqlite_ledger: SQLiteLedger):
        """approve 更新状态为 approved。"""
        tx_id = sqlite_ledger.append(_make_tx())
        result = sqlite_ledger.approve(tx_id)
        assert result is True
        assert sqlite_ledger.get(tx_id).status == TransactionStatus.APPROVED

    def test_reject(self, sqlite_ledger: SQLiteLedger):
        """reject 更新状态为 rejected 并记录 reason。"""
        tx_id = sqlite_ledger.append(_make_tx())
        result = sqlite_ledger.reject(tx_id, "风险过高")
        assert result is True
        tx = sqlite_ledger.get(tx_id)
        assert tx.status == TransactionStatus.REJECTED
        assert "风险过高" in tx.reason

    def test_close(self, sqlite_ledger: SQLiteLedger):
        """close 后资源释放。"""
        sqlite_ledger.append(_make_tx())
        sqlite_ledger.close()
        # close 后不应崩溃


# ── 场景5：SQLiteDecisionRecorder create/get/list ──────────────


class TestSQLiteDecisionRecorderBasic:
    """SQLiteDecisionRecorder 基础 CRUD。"""

    def test_create_returns_dec_id(self, sqlite_decision_recorder: SQLiteDecisionRecorder):
        """create 返回 dec-* ID。"""
        dr = _make_decision()
        dec_id = sqlite_decision_recorder.create(dr)
        assert dec_id.startswith("dec-")

    def test_get_returns_full_record(self, sqlite_decision_recorder: SQLiteDecisionRecorder):
        """get 返回完整记录。"""
        dr = _make_decision(ticker="600519", action="sell", confidence=0.6)
        dec_id = sqlite_decision_recorder.create(dr)
        result = sqlite_decision_recorder.get(dec_id)
        assert result is not None
        assert result.ticker == "600519"
        assert result.action == "sell"
        assert result.confidence == 0.6

    def test_list_pending_filters_draft_and_pending(
        self, sqlite_decision_recorder: SQLiteDecisionRecorder
    ):
        """list_pending 仅返回 DRAFT/PENDING。"""
        sqlite_decision_recorder.create(_make_decision(status=DecisionStatus.DRAFT))
        sqlite_decision_recorder.create(_make_decision(status=DecisionStatus.PENDING))
        sqlite_decision_recorder.create(_make_decision(status=DecisionStatus.EXECUTED))

        pending = sqlite_decision_recorder.list_pending()
        assert len(pending) == 2

    def test_list_with_status_filter(
        self, sqlite_decision_recorder: SQLiteDecisionRecorder
    ):
        """list(status=...) 过滤。"""
        sqlite_decision_recorder.create(_make_decision(status=DecisionStatus.EXECUTED))
        sqlite_decision_recorder.create(_make_decision(status=DecisionStatus.DRAFT))

        executed = sqlite_decision_recorder.list(status="executed")
        assert len(executed) == 1

    def test_get_executed(self, sqlite_decision_recorder: SQLiteDecisionRecorder):
        """get_executed 返回已执行决策。"""
        for i in range(3):
            sqlite_decision_recorder.create(
                _make_decision(status=DecisionStatus.EXECUTED if i < 2 else DecisionStatus.DRAFT)
            )
        results = sqlite_decision_recorder.get_executed()
        assert len(results) == 2


# ── 场景6：SQLiteDecisionRecorder update_status/link/update_review ─


class TestSQLiteDecisionRecorderUpdates:
    """SQLiteDecisionRecorder 更新操作。"""

    def test_update_status(self, sqlite_decision_recorder: SQLiteDecisionRecorder):
        """update_status 影响 total_changes。"""
        dec_id = sqlite_decision_recorder.create(_make_decision())
        result = sqlite_decision_recorder.update_status(dec_id, "approved")
        assert result is True
        updated = sqlite_decision_recorder.get(dec_id)
        assert updated.status == DecisionStatus.APPROVED

    def test_link_transaction(self, sqlite_decision_recorder: SQLiteDecisionRecorder):
        """link_transaction 写入 tx_id。"""
        dec_id = sqlite_decision_recorder.create(_make_decision())
        result = sqlite_decision_recorder.link_transaction(dec_id, "tx-test-001")
        assert result is True
        updated = sqlite_decision_recorder.get(dec_id)
        assert updated.tx_id == "tx-test-001"

    def test_update_review(self, sqlite_decision_recorder: SQLiteDecisionRecorder):
        """update_review 回填 JSON 序列化。"""
        dec_id = sqlite_decision_recorder.create(_make_decision())
        result = sqlite_decision_recorder.update_review(
            dec_id, "5d", {"actual_return_pct": 3.5}
        )
        assert result is True
        updated = sqlite_decision_recorder.get(dec_id)
        assert updated.review_result is not None
        assert "5d" in updated.review_result
        assert "3.5" in updated.review_result


# ── 场景7：与 FileLedger 接口一致性 ────────────────────────────


class TestInterfaceConsistency:
    """同一个 Transaction 在两种 ledger 中行为一致。"""

    def test_same_tx_in_both_ledgers(self, file_ledger: FileLedger, sqlite_ledger: SQLiteLedger):
        """同笔 Transaction 在两种 ledger 中 get 返回一致字段值。"""
        tx = _make_tx(ticker="000001", quantity=150.0, price=12.5)
        # FileLedger
        fl_id = file_ledger.append(tx)
        fl_tx = file_ledger.get(fl_id)
        # SQLiteLedger
        sq_id = sqlite_ledger.append(
            _make_tx(ticker="000001", quantity=150.0, price=12.5)
        )
        sq_tx = sqlite_ledger.get(sq_id)

        # 核心字段一致
        assert fl_tx.ticker == sq_tx.ticker == "000001"
        assert fl_tx.quantity == sq_tx.quantity == 150.0
        assert fl_tx.price == sq_tx.price == 12.5
        # tx_type 枚举值均为字符串形式
        assert str(fl_tx.tx_type.value) == str(sq_tx.tx_type.value)

    def test_list_returns_same_type(self, file_ledger: FileLedger, sqlite_ledger: SQLiteLedger):
        """两种 ledger 的 list 都返回 Transaction 对象。"""
        file_ledger.append(_make_tx())
        sqlite_ledger.append(_make_tx())

        fl_results = file_ledger.list()
        sq_results = sqlite_ledger.list()

        assert all(isinstance(tx, Transaction) for tx in fl_results)
        assert all(isinstance(tx, Transaction) for tx in sq_results)


# ── 场景8：close 资源释放 ──────────────────────────────────────


class TestClose:
    """close 后资源释放。"""

    def test_state_store_close(self, sqlite_store: SQLiteStateStore):
        """close() 后 _conn 为 None（但 :memory: DB 在 close 后销毁）。"""
        sqlite_store.save("before_close", {"x": 1})
        sqlite_store.close()
        # :memory: 数据库 close 后销毁，重新连接是新的空数据库
        # 这里仅验证 close 不抛异常
        assert sqlite_store._conn is None

    def test_sqlite_ledger_close(self, sqlite_ledger: SQLiteLedger):
        """close() 后操作不报错。"""
        sqlite_ledger.append(_make_tx())
        sqlite_ledger.close()
        # close 不抛异常即通过

    def test_decision_recorder_close(
        self, sqlite_decision_recorder: SQLiteDecisionRecorder
    ):
        """close() 后操作不报错。"""
        sqlite_decision_recorder.create(_make_decision())
        sqlite_decision_recorder.close()
        # close 不抛异常即通过
