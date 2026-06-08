"""Tests for evolution memory store"""
import json
import pytest
from pathlib import Path

from praxis.engine.evolution_memory import EvolutionMemoryStore, EvolutionMemory


@pytest.fixture
def store(tmp_path):
    return EvolutionMemoryStore(str(tmp_path))


class TestRecordAndRetrieve:
    """记录与查询测试"""

    def test_record_creates_file(self, store):
        """记录应创建 JSON 文件"""
        path = store.record(
            trigger_event="transaction",
            strategy_name="grid_value",
            evaluation_summary="网格间距正常",
        )
        assert Path(path).exists()

    def test_record_format(self, store):
        """记录格式正确"""
        store.record(
            trigger_event="nav_record",
            strategy_name="grid_value",
            evaluation_summary="现金比例偏高",
            dimensions=[{"name": "cash_floor", "status": "warning"}],
            suggestions=[{"dimension": "cash_floor", "action": "review"}],
        )
        memories = store.load_all()
        assert len(memories) == 1
        m = memories[0]
        assert m.trigger_event == "nav_record"
        assert m.strategy_name == "grid_value"
        assert m.decision == "pending"
        assert len(m.dimensions) == 1
        assert len(m.suggestions) == 1

    def test_load_multiple(self, store):
        """加载多条记录"""
        for i in range(5):
            store.record(
                trigger_event="transaction",
                strategy_name="grid_value",
                evaluation_summary=f"评估 {i}",
            )
        memories = store.load_all()
        assert len(memories) == 5


class TestQuerySimilar:
    """类似情况查询测试"""

    def test_query_by_dimension(self, store):
        """按维度名称查询"""
        store.record("transaction", "grid_value", "止损触发", dimensions=[{"name": "stop_loss"}])
        store.record("nav_record", "grid_value", "现金偏高", dimensions=[{"name": "cash_floor"}])

        results = store.query_similar("stop_loss")
        assert len(results) >= 1
        assert any("stop_loss" in str(m.dimensions) for m in results)

    def test_query_by_strategy(self, store):
        """按策略名称查询"""
        store.record("manual", "grid_value", "网格优化")
        store.record("manual", "momentum", "动量调整")

        results = store.query_similar("grid_value")
        assert len(results) >= 1
        assert results[0].strategy_name == "grid_value"

    def test_query_empty(self, store):
        """无匹配时返回空"""
        store.record("transaction", "grid_value", "正常")
        results = store.query_similar("完全不相关的关键词 xyz")
        assert len(results) == 0

    def test_query_limit(self, store):
        """结果数量限制"""
        for i in range(10):
            store.record("transaction", "grid_value", f"止损 {i}", dimensions=[{"name": "stop_loss"}])
        results = store.query_similar("stop_loss", limit=3)
        assert len(results) <= 3


class TestTimeline:
    """时间线生成测试"""

    def test_timeline_with_records(self, store):
        """有记录时生成时间线"""
        store.record("transaction", "grid_value", "网格间距过密", dimensions=[{"name": "grid_spacing"}])
        store.record("nav_record", "grid_value", "现金偏高", dimensions=[{"name": "cash_floor"}])

        timeline = store.generate_timeline("grid_value")
        assert "grid_value" in timeline
        assert "grid_spacing" in timeline
        assert "cash_floor" in timeline

    def test_timeline_empty(self, store):
        """无记录时生成空时间线"""
        timeline = store.generate_timeline("nonexistent")
        assert "暂无进化记录" in timeline

    def test_timeline_creates_file(self, store):
        """时间线文件应创建"""
        store.record("manual", "grid_value", "测试")
        store.generate_timeline("grid_value")
        timeline_file = store._workspace / "deliverables" / "evolution" / "timeline_grid_value.md"
        assert timeline_file.exists()


class TestUpdateDecision:
    """决策更新测试"""

    def test_approve(self, store):
        """审批通过"""
        store.record("transaction", "grid_value", "测试")
        memories = store.load_all()
        result = store.update_decision(memories[0].memory_id, "approved")
        assert result is True

        updated = store.load_all()
        assert updated[0].decision == "approved"

    def test_reject_with_reason(self, store):
        """拒绝并记录原因"""
        store.record("transaction", "grid_value", "测试")
        memories = store.load_all()
        result = store.update_decision(memories[0].memory_id, "rejected", "数据不足")
        assert result is True

        updated = store.load_all()
        assert updated[0].decision == "rejected"
        assert updated[0].rejection_reason == "数据不足"

    def test_nonexistent(self, store):
        """不存在的 ID"""
        result = store.update_decision("nonexistent", "approved")
        assert result is False


class TestUpdateOutcome:
    """效果回填测试"""

    def test_fill_outcome(self, store):
        """回填实际效果"""
        store.record("transaction", "grid_value", "测试")
        memories = store.load_all()
        result = store.update_outcome(
            memories[0].memory_id,
            "现金比例从 89% 降至 65%",
            {"cash_ratio_before": 0.89, "cash_ratio_after": 0.65},
        )
        assert result is True

        updated = store.load_all()
        assert updated[0].outcome == "现金比例从 89% 降至 65%"
        assert updated[0].outcome_metrics["cash_ratio_after"] == 0.65
