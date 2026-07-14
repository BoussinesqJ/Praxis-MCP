"""估值模块工具测试 — valuation 函数.

Mock 策略：直接 mock praxis.engine.valuation 的底层函数，
避免依赖 akshare/pandas 重型依赖。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from praxis.tools.valuation_module import valuation


# ═══════════════════════════════════════════════════════════════════
# 共享 mock 数据
# ═══════════════════════════════════════════════════════════════════

_PE_RESULT = {
    "index_code": "000300",
    "index_name": "沪深300",
    "current_pe": 14.5,
    "percentile_all": 45.5,
    "percentile_10y": 42.0,
    "pe_30pct": 11.0,
    "pe_80pct": 18.0,
    "data_days": 2000,
    "below_30pct": False,
    "above_80pct": False,
    "valuation_level": "fair",
}

_UNDERVALUED_RESULT = {
    **_PE_RESULT,
    "percentile_all": 20.0,
    "below_30pct": True,
    "valuation_level": "undervalued",
}


@pytest.mark.asyncio
class TestPercentile:
    """percentile 操作."""

    async def test_percentile_single(self):
        """单指数 PE 分位."""
        with patch(
            "praxis.tools.valuation_module.get_valuation_percentile",
            new=AsyncMock(return_value={"success": True, "data": _PE_RESULT}),
        ):
            result = await valuation(action="percentile", index_code="000300")
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["percentile_all"] == 45.5

    async def test_percentile_not_found(self):
        """指数不存在."""
        with patch(
            "praxis.tools.valuation_module.get_valuation_percentile",
            new=AsyncMock(return_value={"success": False, "error": "无法获取"}),
        ):
            result = await valuation(action="percentile", index_code="999999")
        assert result["success"] is False


@pytest.mark.asyncio
class TestAllIndices:
    """all 操作."""

    async def test_all_indices(self):
        """全指数检查."""
        all_result = {
            "success": True,
            "data": {
                "indices": {"000300": _PE_RESULT, "000905": _PE_RESULT},
                "timestamp": "",
                "summary": {"total": 4, "available": 2, "errors": ["000016", "000852"]},
            },
        }
        with patch(
            "praxis.tools.valuation_module.check_valuation_for_all_indices",
            new=AsyncMock(return_value=all_result),
        ):
            result = await valuation(action="all")
        assert "success" in result
        assert "data" in result
        assert "indices" in result["data"]


@pytest.mark.asyncio
class TestCompare:
    """compare 操作."""

    async def test_compare_multiple(self):
        """多指数对比."""
        with patch(
            "praxis.tools.valuation_module.get_index_pe_percentile",
            new=AsyncMock(return_value=_PE_RESULT),
        ):
            result = await valuation(
                action="compare",
                index_codes=["000300", "000905"],
            )
        assert result["success"] is True
        assert result["data"]["count"] == 2
        assert "000300" in result["data"]["indices"]
        assert "000905" in result["data"]["indices"]

    async def test_compare_missing_codes(self):
        """compare 缺少 index_codes."""
        result = await valuation(action="compare")
        assert result["success"] is False
        assert "index_codes" in result["error"]


@pytest.mark.asyncio
class TestLevel:
    """level 操作."""

    async def test_level_returns_valuation_string(self):
        """仅返回估值水平字符串."""
        with patch(
            "praxis.tools.valuation_module.get_index_pe_percentile",
            new=AsyncMock(return_value=_UNDERVALUED_RESULT),
        ):
            result = await valuation(action="level", index_code="000300")
        assert result["success"] is True
        assert result["data"]["valuation_level"] == "undervalued"

    async def test_level_not_found(self):
        """level 在数据不可用时返回 error."""
        with patch(
            "praxis.tools.valuation_module.get_index_pe_percentile",
            new=AsyncMock(return_value=None),
        ):
            result = await valuation(action="level", index_code="000300")
        assert result["success"] is False


@pytest.mark.asyncio
class TestEdgeCases:
    """边界情况."""

    async def test_unknown_action(self):
        """未知 action 返回 error."""
        result = await valuation(action="foobar")
        assert result["success"] is False
        assert "未知" in result["error"]
