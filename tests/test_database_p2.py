"""SQLite 数据库底层基础设施测试"""
import pytest
import sqlite3
from pathlib import Path
import tempfile
from praxis.core.database import Database


def test_database_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_praxis.db"
        db = Database(db_path)
        
        # 验证文件是否被创建
        assert db_path.exists()
        
        # 验证表格结构
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row["name"] for row in cursor.fetchall()]
            assert "idempotency_keys" in tables
            assert "grayscale_proposals" in tables
            assert "portfolio_proposals" in tables
            assert "state_caches" in tables


def test_database_read_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_praxis.db"
        db = Database(db_path)
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO idempotency_keys (idempotency_key, tx_id, created_at) VALUES (?, ?, ?)",
                ("key-123", "tx-456", "2026-06-07T12:00:00Z")
            )
            
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tx_id FROM idempotency_keys WHERE idempotency_key = ?", ("key-123",))
            row = cursor.fetchone()
            assert row is not None
            assert row["tx_id"] == "tx-456"
