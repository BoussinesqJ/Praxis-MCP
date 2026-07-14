"""绩效模块工具测试 — performance 函数."""
from __future__ import annotations

import pytest

from praxis.tools.performance_module import performance
from praxis.engine.tests.conftest import FakePerformanceCalculator


def _make_deps(calculator=None):
    """构造 _deps 字典."""
    return {"performance_calculator": calculator}


class TestCalculate:
    """calculate 测试."""

    @pytest.mark.asyncio
    async def test_calculate_basic(self):
        """基本计算 — 返回绩效指标."""
        calc = FakePerformanceCalculator()
        result = await performance(
            action="calculate",
            investor="inv-test",
            portfolio="core",
            _deps=_make_deps(calc),
        )
        assert result["success"] is True
        data = result["data"]
        assert "total_return" in data
        assert "sharpe_ratio" in data
        assert "max_drawdown" in data

    @pytest.mark.asyncio
    async def test_with_filters(self):
        """带过滤条件."""
        calc = FakePerformanceCalculator()
        result = await performance(
            action="calculate",
            investor="inv-test",
            portfolio="core",
            exclude_reversed=True,
            ticker="600519",
            _deps=_make_deps(calc),
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_no_transactions(self):
        """无交易 — calculator 自身处理."""
        calc = FakePerformanceCalculator(result={"total_return": 0.0})
        result = await performance(
            action="calculate",
            investor="inv-test",
            portfolio="core",
            _deps=_make_deps(calc),
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_no_calculator(self):
        """_deps 缺 calculator → error."""
        result = await performance(
            action="calculate",
            investor="inv-test",
            portfolio="core",
            _deps=_make_deps(None),
        )
        assert result["success"] is False
        assert "未注入" in result["error"]


class TestCompare:
    """compare 测试."""

    @pytest.mark.asyncio
    async def test_compare_versions(self):
        """策略版本对比."""
        calc = FakePerformanceCalculator()
        result = await performance(
            action="compare",
            version_a="v1.0",
            version_b="v1.1",
            metric="sharpe_ratio",
            _deps=_make_deps(calc),
        )
        assert result["success"] is True
        assert result["data"]["version_a"] == "v1.0"
        assert result["data"]["version_b"] == "v1.1"
        assert "improvement" in result["data"]


class TestEdgeCases:
    """边界情况."""

    @pytest.mark.asyncio
    async def test_calculate_explicit_mode(self):
        """显式 action=calculate."""
        calc = FakePerformanceCalculator()
        result = await performance(
            action="calculate",
            investor="inv-test",
            portfolio="core",
            _deps=_make_deps(calc),
        )
        assert result["success"] is True
