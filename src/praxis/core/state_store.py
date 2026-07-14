"""SQLite 状态存储 — Phase 3 JSONL→SQLite 迁移

替换 FileLedger/FileDecisionRecorder 的 JSONL 存储为 SQLite 持久化。

特性:
- WAL 模式（支持并发读）
- 实现 Ledger + DecisionRecorder ABC
- 批量操作 + 事务支持
- 与现有 FileLedger 同名接口（无缝切换）
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from praxis.core.interfaces import Ledger, DecisionRecorder, StateStore
from praxis.core.models import Transaction, DecisionRecord, DecisionStatus, TransactionStatus
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class SQLiteStateStore(StateStore):
    """SQLite 统一状态存储"""

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, isolation_level=None)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def save(self, key: str, data: dict) -> None:
        """通用保存（键值对 JSON 存储）"""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )

    def load(self, key: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else None

    def delete(self, key: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
        return True

    def list_keys(self, prefix: str = "") -> list[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT key FROM kv_store WHERE key LIKE ?", (f"{prefix}%",)
        ).fetchall()
        return [r["key"] for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


class SQLiteLedger(Ledger):
    """SQLite 交易账本 — 实现 Ledger ABC，替代 FileLedger"""

    def __init__(self, db_path: str | Path):
        self._db = SQLiteStateStore(db_path)
        self._ensure_tables()

    def _ensure_tables(self):
        conn = self._db._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                investor_id TEXT NOT NULL DEFAULT '',
                portfolio_id TEXT NOT NULL DEFAULT '',
                ticker TEXT NOT NULL,
                tx_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                fee REAL NOT NULL DEFAULT 0,
                asset_type TEXT NOT NULL DEFAULT 'stock',
                status TEXT NOT NULL DEFAULT 'pending',
                idempotency_key TEXT NOT NULL DEFAULT '',
                tags TEXT DEFAULT '[]',
                decision_id TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                extra_data TEXT DEFAULT '{}'
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_idempotency ON transactions(idempotency_key) WHERE idempotency_key != '';
            CREATE INDEX IF NOT EXISTS idx_tx_ticker ON transactions(ticker);
            CREATE INDEX IF NOT EXISTS idx_tx_status ON transactions(status);

            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

    def append(self, tx: Transaction) -> str:
        if not tx.tx_id:
            tx.tx_id = f"tx-{uuid.uuid4().hex[:12]}"
        if tx.idempotency_key and self.exists(tx.idempotency_key):
            existing = self.get_by_idempotency(tx.idempotency_key)
            return existing.tx_id if existing else tx.tx_id

        now = datetime.now(timezone.utc).isoformat()
        tx.created_at = tx.created_at or now
        tx.updated_at = now

        conn = self._db._get_conn()
        try:
            conn.execute("""INSERT INTO transactions (tx_id, investor_id, portfolio_id, ticker, tx_type,
                quantity, price, fee, asset_type, status, idempotency_key, tags, decision_id,
                reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tx.tx_id, tx.investor_id, tx.portfolio_id, tx.ticker,
                 tx.tx_type.value if hasattr(tx.tx_type, 'value') else str(tx.tx_type),
                 tx.quantity, tx.price, tx.fee,
                 tx.asset_type.value if hasattr(tx.asset_type, 'value') else str(tx.asset_type),
                 tx.status.value if hasattr(tx.status, 'value') else str(tx.status),
                 tx.idempotency_key, json.dumps(tx.tags),
                 tx.decision_id, tx.reason, tx.created_at, tx.updated_at))
            logger.info("sqlite_ledger_append", tx_id=tx.tx_id, ticker=tx.ticker)
            return tx.tx_id
        except sqlite3.IntegrityError:
            existing = self.get(tx.tx_id)
            return existing.tx_id if existing else tx.tx_id

    def list(self, ticker: str | None = None, limit: int = 100) -> list[Transaction]:
        conn = self._db._get_conn()
        if ticker:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE ticker = ? ORDER BY created_at DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_tx(r) for r in rows]

    def get(self, tx_id: str) -> Transaction | None:
        conn = self._db._get_conn()
        row = conn.execute("SELECT * FROM transactions WHERE tx_id = ?", (tx_id,)).fetchone()
        return self._row_to_tx(row) if row else None

    def exists(self, idempotency_key: str) -> bool:
        if not idempotency_key:
            return False
        conn = self._db._get_conn()
        row = conn.execute(
            "SELECT 1 FROM transactions WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return row is not None

    def get_by_idempotency(self, key: str) -> Transaction | None:
        conn = self._db._get_conn()
        row = conn.execute(
            "SELECT * FROM transactions WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return self._row_to_tx(row) if row else None

    def delete(self, tx_id: str) -> bool:
        conn = self._db._get_conn()
        conn.execute("DELETE FROM transactions WHERE tx_id = ?", (tx_id,))
        return True

    def purge(self, tag: str | None = None) -> int:
        conn = self._db._get_conn()
        if tag:
            cursor = conn.execute("DELETE FROM transactions WHERE tags LIKE ?", (f'%"{tag}"%',))
        else:
            cursor = conn.execute("DELETE FROM transactions")
        return cursor.rowcount

    def reverse(self, tx_id: str, reason: str = "") -> str:
        """冲销交易"""
        original = self.get(tx_id)
        if not original:
            raise ValueError(f"交易不存在: {tx_id}")

        reverse_id = f"tx-rev-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        reverse_type = "reverse"

        conn = self._db._get_conn()
        conn.execute("""INSERT INTO transactions (tx_id, ticker, tx_type, quantity, price, fee,
            asset_type, status, reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (reverse_id, original.ticker, reverse_type, original.quantity, original.price, 0,
             original.asset_type.value if hasattr(original.asset_type, 'value') else str(original.asset_type),
             "executed", f"冲销 {tx_id}: {reason}", now, now))
        conn.execute("UPDATE transactions SET status = 'reversed', updated_at = ? WHERE tx_id = ?",
                     (now, tx_id))
        return reverse_id

    def approve(self, tx_id: str) -> bool:
        conn = self._db._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE transactions SET status = 'approved', updated_at = ? WHERE tx_id = ?",
                     (now, tx_id))
        return conn.total_changes > 0

    def reject(self, tx_id: str, reason: str = "") -> bool:
        conn = self._db._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE transactions SET status = 'rejected', reason = ?, updated_at = ? WHERE tx_id = ?",
            (reason, now, tx_id),
        )
        return conn.total_changes > 0

    def close(self):
        self._db.close()

    @staticmethod
    def _row_to_tx(row) -> Transaction:
        if row is None:
            return None
        d = dict(row)
        tags = json.loads(d.get("tags", "[]")) if isinstance(d.get("tags"), str) else (d.get("tags") or [])
        return Transaction(
            tx_id=d["tx_id"], investor_id=d.get("investor_id", ""), portfolio_id=d.get("portfolio_id", ""),
            ticker=d["ticker"], tx_type=d["tx_type"], quantity=d["quantity"], price=d["price"],
            fee=d.get("fee", 0), asset_type=d.get("asset_type", "stock"),
            status=d.get("status", "pending"), idempotency_key=d.get("idempotency_key", ""),
            tags=tags, decision_id=d.get("decision_id", ""), reason=d.get("reason", ""),
            created_at=d.get("created_at", ""), updated_at=d.get("updated_at", ""),
        )


class SQLiteDecisionRecorder(DecisionRecorder):
    """SQLite 决策记录器 — 实现 DecisionRecorder ABC"""

    def __init__(self, db_path: str | Path):
        self._db = SQLiteStateStore(db_path)
        self._ensure_tables()

    def _ensure_tables(self):
        conn = self._db._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                investor_id TEXT NOT NULL DEFAULT '',
                portfolio_id TEXT NOT NULL DEFAULT '',
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                reasoning TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                team_signals TEXT DEFAULT '[]',
                tx_id TEXT DEFAULT '',
                review_result TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                extra_data TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_dec_ticker ON decisions(ticker);
            CREATE INDEX IF NOT EXISTS idx_dec_status ON decisions(status);
        """)

    def create(self, record: DecisionRecord) -> str:
        if not record.decision_id:
            record.decision_id = f"dec-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        record.created_at = record.created_at or now
        record.updated_at = now

        conn = self._db._get_conn()
        conn.execute("""INSERT INTO decisions (decision_id, investor_id, portfolio_id, ticker,
            action, confidence, reasoning, status, team_signals, tx_id, review_result,
            created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record.decision_id, record.investor_id, record.portfolio_id, record.ticker,
             record.action, record.confidence, record.reasoning,
             record.status.value if hasattr(record.status, 'value') else str(record.status),
             json.dumps([s.model_dump() if hasattr(s, 'model_dump') else s for s in (record.team_signals or [])]),
             record.tx_id, record.review_result, record.created_at, record.updated_at))
        return record.decision_id

    def get(self, decision_id: str) -> DecisionRecord | None:
        conn = self._db._get_conn()
        row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        return self._row_to_decision(row) if row else None

    def get_executed(self, limit: int = 100) -> list[DecisionRecord]:
        conn = self._db._get_conn()
        rows = conn.execute(
            "SELECT * FROM decisions WHERE status = 'executed' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_decision(r) for r in rows]

    def list_pending(self, limit: int = 50) -> list[DecisionRecord]:
        conn = self._db._get_conn()
        rows = conn.execute(
            "SELECT * FROM decisions WHERE status IN ('draft','pending') ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_decision(r) for r in rows]

    def list(self, status: str | None = None, limit: int = 100) -> list[DecisionRecord]:
        conn = self._db._get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM decisions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [self._row_to_decision(r) for r in rows]

    def update_status(self, decision_id: str, status: str, **kwargs) -> bool:
        conn = self._db._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE decisions SET status = ?, updated_at = ? WHERE decision_id = ?",
            (status, now, decision_id),
        )
        return conn.total_changes > 0

    def link_transaction(self, decision_id: str, tx_id: str) -> bool:
        conn = self._db._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE decisions SET tx_id = ?, updated_at = ? WHERE decision_id = ?",
            (tx_id, now, decision_id),
        )
        return conn.total_changes > 0

    def update_review(self, decision_id: str, review_type: str, review_data: dict) -> bool:
        conn = self._db._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        review_json = json.dumps({"type": review_type, **review_data}, ensure_ascii=False)
        conn.execute(
            "UPDATE decisions SET review_result = ?, updated_at = ? WHERE decision_id = ?",
            (review_json, now, decision_id),
        )
        return conn.total_changes > 0

    @staticmethod
    def _row_to_decision(row) -> DecisionRecord:
        if row is None:
            return None
        d = dict(row)
        return DecisionRecord(
            decision_id=d["decision_id"], investor_id=d.get("investor_id", ""),
            portfolio_id=d.get("portfolio_id", ""), ticker=d["ticker"],
            action=d["action"], confidence=d.get("confidence", 0),
            reasoning=d.get("reasoning", ""),
            status=d.get("status", "draft"), tx_id=d.get("tx_id", ""),
            review_result=d.get("review_result"),
            created_at=d.get("created_at", ""), updated_at=d.get("updated_at", ""),
        )

    def close(self):
        self._db.close()
