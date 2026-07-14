"""进化引擎测试 — EvolutionEngine."""
from __future__ import annotations

import json
import shutil
from datetime import datetime

import pytest

from praxis.engine.evolution import EvolutionEngine, EvolutionDimension, _default_dimensions
from praxis.engine.tests.conftest import FakePerformanceCalculator
from praxis.core.exceptions import ConfigError


@pytest.fixture
def workspace_with_strategy(tmp_path):
    """创建含策略 YAML 的工作区."""
    strategies_dir = tmp_path / "config" / "strategies"
    strategies_dir.mkdir(parents=True)

    # 策略 YAML 含 evolution_dimensions
    content = """
name: grid_value
description: 网格价值策略
evolution_dimensions:
  - name: return_efficiency
    desc: "收益率是否达到预期"
    metric: annualized_return
    healthy_range: [0.05, 0.30]
    threshold: 0.03
  - name: risk_control
    desc: "最大回撤是否可控"
    metric: max_drawdown
    healthy_range: [0.0, 0.20]
    threshold: 0.25
"""
    (strategies_dir / "grid_value.yaml").write_text(content, encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def workspace_no_dims(tmp_path):
    """创建无 evolution_dimensions 的策略 YAML."""
    strategies_dir = tmp_path / "config" / "strategies"
    strategies_dir.mkdir(parents=True)

    content = """
name: simple_strategy
description: 简单策略
"""
    (strategies_dir / "simple_strategy.yaml").write_text(content, encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def workspace_missing_strategy(tmp_path):
    """创建不含目标策略的工作区."""
    strategies_dir = tmp_path / "config" / "strategies"
    strategies_dir.mkdir(parents=True)
    return str(tmp_path)


class TestEvaluateWithDimensions:
    """evaluate 策略维度."""

    def test_evaluate_with_dimensions(self, workspace_with_strategy):
        """evaluate 返回评分和状态."""
        engine = EvolutionEngine(workspace_with_strategy)
        calculator = FakePerformanceCalculator(result={
            "total_return": 0.05, "annualized_return": 0.12,
            "max_drawdown": 0.08, "win_rate": 0.6,
            "sharpe_ratio": 0.8, "calmar_ratio": 1.5,
        })

        result = engine.evaluate(
            strategy_name="grid_value",
            investor_id="inv-test",
            portfolio_id="core",
            calculator=calculator,
        )
        assert result["success"] is True
        data = result["data"]
        assert data["strategy"] == "grid_value"
        assert "dimensions" in data
        assert len(data["dimensions"]) == 2
        assert "overall_health" in data
        assert "evolution_suggestions" in data


class TestEvaluateDefaultDimensions:
    """evaluate 无 evolution_dimensions."""

    def test_evaluate_default_dims(self, workspace_no_dims):
        """策略无 evolution_dimensions → 返回默认维度."""
        engine = EvolutionEngine(workspace_no_dims)
        calculator = FakePerformanceCalculator()

        result = engine.evaluate(
            strategy_name="simple_strategy",
            investor_id="inv-test",
            portfolio_id="core",
            calculator=calculator,
        )
        assert result["success"] is True
        data = result["data"]
        # 应该有 3 个默认维度
        assert len(data["dimensions"]) == 3
        dim_names = [d["name"] for d in data["dimensions"]]
        assert "return_efficiency" in dim_names
        assert "risk_control" in dim_names
        assert "win_stability" in dim_names


class TestSaveAndGetHistory:
    """save_evaluation + get_history 读写循环."""

    def test_save_and_get_history(self, workspace_with_strategy):
        """读写循环正常."""
        engine = EvolutionEngine(workspace_with_strategy)

        evaluation = {
            "strategy": "grid_value",
            "overall_health": "healthy",
            "dimensions": [
                {"name": "test_dim", "status": "healthy", "current_value": 0.1},
            ],
            "evaluated_at": "2024-06-15T10:00:00",
        }

        path = engine.save_evaluation("grid_value", evaluation)
        assert path.endswith(".json")

        history = engine.get_history("grid_value")
        assert len(history) >= 1
        record = history[0]
        assert record["strategy"] == "grid_value"
        assert record["overall_health"] == "healthy"


class TestGetHistoryLimit:
    """get_history limit 参数."""

    def test_limit_param(self, workspace_with_strategy):
        """get_history 按 limit 截断."""
        engine = EvolutionEngine(workspace_with_strategy)
        evaluation = {"strategy": "grid_value", "overall_health": "healthy"}

        # 保存多条记录
        for i in range(5):
            engine.save_evaluation("grid_value", evaluation)

        limited = engine.get_history("grid_value", limit=3)
        assert len(limited) <= 3


class TestGetHistoryEmpty:
    """get_history 无记录."""

    def test_empty_history(self, workspace_with_strategy):
        """无记录返回空列表."""
        engine = EvolutionEngine(workspace_with_strategy)
        history = engine.get_history("nonexistent")
        assert history == []


class TestStrategyNotFound:
    """策略不存在."""

    def test_strategy_not_found(self, workspace_missing_strategy):
        """策略不存在 → error."""
        engine = EvolutionEngine(workspace_missing_strategy)
        calculator = FakePerformanceCalculator()

        result = engine.evaluate(
            strategy_name="nonexistent",
            calculator=calculator,
        )
        assert result["success"] is False
        assert "err" in result["error"].lower() or "不存在" in result["error"]
