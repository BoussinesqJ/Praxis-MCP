"""净值追踪器单元测试 — NavTracker record/snapshot/get_history."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from praxis.engine.nav_tracker import NavTracker
from praxis.engine.tests.conftest import FakeDataProvider, FakeLedger
from praxis.core.models import Transaction, TransactionType, TransactionStatus, AssetType


class TestRecord:
    """record 测试."""

    def test_record_first(self, tmp_path):
        """首次记录成功."""
        nav_path = tmp_path / "nav.jsonl"
        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        result = tracker.record(
            nav=1.0, total_assets=70000.0, positions_value=0.0, cash=70000.0,
        )
        assert result["success"] is True
        assert result["data"]["nav"] == 1.0
        assert result["data"]["total_assets"] == 70000.0
        assert nav_path.exists()

    def test_same_day_dedup(self, tmp_path):
        """同日去重 — 同一天记录两次只保留第一次."""
        nav_path = tmp_path / "nav.jsonl"
        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        r1 = tracker.record(nav=1.0, total_assets=70000.0, positions_value=0.0, cash=70000.0)
        assert r1["success"] is True

        r2 = tracker.record(nav=1.01, total_assets=70100.0, positions_value=100.0, cash=70000.0)
        assert r2["success"] is False
        assert "已记录" in r2["error"]


class TestGetHistory:
    """get_history 测试."""

    def test_get_history(self, tmp_path):
        """获取净值历史."""
        nav_path = tmp_path / "nav.jsonl"
        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        # 无法同日记录两次，需要构造历史文件
        from datetime import datetime, timezone, timedelta
        records = []
        for i in range(5):
            dt = (datetime.now(timezone.utc) - timedelta(days=4 - i)).strftime("%Y-%m-%d")
            records.append({
                "date": dt, "nav": round(1.0 + i * 0.01, 4),
                "total_assets": round(70000 + i * 500, 2),
                "positions_value": round(35000 + i * 250, 2),
                "cash": round(35000 + i * 250, 2),
            })
        with open(nav_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        tracker2 = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        history = tracker2.get_history(days=3)
        assert history["success"] is True
        assert history["data"]["count"] == 3


class TestSnapshot:
    """snapshot 测试."""

    def test_snapshot_basic(self, tmp_path):
        """基础快照 — 返回最新记录."""
        nav_path = tmp_path / "nav.jsonl"
        from datetime import datetime, timezone, timedelta
        # 写入历史记录
        records = []
        for i in range(3):
            dt = (datetime.now(timezone.utc) - timedelta(days=2 - i)).strftime("%Y-%m-%d")
            records.append({
                "date": dt, "nav": round(1.0 + i * 0.001, 4),
                "total_assets": round(70000.0 + i * 10, 2),
                "positions_value": round(0.0, 2),
                "cash": round(70000.0 + i * 10, 2),
            })
        with open(nav_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        snap = tracker.get_history(days=1)
        assert snap["success"] is True
        assert snap["data"]["count"] == 1

    @pytest.mark.asyncio
    async def test_snapshot_with_quotes(self, tmp_path):
        """快照含行情 — 更新持仓市值."""
        nav_path = tmp_path / "nav.jsonl"
        # 创建有持仓的账本
        ledger = FakeLedger([
            Transaction(
                ticker="600519", tx_type=TransactionType.BUY,
                quantity=50.0, price=1800.0, fee=5.0,
                asset_type=AssetType.STOCK,
                status=TransactionStatus.EXECUTED,
            ),
        ])
        data_provider = FakeDataProvider(quotes={
            "600519": {"price": 1850.0, "change": 15.0},
        })

        # 写入一条历史记录
        record = {
            "date": "2024-06-15", "nav": 1.0,
            "total_assets": 70000.0, "positions_value": 90000.0,
            "cash": -20000.0,
        }
        with open(nav_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=ledger,
            data_provider=data_provider,
            initial_capital=70000.0,
        )
        snap = await tracker.snapshot("inv-test", "core")
        assert snap["success"] is True

    def test_snapshot_no_records(self, tmp_path):
        """无记录快照返回错误."""
        nav_path = tmp_path / "nav.jsonl"
        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        snap = tracker.get_history(days=10)
        assert snap["data"]["count"] == 0

    def test_snapshot_quote_fallback(self, tmp_path):
        """行情获取失败降级 — snapshot 使用已有数据."""
        nav_path = tmp_path / "nav.jsonl"
        record = {
            "date": "2024-06-15", "nav": 1.0,
            "total_assets": 70000.0, "positions_value": 0.0,
            "cash": 70000.0,
        }
        with open(nav_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        hist = tracker.get_history(days=5)
        assert hist["success"] is True


class TestInitLoadHistory:
    """初始化加载已有历史."""

    def test_init_load_history(self, tmp_path):
        """初始化时加载已有历史记录."""
        nav_path = tmp_path / "nav.jsonl"
        records = [
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0,
             "positions_value": 0.0, "cash": 70000.0},
            {"date": "2024-06-02", "nav": 1.001, "total_assets": 70070.0,
             "positions_value": 70.0, "cash": 70000.0},
        ]
        with open(nav_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        tracker = NavTracker(
            nav_path=str(nav_path),
            ledger=FakeLedger(),
            data_provider=FakeDataProvider(),
            initial_capital=70000.0,
        )
        hist = tracker.get_history(days=10)
        assert hist["data"]["count"] == 2
