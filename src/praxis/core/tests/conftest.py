"""Core 层测试专用 fixtures.

为 Core 层 8 个测试模块提供共享的 FileLedger / SQLite / Mock 等 fixtures。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from praxis.core.ledger import FileLedger
from praxis.core.state_store import SQLiteStateStore, SQLiteLedger, SQLiteDecisionRecorder


@pytest.fixture
def tmp_ledger_path() -> Path:
    """创建临时 JSONL 文件路径（文件自动清理）。

    作用域: function
    Returns:
        Path: 不存在的 JSONL 文件路径
    """
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    yield path
    # 清理
    if path.exists():
        path.unlink(missing_ok=True)


@pytest.fixture
def file_ledger(tmp_ledger_path: Path) -> FileLedger:
    """指向临时路径的空账本。

    作用域: function
    Returns:
        FileLedger: 已初始化的空文件账本
    """
    return FileLedger(tmp_ledger_path)


@pytest.fixture
def sqlite_store() -> SQLiteStateStore:
    """指向 :memory: 的内存 SQLiteStateStore（含 kv_store 表）。

    作用域: function
    Returns:
        SQLiteStateStore: 内存数据库
    """
    store = SQLiteStateStore(":memory:")
    # kv_store 表由 SQLiteLedger._ensure_tables 创建，裸 SQLiteStateStore 需要手动建表
    conn = store._get_conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv_store "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    return store


@pytest.fixture
def sqlite_ledger() -> SQLiteLedger:
    """指向 :memory: 的内存 SQLiteLedger。

    作用域: function
    Returns:
        SQLiteLedger: 内存 SQLite 账本
    """
    return SQLiteLedger(":memory:")


@pytest.fixture
def sqlite_decision_recorder() -> SQLiteDecisionRecorder:
    """指向 :memory: 的内存 SQLiteDecisionRecorder。

    作用域: function
    Returns:
        SQLiteDecisionRecorder: 内存 SQLite 决策记录器
    """
    return SQLiteDecisionRecorder(":memory:")


@pytest.fixture
def workflow_agents() -> dict[str, MagicMock]:
    """创建 mock agent 字典，用于 Workflow 测试。

    每个 mock agent 有 async execute 方法。

    作用域: function
    Returns:
        dict[str, Mock]: {"decision": Mock, "risk": Mock, "review": Mock, "admin": Mock}
    """
    class FakeResult:
        """模拟 AgentResult 返回结构。"""

        def __init__(self, success: bool = True, data: dict | None = None):
            self.success = success
            self.data = data or {}

        def to_dict(self) -> dict:
            return {"success": self.success, "data": self.data}

    def _make_agent() -> MagicMock:
        agent = MagicMock()
        # AsyncMock for async execute
        agent.execute = AsyncMock(return_value=FakeResult(success=True, data={"status": "ok"}))
        return agent

    return {
        "decision": _make_agent(),
        "risk": _make_agent(),
        "review": _make_agent(),
        "admin": _make_agent(),
    }
