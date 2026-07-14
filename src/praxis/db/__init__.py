"""PRAXIS DB 层 — SQLite 数据库初始化与 Schema 管理"""

import sqlite3
import os
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """初始化 SQLite 数据库，执行 Schema DDL。

    Args:
        db_path: 数据库文件路径。为 None 时使用 WORKSPACE/db/praxis.db

    Returns:
        sqlite3.Connection: 已初始化的数据库连接（WAL 模式）
    """
    if db_path is None:
        workspace = os.environ.get("PRAXIS_WORKSPACE", ".")
        db_dir = Path(workspace) / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(db_dir / "praxis.db")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # 执行 Schema DDL
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()

    return conn


def get_db_path() -> str:
    """获取数据库文件路径"""
    workspace = os.environ.get("PRAXIS_WORKSPACE", ".")
    return str(Path(workspace) / "db" / "praxis.db")
