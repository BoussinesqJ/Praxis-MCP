"""E1.10 — 进化引擎测试"""
import os
import pytest

from praxis.engine.evolution import EvolutionEngine


@pytest.fixture
def engine():
    workspace = os.environ.get("PRAXIS_WORKSPACE", ".")
    return EvolutionEngine(workspace)


class TestEvolutionEvaluate:
    """进化评估测试"""

    def test_evaluate_basic(self, engine):
        """基本评估测试"""
        result = engine.evaluate("grid_value", "example", "demo")
        assert result["success"] is True
        assert "dimensions" in result["data"]
        assert "overall_health" in result["data"]

    def test_evaluate_dimensions(self, engine):
        """评估维度测试"""
        result = engine.evaluate("grid_value", "example", "demo")
        dimensions = result["data"]["dimensions"]
        assert len(dimensions) == 4

        dim_names = [d["name"] for d in dimensions]
        assert "grid_spacing" in dim_names
        assert "stop_loss_tightness" in dim_names
        assert "cost_anchor_effectiveness" in dim_names
        assert "cash_floor_calibration" in dim_names

    def test_evaluate_health_status(self, engine):
        """健康状态测试"""
        result = engine.evaluate("grid_value", "example", "demo")
        assert result["data"]["overall_health"] in ["healthy", "warning", "critical"]

    def test_evaluate_suggestions(self, engine):
        """进化建议测试"""
        result = engine.evaluate("grid_value", "example", "demo")
        suggestions = result["data"]["evolution_suggestions"]
        # 应该有建议（因为样本数据有限，指标为0）
        assert len(suggestions) > 0


class TestEvolutionFormat:
    """格式化输出测试"""

    def test_format_evaluation(self, engine):
        """格式化评估结果"""
        result = engine.evaluate("grid_value", "example", "demo")
        formatted = engine.format_evaluation(result)
        assert "进化维度评估" in formatted
        assert "grid_spacing" in formatted


class TestEvolutionBackup:
    """策略备份测试"""

    def test_backup_strategy(self, engine):
        """备份策略文件"""
        backup_path = engine.backup_strategy("grid_value")
        assert backup_path is not None
        assert ".bak" in backup_path
