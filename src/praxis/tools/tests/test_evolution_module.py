"""进化工具测试 — evolution 函数."""
from __future__ import annotations

import pytest

from praxis.tools.evolution import evolution
from praxis.engine.tests.conftest import FakePerformanceCalculator


@pytest.fixture
def workspace_with_strategy(tmp_path):
    """创建含策略 YAML 的工作区."""
    strategies_dir = tmp_path / "config" / "strategies"
    strategies_dir.mkdir(parents=True)

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


def _make_deps(workspace, calculator=None):
    return {
        "workspace": workspace,
        "performance_calculator": calculator,
    }


class TestEvaluateRouting:
    """evaluate 工具路由."""

    @pytest.mark.asyncio
    async def test_evaluate(self, workspace_with_strategy):
        """evaluate 返回评估结果."""
        calc = FakePerformanceCalculator()
        deps = _make_deps(workspace_with_strategy, calc)

        result = await evolution(
            action="evaluate",
            strategy_name="grid_value",
            investor_id="inv-test",
            portfolio_id="core",
            _deps=deps,
        )
        assert result["success"] is True
        data = result["data"]
        assert data["strategy"] == "grid_value"
        assert "dimensions" in data
        assert "overall_health" in data


class TestHistoryRouting:
    """history 工具路由."""

    @pytest.mark.asyncio
    async def test_history(self, workspace_with_strategy):
        """history 返回历史记录."""
        deps = _make_deps(workspace_with_strategy)

        result = await evolution(
            action="history",
            strategy_name="grid_value",
            _deps=deps,
        )
        assert result["success"] is True
        assert "records" in result["data"]
        assert "count" in result["data"]


class TestProposeRouting:
    """propose 工具路由."""

    @pytest.mark.asyncio
    async def test_propose(self, workspace_with_strategy):
        """propose 返回进化建议."""
        calc = FakePerformanceCalculator()
        deps = _make_deps(workspace_with_strategy, calc)

        result = await evolution(
            action="propose",
            strategy_name="grid_value",
            investor_id="inv-test",
            portfolio_id="core",
            _deps=deps,
        )
        assert result["success"] is True
        assert "status" in result["data"]


class TestMissingDeps:
    """_deps 缺失."""

    @pytest.mark.asyncio
    async def test_missing_calculator(self, workspace_with_strategy):
        """_deps 缺 performance_calculator → error."""
        deps = {"workspace": workspace_with_strategy}

        result = await evolution(
            action="evaluate",
            strategy_name="grid_value",
            investor_id="inv-test",
            portfolio_id="core",
            _deps=deps,
        )
        assert result["success"] is False
        assert "未注入" in result["error"]


class TestInvalidAction:
    """非法 action."""

    @pytest.mark.asyncio
    async def test_invalid_action(self, workspace_with_strategy):
        """非法 action → error."""
        result = await evolution(
            action="invalid_action",
            strategy_name="grid_value",
            _deps={"workspace": workspace_with_strategy},
        )
        assert result["success"] is False
        assert "未知" in result["error"]


class TestResponseFormat:
    """工具 handler 返回正确格式."""

    @pytest.mark.asyncio
    async def test_evaluate_format(self, workspace_with_strategy):
        """evaluate 返回正确格式."""
        calc = FakePerformanceCalculator()
        deps = _make_deps(workspace_with_strategy, calc)

        result = await evolution(
            action="evaluate",
            strategy_name="grid_value",
            investor_id="inv-test",
            portfolio_id="core",
            _deps=deps,
        )
        assert "success" in result
        assert isinstance(result["success"], bool)
        if result["success"]:
            assert "data" in result
        else:
            assert "error" in result

    @pytest.mark.asyncio
    async def test_history_format(self, workspace_with_strategy):
        """history 返回 {success, data, ...}."""
        result = await evolution(
            action="history",
            strategy_name="grid_value",
            _deps={"workspace": workspace_with_strategy},
        )
        assert "success" in result
        assert "data" in result
        assert "records" in result["data"]
        assert "count" in result["data"]
