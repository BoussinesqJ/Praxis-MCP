"""E1.2-E1.4 — Ledger 测试（幂等性/原子性/反向冲销）"""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType, TransactionStatus


@pytest.fixture
def temp_ledger(tmp_path):
    """创建临时 ledger"""
    ledger_path = tmp_path / "test_transactions.jsonl"
    return FileLedger(ledger_path)


@pytest.fixture
def sample_tx():
    """示例交易"""
    return Transaction(
        tx_id="",
        type=TransactionType.BUY,
        ticker="000001",
        quantity=100,
        price=13.50,
        fee=5.0,
    )


class TestLedgerAppend:
    """E1.2 — Ledger 幂等性测试"""

    def test_append_basic(self, temp_ledger, sample_tx):
        """基本追加测试"""
        tx_id = temp_ledger.append(sample_tx)
        assert tx_id.startswith("tx-")
        assert temp_ledger.count() == 1

    def test_append_with_idempotency_key(self, temp_ledger):
        """幂等键测试：相同幂等键返回相同 tx_id"""
        tx1 = Transaction(
            tx_id="",
            type=TransactionType.BUY,
            ticker="000001",
            quantity=100,
            price=13.50,
            idempotency_key="test-key-001",
        )
        tx2 = Transaction(
            tx_id="",
            type=TransactionType.BUY,
            ticker="000001",
            quantity=100,
            price=13.50,
            idempotency_key="test-key-001",
        )

        tx_id1 = temp_ledger.append(tx1)
        tx_id2 = temp_ledger.append(tx2)

        assert tx_id1 == tx_id2
        assert temp_ledger.count() == 1

    def test_append_different_keys(self, temp_ledger):
        """不同幂等键创建不同记录"""
        tx1 = Transaction(
            tx_id="",
            type=TransactionType.BUY,
            ticker="000001",
            quantity=100,
            price=13.50,
            idempotency_key="key-001",
        )
        tx2 = Transaction(
            tx_id="",
            type=TransactionType.BUY,
            ticker="000001",
            quantity=100,
            price=13.50,
            idempotency_key="key-002",
        )

        tx_id1 = temp_ledger.append(tx1)
        tx_id2 = temp_ledger.append(tx2)

        assert tx_id1 != tx_id2
        assert temp_ledger.count() == 2


class TestLedgerAtomicity:
    """E1.3 — Ledger 原子性测试"""

    def test_file_exists_after_append(self, temp_ledger, sample_tx):
        """追加后文件存在"""
        temp_ledger.append(sample_tx)
        assert temp_ledger._path.exists()

    def test_file_readable_after_append(self, temp_ledger, sample_tx):
        """追加后文件可读"""
        temp_ledger.append(sample_tx)

        with open(temp_ledger._path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["ticker"] == "000001"

    def test_multiple_appends(self, temp_ledger):
        """多次追加"""
        for i in range(10):
            tx = Transaction(
                tx_id=f"tx-test-{i:03d}",
                type=TransactionType.BUY,
                ticker="000001",
                quantity=100,
                price=13.50,
            )
            temp_ledger.append(tx)

        assert temp_ledger.count() == 10

        with open(temp_ledger._path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 10


class TestLedgerReverse:
    """E1.4 — Ledger 反向冲销测试"""

    def test_reverse_buy(self, temp_ledger):
        """冲销买入交易"""
        # 先创建买入
        buy_tx = Transaction(
            tx_id="",
            type=TransactionType.BUY,
            ticker="000001",
            quantity=100,
            price=13.50,
            fee=5.0,
        )
        tx_id = temp_ledger.append(buy_tx)

        # 冲销
        correction_id = temp_ledger.reverse(tx_id, "测试冲销")

        # 验证
        assert correction_id != tx_id
        assert temp_ledger.count() == 2

        correction = temp_ledger.get(correction_id)
        assert correction.type == TransactionType.SELL
        assert correction.target_tx_id == tx_id
        assert correction.reason == "测试冲销"

    def test_reverse_sell(self, temp_ledger):
        """冲销卖出交易"""
        sell_tx = Transaction(
            tx_id="",
            type=TransactionType.SELL,
            ticker="000001",
            quantity=100,
            price=16.35,
            fee=5.0,
        )
        tx_id = temp_ledger.append(sell_tx)

        correction_id = temp_ledger.reverse(tx_id, "价格错误")
        correction = temp_ledger.get(correction_id)

        assert correction.type == TransactionType.BUY
        assert correction.target_tx_id == tx_id

    def test_reverse_nonexistent(self, temp_ledger):
        """冲销不存在的交易"""
        with pytest.raises(Exception):
            temp_ledger.reverse("tx-nonexistent", "测试")


class TestLedgerQuery:
    """Ledger 查询测试"""

    def test_list_all(self, temp_ledger):
        """查询所有记录"""
        for i in range(5):
            tx = Transaction(
                tx_id=f"tx-{i:03d}",
                type=TransactionType.BUY,
                ticker="000001",
                quantity=100,
                price=13.50,
            )
            temp_ledger.append(tx)

        results = temp_ledger.list()
        assert len(results) == 5

    def test_list_by_ticker(self, temp_ledger):
        """按标的查询"""
        tx1 = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="000001",
            quantity=100,
            price=13.50,
        )
        tx2 = Transaction(
            tx_id="tx-002",
            type=TransactionType.BUY,
            ticker="510310",
            quantity=400,
            price=4.826,
        )
        temp_ledger.append(tx1)
        temp_ledger.append(tx2)

        results = temp_ledger.list(ticker="000001")
        assert len(results) == 1
        assert results[0].ticker == "000001"

    def test_get_by_id(self, temp_ledger, sample_tx):
        """按 ID 查询"""
        tx_id = temp_ledger.append(sample_tx)
        result = temp_ledger.get(tx_id)
        assert result is not None
        assert result.ticker == "000001"

    def test_get_nonexistent(self, temp_ledger):
        """查询不存在的记录"""
        result = temp_ledger.get("tx-nonexistent")
        assert result is None
