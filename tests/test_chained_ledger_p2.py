"""Chained Ledger 链式哈希防篡改与完整性校验测试"""
import pytest
import tempfile
import json
from pathlib import Path
from praxis.core.ledger import FileLedger
from praxis.core.database import Database
from praxis.core.models.transaction import Transaction, TransactionType


def test_chained_ledger_integrity():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        ledger_path = Path(tmpdir) / "ledger.jsonl"
        ledger = FileLedger(ledger_path, db=db)
        
        tx1 = Transaction(
            tx_id="",
            type=TransactionType.BUY,
            ticker="600995",
            quantity=100.0,
            price=10.0,
            idempotency_key="key-001"
        )
        tx2 = Transaction(
            tx_id="",
            type=TransactionType.SELL,
            ticker="600995",
            quantity=50.0,
            price=12.0,
            idempotency_key="key-002"
        )
        
        tx_id1 = ledger.append(tx1)
        tx_id2 = ledger.append(tx2)
        
        # 验证 prev_hash 与 tx_hash 链条
        t1 = ledger.get(tx_id1)
        t2 = ledger.get(tx_id2)
        
        assert t1.prev_hash is None
        assert t1.tx_hash is not None
        assert t2.prev_hash == t1.tx_hash
        assert t2.tx_hash is not None
        
        # 验证完整性检查通过
        passed, errors = ledger.verify_integrity()
        assert passed
        assert len(errors) == 0


def test_chained_ledger_tampering_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        ledger_path = Path(tmpdir) / "ledger.jsonl"
        ledger = FileLedger(ledger_path, db=db)
        
        tx1 = Transaction(
            tx_id="tx-1",
            type=TransactionType.BUY,
            ticker="600995",
            quantity=100.0,
            price=10.0,
        )
        tx2 = Transaction(
            tx_id="tx-2",
            type=TransactionType.SELL,
            ticker="600995",
            quantity=50.0,
            price=12.0,
        )
        
        ledger.append(tx1)
        ledger.append(tx2)
        
        # 验证通过
        passed, errors = ledger.verify_integrity()
        assert passed
        
        # 模拟人为篡改 ledger.jsonl 文件中的 tx1 价格
        lines = []
        with open(ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                if data["tx_id"] == "tx-1":
                    data["price"] = 9.99  # 恶意篡改
                lines.append(json.dumps(data) + "\n")
                
        with open(ledger_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        # 重新加载 ledger
        ledger_tampered = FileLedger(ledger_path, db=db)
        passed, errors = ledger_tampered.verify_integrity()
        
        # 应该检测到哈希不匹配
        assert not passed
        assert any("hash mismatch" in err or "prev_hash mismatch" in err for err in errors)
