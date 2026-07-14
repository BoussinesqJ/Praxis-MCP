"""净值模块工具测试 — nav 函数."""
from __future__ import annotations

import pytest

from praxis.tools.nav_module import nav
from praxis.engine.tests.conftest import FakeNavTracker


def _make_deps(tracker=None):
    """构造 _deps 字典."""
    return {"nav_tracker": tracker}


class TestRecord:
    """record 测试."""

    @pytest.mark.asyncio
    async def test_record_success(self):
        """成功记录净值."""
        tracker = FakeNavTracker()
        result = await nav(
            action="record",
            nav=1.05,
            total_assets=73500.0,
            positions_value=35000.0,
            cash=38500.0,
            benchmark_nav=1.02,
            benchmark_code="000300",
            _deps=_make_deps(tracker),
        )
        assert result["success"] is True
        assert result["data"]["nav"] == 1.05
        assert result["data"]["total_assets"] == 73500.0

    @pytest.mark.asyncio
    async def test_record_missing_params(self):
        """缺少必填参数 → error."""
        tracker = FakeNavTracker()
        result = await nav(
            action="record",
            nav=None,
            total_assets=None,
            positions_value=None,
            cash=None,
            _deps=_make_deps(tracker),
        )
        assert result["success"] is False
        assert "必填" in result["error"]


class TestSnapshot:
    """snapshot 测试."""

    @pytest.mark.asyncio
    async def test_snapshot(self):
        """快照返回最新净值记录."""
        tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0,
             "positions_value": 0.0, "cash": 70000.0},
            {"date": "2024-06-02", "nav": 1.01, "total_assets": 70700.0,
             "positions_value": 7700.0, "cash": 63000.0},
        ])
        result = await nav(
            action="snapshot",
            investor="inv-test",
            portfolio="core",
            _deps=_make_deps(tracker),
        )
        assert result["success"] is True
        assert result["data"]["nav"] == 1.01


class TestHistory:
    """history 测试."""

    @pytest.mark.asyncio
    async def test_history(self):
        """获取净值历史."""
        tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0,
             "positions_value": 0.0, "cash": 70000.0},
            {"date": "2024-06-02", "nav": 1.005, "total_assets": 70350.0,
             "positions_value": 350.0, "cash": 70000.0},
            {"date": "2024-06-03", "nav": 1.01, "total_assets": 70700.0,
             "positions_value": 700.0, "cash": 70000.0},
        ])
        result = await nav(
            action="history",
            days=2,
            _deps=_make_deps(tracker),
        )
        assert result["success"] is True
        assert result["data"]["count"] == 2


class TestNoTracker:
    """无 tracker 测试."""

    @pytest.mark.asyncio
    async def test_no_tracker(self):
        """_deps 缺 nav_tracker → error."""
        result = await nav(
            action="snapshot",
            _deps=_make_deps(None),
        )
        assert result["success"] is False
        assert "未注入" in result["error"]


class TestLatest:
    """latest 测试."""

    @pytest.mark.asyncio
    async def test_latest(self):
        """返回最新一条净值记录."""
        tracker = FakeNavTracker(records=[
            {"date": "2024-06-01", "nav": 1.0, "total_assets": 70000.0,
             "positions_value": 0.0, "cash": 70000.0},
            {"date": "2024-06-05", "nav": 1.03, "total_assets": 72100.0,
             "positions_value": 2100.0, "cash": 70000.0},
        ])
        result = await nav(
            action="latest",
            _deps=_make_deps(tracker),
        )
        assert result["success"] is True
        assert result["data"]["nav"] == 1.03
        assert result["data"]["date"] == "2024-06-05"


class TestInvalidAction:
    """无效 action 测试."""

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """未知 action → error."""
        tracker = FakeNavTracker()
        result = await nav(
            action="foobar",
            _deps=_make_deps(tracker),
        )
        assert result["success"] is False
        assert "未知" in result["error"]
