"""SQLite 数据库底层基础设施"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

DEFAULT_DB_PATH = Path("data/praxis_system.db")

class Database:
    """系统统一 SQLite 数据库类"""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """连接上下文管理器，自动 commit / rollback"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 幂等键记录表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                idempotency_key TEXT PRIMARY KEY,
                tx_id TEXT,
                created_at TEXT
            )
            """)
            
            # 2. 灰度更新提案表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS grayscale_proposals (
                backup_path TEXT PRIMARY KEY,
                strategy_name TEXT,
                content_hash TEXT,
                prepared_at TEXT
            )
            """)
            
            # 3. 投资组合修改提案表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_proposals (
                proposal_id TEXT PRIMARY KEY,
                investor TEXT,
                portfolio TEXT,
                field TEXT,
                new_value TEXT,
                old_value TEXT,
                timestamp TEXT
            )
            """)
            
            # 4. 状态增量重构缓存表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_caches (
                investor_id TEXT,
                portfolio_id TEXT,
                last_processed_tx_id TEXT,
                state_json TEXT,
                PRIMARY KEY (investor_id, portfolio_id)
            )
            """)
